import type { JournalEvent, StageRun } from '../types'

// Pure readers of what factory.sh and the run folders already hold; the view decides nothing.

export function parseJournal(text: string): JournalEvent[] {
  return text
    .split('\n')
    .filter(line => line.trim().length > 0)
    .map(line => {
      const [at = '', kind = '', stage = '', ...rest] = line.split('\t')
      const fields: Record<string, string> = {}
      for (const pair of rest) {
        const eq = pair.indexOf('=')
        if (eq > 0) fields[pair.slice(0, eq)] = pair.slice(eq + 1)
      }

      return { at, kind, stage, fields }
    })
}

// Who ran a gate: the runner (also every line of a journal older than the `by` field), a stage checking
// its own work under a runner, or a session or a person by hand.
export function gateBy(event: JournalEvent): string {
  return event.fields.by ?? 'runner'
}

// A stage's own run of the gate is a self-check, not the verdict between two stages.
export function isSelfCheck(event: JournalEvent): boolean {
  return event.kind === 'gate' && gateBy(event) !== 'runner' && gateBy(event) !== 'session'
}

// Only the runner refuses a stage; a stage's failing self-check is its own business.
export function isRefusal(event: JournalEvent): boolean {
  return event.kind === 'gate' && event.fields.exit !== '0' && gateBy(event) === 'runner'
}

// The lines a story's history shows: stages starting and ending, and gates — not usage, written
// hand-overs or outdated marks.
export function isHistory(event: JournalEvent): boolean {
  return event.kind === 'stage-start' || event.kind === 'stage-end' || event.kind === 'gate'
}

// A story's process or stage as a view shows it: a reviewer — `review:<name>` in the journal and the figures,
// `review-<name>` as its output — only for a perspective the profile asks for now (`perspectives` in the status, dca-factory
// 0.84.2); a reviewer an earlier profile named stays out. Everything else, and every reviewer on an older pipeline, shows.
export function isShownProcess(name: string, perspectives?: { name: string }[]): boolean {
  if (!perspectives) return true
  const reviewer = /^review[:-](.+)$/.exec(name)?.[1]
  return reviewer === undefined || perspectives.some(perspective => perspective.name === reviewer)
}

// The stages in the order the journal first names them: plan…document, or builder/judge/document
// when the project runs a shared builder — whatever the runner wrote, nothing assumed.
export function stagesOf(events: JournalEvent[]): StageRun[] {
  const runs = new Map<string, StageRun>()
  const run = (stage: string): StageRun => {
    const found = runs.get(stage)
    if (found) return found
    const made: StageRun = { stage, rounds: 0, gates: [], seconds: 0, cost: 0, tokens: 0, runningSince: null }
    runs.set(stage, made)
    return made
  }

  // The runner's own steps (integrate, merge, format) run as chips too; a stage inside a step of its name
  // keeps one clock — the step's resumes when the stage ends.
  const steps = new Set<string>()
  const stop = (stage: StageRun, at: string) => {
    if (stage.runningSince) stage.seconds += Math.max(0, (Date.parse(at) - Date.parse(stage.runningSince)) / 1000)
    stage.runningSince = null
  }

  for (const event of events) {
    if (event.kind === 'stage-start') {
      const stage = run(event.stage)
      if (steps.has(event.stage)) stop(stage, event.at)
      stage.rounds += 1
      stage.runningSince = event.at
    } else if (event.kind === 'stage-end') {
      const stage = run(event.stage)
      stop(stage, event.at)
      if (steps.has(event.stage)) stage.runningSince = event.at
    } else if (event.kind === 'step-start') {
      const stage = run(event.stage)
      steps.add(event.stage)
      if (!stage.runningSince) stage.runningSince = event.at
    } else if (event.kind === 'step-end') {
      steps.delete(event.stage)
      stop(run(event.stage), event.at)
    } else if (event.kind === 'gate' && !isSelfCheck(event)) {
      run(event.stage).gates.push(event.fields.exit === '0')
    } else if (event.kind === 'usage') {
      const stage = run(event.stage)
      stage.cost += Number(event.fields.cost ?? 0) || 0
      stage.tokens += ['input', 'output', 'cache_read', 'cache_write'].reduce((sum, key) => sum + (Number(event.fields[key] ?? 0) || 0), 0)
    }
  }

  return [...runs.values()]
}

export function duration(seconds: number): string {
  const s = Math.round(seconds)
  if (s < 60) return `${s} s`
  const m = Math.floor(s / 60)
  if (m < 60) return s % 60 === 0 ? `${m} min` : `${m} min ${s % 60} s`
  return `${Math.floor(m / 60)} h ${m % 60} min`
}

