
export type Action = { text: string; skill: string; shell: string }

// What `factory.sh status --format json --live` prints — the fields the cockpit reads.
export type Row = {
  story: string
  title: string
  epic: string
  mark: string
  state: string
  stage: string
  passes: number
  started: string
  delivered: string
  seconds: number
  tokens: number
  cost: number
  priced: number
  done: boolean
}

export type FactoryStatus = {
  project: string
  waiting: { mark: string; story: string; what: string; action: Action }[]
  running: { story: string; stage: string; since: string | null; interrupted: boolean; ago?: string; activity?: string; part?: string }[]
  epics: {
    epic: string
    rows: Row[]
    delivered: number
    total: number
    tokens: number
    seconds: number
    title?: string
    goal?: string
    metric?: string
    discovery?: string
  }[]
  description?: DescriptionPart[]
  rows: Row[]
  next: { text: string; action: Action }
  journeys: { epic: string; text: string; action: Action }[]
  extra: string[]
  delivered: number
  total: number
  tokens: number
  seconds: number
}

// What `factory.sh decisions --format json` prints.
export type DecisionRecord = {
  id: string
  state: string
  kind: string
  story: string
  stage: string
  asked: string
  text: string
  path: string
}

// One part of the project description as `status` reports it.
export type DescriptionPart = {
  part: string
  path: string
  present: boolean
  missing: string[]
  empty: string[]
  sections: string[]
  required: string[]
}

// What `factory.sh discover --list --format json` prints for one topic.
export type Topic = {
  topic: string
  report: string
  title: string
  proposals: { id: string; intent: string; goal: string; metric: string; domain_contact: string; epic: string }[]
  description_changes: { target: string; change: string; why: string }[]
}

export type JournalEvent = { at: string; kind: string; stage: string; fields: Record<string, string> }

export type StageRun = {
  stage: string
  rounds: number
  gates: boolean[]
  seconds: number
  cost: number
  tokens: number
  runningSince: string | null
}

// What `factory.sh status --story <id> --format json --live` prints — the factory's own numbers for one story.
export type StoryView = {
  story: string
  context: string
  criteria: number
  accepted_by: string
  passes: { label: string; start: string; end: string; seconds: number; tokens: number; stages: string[]; waited: number }[]
  stages: Record<string, { runs: number; seconds: number; tokens: number; cost: number; models: string[]; parts?: StagePart[] }>
}

export type Cockpit = {
  root: string
  project: string
  status: FactoryStatus
  decisions: DecisionRecord[]
  topics: Topic[]
  // the project's pipeline is older than the views the cockpit reads (no `description`, no `discover --list`)
  isBehind: boolean
  journals: Record<string, JournalEvent[]>
  handovers: Record<string, string[]>
  // the processes that ran for a story — builder, review-ddd, verifier, … — in the order they began
  outputs: Record<string, string[]>
  // what the newest stage does, from `factory.sh follow --once` — whoever started it; null on an older pipeline
  stage: StageOutput | null
  updatedAt: number
}

export type StageOutput = { story: string; stage: string; running: boolean; lines: string[] }

export type Tab = 'describe' | 'discover' | 'backlog' | 'run' | 'decide' | 'delivered'

// `back`: where the view returns to — a topic that opened an epic, a story that opened a hand-over.
export type Detail =
  | { kind: 'story'; id: string }
  | { kind: 'epic'; epic: string; back?: Detail | null }
  | { kind: 'topic'; topic: string; back?: Detail | null }
  | { kind: 'file'; path: string; title: string; back: Detail | null }
  | { kind: 'output'; story: string; process: string; back: Detail | null }

export type Worker = {
  state: 'idle' | 'running' | 'ended'
  label: string
  startedAt: number
  code: number | null
  // the person stopped it from the cockpit; the exit code then says nothing
  isStopped: boolean
  lines: string[]
}

declare module 'claude-code' {
  interface PluginState {
    'dca-factory-cockpit': {
      cockpit: Cockpit | null
      story: StoryView | null
      tab: Tab
      detail: Detail | null
      fileText: string
      outputLines: string[]
      worker: Worker
    }
  }
}

// One stage inside a shared builder or verifier: its time and tokens read from the process's stream, its output and
// cost an estimate (the process reports them once) — `factory.sh status --story` shows them as `≈`
export type StagePart = { stage: string; runs: number; seconds: number; tokens: number; cost: number | null }
