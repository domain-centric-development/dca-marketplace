import { atom, read, update } from 'claude-code'
import type { EngineInterface, HookStream, ProcessSpawnChunk, ProcessSpawnResult, Register, RenderElement, RenderInput } from 'claude-code'

import type { Cockpit, DecisionRecord, Detail, FactoryStatus, JournalEvent, Row, StoryView, Tab, Topic, Worker } from '../types'
import { C, COL, MARK_COLOR, MARK_GLYPH, applyPalette, components, fmt, type Cell } from './components'
import { appendLines, bar, clock, day, moment, parseJournal, stagesOf, touchesFactory } from './parse'

// The cockpit over the whole product flow: describe beside the cycle discover, backlog, run, decide, delivered.
// It shows what factory.sh and the project's files hold and decides nothing; a press either sends the
// matching command into this session or starts the runner — both are the person's act. How things look lives in
// components.tsx; this file reads, acts and arranges.
const PANE = 'factory-view'
const STATUS_MS = 20_000
const LIVE_MS = 5_000

const cockpit = atom({ plugin: 'dca-factory-view', key: 'cockpit' } as const, null)
const storyView = atom({ plugin: 'dca-factory-view', key: 'story' } as const, null as StoryView | null)
const tab = atom({ plugin: 'dca-factory-view', key: 'tab' } as const, 'backlog' as Tab)
const detail = atom({ plugin: 'dca-factory-view', key: 'detail' } as const, null as Detail | null)
const fileText = atom({ plugin: 'dca-factory-view', key: 'fileText' } as const, '')

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
    if (open?.kind === 'file') await readFile($, open.path)
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

async function showDetail($: EngineInterface, next: Detail): Promise<void> {
  await update($, detail, () => next)
}