// The journal writes UTC; the view says so instead of guessing the reader's zone, as factory.sh status does.
export function clock(at: string): string {
  return `${at.slice(11, 16)} UTC`
}

export function day(at: string): string {
  const [year, month, date] = at.slice(0, 10).split('-')
  return year && month && date ? `${date}.${month}.${year}` : ''
}

export function moment(at: string): string {
  return at.length >= 16 ? `${day(at)} ${clock(at)}` : ''
}

export function rounds(count: number): string {
  return count === 1 ? '1 round' : `${count} rounds`
}

// A tool call's arguments sit on the event itself (`command` for Bash, `skill` for Skill).
export function touchesFactory(call: { tool: string }): boolean {
  const text = JSON.stringify(call)
  const writes = ['Write', 'Edit', 'MultiEdit', 'NotebookEdit'].includes(call.tool)

  return (
    (call.tool === 'Bash' && text.includes('factory')) ||
    (call.tool === 'Skill' && /factory-|stage-|dca-describe/.test(text)) ||
    // what the skills write: the description, the backlog, the discovery reports, the run folders
    (writes && /product\/|project\/|\.dca-factory\//.test(text))
  )
}

// How many of `width` cells a part of a whole fills — the progress component draws them as a line.
export function filledCells(part: number, whole: number, width: number): number {
  return whole <= 0 ? 0 : Math.round((Math.min(part, whole) / whole) * width)
}

export function tokens(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)} M`
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)} k`
  return String(count)
}

// A short point in time for a table cell: day and month, then the time; the column header says UTC.
export function short(at: string): string {
  return at.length >= 16 ? `${at.slice(8, 10)}.${at.slice(5, 7)}. ${at.slice(11, 16)}` : '—'
}

// The worker's output arrives in pieces, not lines: keep the last `keep` whole lines. A piece without a line
// break would grow one line without end — a line is cut at `LINE_CAP` cells.
export const LINE_CAP = 2000
export function appendLines(lines: string[], text: string, keep: number): string[] {
  const joined = (lines.length > 0 ? lines.join('\n') : '') + text
  return joined
    .split('\n')
    .slice(-keep)
    .map(line => (line.length > LINE_CAP ? `${line.slice(0, LINE_CAP - 1)}…` : line))
}

// What `factory.sh run` says with its exit code (factory.sh's header); a stop from the cockpit has its own word.
export const EXIT_WORDS: Record<number, string> = {
  0: 'ran through',
  3: 'stopped for a decision — see Decide',
  4: 'stopped at --max-stages',
  5: 'another worker holds the checkout',
  6: 'refused: inside an agent session',
}
export function exitWord(code: number | null, isStopped = false): string {
  if (isStopped) return 'stopped from the cockpit'
  return EXIT_WORDS[code ?? -1] ?? `ended (${code ?? 'signal'})`
}

// A latch one holder takes synchronously — the guard against two presses starting two workers while the first
// is still between its awaits.
export function createLatch() {
  let isHeld = false
  return {
    take: (): boolean => {
      if (isHeld) return false
      isHeld = true
      return true
    },
    release: (): void => {
      isHeld = false
    },
    isHeld: (): boolean => isHeld,
  }
}

// A refresh asked for while one runs is kept, as one: it is quiet only when every request was, and live (the
// running stories alone) only when every request was — a full one asked for is a full one served.
export type RefreshWish = { isQuiet: boolean; isLive: boolean }
export function keepRefresh(pending: RefreshWish | null, isQuiet: boolean, isLive: boolean): RefreshWish {
  return pending ? { isQuiet: pending.isQuiet && isQuiet, isLive: pending.isLive && isLive } : { isQuiet, isLive }
}

// What of a story changes its journal and hand-overs: a new state, stage, pass or delivery. Rows with the same
// signature are not read again.
export function rowSignature(row: { state: string; stage: string; passes: number; done: boolean; delivered: string }): string {
  return `${row.state}|${row.stage}|${row.passes}|${row.done ? 1 : 0}|${row.delivered}`
}

