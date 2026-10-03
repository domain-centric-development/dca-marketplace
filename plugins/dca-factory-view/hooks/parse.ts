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

  return (call.tool === 'Bash' && text.includes('factory')) || (call.tool === 'Skill' && /factory-|stage-/.test(text))
}

export function bar(part: number, whole: number, width: number): string {
  if (whole <= 0) return '░'.repeat(width)
  const filled = Math.round((Math.min(part, whole) / whole) * width)
  return '█'.repeat(filled) + '░'.repeat(width - filled)
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