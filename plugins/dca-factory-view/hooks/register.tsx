import { atom, read, update } from 'claude-code'
import type { EngineInterface, RenderElement, HookStream, ProcessSpawnChunk, ProcessSpawnResult, Register, RenderInput } from 'claude-code'

import type { Cockpit, DecisionRecord, Detail, FactoryStatus, JournalEvent, Row, StageRun, StoryView, Tab, Topic, Worker } from '../types'
import {
  appendLines,
  bar,
  clock,
  day,
  duration,
  moment,
  parseJournal,
  rounds as roundsText,
  short,
  stagesOf,
  tokens as tokensText,
  touchesFactory,
} from './parse'

// The cockpit over the whole product flow: describe, discover, backlog, run, decide, delivered.
// It shows what factory.sh and the project's files hold and decides nothing; a press either sends the
// matching command into this session or starts the runner — both are the person's act.
const PANE = 'factory-view'
const STATUS_MS = 20_000
const LIVE_MS = 5_000

const cockpit = atom({ plugin: 'dca-factory-view', key: 'cockpit' } as const, null)
const storyView = atom({ plugin: 'dca-factory-view', key: 'story' } as const, null as StoryView | null)
const tab = atom({ plugin: 'dca-factory-view', key: 'tab' } as const, 'backlog' as Tab)
const detail = atom({ plugin: 'dca-factory-view', key: 'detail' } as const, null as Detail | null)
const fileText = atom({ plugin: 'dca-factory-view', key: 'fileText' } as const, '')

// The DCA brand palette (branding/README.md): teal is the accent, amber, coral and indigo share its tone.
const C = { accent: '#148f96', done: '#3f9d5b', wait: '#c9922e', fail: '#c96a5a', info: '#5f5bd0', muted: 'gray', onAccent: '#ffffff' }

const MARK_GLYPH: Record<string, string> = { done: '✓', running: '▶', look: '!', question: '?', stopped: '✗', next: '→', none: '·' }
const MARK_COLOR: Record<string, string> = {
  done: C.done,
  running: C.accent,
  look: C.wait,
  question: C.wait,
  stopped: C.fail,
  next: C.accent,
  none: C.muted,
}

// The recurring cycle; Describe sits beside it with set up and update — written once, changed when things move.
const TABS: { id: Tab; label: string; key: string }[] = [
  { id: 'discover', label: 'Discover', key: '1' },
  { id: 'backlog', label: 'Backlog', key: '2' },
  { id: 'run', label: 'Run', key: '3' },
  { id: 'decide', label: 'Decide', key: '4' },
  { id: 'delivered', label: 'Delivered', key: '5' },
]

// What `factory.sh run` says with its exit code (factory.sh's header).
const EXIT_WORDS: Record<number, string> = {
  0: 'ran through',
  3: 'stopped for a decision — see Decide',
  4: 'stopped at --max-stages',
  5: 'another worker holds the checkout',
  6: 'refused: inside an agent session',
}

function stageLabel(run: StageRun, now: number): string {
  const gate = run.gates.length === 0 ? '' : run.gates[run.gates.length - 1] ? ' ✓' : ' ✗'
  const rounds = run.rounds > 1 ? ` · ${roundsText(run.rounds)}` : ''
  const time = run.runningSince ? ` · ▶ ${duration((now - Date.parse(run.runningSince)) / 1000)}` : ` · ${duration(run.seconds)}`
  return `${run.stage}${gate}${rounds}${time}`
}

function stageColor(run: StageRun): string {
  if (run.runningSince) return C.accent
  if (run.gates.length > 0 && !run.gates[run.gates.length - 1]) return C.fail
  return C.done
}

// ---------------------------------------------------------------- reading the factory

// The factory's own views are the source: status, one story and decisions as JSON from factory.sh.
// The files read directly are the append-only journals and the hand-overs, never a state the factory computes.
const RUNNER = '.agents/factory/factory.sh'
const RUNS = '.dca-factory/runs'

async function factoryJson<T>($: EngineInterface, root: string, args: string[]): Promise<T | null> {
  const ran = await $.process.run(['bash', `${root}/${RUNNER}`, ...args], { cwd: root, timeoutMs: 60_000 })
  if (ran.exitCode !== 0) return null
  try {
    return JSON.parse(ran.stdout) as T
  } catch {
    return null
  }
}

async function readText($: EngineInterface, path: string): Promise<string> {
  return $.fs.read(path).catch(() => '')
}

async function loadJournal($: EngineInterface, root: string, story: string): Promise<JournalEvent[]> {
  return parseJournal(await readText($, `${root}/${RUNS}/${story}/.verify/journal.tsv`))
}

async function handovers($: EngineInterface, root: string, story: string): Promise<string[]> {
  return (await $.fs.list(`${root}/${RUNS}/${story}`).catch(() => []))
    .filter(entry => entry.kind === 'file' && entry.name.endsWith('.md') && !entry.name.startsWith('.'))
    .map(entry => entry.name)
}

