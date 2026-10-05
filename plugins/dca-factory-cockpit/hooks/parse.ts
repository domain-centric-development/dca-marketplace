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

  for (const event of events) {
    if (event.kind === 'stage-start') {
      const stage = run(event.stage)
      stage.rounds += 1
      stage.runningSince = event.at
    } else if (event.kind === 'stage-end') {
      const stage = run(event.stage)
      if (stage.runningSince) {
        stage.seconds += Math.max(0, (Date.parse(event.at) - Date.parse(stage.runningSince)) / 1000)
      }
      stage.runningSince = null
    } else if (event.kind === 'gate') {
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
    (writes && /project\/|\.dca-factory\//.test(text))
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
