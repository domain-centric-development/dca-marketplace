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

// The worker's output arrives in pieces, not lines: keep the last `keep` whole lines.
export function appendLines(lines: string[], text: string, keep: number): string[] {
  const joined = (lines.length > 0 ? lines.join('\n') : '') + text
  return joined.split('\n').slice(-keep)
}
// Word-wraps a text to a width, as a table cell shows it: whole words where they fit, a word longer than the width
// cut into pieces. The table draws each line itself, so it knows how tall a row is.
export function wrapWords(text: string, width: number): string[] {
  const lines: string[] = []
  let current = ''
  for (const word of text.split(/\s+/).filter(Boolean)) {
    let rest = word
    while (rest.length > width) {
      if (current) {
        lines.push(current)
        current = ''
      }
      lines.push(rest.slice(0, width))
      rest = rest.slice(width)
    }
    if (!rest) continue
    if (!current) current = rest
    else if (current.length + 1 + rest.length <= width) current = `${current} ${rest}`
    else {
      lines.push(current)
      current = rest
    }
  }
  if (current) lines.push(current)
  return lines.length > 0 ? lines : ['']
}