async function loadCockpit($: EngineInterface): Promise<Cockpit | null> {
  const root = await $.session.root()
  if (!(await $.fs.exists(`${root}/${RUNNER}`))) return null

  const [status, decisions, discovery] = await Promise.all([
    factoryJson<FactoryStatus>($, root, ['status', '--format', 'json', '--live']),
    factoryJson<{ records?: DecisionRecord[] }>($, root, ['decisions', '--format', 'json']),
    factoryJson<{ topics?: Topic[] }>($, root, ['discover', '--list', '--format', 'json']),
  ])
  if (!status) return null

  const ids = status.rows.map(row => row.story)
  const [journals, files] = await Promise.all([
    Promise.all(ids.map(id => loadJournal($, root, id))),
    Promise.all(ids.map(id => handovers($, root, id))),
  ])

  return {
    root,
    project: status.project,
    status,
    decisions: decisions?.records ?? [],
    topics: discovery?.topics ?? [],
    isBehind: !status.description || !discovery,
    journals: Object.fromEntries(ids.map((id, index) => [id, journals[index] ?? []])),
    handovers: Object.fromEntries(ids.map((id, index) => [id, files[index] ?? []])),
    updatedAt: await $.clock.now(),
  }
}

// While a stage runs only what moves is read again: the status and the running stories' journals.
async function loadLive($: EngineInterface, before: Cockpit): Promise<Cockpit> {
  const status = await factoryJson<FactoryStatus>($, before.root, ['status', '--format', 'json', '--live'])
  if (!status) return before
  const moving = status.running.map(running => running.story)
  const journals = await Promise.all(moving.map(id => loadJournal($, before.root, id)))
  return {
    ...before,
    status,
    journals: { ...before.journals, ...Object.fromEntries(moving.map((id, index) => [id, journals[index] ?? []])) },
    updatedAt: await $.clock.now(),
  }
}

async function loadStory($: EngineInterface, root: string, id: string): Promise<StoryView | null> {
  const view = await factoryJson<StoryView>($, root, ['status', '--story', id, '--format', 'json', '--live'])
  return view && view.story === id && typeof view.stages === 'object' && Array.isArray(view.passes) ? view : null
}

// ---------------------------------------------------------------- the worker

// The worker is factory.sh run, started by the person's press and nothing else. It runs as a child of
// this module: a reload of the mod or the end of the session ends it, and the runner gives its claim back.
const worker = atom({ plugin: 'dca-factory-view', key: 'worker' } as const, {
  state: 'idle',
  label: '',
  startedAt: 0,
  code: null,
  lines: [],
} as Worker)

const KEEP_LINES = 200
let child: HookStream<ProcessSpawnChunk, ProcessSpawnResult> | null = null

function isRunning(): boolean {
  return child !== null
}

async function startWorker($: EngineInterface, label: string, args: string[], onEnd: () => void): Promise<void> {
  if (child) return

  const root = await $.session.root()
  const startedAt = await $.clock.now()
  await update($, worker, (): Worker => ({ state: 'running', label, startedAt, code: null, lines: [`$ factory.sh ${args.join(' ')}`] }))

  // The runner refuses to start inside an agent session unless told it is deliberate; a press is.
  const stream = $.process.spawn({
    argv: ['bash', `${root}/${RUNNER}`, ...args],
    cwd: root,
    env: { FACTORY_ALLOW_NESTED: '1' },
  })
  child = stream

  void (async () => {
    let code: number | null = null
    try {
      for await (const piece of stream) {
        await update($, worker, now => ({ ...now, lines: appendLines(now.lines, piece.text, KEEP_LINES) }))
      }
      code = (await stream.result).code
    } catch (error) {
      await update($, worker, now => ({ ...now, lines: appendLines(now.lines, `\n${String(error)}`, KEEP_LINES) }))
    } finally {
      child = null
      await update($, worker, (now): Worker => ({ ...now, state: 'ended', code }))
      onEnd()
    }
  })()
}

async function stopWorker($: EngineInterface): Promise<void> {
  const running = child
  if (!running) return
  await update($, worker, now => ({ ...now, lines: appendLines(now.lines, '\n— stopped from the cockpit —', KEEP_LINES) }))
  await running.return(undefined as never)
}

// ---------------------------------------------------------------- loading and acting

let isLoading = false

async function refresh($: EngineInterface, isQuiet = false, isLive = false): Promise<void> {
  if (isLoading) return
  isLoading = true
  try {
    const before = await read($, cockpit)
    const now = isLive && before ? await loadLive($, before).catch(() => before) : await loadCockpit($).catch(() => before)
    await update($, cockpit, () => now)
    const open = await read($, detail)
    if (now && open?.kind === 'story') {
      const view = await loadStory($, now.root, open.id).catch(() => null)
      await update($, storyView, () => view)
    }
    if (!now) {
      $.ui.status(undefined)
      return
    }
    if (!isQuiet && before) announce($, before, now)
    const running = now.status.running[0]
    const waiting = now.status.waiting[0]
    $.ui.status(
      waiting
        ? `factory: waits for you — ${waiting.story} ${waiting.what}`
        : running
          ? `factory: ${running.story} · ${running.stage}`
          : `factory: ${now.status.next.text}`,
    )
  } finally {
    isLoading = false
  }
}

// What changed since the last look: a stage started, a gate refused, a story delivered, a new question.
function announce($: EngineInterface, before: Cockpit, now: Cockpit): void {
  for (const [story, events] of Object.entries(now.journals)) {
    for (const event of events.slice(before.journals[story]?.length ?? events.length)) {
      if (event.kind === 'stage-start') $.ui.toast(`factory: ${story} — ${event.stage} started`)
      if (event.kind === 'gate' && event.fields.exit !== '0') $.ui.toast(`factory: ${story} — ${event.stage} gate refused`)
    }
  }
  for (const row of now.status.rows) {
    const old = before.status.rows.find(one => one.story === row.story)
    if (old && !old.done && row.done) $.ui.toast(`factory: ${row.story} delivered`)
  }
  for (const wait of now.status.waiting) {
    if (!before.status.waiting.some(one => one.story === wait.story && one.what === wait.what)) {
      $.ui.toast(`factory: waits for you — ${wait.story} ${wait.what}`)
    }
  }
}