// The cells a text takes in a terminal: East Asian wide and fullwidth forms, and emoji, take two; combining marks
// none. Enough for titles and goals in any script; the cockpit's own marks (✓ ▶ ◇ ━ ─) are one cell each.
export function charWidth(point: number): number {
  if (point === 0 || (point >= 0x300 && point <= 0x36f) || (point >= 0x200b && point <= 0x200f) || point === 0xfe0f) return 0
  if (
    (point >= 0x1100 && point <= 0x115f) ||
    (point >= 0x2e80 && point <= 0x303e) ||
    (point >= 0x3041 && point <= 0x33ff) ||
    (point >= 0x3400 && point <= 0x4dbf) ||
    (point >= 0x4e00 && point <= 0x9fff) ||
    (point >= 0xa000 && point <= 0xa4cf) ||
    (point >= 0xac00 && point <= 0xd7a3) ||
    (point >= 0xf900 && point <= 0xfaff) ||
    (point >= 0xfe30 && point <= 0xfe4f) ||
    (point >= 0xff00 && point <= 0xff60) ||
    (point >= 0xffe0 && point <= 0xffe6) ||
    (point >= 0x1f300 && point <= 0x1f64f) ||
    (point >= 0x1f900 && point <= 0x1f9ff) ||
    (point >= 0x20000 && point <= 0x3fffd)
  )
    return 2
  return 1
}

export function displayWidth(text: string): number {
  let width = 0
  for (const char of text) width += charWidth(char.codePointAt(0) ?? 0)
  return width
}

// The longest head of a text that fits `width` cells, an ellipsis where it was cut.
export function fit(text: string, width: number): string {
  if (displayWidth(text) <= width) return text
  let out = ''
  let used = 0
  for (const char of text) {
    const w = charWidth(char.codePointAt(0) ?? 0)
    if (used + w > width - 1) break
    out += char
    used += w
  }
  return `${out}…`
}

// The longest head of a text that fits `width` cells, and the rest.
function cutCells(text: string, width: number): [string, string] {
  let head = ''
  let used = 0
  let index = 0
  for (const char of text) {
    const w = charWidth(char.codePointAt(0) ?? 0)
    if (used + w > width) break
    head += char
    used += w
    index += char.length
  }
  return [head, text.slice(index)]
}

// Word-wraps a text to a width in cells, as a table cell shows it: whole words where they fit, a word longer
// than the width cut into pieces. The table draws each line itself, so it knows how tall a row is.
export function wrapWords(text: string, width: number): string[] {
  const lines: string[] = []
  let current = ''
  for (const word of text.split(/\s+/).filter(Boolean)) {
    let rest = word
    while (displayWidth(rest) > width) {
      if (current) {
        lines.push(current)
        current = ''
      }
      const [head, tail] = cutCells(rest, width)
      if (!head) break
      lines.push(head)
      rest = tail
    }
    if (!rest) continue
    if (!current) current = rest
    else if (displayWidth(current) + 1 + displayWidth(rest) <= width) current = `${current} ${rest}`
    else {
      lines.push(current)
      current = rest
    }
  }
  if (current) lines.push(current)
  return lines.length > 0 ? lines : ['']
}

// A foreign claim a person has to act on: a stale one, an orphan, an id collision — a fresh one held elsewhere is
// information only. (WP-104)
export function claimNeedsPerson(claim: { kind: string; stale: boolean }): boolean {
  return claim.kind !== 'held' || claim.stale
}

// What the Decide tab counts: the stories and records waiting, and the claims a person must act on. The judge's open
// minors are listed there too, but not counted — they wait for a later story, not for an answer now.
export function waitingCount(status: { waiting: unknown[]; claims?: { kind: string; stale: boolean }[] }): number {
  return status.waiting.length + (status.claims ?? []).filter(claimNeedsPerson).length
}

// The press a waiting row offers: its own skill where it names one, the story added where the factory names the skill
// alone (`/factory-decisions`), labelled as the factory labels it (dca-factory 0.93.0), else by what it does; none where
// the factory says what to do in words only — a story waiting for its merge, a claim to release in a terminal.
export function waitPress(story: string, action: { text: string; skill: string; label?: string }): { label: string; command: string } | null {
  if (!action.skill) return null
  const command = action.skill.trim().includes(' ') ? action.skill.trim() : `${action.skill.trim()} ${story}`
  const verb = command.split(' ')[0] ?? ''
  const label = action.label || ({ '/factory-decisions': 'answer', '/factory-status': 'look', '/factory-run': 'run', '/factory-backlog': 'release' }[verb] ?? 'open')
  return { label, command }
}

// ---- what the session is told and shown beside the cockpit

type Told = {
  running: { story: string; stage: string; part?: string }[]
  waiting: { story: string; what: string }[]
  next: { text: string }
}

// What the model reads beside a prompt: what runs, what waits for the person, what comes next — the factory's own words.
// The cockpit attaches it only when it differs from what it attached last, so an unchanged factory costs nothing.
export function factoryNote(status: Told): string {
  const running = status.running.map(run => `${run.story} · ${run.part ? `${run.stage} · ${run.part}` : run.stage}`)
  const waiting = status.waiting.map(wait => `${wait.story} — ${wait.what}`)
  return [
    "The project's dca-factory now (from the cockpit; said again only when it changes):",
    `- running: ${running.join('; ') || 'nothing'}`,
    `- waits for the person: ${waiting.join('; ') || 'nothing'}`,
    `- next: ${status.next.text}`,
  ].join('\n')
}

