import { expect, test } from 'claude-code/testing'

const ROOT = '/p'
const ROW = {
  story: 'add-book', title: 'Add a book', epic: 'books', mark: 'none', state: 'ready', stage: 'plan', passes: 1,
  started: '2026-09-23T17:24:53Z', delivered: '', seconds: 120, tokens: 1_500_000, cost: 1.25, priced: 1, done: false,
}
const STATUS = {
  project: 'books-app',
  waiting: [{ mark: 'question', story: 'add-book', what: 'plan asks a question', action: { text: '', skill: '', shell: '' } }],
  running: [],
  epics: [
    { epic: 'books', rows: [ROW], delivered: 0, total: 1, tokens: 1_500_000, seconds: 120, title: 'Keep track of books', goal: 'one list', metric: 'BookAdded', discovery: '' },
    { epic: 'reminders', rows: [], delivered: 0, total: 0, tokens: 0, seconds: 0, title: 'Remind the reader', goal: '', metric: 'ReminderSent', discovery: 'project/discovery/forgetting/discovery.md' },
  ],
  description: [
    { part: 'product', path: 'project/product.md', present: true, missing: ['How it works'], empty: [], sections: ['What and for whom', 'For whom'], required: [] },
    { part: 'tech', path: 'project/tech.md', present: false, missing: [], empty: [], sections: [], required: [] },
    { part: 'domain', path: 'project/domain.md', present: false, missing: [], empty: [], sections: [], required: [] },
  ],
  rows: [ROW],
  next: { text: 'Nothing else starts until add-book has its answer.', action: { text: '', skill: '', shell: '' } },
  journeys: [],
  extra: [],
  delivered: 0,
  total: 1,
  tokens: 1_500_000,
  seconds: 120,
}
const DISCOVERY = {
  topics: [{
    topic: 'forgetting', report: 'project/discovery/forgetting/discovery.md', title: 'Readers forget what they meant to read',
    proposals: [
      { id: 'reminders', intent: 'remind', goal: 'fewer forgotten books', metric: 'ReminderSent', domain_contact: 'open', epic: 'reminders' },
      { id: 'reading-goals', intent: 'goals', goal: 'a yearly goal', metric: 'GoalSet', domain_contact: 'open', epic: '' },
    ],
    description_changes: [{ target: 'product.md — For whom', change: 'also readers on paper', why: '' }],
  }],
}
const DECISIONS = {
  records: [{ id: 'add-book-01', state: 'open', kind: 'question', story: 'add-book', stage: 'plan', asked: '2026-09-23T17:27:00Z', text: 'Which list?', path: 'project/epics/books/add-book.decisions/01.md' }],
}
const STORY = {
  story: 'add-book', context: 'reading', criteria: 3, accepted_by: '',
  passes: [{ label: 'first delivery', start: '2026-09-23T17:24:53Z', end: '2026-09-23T17:27:00Z', seconds: 120, tokens: 1_500_000, stages: ['plan'], waited: 0 }],
  stages: { plan: { runs: 1, seconds: 120, tokens: 1_500_000, cost: 1.25, models: ['claude-opus-5-5'] } },
}
const FILES: Record<string, string> = {
  [`${ROOT}/project/product.md`]: '# Product\n\n## What\n\n## For whom\n',
  [`${ROOT}/project/epics/books/epic.md`]: '---\ntitle: Keep track of books\ngoal: one list\nmetric: BookAdded\n---\n',
  [`${ROOT}/project/epics/reminders/epic.md`]: '---\nid: reminders\ntitle: Remind the reader\ndiscovery: project/discovery/forgetting/discovery.md\n---\n',
  [`${ROOT}/project/discovery/forgetting/discovery.md`]: [
    '# Readers forget what they meant to read',
    '',
    '## Proposed work',
    '',
    '### reminders',
    '- intent: remind',
    '- goal: fewer forgotten books',
    '- metric: ReminderSent',
    '',
    '### reading-goals',
    '- intent: goals',
    '- goal: a yearly goal',
    '- metric: GoalSet',
    '- domain_contact: open',
    '',
    '## Sources',
  ].join('\n'),
  [`${ROOT}/.dca-factory/runs/add-book/.verify/journal.tsv`]: [
    '2026-09-23T17:24:53Z\tstage-start\tplan\ttool=claude',
    '2026-09-23T17:26:53Z\tstage-end\tplan\texit=0',
    '2026-09-23T17:27:00Z\tgate\tplan\texit=1',
  ].join('\n'),
}
const DIRS: Record<string, { name: string; kind: 'file' | 'dir' }[]> = {
  [`${ROOT}/project/epics`]: [{ name: 'books', kind: 'dir' }, { name: 'reminders', kind: 'dir' }],
  [`${ROOT}/project/discovery`]: [{ name: 'forgetting', kind: 'dir' }],
  [`${ROOT}/.dca-factory/runs/add-book`]: [{ name: 'plan.md', kind: 'file' }],
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`the cockpit walks the tabs, opens a story, sends commands and runs the worker (${surface})`, async ($, on) => {
    const sent: string[] = []
    const spawned: string[][] = []
    on('session.root', async () => ({ value: ROOT }))
    on('fs.exists', async () => ({ value: true }))
    on('fs.list', async (_, e) => ({ value: (DIRS[e.path] ?? []).map(entry => ({ ...entry, size: 0, mtimeMs: 0, isLink: false })) }))
    on('fs.read', async (_, e) => (FILES[e.path] === undefined ? { deny: 'missing' } : { value: FILES[e.path] as string }))
    on('process.run', async (_: unknown, e: { argv: readonly string[] }) => {
      const out = e.argv.includes('--story') ? STORY : e.argv.includes('decisions') ? DECISIONS : e.argv.includes('--list') ? DISCOVERY : STATUS
      return { value: { exitCode: 0, stdout: JSON.stringify(out), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    })
    on('process.spawn', async function* (_: unknown, e: { argv: readonly string[] }) {
      spawned.push([...e.argv.slice(2)])
      yield { stream: 'stdout' as const, text: 'factory: add-book — plan\n' }
      return { value: { code: 3, signal: null } }
    } as never)
    on('clock.now', async () => ({ value: Date.parse('2026-09-23T17:30:00Z') }))
    on('clock.every', async () => ({ value: { cancel: () => {} } }) as never)
    const closed: string[] = []
    on('ui.open', async () => ({ value: { isPlaced: true } }) as never)
    on('ui.close', async (_: unknown, e: { id: string }) => {
      closed.push(e.id)
      return { value: undefined } as never
    })
    on('ui.status', async () => ({ value: undefined }) as never)
    on('ui.toast', async () => ({ value: undefined }) as never)
    on('command.list', async () => ({ value: [{ name: 'dca-core:dca-describe' }, { name: 'dca-factory:factory-decisions' }, { name: 'dca-factory:factory-backlog' }, { name: 'factory-run' }] }) as never)
    on('command.run', async (_: unknown, e: { command: string; args: string }) => {
      sent.push(`/${e.command}${e.args ? ` ${e.args}` : ''}`)
      return { text: '' } as never
    })
    on('prompt.fill', async () => ({ isFilled: true }) as never)

    await $.command.run({ command: 'factory-view', args: '' } as never)
    const pane = await $.ui.mount({ plugin: 'dca-factory-view', surface, component: 'Pane', requestId: 'factory-view', props: { title: 'Factory', isFocused: true } as never })

    // the head: project, waiting banner, next; the backlog tab is the start
    expect(await pane.find({ text: /books-app/ })).toBeDefined()
    expect(await pane.find({ text: /add-book — plan asks a question/ })).toBeDefined()
    expect(await pane.find({ text: /Keep track of books/ })).toBeDefined()
    expect(await pane.find({ text: 'BookAdded' })).toBeDefined()

    // backlog: an epic from a discovery without stories, and the button that cuts them
    expect(await pane.find({ text: /Remind the reader/ })).toBeDefined()
    // two epics: an overview, and an epic opens on Enter with its card and its stories
    await pane.press({ key: 'epic-reminders' })
    expect(await pane.find({ text: /no stories yet/ })).toBeDefined()
    await pane.press({ key: 'stories-reminders' })
    expect(sent.at(-1)).toBe('/dca-factory:factory-backlog stories reminders')

    // discover: the report's proposals, one already an epic, one released by a press
    await pane.press({ key: 'tab-discover' })
    // the topics as an overview; Enter opens one with its card, its proposals and its description changes
    expect(await pane.find({ text: /Readers forget/ })).toBeDefined()
    await pane.press({ key: 'topic-forgetting' })
    expect(await pane.find({ text: 'epic reminders' })).toBeDefined()
    expect(await pane.find({ text: 'GoalSet' })).toBeDefined()
    await pane.press({ key: 'release-forgetting-reading-goals' })
    expect(sent.at(-1)).toBe('/dca-factory:factory-backlog epic reading-goals --from project/discovery/forgetting/discovery.md')
    await pane.press({ key: 'describe-forgetting-0' })
    expect(sent.at(-1)).toBe('/dca-core:dca-describe product.md — For whom: also readers on paper')
    sent.length = 0

    // describe: the description files with their sections
    await pane.press({ key: 'tab-describe' })
    expect(await pane.find({ text: /What and for whom · For whom/ })).toBeDefined()
    expect(await pane.find({ text: /missing How it works/ })).toBeDefined()
    expect(await pane.find({ text: /missing — Describe writes it/ })).toBeDefined()
    await pane.press({ key: 'describe' })
    expect(sent).toEqual(['/dca-core:dca-describe'])

    // decide: the open record and the answer button
    await pane.press({ key: 'tab-decide' })
    expect(await pane.find({ text: /Which list\?/ })).toBeDefined()
    await pane.press({ key: 'answer-add-book' })
    expect(sent.at(-1)).toBe('/dca-factory:factory-decisions add-book')

    // a story: pipeline and history from the journal
    await pane.press({ key: 'tab-backlog' })
    await pane.press({ key: 'epic-books' })
    expect(await pane.find({ text: '1.5 M' })).toBeDefined()
    await pane.press({ key: 'story-add-book' })
    expect(await pane.find({ text: /plan ✗ · 2 min/ })).toBeDefined()
    expect(await pane.find({ text: 'gate ✗' })).toBeDefined()
    expect(await pane.find({ text: /3 acceptance criteria/ })).toBeDefined()
    expect(await pane.find({ text: /first delivery/ })).toBeDefined()
    expect(await pane.find({ text: /claude-opus-5-5/ })).toBeDefined()

    // the worker: started by the press, its output and its exit code in the run tab
    await pane.press({ key: 'run' })
    expect(spawned).toEqual([['run', '--story', 'add-book']])
    expect(await pane.find({ text: /factory: add-book — plan/ })).toBeDefined()
    expect(await pane.find({ text: /stopped for a decision/ })).toBeDefined()

    // the close button closes the pane
    await pane.press({ key: 'close' })
    expect(closed).toEqual(['factory-view'])
  })
}