// A mod may not submit a text that begins with "/" — the host refuses it; a skill's slash command runs through
// $.command.run as if the person typed it, queued until the session is idle. Its name is looked up in the
// session's own list, so a plugin skill is found under its short name (`dca-describe`) or its full one
// (`dca-core:dca-describe`). Whatever happens, the person sees it: a toast when sent, the prompt box when not.
function send($: EngineInterface, text: string): void {
  const [head = '', ...words] = text.trim().split(' ')
  const args = words.join(' ').trim()
  void (async () => {
    try {
      if (!head.startsWith('/')) {
        await $.prompt.submit({ text, asUser: true })
      } else {
        const wanted = head.slice(1)
        const names = (await $.command.list()).map(command => command.name)
        const name = names.find(one => one === wanted) ?? names.find(one => one.endsWith(`:${wanted}`))
        if (!name) throw new Error(`no command /${wanted} in this session`)
        $.ui.toast(`factory: sent /${name}${args ? ` ${args}` : ''}`)
        await $.command.run({ command: name, args })
      }
    } catch (error) {
      $.ui.toast(`factory: could not send (${String(error)}) — it is in the prompt, press Enter`)
      await $.prompt.fill({ text }).catch(() => undefined)
    }
  })()
}

// A description file opened for the person's own hand, in the editor the system names for it.
async function editFile($: EngineInterface, path: string): Promise<void> {
  const opened = await $.process.run(['open', path]).catch(() => null)
  if (opened?.exitCode === 0) {
    $.ui.toast(`factory: opened ${path.split('/').pop()} in the editor`)
    return
  }
  const fallback = await $.process.run(['xdg-open', path]).catch(() => null)
  $.ui.toast(fallback?.exitCode === 0 ? `factory: opened ${path.split('/').pop()} in the editor` : `factory: no editor could open ${path}`)
}

async function openStory($: EngineInterface, id: string): Promise<void> {
  await update($, storyView, () => null)
  await update($, detail, () => ({ kind: 'story', id }) as Detail)
  const now = await read($, cockpit)
  if (now) {
    const view = await loadStory($, now.root, id).catch(() => null)
    await update($, storyView, () => view)
  }
}

async function openFile($: EngineInterface, path: string, title: string, back: Detail | null): Promise<void> {
  const text = await $.fs.read(path).catch(() => '(not readable)')
  await update($, fileText, () => (text.length > 30_000 ? `${text.slice(0, 30_000)}\n\n…` : text))
  await update($, detail, () => ({ kind: 'file', path, title, back }) as Detail)
}

async function runWorker($: EngineInterface, label: string, args: string[]): Promise<void> {
  await update($, tab, () => 'run' as Tab)
  await update($, detail, () => null)
  await startWorker($, label, args, () => {
    void (async () => {
      const ended = await read($, worker)
      $.ui.toast(`factory: worker ${EXIT_WORDS[ended.code ?? -1] ?? `ended (${ended.code ?? 'signal'})`}`)
      await refresh($, true)
    })()
  })
}

// ---------------------------------------------------------------- hooks

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'factory-view', description: 'The product flow as a cockpit: describe beside the cycle discover, backlog, run, decide, delivered' })
    await refresh($, true)
    $.clock.every(STATUS_MS, () => void refresh($))
    $.clock.every(LIVE_MS, () => {
      void (async () => {
        const now = await read($, cockpit)
        if (isRunning() || (now && now.status.running.length > 0)) await refresh($, false, true)
      })()
    })
    return next(e)
  })

  on('command.run', { command: 'factory-view' }, async $ => {
    await refresh($, true)
    if (!(await read($, cockpit))) {
      return { text: 'No factory in this project (.agents/factory/factory.sh is missing) — /factory-setup installs it.' }
    }
    await update($, detail, () => null)
    await $.ui.open({ id: PANE, title: 'Factory', focus: true })
    return { text: 'Factory cockpit opened.' }
  })

  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    if (touchesFactory(e)) await refresh($)
    return ran
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const now = await read($, cockpit)
    const { Text } = $.ui.resolve(e)
    if (!now) return <Text color={C.muted}>No factory in this project.</Text>
    return draw($, e, now)
  })
}

// ---------------------------------------------------------------- drawing

