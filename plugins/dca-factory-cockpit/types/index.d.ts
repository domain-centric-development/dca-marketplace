
// What to do, every way: `skill` in a session, `shell` in a terminal; since dca-factory 0.93.0 also the word on its button
// (`label`), whether it is the one to press (`primary`) and the request a page writes for it
export type Action = {
  text: string
  skill: string
  shell: string
  label?: string
  primary?: boolean
  request?: { kind: string; fields: Record<string, string>; words: string; open: '' | 'words' | 'record'; choices?: string[] }
  // the id of a request that does it already — queued, running or waiting; '' where none does
  queued?: string
  // another choice of the same record is pending (that request's id): a view leaves this one out
  waits_on?: string
  // where that request is, in a word: queued, running, asks you
  queued_text?: string
}

// One story's signals as its gates recorded them in the journal (dca-factory 0.89.0): a fact no gate recorded is null —
// "not recorded", never 0; `rules` is null for a story built before the rule check (0.88.0) — "not measured".
export type Signals = {
  asked: number
  answered: number
  assumptions_open: number
  assumptions_answered: number
  plan_open: number | null
  rules: Record<string, number> | null
  findings: Record<string, number> | null
  domain: Record<string, number> | null
  corrections: Record<string, number>
}

// The signals of several stories summed by the factory (dca-factory 0.89.0) — `line` is the figures in one line, as
// every view prints them; '' where nothing was measured or found.
export type SignalTotals = {
  stories: number
  measured: number
  not_measured: number
  named: number
  kill_rate: number | null
  guarded_rate: number | null
  domain: Record<string, number>
  corrections: Record<string, number>
  line: string
}

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
  // the tests a gate of this story ran again alone and saw green — red in a whole suite, outside the story's change
  // (dca-factory 0.86.0; absent from an older pipeline)
  flaky?: string[]
  // when the story was written, `created:` in its front matter (dca-factory 0.87.0; '' without one)
  created?: string
  signals?: Signals
  // what a person can do with the story — release, answer, run now (dca-factory 0.93.0; absent from an older pipeline)
  actions?: Action[]
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
    // dca-factory 0.87.0: the epic's other fields, when it was written and its file — the epics come newest first
    intent?: string
    domain_contact?: string
    created?: string
    path?: string
    signals?: SignalTotals
    // the epic's next stories, its drafts released, its journey, and how many drafts it holds (dca-factory 0.93.0;
    // absent from an older pipeline)
    actions?: Action[]
    drafts?: number
  }[]
  description?: DescriptionPart[]
  // what comes next in the schedule's order, and how many cannot yet (dca-factory 0.87.0)
  queue?: { ready: string[]; blocked: number; drafts: number }
  // the delivered stories, the newest delivery first — the factory's order (dca-factory 0.87.0)
  delivered_order?: string[]
  rows: Row[]
  next: { text: string; action: Action }
  journeys: { epic: string; text: string; action: Action }[]
  // the judge's open minors and other factories' claims (dca-factory 0.79.3; absent from an older pipeline); `plain`, the
  // finding in one sentence a person understands at once, since 0.84.0 — '' for a row the judge wrote before it
  findings?: { story: string; row?: string; project?: boolean; plain?: string; where: string; severity: string; defect: string; perspective?: string; fix?: string; file: string; action: Action }[]
  // the review perspectives the profile asks for now, the built-ins first (dca-factory 0.84.2; absent from an older
  // pipeline, which then shows every reviewer a story ran)
  perspectives?: { name: string; carrier: string }[]
  claims?: {
    story: string
    kind: 'held' | 'orphan' | 'collision'
    who: string
    host: string
    age: string
    stale: boolean
    title: string
    action: Action
  }[]
  extra: string[]
  // who holds the checkout (`--live`, dca-factory 0.93.0): `how` is `up` (factory.sh up), `runner` or `session`
  worker?: { owner: string; since: string; beat: string; how: 'up' | 'runner' | 'session'; pid?: number | null; alive: boolean; log?: string; stopping: boolean } | null
  // what a person asked the factory to do from a page or a terminal, by state (dca-factory 0.93.0)
  requests?: { queued: number; running: number; waiting: number; failed: number }
  delivered: number
  total: number
  tokens: number
  seconds: number
  // the project's figures — kill rate, guarded rate, domain findings and corrections by code (dca-factory 0.89.0)
  signals?: SignalTotals
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
  // the record's `## Options` and the key its `## Recommendation` names, read by the factory's one option reader
  // (`decisions --format json`, dca-factory 0.82.1); absent from an older pipeline, which then offers no choices
  options?: { key: string; text: string }[]
  recommended?: string | null
  // an open record's answers — one per option, the person's words; at an acceptance, accept and correct
  // (dca-factory 0.93.0; absent from an older pipeline, which then offers no choices)
  actions?: Action[]
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
  // each with what a person can do with it — make the epic, apply the change (dca-factory 0.93.0)
  proposals: { id: string; intent: string; goal: string; metric: string; domain_contact: string; epic: string; actions?: Action[] }[]
  description_changes: { target: string; change: string; why: string; actions?: Action[] }[]
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
  // dca-factory 0.87.0: the story's file, its own words and its criteria as scenarios
  path?: string
  description?: string
  scenarios?: Scenario[]
  // dca-factory 0.87.2: every section in the factory's order, where the criteria stand among them, one line of what
  // is up, and the view the detail opens with
  sections?: Section[]
  criteria_at?: number | null
  superseded?: boolean
  situation?: string
  view?: 'story' | 'pipeline'
  context: string
  criteria: number
  accepted_by: string
  // dca-factory 0.89.0: what the gates recorded about the story — questions, assumptions, rules, findings
  signals?: Signals
  passes: { label: string; start: string; end: string; seconds: number; tokens: number; stages: string[]; waited: number }[]
  stages: Record<string, { runs: number; seconds: number; tokens: number; cost: number; models: string[]; parts?: StagePart[]; parts_incomplete?: boolean; denied?: number; denials?: Denial[] } & TokenClasses>
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