// What a session saw of the factory when it last looked: kept across sessions, per project.
export type Seen = { at: string; delivered: string[]; waiting: string[] }

const waitKey = (wait: { story: string; what: string }) => `${wait.story} — ${wait.what}`

export function seenOf(status: { rows: { story: string; done: boolean }[]; waiting: { story: string; what: string }[] }, at: string): Seen {
  return { at, delivered: status.rows.filter(row => row.done).map(row => row.story), waiting: status.waiting.map(waitKey) }
}

// What moved since a session last looked, in one line — null when nothing did.
export function sinceSeen(seen: Seen, status: { rows: { story: string; done: boolean }[]; waiting: { story: string; what: string }[] }): string | null {
  const delivered = status.rows.filter(row => row.done && !seen.delivered.includes(row.story)).map(row => row.story)
  const waiting = status.waiting.filter(wait => !seen.waiting.includes(waitKey(wait))).map(wait => wait.story)
  const parts = [
    delivered.length > 0 && `${delivered.length} delivered (${delivered.slice(0, 3).join(', ')}${delivered.length > 3 ? ', …' : ''})`,
    waiting.length > 0 && `${waiting.length} new for you (${waiting.slice(0, 3).join(', ')}${waiting.length > 3 ? ', …' : ''})`,
  ].filter(Boolean)
  return parts.length > 0 ? `factory since ${moment(seen.at)}: ${parts.join(' · ')}` : null
}

// The first line of a status the cockpit printed into the transcript names the moment it was read: its drawing is
// found by it.
export const GLANCE_HEAD = 'Factory status at '
export function glanceId(text: string): string | null {
  return text.startsWith(GLANCE_HEAD) ? (text.slice(GLANCE_HEAD.length).split(/\s/)[0] ?? null) : null
}

// The status `/factory-cockpit status` prints: what the model reads, and the transcript shows where nothing draws it.
export function glanceText(
  status: Told & { project: string; delivered: number; total: number; tokens: number; queue?: { ready: string[] }; signals?: { line: string } },
  at: string,
): string {
  const ready = status.queue?.ready ?? []
  return [
    `${GLANCE_HEAD}${at} — ${status.project}: ${status.delivered} of ${status.total} stories delivered${status.tokens > 0 ? ` · ${tokens(status.tokens)} tokens` : ''}`,
    ...factoryNote(status).split('\n').slice(1),
    ...(ready.length > 0 ? [`- ready: ${ready.slice(0, 5).join(', ')}${ready.length > 5 ? `, … ${ready.length - 5} more` : ''}`] : []),
    ...(status.signals?.line ? [`- signals: ${status.signals.line}`] : []),
  ].join('\n')
}

// One story's signals as the pane lists them — what the gates recorded; "not recorded" and "not measured" where a gate
// recorded nothing, never a zero that was not counted.
export function signalFields(signals: {
  asked: number
  answered: number
  assumptions_open: number
  assumptions_answered: number
  plan_open: number | null
  rules: Record<string, number> | null
  findings: Record<string, number> | null
  domain: Record<string, number> | null
  corrections: Record<string, number>
}): { label: string; text: string }[] {
  const counted = (map: Record<string, number>, strip = '') =>
    Object.entries(map)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([name, n]) => `${n} ${name.replace(strip, '')}`)
      .join(' · ')
  const rules = signals.rules
  const named = rules ? Object.values(rules).reduce((sum, n) => sum + n, 0) : 0
  return [
    { label: 'questions', text: `${signals.asked} asked, ${signals.answered} answered` },
    { label: 'assumptions', text: `${signals.assumptions_open} open, ${signals.assumptions_answered} answered` },
    { label: 'plan left open', text: signals.plan_open === null ? 'not recorded' : String(signals.plan_open) },
    { label: 'rules', text: rules === null ? 'not measured' : named === 0 ? 'none named' : `${named} named — ${counted(rules)}` },
    {
      label: 'findings',
      text:
        signals.findings === null
          ? 'not recorded'
          : Object.keys(signals.findings).length === 0
            ? 'none confirmed'
            : counted(signals.findings) + (signals.domain && Object.keys(signals.domain).length > 0 ? ` · domain ${counted(signals.domain, 'domain-')}` : ''),
    },
    { label: 'corrections', text: Object.keys(signals.corrections).length === 0 ? 'none' : counted(signals.corrections, 'domain-') },
  ]
}