async function draw($: EngineInterface, e: RenderInput<'Pane'>, now: Cockpit) {
  const { Box, Text, Button, Markdown, ...rest } = $.ui.resolve(e)
  const Input = 'Input' in rest ? rest.Input : null
  const at = await $.clock.now()
  const current = await read($, tab)
  const open = await read($, detail)
  const job = await read($, worker)
  const rows = e.viewport?.rows ?? 40
  const status = now.status

  const section = (title: string, hint?: string) => (
    <Box marginTop={1} gap={1}>
      <Text bold color={C.accent}>
        {title}
      </Text>
      {hint && <Text color={C.muted}>{hint}</Text>}
    </Box>
  )
  const keys = (hint: string) => (
    <Box marginTop={1}>
      <Text color={C.muted}>
        {e.props.isFocused ? `${hint} · 0 describe · 1–5 cycle · Tab/↑↓ move · Enter choose · Esc prompt` : 'ctrl+x tab — steer the cockpit'}
      </Text>
    </Box>
  )
  // Where the surface has no Input (mobile), the button fills the prompt and the person types there.
  const ask = (key: string, label: string, placeholder: string, command: string) =>
    Input ? (
      <Input key={key} label={label} placeholder={placeholder} submitLabel="send" onSubmit={(value: string) => void send($, `${command} ${value}`.trim())} />
    ) : (
      <Button key={key} label={label} onPress={() => $.prompt.fill({ text: `${command} ` })} />
    )
  const cell = (width: number, text: string, color?: string, bold?: boolean) => (
    <Box width={width} flexShrink={0}>
      <Text color={color} bold={bold} wrap="truncate">
        {text}
      </Text>
    </Box>
  )

  // A table drawn as one: a frame, a bold header, a rule under it, a thin bar between the columns, room in each cell.
  type Column = { name: string; width: number; isNumber?: boolean }
  type Cell = { text?: string; color?: string; bold?: boolean; node?: RenderElement }
  const divider = <Text color={C.muted}> │ </Text>
  const tableCell = (column: Column, value: Cell) => (
    <Box width={column.width} flexShrink={0} justifyContent={column.isNumber ? 'flex-end' : 'flex-start'}>
      {value.node ?? (
        <Text color={value.color} bold={value.bold} wrap="truncate">
          {value.text ?? ''}
        </Text>
      )}
    </Box>
  )
  const table = (columns: Column[], rows: Cell[][]) => (
    <Box flexDirection="column" borderStyle="round" borderColor={C.muted} paddingX={1} marginTop={1}>
      <Box>{columns.flatMap((column, index) => [...(index > 0 ? [divider] : []), tableCell(column, { text: column.name, bold: true, color: C.accent })])}</Box>
      <Text color={C.muted}>{columns.map(column => '─'.repeat(column.width)).join('─┼─')}</Text>
      {rows.map(row => (
        <Box>{columns.flatMap((column, index) => [...(index > 0 ? [divider] : []), tableCell(column, row[index] ?? {})])}</Box>
      ))}
    </Box>
  )

  const head = (
    <Box flexDirection="column">
      <Box borderStyle="round" borderColor={C.accent} paddingX={1} justifyContent="space-between">
        <Text bold color={C.accent}>
          ⬡ {now.project}
        </Text>
        <Text color={C.muted}>
          {status.delivered} of {status.total} stories delivered
          {status.tokens > 0 ? ` · ${tokensText(status.tokens)} tokens` : ''}
          {job.state === 'running' ? ' · worker ▶' : ''}
        </Text>
      </Box>
      <Box gap={1} flexWrap="wrap">
        {/* The foundation: done once, changed when the product or the technical situation moves. */}
        <Button
          key="tab-describe"
          label="0 Describe"
          hotkey="0"
          variant={current === 'describe' && !open ? 'primary' : 'secondary'}
          onPress={() => {
            void update($, detail, () => null)
            void update($, tab, () => 'describe' as Tab)
          }}
        />
        <Button key="setup" label="setup" plain onPress={() => send($, '/factory-setup')} />
        <Button key="update" label="update" plain onPress={() => send($, '/factory-update')} />
        <Text color={C.muted}>│ cycle ›</Text>
        {TABS.map(one => (
          <Button
            key={`tab-${one.id}`}
            label={`${one.key} ${one.label}${one.id === 'decide' && status.waiting.length > 0 ? ` (${status.waiting.length})` : ''}`}
            hotkey={one.key}
            variant={one.id === current && !open ? 'primary' : 'secondary'}
            onPress={() => {
              void update($, detail, () => null)
              void update($, tab, () => one.id)
            }}
          />
        ))}
      </Box>
      {status.waiting.length > 0 && (
        <Box borderStyle="round" borderColor={C.wait} paddingX={1} flexDirection="column">
          {status.waiting.map(wait => (
            <Text bold color={C.wait}>
              {MARK_GLYPH[wait.mark] ?? '?'} {wait.story} — {wait.what}
            </Text>
          ))}
        </Box>
      )}
      <Box gap={1}>
        <Text bold color={C.accent}>
          Next ›
        </Text>
        <Text>{status.next.text}</Text>
      </Box>
      {now.isBehind && (
        <Box gap={1}>
          <Text color={C.wait}>This project's pipeline is older than the cockpit reads — the description and discovery views stay empty.</Text>
          <Button key="behind-update" label="update" plain onPress={() => send($, '/factory-update')} />
        </Box>
      )}
    </Box>
  )

  // ---- a file: a description, a discovery report, a hand-over, a decision record
  if (open?.kind === 'file') {
    return (
      <Box flexDirection="column">
        {head}
        <Box gap={1} marginTop={1}>
          <Button key="back" label="← back" hotkey="b" onPress={() => (open.back?.kind === 'story' ? openStory($, open.back.id) : update($, detail, () => open.back))} />
          <Button key="edit" label="✎ edit" hotkey="e" onPress={() => editFile($, open.path)} />
          <Text bold>{open.title}</Text>
        </Box>
        <Box borderStyle="single" borderColor={C.muted} paddingX={1} flexDirection="column">
          <Markdown text={await read($, fileText)} />
        </Box>
        {keys('b back · e edit in your editor')}
      </Box>
    )
  }

  // ---- one story: its pipeline, history and hand-overs
  if (open?.kind === 'story') {
    const row = status.rows.find(one => one.story === open.id)
    const events = now.journals[open.id] ?? []
    const stages = stagesOf(events)
    const view = (await read($, storyView))?.story === open.id ? await read($, storyView) : null
    const perStage = view ? Object.entries(view.stages) : []
    const longest = Math.max(1, ...perStage.map(([, one]) => one.seconds))
    const records = now.decisions.filter(record => record.story === open.id)
    const waits = status.waiting.some(wait => wait.story === open.id)
    const room = Math.max(4, rows - 30)
    return (
      <Box flexDirection="column">
        {head}
        <Box gap={1} marginTop={1}>
          <Text bold color={MARK_COLOR[row?.mark ?? 'none']}>
            {MARK_GLYPH[row?.mark ?? 'none']}
          </Text>
          <Text bold>
            {open.id} — {row?.title ?? ''}
          </Text>
        </Box>
        <Box gap={2} flexWrap="wrap">
          <Text color={MARK_COLOR[row?.mark ?? 'none']}>{row?.state ?? ''}</Text>
          <Text color={C.muted}>{row?.epic ?? ''}</Text>
          {row && row.seconds > 0 && <Text color={C.muted}>worked {duration(row.seconds)}</Text>}
          {row && row.tokens > 0 && <Text color={C.muted}>{tokensText(row.tokens)} tokens</Text>}
          {row && row.cost > 0 && <Text color={C.muted}>cost {row.cost.toFixed(2)} USD</Text>}
        </Box>
        <Box gap={2} flexWrap="wrap">
          {row?.started && <Text color={C.muted}>started {moment(row.started)}</Text>}
          {row?.delivered && <Text color={C.done}>delivered {moment(row.delivered)}</Text>}
          {view?.accepted_by && <Text color={C.done}>accepted ({view.accepted_by})</Text>}
        </Box>
        {view && (
          <Box gap={2} flexWrap="wrap">
            {view.context && <Text color={C.muted}>context {view.context}</Text>}
            {view.criteria > 0 && <Text color={C.muted}>{view.criteria} acceptance criteria</Text>}
          </Box>
        )}
        <Box gap={1} marginTop={1} flexWrap="wrap">
          <Button key="back" label="← back" hotkey="b" onPress={() => update($, detail, () => null)} />
          {row && !row.done && !isRunning() && (
            <Button key="run" label="▶ Run (worker)" hotkey="r" variant="primary" onPress={() => runWorker($, `run ${open.id}`, ['run', '--story', open.id])} />
          )}
          {row && !row.done && <Button key="session" label="Run in this session" hotkey="e" onPress={() => send($, `/factory-run ${open.id}`)} />}
          {waits && <Button key="answer" label="? Answer" hotkey="a" variant="primary" onPress={() => send($, `/factory-decisions ${open.id}`)} />}
          {row?.done && <Button key="verify" label="Verify" hotkey="v" onPress={() => send($, `/factory-verify ${open.id}`)} />}
        </Box>

        {section('Pipeline')}
        {stages.length === 0 ? (
          <Text color={C.muted}>Not run yet.</Text>
        ) : (
          <Box flexWrap="wrap" columnGap={1}>
            {stages.map((run, index) => (
              <Box gap={1}>
                {index > 0 && <Text color={C.muted}>›</Text>}
                <Text backgroundColor={run.runningSince ? C.accent : undefined} color={run.runningSince ? C.onAccent : stageColor(run)} bold={run.runningSince !== null}>
                  {` ${stageLabel(run, at)} `}
                </Text>
              </Box>
            ))}
          </Box>
        )}
        {perStage.length > 0 && section('Time per stage', 'the factory\'s own numbers')}
        {perStage.map(([name, one]) => (
          <Box gap={1}>
            {cell(10, name, C.muted)}
            <Text color={C.accent}>{bar(one.seconds, longest, 20)}</Text>
            <Text color={C.muted}>
              {duration(one.seconds)}
              {one.runs > 1 ? ` · ${one.runs} runs` : ''}
              {one.tokens > 0 ? ` · ${tokensText(one.tokens)} tokens` : ''}
              {one.cost > 0 ? ` · ${one.cost.toFixed(2)} USD` : ''}
              {one.models.length > 0 ? ` · ${one.models.join(', ')}` : ''}
            </Text>
          </Box>
        ))}
        {view && view.passes.length > 0 && section('Passes')}
        {view?.passes.map((pass, index) => (
          <Box gap={1}>
            {cell(3, `${index + 1}.`, C.muted)}
            {cell(18, pass.label, index === 0 ? C.done : C.wait)}
            <Text color={C.muted} wrap="truncate">
              {short(pass.start)} · {duration(pass.seconds)}
              {pass.tokens > 0 ? ` · ${tokensText(pass.tokens)} tokens` : ''}
              {pass.waited > 0 ? ` · waited ${duration(pass.waited)}` : ''} · {pass.stages.join(' ')}
            </Text>
          </Box>
        ))}
        {section('History')}
        {events.length === 0 && <Text color={C.muted}>Nothing yet.</Text>}
        {events
          .filter(event => event.kind !== 'usage')
          .slice(-room)
          .map((event, index, shown) => {
            const isGate = event.kind === 'gate'
            const passed = event.fields.exit === '0'
            const color = isGate ? (passed ? C.done : C.fail) : event.kind === 'stage-start' ? C.accent : C.muted
            const what = isGate ? (passed ? 'gate ✓' : 'gate ✗') : event.kind === 'stage-start' ? '▶ start' : '■ end'
            const isNewDay = index === 0 || day(shown[index - 1]?.at ?? '') !== day(event.at)
            return (
              <Box flexDirection="column">
                {isNewDay && (
                  <Text bold color={C.muted}>
                    {day(event.at)}
                  </Text>
                )}
                <Box gap={1} paddingLeft={2}>
                  <Text color={C.muted}>{clock(event.at)}</Text>
                  <Text color={color}>{`${what} ${event.stage}`}</Text>
                </Box>
              </Box>
            )
          })}
        {(now.handovers[open.id] ?? []).length > 0 && section('Hand-over')}
        <Box gap={1} flexWrap="wrap">
          {(now.handovers[open.id] ?? []).map(file => (
            <Button key={`file-${file}`} label={file} onPress={() => openFile($, `${now.root}/.dca-factory/runs/${open.id}/${file}`, `${open.id} / ${file}`, open)} />
          ))}
        </Box>
        {records.length > 0 && section('Decisions')}
        {records.map(record => (
          <Box gap={1}>
            <Text color={record.state === 'open' ? C.wait : C.muted}>{record.state}</Text>
            <Button key={`record-${record.id}`} label={record.id} plain onPress={() => openFile($, `${now.root}/${record.path}`, record.id, open)} />
            <Text color={C.muted} wrap="truncate">
              {record.text}
            </Text>
          </Box>
        ))}
        {keys(`b back${row && !row.done ? ' · r run · e in session' : ''}${waits ? ' · a answer' : ''}`)}
      </Box>
    )
  }

  const storyButton = (row: Row) => (
    <Box gap={1}>
      <Text bold color={MARK_COLOR[row.mark] ?? C.muted}>
        {MARK_GLYPH[row.mark] ?? '·'}
      </Text>
      <Button key={`story-${row.story}`} label={row.story} plain onPress={() => openStory($, row.story)} />
    </Box>
  )
  const idWidth = Math.max(8, ...status.rows.map(row => row.story.length)) + 4

  // ---- the six tabs
  let body
  if (current === 'describe') {
    body = (
      <Box flexDirection="column">
        {section('Project description', 'the foundation — written once, changed when the product or the technical situation moves')}
        {(status.description ?? []).map(part => {
          const path = `${now.root}/${part.path}`
          const name = part.path.split('/').pop() ?? part.part
          const gaps = [...part.missing.map(h => `missing ${h}`), ...part.empty.map(h => `empty ${h}`)]
          return (
            <Box flexDirection="column">
              <Box gap={1}>
                <Text bold color={!part.present ? C.fail : gaps.length > 0 ? C.wait : C.done}>
                  {!part.present ? '✗' : gaps.length > 0 ? '!' : '✓'}
                </Text>
                {part.present ? (
                  <Button key={`doc-${part.part}`} label={name} plain onPress={() => openFile($, path, name, null)} />
                ) : (
                  <Text color={C.fail}>{name} missing</Text>
                )}
                {part.present && <Button key={`edit-${part.part}`} label="✎ edit" plain onPress={() => editFile($, path)} />}
                <Text color={C.muted} wrap="truncate">
                  {part.sections.join(' · ')}
                </Text>
              </Box>
              {gaps.length > 0 && (
                <Text color={C.wait} wrap="truncate">
                  {'    '}
                  {gaps.join(' · ')}
                </Text>
              )}
            </Box>
          )
        })}
        <Box marginTop={1} flexDirection="column">
          {ask('change', 'Change the description', 'what should change? e.g. "the shop also sells gift cards"', '/dca-describe')}
        </Box>
        <Box gap={1} marginTop={1}>
          <Button key="describe" label="✎ Describe / complete the project" variant="primary" onPress={() => send($, '/dca-describe')} />
        </Box>
      </Box>
    )
  } else if (current === 'discover') {
    body = (
      <Box flexDirection="column">
        {section('Discovery', 'which problem is worth solving, and how anyone will know it got better')}
        {now.topics.length === 0 && <Text color={C.muted}>No discovery yet.</Text>}
        {now.topics.map(topic => (
          <Box flexDirection="column" marginTop={1}>
            <Box gap={1}>
              <Text color={C.info}>◆</Text>
              <Button key={`topic-${topic.topic}`} label={topic.topic} plain onPress={() => openFile($, `${now.root}/${topic.report}`, topic.title, null)} />
              <Text color={C.muted} wrap="truncate">
                {topic.title}
              </Text>
            </Box>
            {topic.proposals.length === 0 && <Text color={C.muted}>{'  '}no proposed work in the report yet</Text>}
            {topic.proposals.map(proposal => (
              <Box flexDirection="column" paddingLeft={2}>
                <Box gap={1}>
                  <Text bold color={proposal.epic ? C.done : C.info}>
                    {proposal.epic ? '✓' : '○'} {proposal.id}
                  </Text>
                  {proposal.epic ? (
                    <Text color={C.done}>epic {proposal.epic} — see Backlog</Text>
                  ) : (
                    <Button
                      key={`release-${topic.topic}-${proposal.id}`}
                      label="→ Make epic"
                      variant="primary"
                      onPress={() => send($, `/factory-backlog epic ${proposal.id} --from ${topic.report}`)}
                    />
                  )}
                </Box>
                {proposal.goal && (
                  <Text color={C.muted} wrap="truncate">
                    {'  '}goal: {proposal.goal}
                  </Text>
                )}
                {proposal.metric && (
                  <Text color={C.info} wrap="truncate">
                    {'  '}outcome: {proposal.metric}
                  </Text>
                )}
              </Box>
            ))}
            {topic.description_changes.map((change, index) => (
              <Box gap={1} paddingLeft={2}>
                <Text color={C.wait}>◇ {change.target}</Text>
                <Text color={C.muted} wrap="truncate">
                  {change.change}
                </Text>
                <Button
                  key={`describe-${topic.topic}-${index}`}
                  label="→ apply"
                  onPress={() => send($, `/dca-describe ${change.target}: ${change.change}`)}
                />
              </Box>
            ))}
          </Box>
        ))}
        <Box marginTop={1} flexDirection="column">
          {ask('discover', 'New topic', 'a problem or a wished deliverable', '/factory-discover')}
        </Box>
      </Box>
    )
  } else if (current === 'backlog') {
    body = (
      <Box flexDirection="column">
        <Box flexDirection="column" gap={1}>
          {ask('story', 'Write a story', 'what should the product do next?', '/factory-backlog')}
          {ask('wish', 'Wish', 'a wish in your words — it becomes a story and runs', '/factory-run')}
        </Box>
        {status.epics.length === 0 && <Text color={C.muted}>The backlog is empty.</Text>}
        {status.epics.map(epic => {
          const front = epic
          const drafts = epic.rows.filter(row => /draft/.test(row.state))
          return (
            <Box flexDirection="column" marginTop={2}>
              <Box gap={1}>
                <Text bold>{front.title || epic.epic}</Text>
                <Text color={C.done}>{bar(epic.delivered, epic.total, 10)}</Text>
                <Text color={C.muted}>
                  {epic.delivered} of {epic.total} delivered{epic.tokens > 0 ? ` · ${tokensText(epic.tokens)} tokens` : ''}
                </Text>
                <Button
                  key={`stories-${epic.epic}`}
                  label="+ stories"
                  variant={epic.total === 0 ? 'primary' : 'secondary'}
                  onPress={() => send($, `/factory-backlog stories ${epic.epic}`)}
                />
                {drafts.length > 0 && (
                  <Button
                    key={`release-all-${epic.epic}`}
                    label={`release ${drafts.length} draft${drafts.length === 1 ? '' : 's'}`}
                    onPress={() => send($, `/factory-backlog release ${drafts.map(row => row.story).join(' ')}`)}
                  />
                )}
              </Box>
              {front?.discovery && (
                <Text color={C.muted} wrap="truncate">
                  from discovery: {front.discovery}
                </Text>
              )}
              {epic.total === 0 && <Text color={C.wait}>no stories yet — + stories cuts the first</Text>}
              {front?.goal && (
                <Text color={C.muted} wrap="truncate">
                  goal: {front.goal}
                </Text>
              )}
              {front?.metric && (
                <Text color={C.info} wrap="truncate">
                  outcome: {front.metric}
                </Text>
              )}
              {epic.total > 0 &&
                table(
                  [
                    { name: 'story', width: idWidth },
                    { name: 'state', width: 20 },
                    { name: 'stage', width: 9 },
                    { name: 'passes', width: 6, isNumber: true },
                    { name: 'started UTC', width: 12 },
                    { name: 'worked', width: 12, isNumber: true },
                    { name: 'tokens', width: 8, isNumber: true },
                    { name: 'cost', width: 10, isNumber: true },
                  ],
                  epic.rows.map(row => [
                    { node: storyButton(row) },
                    { text: row.state, color: MARK_COLOR[row.mark] },
                    { text: row.stage, color: C.muted },
                    { text: row.passes > 0 ? String(row.passes) : '—', color: row.passes > 1 ? C.wait : C.muted },
                    { text: short(row.started), color: C.muted },
                    { text: row.seconds > 0 ? duration(row.seconds) : '—' },
                    { text: row.tokens > 0 ? tokensText(row.tokens) : '—' },
                    { text: row.cost > 0 ? `${row.cost.toFixed(2)} USD` : '—' },
                  ]),
                )}
            </Box>
          )
        })}
        {status.journeys.length > 0 && section('Journeys')}
        {status.journeys.map(hint => (
          <Text color={C.wait} wrap="truncate">
            ◇ {hint.epic}: {hint.text}
          </Text>
        ))}
      </Box>
    )
  } else if (current === 'run') {
    const log = job.lines.slice(-Math.max(6, rows - 26))
    body = (
      <Box flexDirection="column">
        {section('Worker', 'factory.sh run in the background — one stage per process, a gate between them')}
        <Box gap={1} flexWrap="wrap">
          {!isRunning() && <Button key="run-all" label="▶ Run the backlog" hotkey="r" variant="primary" autoFocus onPress={() => runWorker($, 'run the backlog', ['run'])} />}
          {!isRunning() && <Button key="run-watch" label="◉ Run & keep watching" hotkey="w" onPress={() => runWorker($, 'run and watch', ['run', '--watch'])} />}
          {isRunning() && <Button key="stop" label="■ Stop" hotkey="x" variant="primary" onPress={() => stopWorker($)} />}
        </Box>
        <Box gap={2}>
          <Text color={job.state === 'running' ? C.accent : job.code === 0 ? C.done : job.state === 'ended' ? C.wait : C.muted}>
            {job.state === 'running'
              ? `▶ ${job.label} · ${duration((at - job.startedAt) / 1000)}`
              : job.state === 'ended'
                ? `■ ${job.label} — ${EXIT_WORDS[job.code ?? -1] ?? `ended (${job.code ?? 'signal'})`}`
                : 'no worker started from here'}
          </Text>
        </Box>
        {status.extra.map(line => (
          <Text color={C.muted} wrap="truncate">
            {line}
          </Text>
        ))}
        {section('Running')}
        {status.running.length === 0 && <Text color={C.muted}>No stage is running.</Text>}
        {status.running.map(running => {
          const stages = stagesOf(now.journals[running.story] ?? [])
          return (
            <Box flexDirection="column">
              <Box gap={1}>
                <Button key={`running-${running.story}`} label={running.story} plain onPress={() => openStory($, running.story)} />
                <Text color={running.interrupted ? C.fail : C.accent}>
                  {running.stage}
                  {running.ago ? ` · since ${running.ago}` : ''}
                  {running.interrupted ? ' · interrupted' : ''}
                </Text>
              </Box>
              {running.activity && (
                <Text color={C.muted} wrap="truncate">
                  {'  '}
                  {running.activity}
                </Text>
              )}
              <Box flexWrap="wrap" columnGap={1} paddingLeft={2}>
                {stages.map(run => (
                  <Text backgroundColor={run.runningSince ? C.accent : undefined} color={run.runningSince ? C.onAccent : stageColor(run)}>
                    {` ${stageLabel(run, at)} `}
                  </Text>
                ))}
              </Box>
            </Box>
          )
        })}
        {section('Output', job.lines.length > 0 ? `last ${log.length} lines` : undefined)}
        <Box borderStyle="single" borderColor={C.muted} paddingX={1} flexDirection="column">
          {log.length === 0 ? (
            <Text color={C.muted}>Nothing yet. A worker started here writes its output into this box.</Text>
          ) : (
            log.map(line => (
              <Text wrap="truncate" color={/refus|fail|error|✗/i.test(line) ? C.fail : /✓|pass|delivered/i.test(line) ? C.done : undefined}>
                {line || ' '}
              </Text>
            ))
          )}
        </Box>
        <Text color={C.muted}>The worker is a child of this session: ending the session or reloading the mod stops it.</Text>
      </Box>
    )
  } else if (current === 'decide') {
    const pending = now.decisions.filter(record => record.state === 'open' || record.state === 'draft')
    const answered = now.decisions.filter(record => !pending.includes(record)).slice(0, Math.max(3, rows - 24))
    const line = (record: (typeof now.decisions)[number]) => (
      <Box gap={1}>
        <Text color={record.kind === 'acceptance' ? C.info : C.wait}>{record.kind === 'acceptance' ? '!' : '?'}</Text>
        {cell(9, record.state, record.state === 'open' ? C.wait : C.muted)}
        <Button key={`record-${record.id}`} label={record.id} plain onPress={() => openFile($, `${now.root}/${record.path}`, record.id, null)} />
        <Text color={C.muted} wrap="truncate">
          {short(record.asked)} · {record.text}
        </Text>
      </Box>
    )
    body = (
      <Box flexDirection="column">
        {section('Waiting for you', 'questions a stage may not decide alone, results to look at')}
        {pending.length === 0 && status.waiting.length === 0 && <Text color={C.done}>Nothing waits for you.</Text>}
        {pending.map(line)}
        {status.waiting.map(wait => (
          <Box gap={1}>
            <Text color={C.wait}>{MARK_GLYPH[wait.mark] ?? '?'}</Text>
            <Text bold>{wait.story}</Text>
            <Text color={C.muted}>{wait.what}</Text>
            <Button key={`answer-${wait.story}`} label="Answer in session" variant="primary" onPress={() => send($, `/factory-decisions ${wait.story}`)} />
          </Box>
        ))}
        {section('Answered', `${now.decisions.length - pending.length} records`)}
        {answered.map(line)}
      </Box>
    )
  } else {
    const delivered = status.rows.filter(row => row.done)
    body = (
      <Box flexDirection="column">
        {section('Delivered', `${delivered.length} stories · ${duration(delivered.reduce((sum, row) => sum + row.seconds, 0))} worked`)}
        {delivered.length > 0 &&
          table(
            [
              { name: 'story', width: idWidth },
              { name: 'delivered UTC', width: 13 },
              { name: 'worked', width: 12, isNumber: true },
              { name: 'tokens', width: 8, isNumber: true },
              { name: 'cost', width: 10, isNumber: true },
              { name: 'epic', width: 22 },
            ],
            delivered.map(row => [
              { node: storyButton(row) },
              { text: short(row.delivered), color: C.done },
              { text: row.seconds > 0 ? duration(row.seconds) : '—' },
              { text: row.tokens > 0 ? tokensText(row.tokens) : '—' },
              { text: row.cost > 0 ? `${row.cost.toFixed(2)} USD` : '—' },
              { text: row.epic, color: C.muted },
            ]),
          )}
        {section('Epics')}
        {status.epics.map(epic => {
          const front = epic
          const unguarded = status.journeys.find(hint => hint.epic === epic.epic)
          return (
            <Box flexDirection="column">
              <Box gap={1}>
                <Text bold color={epic.delivered === epic.total ? C.done : undefined}>
                  {epic.delivered === epic.total ? '✓' : '·'} {front.title || epic.epic}
                </Text>
                <Text color={C.muted}>
                  {epic.delivered} of {epic.total}
                </Text>
                {unguarded && <Text color={C.wait}>◇ {unguarded.text}</Text>}
              </Box>
              {front?.metric && (
                <Text color={C.info} wrap="truncate">
                  {'  '}outcome: {front.metric}
                </Text>
              )}
            </Box>
          )
        })}
      </Box>
    )
  }

  const hints: Record<Tab, string> = {
    describe: 'Enter on a file opens it · ✎ edit opens it in your editor · type a change, Enter sends it',
    discover: '→ Make epic releases a proposal into the backlog · type a topic, Enter sends it',
    backlog: '+ stories cuts stories · release approves drafts · Enter on a story opens it',
    run: isRunning() ? 'x stop' : 'r run the backlog · w run & watch',
    decide: 'Enter on a record opens it',
    delivered: 'Enter on a story opens it',
  }

  return (
    <Box flexDirection="column" paddingX={1}>
      {head}
      <Box flexDirection="column" marginTop={1}>
        {body}
      </Box>
      {keys(hints[current])}
    </Box>
  )
}