async function showTab($: EngineInterface, id: Tab): Promise<void> {
  await update($, detail, () => null)
  await update($, tab, () => id)
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

// A file is read when it opens and again on every refresh, so a report or a hand-over a skill rewrites shows as it
// stands now.
async function readFile($: EngineInterface, path: string): Promise<void> {
  const text = await $.fs.read(path).catch(() => '(not readable)')
  await update($, fileText, () => (text.length > 30_000 ? `${text.slice(0, 30_000)}\n\n…` : text))
}

async function openFile($: EngineInterface, path: string, title: string, back: Detail | null): Promise<void> {
  await readFile($, path)
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
    await $.command.register({ name: 'factory-view', description: 'The product flow as a cockpit: describe beside the cycle discover, backlog, run, decide, delivered — `close` closes it' })
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

  on('command.run', { command: 'factory-view' }, async ($, e) => {
    if (e.args.trim() === 'close') {
      await $.ui.close({ id: PANE })
      return { text: 'Factory cockpit closed — /factory-view opens it again.' }
    }
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

  // A slash command the cockpit sent runs as a turn of its own; when any turn ends, what it wrote is read.
  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    void refresh($)
    return done
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
  const { Box, Text, Button, ...rest } = $.ui.resolve(e)
  // the site's paper for a light theme, its deep plates for a dark one — before anything is drawn
  const theme = (await $.config.list().catch(() => [])).find(row => row.key === 'theme')
  applyPalette(/light/i.test(String(theme?.value ?? '')))
  const ui = components({ Box, Text, Button, Input: 'Input' in rest ? rest.Input : null })
  const at = await $.clock.now()
  const current = await read($, tab)
  const open = await read($, detail)
  const job = await read($, worker)
  const rows = e.viewport?.rows ?? 40
  const status = now.status
  const isFocused = Boolean(e.props.isFocused)

  // The links every view shares — one way to open a story, a record, a file.
  const storyCell = (row: Row): Cell => ({ node: ui.marked(row.mark, `story-${row.story}`, row.story, () => void openStory($, row.story)) })
  const recordCell = (record: DecisionRecord, back: Detail | null): Cell => ({
    node: ui.link(`record-${record.id}`, record.id, () => void openFile($, `${now.root}/${record.path}`, record.id, back)),
  })
  const ask = (key: string, label: string, placeholder: string, command: string) =>
    ui.ask(key, label, placeholder, value => send($, `${command} ${value}`.trim()), () => void $.prompt.fill({ text: `${command} ` }))
  const idWidth = Math.max(8, ...status.rows.map(row => row.story.length)) + 4
  const recordTable = (list: DecisionRecord[], back: Detail | null) =>
    ui.table(
      [COL.mark, { name: 'state', width: 9 }, COL.record, COL.asked, COL.what],
      list.map(record => [
        { text: record.kind === 'acceptance' ? '!' : '?', color: record.kind === 'acceptance' ? C.info : C.wait, bold: true },
        { text: record.state, color: record.state === 'open' ? C.wait : C.muted },
        recordCell(record, back),
        { text: fmt.when(record.asked), color: C.muted },
        { text: record.text, color: C.muted },
      ]),
      'No record.',
    )

  const head = (
    <Box flexDirection="column">
      <Box borderStyle="round" borderColor={C.accent} paddingX={1} justifyContent="space-between">
        {/* as the site's word mark: the name bright, the part after the dot in teal */}
        <Text bold color={C.bright}>
          <Text color={C.accent}>⬡ </Text>
          {now.project}
          <Text color={C.accent}>.factory</Text>
        </Text>
        <Text color={C.muted}>
          {status.delivered} of {status.total} stories delivered
          {status.tokens > 0 ? ` · ${fmt.tokens(status.tokens)} tokens` : ''}
          {job.state === 'running' ? ' · worker ▶' : ''}
        </Text>
        {ui.button('close', '✕ close', () => void $.ui.close({ id: PANE }), { hotkey: 'q' })}
      </Box>
      <Box marginTop={1}>
        {ui.phases(
          [
            { key: 'tab-describe', label: 'Describe', hotkey: '0', isOpen: current === 'describe' && !open, onPress: () => void showTab($, 'describe') },
            { key: 'setup', label: '✦ setup', isOpen: false, onPress: () => send($, '/factory-setup') },
            { key: 'update', label: '✦ update', isOpen: false, onPress: () => send($, '/factory-update') },
          ],
          TABS.map(one => ({
            key: `tab-${one.id}`,
            label: one.label,
            hotkey: one.key,
            isOpen: one.id === current && !open,
            mark:
              one.id === 'decide' && status.waiting.length > 0
                ? { text: String(status.waiting.length), color: C.wait }
                : one.id === 'run' && (isRunning() || status.running.length > 0)
                  ? { text: '▶', color: C.accent }
                  : one.id === 'delivered' && status.delivered > 0
                    ? { text: String(status.delivered), color: C.done }
                    : undefined,
            onPress: () => void showTab($, one.id),
          })),
        )}
      </Box>
      {status.waiting.length > 0 && ui.banner(C.wait, status.waiting.map(wait => `${MARK_GLYPH[wait.mark] ?? '?'} ${wait.story} — ${wait.what}`))}
      <Box gap={1} marginTop={1}>
        <Text bold color={C.accent}>
          Next ›
        </Text>
        <Text color={C.text}>{status.next.text}</Text>
      </Box>
      {now.isBehind && (
        <Box gap={1}>
          <Text color={C.wait}>This project's pipeline is older than the cockpit reads — the description and discovery views stay empty.</Text>
          {ui.link('behind-update', '✦ update', () => send($, '/factory-update'))}
        </Box>
      )}
    </Box>
  )

  const page = (body: RenderElement | RenderElement[], hint: string) => (
    // the painted surface fills the pane: at least the rows the surface gave its body, the whole width
    <Box flexDirection="column" paddingX={1} paddingY={1} backgroundColor={C.bg} minHeight={e.props.scroll?.bodyRows ?? rows} width={e.props.bodyColumns ?? '100%'}>
      {head}
      <Box flexDirection="column" marginTop={1}>
        {body}
      </Box>
      {ui.keys(isFocused, hint)}
    </Box>
  )

  // ---- a file: a description, a discovery report, a hand-over, a decision record
  if (open?.kind === 'file') {
    return page(
      [
        <Box gap={1}>
          <Text bold color={C.bright}>
            {open.title}
          </Text>
        </Box>,
        ui.actions([
          ui.button('back', '← back', () => void (open.back?.kind === 'story' ? openStory($, open.back.id) : update($, detail, () => open.back)), { hotkey: 'b' }),
          ui.button('edit', '✎ edit', () => void editFile($, open.path), { hotkey: 'e' }),
        ]),
        ui.framed(ui.doc(await read($, fileText))),
      ],
      'b back · e edit in your editor',
    )
  }

  // ---- one story: its pipeline, numbers, passes, history, hand-overs and decisions
  if (open?.kind === 'story') {
    const row = status.rows.find(one => one.story === open.id)
    const events = now.journals[open.id] ?? []
    const stored = await read($, storyView)
    const view = stored?.story === open.id ? stored : null
    const perStage = view ? Object.entries(view.stages) : []
    const longest = Math.max(1, ...perStage.map(([, one]) => one.seconds))
    const records = now.decisions.filter(record => record.story === open.id)
    const waits = status.waiting.some(wait => wait.story === open.id)
    const shown = events.filter(event => event.kind !== 'usage').slice(-Math.max(4, rows - 34))
    const mark = row?.mark ?? 'none'
    return page(
      [
        <Box gap={1}>
          <Text bold color={MARK_COLOR[mark]}>
            {MARK_GLYPH[mark]}
          </Text>
          <Text bold color={C.bright}>
            {open.id} — {row?.title ?? ''}
          </Text>
        </Box>,
        ui.fields(
          [
            { label: 'state', text: row?.state ?? '', color: MARK_COLOR[mark], bold: true },
            { label: 'epic', text: row?.epic ?? '' },
            view?.context && { label: 'context', text: view.context },
            view && view.criteria > 0 && { label: 'criteria', text: `${view.criteria} acceptance criteria` },
            row?.started && { label: 'started', text: moment(row.started) },
            row?.delivered && { label: 'delivered', text: moment(row.delivered), color: C.done },
            view?.accepted_by && { label: 'accepted', text: view.accepted_by, color: C.done },
            row && row.seconds > 0 && { label: 'worked', text: fmt.time(row.seconds) },
            row && row.tokens > 0 && { label: 'tokens', text: fmt.tokens(row.tokens) },
            row && row.cost > 0 && { label: 'cost', text: fmt.cost(row.cost) },
          ],
          2,
        ),
        ui.actions([
          ui.button('back', '← back', () => void update($, detail, () => null), { hotkey: 'b' }),
          row && !row.done && !isRunning() && ui.button('run', '▶ Run (worker)', () => void runWorker($, `run ${open.id}`, ['run', '--story', open.id]), { hotkey: 'r', isPrimary: true }),
          row && !row.done && ui.button('session', 'run in this session', () => send($, `/factory-run ${open.id}`), { hotkey: 'e', byClaude: true }),
          waits && ui.button('answer', 'answer', () => send($, `/factory-decisions ${open.id}`), { hotkey: 'a', isPrimary: true, byClaude: true }),
          row?.done && ui.button('verify', 'verify', () => send($, `/factory-verify ${open.id}`), { hotkey: 'v', byClaude: true }),
        ]),
        ui.section('Pipeline'),
        ui.chips(stagesOf(events), at),
        ui.section('Time per stage', "the factory's own numbers"),
        ui.table(
          [COL.stage, { name: 'share', width: 20 }, COL.time, COL.runs, COL.tokens, COL.cost, { name: 'model', width: 18 }],
          perStage.map(([name, one]) => [
            { text: name, bold: true },
            { text: bar(one.seconds, longest, 20), color: C.accent },
            { text: fmt.time(one.seconds) },
            { text: String(one.runs), color: one.runs > 1 ? C.wait : C.muted },
            { text: fmt.tokens(one.tokens) },
            { text: fmt.cost(one.cost) },
            { text: one.models.join(', ') || '—', color: C.muted },
          ]),
          'Not run yet.',
        ),
        ui.section('Passes'),
        ui.table(
          [{ name: '#', width: 2, isNumber: true }, { name: 'pass', width: 16 }, COL.started, COL.time, { name: 'waited', width: 10, isNumber: true }, COL.tokens, { name: 'stages', width: 30 }],
          (view?.passes ?? []).map((pass, index) => [
            { text: String(index + 1), color: C.muted },
            { text: pass.label, color: index === 0 ? C.done : C.wait },
            { text: fmt.when(pass.start), color: C.muted },
            { text: fmt.time(pass.seconds) },
            { text: fmt.time(pass.waited), color: C.muted },
            { text: fmt.tokens(pass.tokens) },
            { text: pass.stages.join(' '), color: C.muted },
          ]),
          'No pass yet.',
        ),
        ui.section('History', 'UTC'),
        ui.table(
          [{ name: 'day', width: 10 }, { name: 'time', width: 9 }, { name: 'event', width: 8 }, COL.stage],
          shown.map((event, index) => {
            const isGate = event.kind === 'gate'
            const passed = event.fields.exit === '0'
            return [
              { text: index === 0 || day(shown[index - 1]?.at ?? '') !== day(event.at) ? day(event.at) : '', color: C.muted, bold: true },
              { text: clock(event.at), color: C.muted },
              {
                text: isGate ? (passed ? 'gate ✓' : 'gate ✗') : event.kind === 'stage-start' ? '▶ start' : '■ end',
                color: isGate ? (passed ? C.done : C.fail) : event.kind === 'stage-start' ? C.accent : C.muted,
              },
              { text: event.stage },
            ]
          }),
        ),
        ui.section('Hand-over'),
        ui.table(
          [{ name: 'file', width: 20 }],
          (now.handovers[open.id] ?? []).map(file => [
            { node: ui.link(`file-${file}`, file, () => void openFile($, `${now.root}/.dca-factory/runs/${open.id}/${file}`, `${open.id} / ${file}`, open)) },
          ]),
          'No hand-over yet.',
        ),
        ui.section('Decisions'),
        recordTable(records, open),
      ],
      `b back${row && !row.done ? ' · r run · e in session' : ''}${waits ? ' · a answer' : ''}`,
    )
  }

  // ---- the foundation and the five steps of the cycle
  const story = (row: Row): Cell[] => [
    storyCell(row),
    { text: row.state, color: MARK_COLOR[row.mark] },
    { text: row.stage, color: C.muted },
    { text: row.passes > 0 ? String(row.passes) : '—', color: row.passes > 1 ? C.wait : C.muted },
    { text: fmt.when(row.started), color: C.muted },
    { text: fmt.time(row.seconds) },
    { text: fmt.tokens(row.tokens) },
    { text: fmt.cost(row.cost) },
  ]
  const storyColumns = [COL.story(idWidth), COL.state, COL.stage, COL.passes, COL.started, COL.worked, COL.tokens, COL.cost]

  if (current === 'describe') {
    return page(
      [
        ui.section('Project description', 'the foundation — written once, changed when the product or the technical situation moves'),
        ui.table(
          [COL.mark, { name: 'file', width: 12 }, { name: 'sections', width: 44 }, { name: 'open', width: 30 }, COL.action(7)],
          (status.description ?? []).map(part => {
            const path = `${now.root}/${part.path}`
            const name = part.path.split('/').pop() ?? part.part
            const gaps = [...part.missing.map(h => `missing ${h}`), ...part.empty.map(h => `empty ${h}`)]
            return [
              { text: !part.present ? '✗' : gaps.length > 0 ? '!' : '✓', color: !part.present ? C.fail : gaps.length > 0 ? C.wait : C.done, bold: true },
              part.present ? { node: ui.link(`doc-${part.part}`, name, () => void openFile($, path, name, null)) } : { text: name, color: C.fail },
              { text: part.present ? part.sections.join(' · ') : 'missing — Describe writes it', color: C.muted },
              { text: gaps.join(' · ') || '—', color: gaps.length > 0 ? C.wait : C.muted },
              part.present ? { node: ui.link(`edit-${part.part}`, '✎ edit', () => void editFile($, path)) } : {},
            ]
          }),
          'No description view — update the pipeline.',
        ),
        <Box marginTop={1} flexDirection="column">
          {ask('change', 'Change the description', 'what should change? e.g. "the shop also sells gift cards"', '/dca-describe')}
        </Box>,
        ui.actions([ui.button('describe', 'describe / complete the project', () => send($, '/dca-describe'), { isPrimary: true, byClaude: true })]),
      ],
      'Enter on a file opens it · ✎ edit opens it in your editor · type a change, Enter sends it',
    )
  }

  // One topic and one epic as they are drawn in their own detail view, opened from the tab's overview.
  type Epic = (typeof status.epics)[number]
  const topicBody = (topic: Topic) => (
    <Box flexDirection="column">
      {ui.card(
        {
          title: topic.title,
          meta: `${topic.proposals.length} proposed epic${topic.proposals.length === 1 ? '' : 's'} · ${topic.proposals.filter(p => p.epic).length} in the backlog`,
        },
        [ui.button(`report-${topic.topic}`, 'open report', () => void openFile($, `${now.root}/${topic.report}`, topic.title, open), { isPrimary: true })],
        [
          { label: 'topic', text: topic.topic },
          { label: 'report', text: topic.report, color: C.muted },
          topic.description_changes.length > 0 && { label: 'changes', text: `${topic.description_changes.length} to the description`, color: C.wait },
        ],
      )}
      {ui.table(
        [COL.mark, { name: 'proposal', width: 18 }, { name: 'outcome', width: 18 }, { name: 'goal', width: 36 }, COL.action(16)],
        topic.proposals.map(proposal => [
          { text: proposal.epic ? '✓' : '○', color: proposal.epic ? C.done : C.info, bold: true },
          { text: proposal.id, bold: true },
          { text: proposal.metric, color: C.info },
          { text: proposal.goal, color: C.muted },
          proposal.epic
            ? { node: ui.link(`epic-of-${proposal.id}`, `epic ${proposal.epic}`, () => void showDetail($, { kind: 'epic', epic: proposal.epic })) }
            : { node: ui.button(`release-${topic.topic}-${proposal.id}`, 'make epic', () => send($, `/factory-backlog epic ${proposal.id} --from ${topic.report}`), { isPrimary: true, byClaude: true }) },
        ]),
        'No proposed work in the report yet.',
      )}
      {topic.description_changes.length > 0 &&
        ui.table(
          [{ name: 'description', width: 24 }, { name: 'change', width: 46 }, COL.action(9)],
          topic.description_changes.map((change, index) => [
            { text: change.target, color: C.wait },
            { text: change.change, color: C.muted },
            { node: ui.button(`describe-${topic.topic}-${index}`, 'apply', () => send($, `/dca-describe ${change.target}: ${change.change}`), { byClaude: true }) },
          ]),
        )}
    </Box>
  )
  const epicBody = (epic: Epic) => {
    const drafts = epic.rows.filter(row => /draft/.test(row.state))
    return (
      <Box flexDirection="column">
        {ui.card(
          {
            title: epic.title || epic.epic,
            color: epic.total > 0 && epic.delivered === epic.total ? C.done : undefined,
            progress: { done: epic.delivered, total: epic.total },
            meta: `${epic.delivered} of ${epic.total} delivered${epic.tokens > 0 ? ` · ${fmt.tokens(epic.tokens)} tokens` : ''}`,
          },
          [
            ui.button(`stories-${epic.epic}`, 'suggest stories', () => send($, `/factory-backlog stories ${epic.epic}`), { isPrimary: epic.total === 0, byClaude: true }),
            drafts.length > 0 &&
              ui.button(
                `release-all-${epic.epic}`,
                `release ${drafts.length} draft${drafts.length === 1 ? '' : 's'}`,
                () => send($, `/factory-backlog release ${drafts.map(row => row.story).join(' ')}`),
                { byClaude: true },
              ),
          ],
          [
            epic.goal && { label: 'goal', text: epic.goal },
            epic.metric && { label: 'outcome', text: epic.metric, color: C.info },
            epic.discovery && { label: 'discovery', text: epic.discovery, color: C.muted },
          ],
        )}
        {ui.table(storyColumns, epic.rows.map(story), 'no stories yet — ✦ suggest stories: Claude drafts the first, you release them')}
      </Box>
    )
  }
  const journeys = () =>
    status.journeys.length > 0
      ? [
          ui.section('Journeys'),
          ui.table(
            [COL.mark, COL.epic, { name: 'journey', width: 56 }],
            status.journeys.map(hint => [{ text: '◇', color: C.wait }, { text: hint.epic }, { text: hint.text, color: C.wait }]),
          ),
        ]
      : []
  const back = ui.actions([ui.button('back', '← back', () => void update($, detail, () => null), { hotkey: 'b' })])

  // ---- one topic, one epic
  if (open?.kind === 'topic') {
    const topic = now.topics.find(one => one.topic === open.topic)
    return page([back, topic ? topicBody(topic) : <Text color={C.muted}>No such topic.</Text>], 'b back · ✦ make epic: Claude writes the proposal as an epic')
  }
  if (open?.kind === 'epic') {
    const epic = status.epics.find(one => one.epic === open.epic)
    return page([back, epic ? epicBody(epic) : <Text color={C.muted}>No such epic.</Text>], 'b back · ✦ suggest stories: Claude drafts them, you release them · Enter on a story opens it')
  }

  if (current === 'discover') {
    return page(
      [
        ui.section('Discovery', 'which problem is worth solving, and how anyone will know it got better'),
        ui.table(
              [COL.mark, { name: 'topic', width: 20 }, { name: 'title', width: 40 }, { name: 'proposed', width: 8, isNumber: true }, { name: 'in backlog', width: 10, isNumber: true }, { name: 'changes', width: 7, isNumber: true }],
              now.topics.map(topic => {
                const held = topic.proposals.filter(p => p.epic).length
                return [
                  { text: held === topic.proposals.length && held > 0 ? '✓' : '◆', color: held === topic.proposals.length && held > 0 ? C.done : C.info, bold: true },
                  { node: ui.link(`topic-${topic.topic}`, topic.topic, () => void showDetail($, { kind: 'topic', topic: topic.topic })) },
                  { text: topic.title, color: C.muted },
                  { text: String(topic.proposals.length) },
                  { text: String(held), color: held > 0 ? C.done : C.muted },
                  { text: topic.description_changes.length > 0 ? String(topic.description_changes.length) : '—', color: topic.description_changes.length > 0 ? C.wait : C.muted },
                ]
              }),
              'No discovery yet.',
            ),
        <Box marginTop={1} flexDirection="column">
          {ask('discover', 'New topic', 'a problem or a wished deliverable', '/factory-discover')}
        </Box>,
      ],
      'Enter on a topic opens it · type a topic, Enter sends it',
    )
  }

  if (current === 'backlog') {
    return page(
      [
        <Box flexDirection="column" gap={1}>
          {ask('story', 'Write a story', 'what should the product do next?', '/factory-backlog')}
          {ask('wish', 'Wish', 'a wish in your words — it becomes a story and runs', '/factory-run')}
        </Box>,
        ui.table(
              [COL.mark, { name: 'epic', width: 26 }, { name: 'progress', width: 10 }, { name: 'delivered', width: 9, isNumber: true }, { name: 'drafts', width: 6, isNumber: true }, { name: 'outcome', width: 30 }],
              status.epics.map(epic => {
                const isDone = epic.total > 0 && epic.delivered === epic.total
                const drafts = epic.rows.filter(row => /draft/.test(row.state)).length
                return [
                  { text: isDone ? '✓' : epic.total === 0 ? '○' : '·', color: isDone ? C.done : epic.total === 0 ? C.wait : C.muted, bold: true },
                  { node: ui.link(`epic-${epic.epic}`, epic.title || epic.epic, () => void showDetail($, { kind: 'epic', epic: epic.epic })) },
                  { text: '█'.repeat(epic.total > 0 ? Math.round((epic.delivered / epic.total) * 10) : 0).padEnd(10, '░'), color: C.done },
                  { text: `${epic.delivered} of ${epic.total}`, color: C.muted },
                  { text: drafts > 0 ? String(drafts) : '—', color: drafts > 0 ? C.wait : C.muted },
                  { text: epic.metric || '—', color: C.info },
                ]
              }),
              'The backlog is empty.',
            ),
        ...journeys(),
      ],
      'Enter on an epic opens it',
    )
  }

  if (current === 'run') {
    const log = job.lines.slice(-Math.max(6, rows - 30))
    return page(
      [
        ui.section('Worker', 'factory.sh run in the background — one stage per process, a gate between them'),
        ui.actions([
          !isRunning() && ui.button('run-all', '▶ Run the backlog', () => void runWorker($, 'run the backlog', ['run']), { hotkey: 'r', isPrimary: true }),
          !isRunning() && ui.button('run-watch', '◉ Run & keep watching', () => void runWorker($, 'run and watch', ['run', '--watch']), { hotkey: 'w' }),
          isRunning() && ui.button('stop', '■ Stop', () => void stopWorker($), { hotkey: 'x', isPrimary: true }),
        ]),
        ui.facts([
          {
            text:
              job.state === 'running'
                ? `▶ ${job.label} · ${fmt.time((at - job.startedAt) / 1000)}`
                : job.state === 'ended'
                  ? `■ ${job.label} — ${EXIT_WORDS[job.code ?? -1] ?? `ended (${job.code ?? 'signal'})`}`
                  : 'no worker started from here',
            color: job.state === 'running' ? C.accent : job.code === 0 ? C.done : job.state === 'ended' ? C.wait : C.muted,
          },
          ...status.extra.map(text => ({ text })),
        ]),
        ui.section('Running'),
        ui.table(
          [COL.story(idWidth), COL.stage, { name: 'since', width: 14 }, { name: 'activity', width: 40 }],
          status.running.map(running => [
            { node: ui.link(`running-${running.story}`, running.story, () => void openStory($, running.story)) },
            { text: running.stage, color: running.interrupted ? C.fail : C.accent, bold: true },
            { text: running.interrupted ? 'interrupted' : running.ago ?? fmt.when(running.since), color: running.interrupted ? C.fail : C.muted },
            { text: running.activity ?? '—', color: C.muted },
          ]),
          'No stage is running.',
        ),
        ...status.running.map(running => ui.chips(stagesOf(now.journals[running.story] ?? []), at, running.story)),
        ui.section('Output', job.lines.length > 0 ? `last ${log.length} lines` : undefined),
        ui.framed(
          log.length === 0
            ? [<Text color={C.muted}>Nothing yet. A worker started here writes its output into this box.</Text>]
            : log.map(text => (
                <Text wrap="truncate" color={/refus|fail|error|✗/i.test(text) ? C.fail : /✓|pass|delivered/i.test(text) ? C.done : undefined}>
                  {text || ' '}
                </Text>
              )),
        ),
        <Text color={C.muted}>The worker is a child of this session: ending the session or reloading the mod stops it.</Text>,
      ],
      isRunning() ? 'x stop' : 'r run the backlog · w run & watch',
    )
  }

  if (current === 'decide') {
    const pending = now.decisions.filter(record => record.state === 'open' || record.state === 'draft')
    const answered = now.decisions.filter(record => !pending.includes(record)).slice(0, Math.max(3, rows - 26))
    return page(
      [
        ui.section('Waiting for you', 'questions a stage may not decide alone, results to look at'),
        ...(pending.length === 0 && status.waiting.length === 0 ? [<Text color={C.done}>Nothing waits for you.</Text>] : []),
        ...(pending.length > 0 ? [recordTable(pending, null)] : []),
        ...(status.waiting.length > 0
          ? [
              ui.table(
                [COL.mark, COL.story(idWidth), { name: 'what', width: 36 }, COL.action(20)],
                status.waiting.map(wait => [
                  { text: MARK_GLYPH[wait.mark] ?? '?', color: C.wait, bold: true },
                  { text: wait.story, bold: true },
                  { text: wait.what, color: C.muted },
                  { node: ui.button(`answer-${wait.story}`, 'answer', () => send($, `/factory-decisions ${wait.story}`), { isPrimary: true, byClaude: true }) },
                ]),
              ),
            ]
          : []),
        ui.section('Answered', `${now.decisions.length - pending.length} records`),
        recordTable(answered, null),
      ],
      'Enter on a record opens it',
    )
  }

  const delivered = status.rows.filter(row => row.done)
  return page(
    [
      ui.section('Delivered', `${delivered.length} stories · ${fmt.time(delivered.reduce((sum, row) => sum + row.seconds, 0))} worked`),
      ui.table(
        [COL.story(idWidth), COL.delivered, COL.worked, COL.tokens, COL.cost, COL.epic],
        delivered.map(row => [
          storyCell(row),
          { text: fmt.when(row.delivered), color: C.done },
          { text: fmt.time(row.seconds) },
          { text: fmt.tokens(row.tokens) },
          { text: fmt.cost(row.cost) },
          { text: row.epic, color: C.muted },
        ]),
        'Nothing delivered yet.',
      ),
      ui.section('Epics'),
      ui.table(
        [COL.mark, { name: 'epic', width: 26 }, { name: 'delivered', width: 9, isNumber: true }, { name: 'outcome', width: 30 }, { name: 'journey', width: 30 }],
        status.epics.map(epic => {
          const unguarded = status.journeys.find(hint => hint.epic === epic.epic)
          const isDone = epic.total > 0 && epic.delivered === epic.total
          return [
            { text: isDone ? '✓' : '·', color: isDone ? C.done : C.muted, bold: true },
            { text: epic.title || epic.epic, bold: true },
            { text: `${epic.delivered} of ${epic.total}`, color: C.muted },
            { text: epic.metric || '—', color: C.info },
            { text: unguarded ? `◇ ${unguarded.text}` : '—', color: unguarded ? C.wait : C.muted },
          ]
        }),
      ),
    ],
    'Enter on a story opens it',
  )
}