// One criterion as a person reads it: its title, the rule it serves, its steps — or the line form's text.
// One `## ` section of a story's or an epic's file as the factory gives it (dca-factory 0.87.2): its heading (empty
// for the prose before the first), its Markdown, and a kind where the factory puts it first (`superseded`).
export type Section = { heading: string; text: string; kind: string }

export type Scenario = { key: string; title: string; rule: string; happy: boolean; steps: { word: string; text: string }[]; text: string }

// What `factory.sh status --epic <id> --format json` prints (dca-factory 0.87.0): one epic with its fields, its own
// text and its stories, newest first.
export type EpicView = {
  epic: string
  title: string
  path: string
  created: string
  intent: string
  goal: string
  metric: string
  domain_contact: string
  discovery: string
  description: string
  // dca-factory 0.87.2: the sections, where the stories stand among them, what is up
  sections?: Section[]
  stories_at?: number | null
  situation?: string
  rows: Row[]
  delivered: number
  total: number
  tokens: number
}

// What `factory.sh spec-delta <story> --format json` prints: what holds before and after a story (dca-factory 0.81.0).
export type SpecDelta = {
  story: string
  context: string
  feature: string
  features: string[]
  rows: { key: string; verb: string; before_feature: string | null; after_feature: string | null; before: string[]; after: string[]; reason: string }[]
}

export type StageOutput = { story: string; stage: string; running: boolean; lines: string[] }

export type Tab = 'describe' | 'discover' | 'backlog' | 'run' | 'decide' | 'delivered'

// `back`: where the view returns to — a topic that opened an epic, a story that opened a hand-over.
export type Detail =
  | { kind: 'story'; id: string; pane?: 'story' | 'pipeline' }
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

// One status as `/factory-cockpit status` printed it: what the transcript's row draws, as it stood then.
export type Glance = Pick<FactoryStatus, 'project' | 'running' | 'waiting' | 'next' | 'queue' | 'delivered' | 'total' | 'tokens' | 'signals'> & { at: string }

declare module 'claude-code' {
  interface PluginState {
    'dca-factory-cockpit': {
      cockpit: Cockpit | null
      story: StoryView | null
      epicView: EpicView | null
      tab: Tab
      detail: Detail | null
      fileText: string
      outputLines: string[]
      specDelta: SpecDelta | null
      worker: Worker
      // the note last attached to a prompt; the next is attached only when it differs
      told: string
      // the statuses `/factory-cockpit status` printed into the transcript, by the moment they were read
      glances: Record<string, Glance>
    }
  }
}

// One stage inside a shared builder or verifier: its time and tokens read from the process's stream, its output and
// cost an estimate (the process reports them once) — `factory.sh status --story` shows them as `≈`
export type StagePart = { stage: string; runs: number; seconds: number; tokens: number; cost: number | null; denied?: number } & TokenClasses

// The four classes the tool reports a session's tokens in — a cache read costs a tenth of an input token, a cache
// write a quarter more, an output five times; the sum alone hides which one a stage spends
export type TokenClasses = { input?: number; output?: number; cache_write?: number; cache_read?: number }

// A call the tool refused because nobody could grant it in a headless stage — each a turn spent on another way
export type Denial = { stage: string; tool: string; command: string }
