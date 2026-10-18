import { expect, test } from 'claude-code/testing'

const ROOT = '/p'
const ROW = {
  story: 'add-book', title: 'Add a book', epic: 'books', mark: 'none', state: 'ready', stage: 'plan', passes: 1,
  started: '2026-09-23T17:24:53Z', delivered: '', seconds: 120, tokens: 1_500_000, cost: 1.25, priced: 1, done: false,
}
const STATUS = {
  project: 'books-app',
  waiting: [
    { mark: 'question', story: 'add-book', what: 'plan asks a question', action: { text: '', skill: '/factory-decisions', shell: '' } },
    { mark: 'look', story: 'sort-books', what: 'published — waits for its merge', action: { text: 'open the merge request from its branch', skill: '', shell: '' } },
  ],
  findings: [
    { story: 'add-book', plain: 'the book is checked where nobody looks', where: 'src/Book.java:12', severity: 'minor', defect: 'a guard the plan did not name', perspective: 'ddd', fix: 'name the guard in the plan', file: 'product/epics/books/add-book/findings.md', action: { text: '', skill: '/factory-backlog add-book: the book is checked where nobody looks', shell: '' } },
    { story: 'add-book', where: 'src/Book.java:30', severity: 'minor', defect: 'a comment names the old term', file: 'product/epics/books/add-book/findings.md', action: { text: '', skill: '/factory-backlog add-book: a comment names the old term', shell: '' } },
  ],
  claims: [
    { story: 'lend-book', kind: 'held', who: 'anna@example.org', host: 'laptop-a', age: '6 d', stale: true, title: '', action: { text: 'not built here', skill: '', shell: 'bash .agents/factory/factory.sh release lend-book --force' } },
    { story: 'old-one', kind: 'orphan', who: 'ben@example.org', host: 'desk-b', age: '2 h', stale: false, title: '', action: { text: 'this checkout has no such story — take the claim away', skill: '', shell: 'bash .agents/factory/factory.sh release old-one --force' } },
  ],
  running: [],
  epics: [
    { epic: 'books', rows: [ROW], delivered: 0, total: 1, tokens: 1_500_000, seconds: 120, title: 'Keep track of books', goal: 'one list', metric: 'BookAdded', discovery: '' },
    { epic: 'reminders', rows: [], delivered: 0, total: 0, tokens: 0, seconds: 0, title: 'Remind the reader', goal: '', metric: 'ReminderSent', discovery: 'product/discovery/forgetting/discovery.md' },
  ],
  description: [
    { part: 'product', path: 'product/overview.md', present: true, missing: ['How it works'], empty: [], sections: ['What and for whom', 'For whom'], required: [] },
    { part: 'tech', path: 'product/tech.md', present: false, missing: [], empty: [], sections: [], required: [] },
    { part: 'domain', path: 'product/domain.md', present: false, missing: [], empty: [], sections: [], required: [] },
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
    topic: 'forgetting', report: 'product/discovery/forgetting/discovery.md', title: 'Readers forget what they meant to read',
    proposals: [
      { id: 'reminders', intent: 'remind', goal: 'fewer forgotten books', metric: 'ReminderSent', domain_contact: 'open', epic: 'reminders' },
      { id: 'reading-goals', intent: 'goals', goal: 'a yearly goal', metric: 'GoalSet', domain_contact: 'open', epic: '' },
    ],
    description_changes: [{ target: 'overview.md — For whom', change: 'also readers on paper', why: '' }],
  }],
}
const DECISIONS = {
  records: [
    { id: 'add-book-01', state: 'open', kind: 'question', story: 'add-book', stage: 'plan', asked: '2026-09-23T17:27:00Z', text: 'Which list?', path: 'product/epics/books/add-book/decisions/01.md',
      options: [{ key: 'a', text: 'the reading list' }, { key: 'b', text: 'the shelf, read or not' }], recommended: 'b' },
    { id: 'add-book-accept-1', state: 'open', kind: 'acceptance', story: 'add-book', stage: 'document', asked: '2026-09-23T18:00:00Z', text: 'Accept add-book?', path: 'product/epics/books/add-book/decisions/accept-1.md' },
  ],
}
const SPEC_DELTA = {
  story: 'add-book', context: 'reading', feature: 'shelf', features: ['shelf'],
  rows: [
    { key: 'adds-a-book', verb: 'adds', before_feature: null, after_feature: 'shelf', before: [], after: ['- adds-a-book: A new book stands on the shelf.'], reason: '' },
    { key: 'old-list', verb: 'removes', before_feature: '', after_feature: null, before: ['- old-list: The list shows it.'], after: [], reason: 'the shelf replaces the list' },
  ],
}
const STORY = {
  story: 'add-book', context: 'reading', criteria: 3, accepted_by: '',
  passes: [{ label: 'first delivery', start: '2026-09-23T17:24:53Z', end: '2026-09-23T17:27:00Z', seconds: 120, tokens: 1_500_000, stages: ['plan'], waited: 0 }],
  stages: { plan: { runs: 1, seconds: 120, tokens: 1_500_000, cost: 1.25, models: ['claude-opus-5-5'] } },
}
const FILES: Record<string, string> = {
  [`${ROOT}/product/epics/books/add-book/decisions/accept-1.md`]: '---\nid: add-book-accept-1\nkind: acceptance\n---\n\n# Accept add-book?\n',
  [`${ROOT}/product/epics/books/add-book/decisions/01.md`]: [
    '---', 'id: add-book-01', 'story: add-book', 'stage: plan', 'asked: 2026-09-23T17:27:00Z', '---', '',
    '# Which list?', '', '## Question', 'Which list takes a new book?', '',
    '## Options', '- a: the reading list', '- b: the shelf,', '  read or not', '',
    '## Recommendation', 'b — a book is owned before it is read', '',
  ].join('\n'),
  [`${ROOT}/product/overview.md`]: '# Product\n\n## What\n\n## For whom\n',
  [`${ROOT}/product/epics/books/epic.md`]: '---\ntitle: Keep track of books\ngoal: one list\nmetric: BookAdded\n---\n',
  [`${ROOT}/product/epics/reminders/epic.md`]: '---\nid: reminders\ntitle: Remind the reader\ndiscovery: product/discovery/forgetting/discovery.md\n---\n',
  [`${ROOT}/product/discovery/forgetting/discovery.md`]: [
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
  [`${ROOT}/.dca-factory/evidence/add-book/journal.tsv`]: [
    '2026-09-23T17:24:53Z\tstage-start\tplan\ttool=claude',
    '2026-09-23T17:26:53Z\tstage-end\tplan\texit=0',
    '2026-09-23T17:27:00Z\tgate\tplan\texit=1',
  ].join('\n'),
}
const DIRS: Record<string, { name: string; kind: 'file' | 'dir' }[]> = {
  [`${ROOT}/product/epics`]: [{ name: 'books', kind: 'dir' }, { name: 'reminders', kind: 'dir' }],
  [`${ROOT}/product/discovery`]: [{ name: 'forgetting', kind: 'dir' }],
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
      const out = e.argv.includes('spec-delta') ? SPEC_DELTA : e.argv.includes('--story') ? STORY : e.argv.includes('decisions') ? DECISIONS : e.argv.includes('--list') ? DISCOVERY : STATUS
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

    await $.command.run({ command: 'factory-cockpit', args: '' } as never)
    const pane = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface, component: 'Pane', requestId: 'factory-cockpit', props: { title: 'Factory', isFocused: true } as never })

    // the head: project, waiting banner, next; the backlog tab is the start
    expect(await pane.find({ text: /books-app/ })).toBeDefined()
    expect(await pane.find({ text: 'FACTORY COCKPIT' })).toBeDefined()
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
    // an epic opened from the topic returns to the topic, not to the overview
    await pane.press({ key: 'epic-of-reminders' })
    expect(await pane.find({ text: /no stories yet/ })).toBeDefined()
    await pane.press({ key: 'back' })
    expect(await pane.find({ text: 'epic reminders' })).toBeDefined()
    await pane.press({ key: 'release-forgetting-reading-goals' })
    expect(sent.at(-1)).toBe('/dca-factory:factory-backlog epic reading-goals --from product/discovery/forgetting/discovery.md')
    await pane.press({ key: 'describe-forgetting-0' })
    expect(sent.at(-1)).toBe('/dca-core:dca-describe overview.md — For whom: also readers on paper')
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
    // a story waiting for its merge says what to do and offers no answer; other factories' claims show their release
    // as a command, never a button; the judge's open minors open their file or go to the backlog
    expect(await pane.find({ text: /waits for its merge — open the merge/ })).toBeDefined()
    await expect(pane.press({ key: 'answer-sort-books' })).rejects.toThrow()
    expect(await pane.find({ text: /claimed by other factories/i })).toBeDefined()
    expect(await pane.find({ text: /6 d — stale\?/ })).toBeDefined()
    expect(await pane.find({ text: /release old-one --force/ })).toBeDefined()
    expect(await pane.find({ text: /open findings/i })).toBeDefined()
    // a story's findings stand under its name, given once; the name opens the findings file
    await expect(pane.press({ key: 'finding-file-1' })).rejects.toThrow()
    // the finding stands in front with what to do beside it, the file only by its name
    expect(await pane.find({ text: /→/ })).toBeDefined()
    expect(await pane.find({ text: /the guard/ })).toBeDefined()
    // the finding in plain words leads, the reviewer's defect beside it; a row without the sentence shows its defect
    expect(await pane.find({ text: /the book is/ })).toBeDefined()
    expect(await pane.find({ text: /guard/ })).toBeDefined()
    expect(await pane.find({ text: /a comment/ })).toBeDefined()
    expect(await pane.find({ text: 'Book.java:12' })).toBeDefined()
    await pane.press({ key: 'finding-story-0' })
    expect(sent.at(-1)).toBe('/dca-factory:factory-backlog add-book: the book is checked where nobody looks')
    // the open record offers its options as choices; a press hands the answer to the decisions skill
    await pane.press({ key: 'record-add-book-01' })
    expect(await pane.find({ text: /the stage recommends b/ })).toBeDefined()
    expect(await pane.find({ text: /the shelf, read or not/ })).toBeDefined()
    await pane.press({ key: 'option-add-book-01-b' })
    expect(sent.at(-1)).toBe('/dca-factory:factory-decisions add-book add-book-01: answer b')
    await pane.press({ key: 'back' })
    // an acceptance shows what the spec will say beside the record: added, removed with its reason, the new feature
    await pane.press({ key: 'record-add-book-accept-1' })
    expect(await pane.find({ text: /what the spec will say/i })).toBeDefined()
    expect(await pane.find({ text: /new feature shelf/ })).toBeDefined()
    expect(await pane.find({ text: /the shelf replaces the list/ })).toBeDefined()
    await pane.press({ key: 'back' })

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

    // the worker: started by the press, its output and its exit code in the run tab; a second press in the same
    // breath starts nothing
    await Promise.all([pane.press({ key: 'run' }), pane.press({ key: 'run' })])
    expect(spawned).toEqual([['run', '--story', 'add-book']])
    expect(await pane.find({ text: /factory: add-book — plan/ })).toBeDefined()
    expect(await pane.find({ text: /stopped for a decision/ })).toBeDefined()

    // the close button closes the pane
    await pane.press({ key: 'close' })
    expect(closed).toEqual(['factory-cockpit'])
  })
}

test('a backlog with hundreds of open findings still draws the decide tab', async ($, on) => {
  const many = Array.from({ length: 300 }, (_, index) => ({ ...STATUS.findings[0], where: `src/Book.java:${index}`, defect: `defect ${index} `.repeat(40) }))
  on('session.root', async () => ({ value: ROOT }))
  on('fs.exists', async () => ({ value: true }))
  on('fs.list', async () => ({ value: [] }))
  on('fs.read', async () => ({ deny: 'missing' }))
  on('process.run', async (_: unknown, e: { argv: readonly string[] }) => {
    const out = e.argv.includes('decisions') ? DECISIONS : e.argv.includes('--list') ? { topics: [] } : { ...STATUS, findings: many }
    return { value: { exitCode: 0, stdout: JSON.stringify(out), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('clock.now', async () => ({ value: Date.parse('2026-09-23T17:30:00Z') }))
  on('clock.every', async () => ({ value: { cancel: () => {} } }) as never)
  on('ui.open', async () => ({ value: { isPlaced: true } }) as never)
  on('ui.status', async () => ({ value: undefined }) as never)
  on('command.list', async () => ({ value: [] }) as never)

  await $.command.run({ command: 'factory-cockpit', args: '' } as never)
  const pane = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface: 'terminal', component: 'Pane', requestId: 'factory-cockpit', props: { title: 'Factory', isFocused: true } as never })
  await pane.press({ key: 'tab-decide' })
  expect(await pane.find({ text: /300 from the judge · the first \d+ shown/ })).toBeDefined()
  expect(await pane.find({ text: /defect 299 / })).toBeUndefined()
})

// WP-146: a story opens with its own words and its criteria as scenarios, an epic with what it is for, its text and its
// stories; the delivered tab shows the factory's order. Both details are drawn from the same blocks.
const DETAIL_STATUS = {
  ...STATUS,
  waiting: [],
  findings: [],
  claims: [],
  rows: [
    { ...ROW, story: 'shelve-book', title: 'Shelve a book', mark: 'done', state: 'delivered', done: true, delivered: '2026-09-20T10:00:00Z' },
    { ...ROW, story: 'lend-book', title: 'Lend a book', mark: 'done', state: 'delivered', done: true, delivered: '2026-09-22T10:00:00Z' },
    ROW,
  ],
  // the factory's order: the newest delivery first — not the order of the rows
  delivered_order: ['lend-book', 'shelve-book'],
  delivered: 2,
  total: 3,
  epics: [{ ...STATUS.epics[0], intent: 'readers lose track of their books', domain_contact: 'the librarian', path: 'product/epics/books/epic.md', created: '2026-09-01T08:00:00Z' }],
}
const STORY_VIEW = {
  ...STORY,
  path: 'product/epics/books/add-book/story.md',
  description: 'As a reader I want to add a book, so that it stands on my shelf.',
  scenarios: [
    { key: 'adds-a-book', title: 'A new book stands on the shelf', rule: 'A book is added once', happy: true, text: '',
      steps: [{ word: 'Given', text: 'an empty shelf' }, { word: 'When', text: 'the reader adds "Dune"' }, { word: 'Then', text: 'the shelf shows "Dune"' }] },
    { key: 'twice-is-once', title: 'Twice is once', rule: 'A book is added once', happy: false, text: 'Adding "Dune" again keeps one.', steps: [] },
  ],
}
const EPIC_VIEW = {
  epic: 'books', title: 'Keep track of books', path: 'product/epics/books/epic.md', created: '2026-09-01T08:00:00Z',
  intent: 'readers lose track of their books', goal: 'one list', metric: 'BookAdded', domain_contact: 'the librarian', discovery: '',
  description: '## Journey\n\n- open: a reader adds a book and finds it again', rows: [ROW], delivered: 0, total: 1, tokens: 0,
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`a story and an epic open with what they say; delivered shows the factory's order (${surface})`, async ($, on) => {
    on('session.root', async () => ({ value: ROOT }))
    on('fs.exists', async () => ({ value: true }))
    on('fs.list', async () => ({ value: [] }))
    const files: Record<string, string> = {
      ...FILES,
      [`${ROOT}/product/epics/books/add-book/story.md`]: '---\nid: add-book\n---\n\n# Add a book\n',
    }
    on('fs.read', async (_, e) => (files[e.path] === undefined ? { deny: 'missing' } : { value: files[e.path] as string }))
    on('process.run', async (_: unknown, e: { argv: readonly string[] }) => {
      const out = e.argv.includes('--epic') ? EPIC_VIEW : e.argv.includes('--story') ? STORY_VIEW : e.argv.includes('decisions') ? { records: [] } : e.argv.includes('--list') ? { topics: [] } : DETAIL_STATUS
      return { value: { exitCode: 0, stdout: JSON.stringify(out), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    })
    on('clock.now', async () => ({ value: Date.parse('2026-09-23T17:30:00Z') }))
    on('clock.every', async () => ({ value: { cancel: () => {} } }) as never)
    on('ui.open', async () => ({ value: { isPlaced: true } }) as never)
    on('ui.status', async () => ({ value: undefined }) as never)
    on('command.list', async () => ({ value: [] }) as never)

    await $.command.run({ command: 'factory-cockpit', args: '' } as never)
    const pane = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface, component: 'Pane', requestId: 'factory-cockpit', props: { title: 'Factory', isFocused: true } as never })

    // the epic: what it is for, its own text, its stories, its file
    await pane.press({ key: 'epic-books' })
    expect(await pane.find({ text: 'readers lose track of their books' })).toBeDefined()
    expect(await pane.find({ text: 'the librarian' })).toBeDefined()
    expect(await pane.find({ text: 'newest first' })).toBeDefined()
    expect(await pane.find({ key: 'story-add-book' })).toBeDefined()
    // an older pipeline names no view: the stories open, its own text one press away
    await pane.press({ key: 'view-epic' })
    expect(await pane.find({ text: /a reader adds a book and finds it again/ })).toBeDefined()
    await pane.press({ key: 'view-stories' })
    await pane.press({ key: 'open-epic-books' })
    expect(await pane.find({ text: 'books / epic.md' })).toBeDefined()
    await pane.press({ key: 'back' })
    expect(await pane.find({ text: 'the librarian' })).toBeDefined()

    // the story: its own words, its criteria as scenarios — title, rule, steps — and its file; the pipeline below
    await pane.press({ key: 'story-add-book' })
    expect(await pane.find({ text: /As a reader I want to add a book/ })).toBeDefined()
    expect(await pane.find({ text: 'A new book stands on the shelf' })).toBeDefined()
    expect(await pane.find({ text: 'Rule: A book is added once' })).toBeDefined()
    expect(await pane.find({ text: 'Given' })).toBeDefined()
    expect(await pane.find({ text: 'the reader adds "Dune"' })).toBeDefined()
    expect(await pane.find({ text: 'Adding "Dune" again keeps one.' })).toBeDefined()
    expect(await pane.find({ text: /first delivery/ })).toBeUndefined()
    await pane.press({ key: 'view-pipeline' })
    expect(await pane.find({ text: /first delivery/ })).toBeDefined()
    await pane.press({ key: 'view-story' })
    await pane.press({ key: 'open-story' })
    expect(await pane.find({ text: 'add-book / story.md' })).toBeDefined()
    await pane.press({ key: 'back' })
    expect(await pane.find({ text: 'A new book stands on the shelf' })).toBeDefined()

    // delivered: the newest delivery first, as the factory ordered them
    await pane.press({ key: 'back' })
    await pane.press({ key: 'tab-delivered' })
    const shown = (await pane.findAll({ type: 'Button' })).map(one => one.key).filter(key => key === 'story-lend-book' || key === 'story-shelve-book')
    expect(shown).toEqual(['story-lend-book', 'story-shelve-book'])
  })
}

// The story detail stays short: a head with the factory's one line of what is up, then two views — the story's own
// sections in the factory's order (why it is not built framed first, the criteria where they stand) and the
// pipeline. The factory names the view to open with; a press switches. An epic the same way.
const SECTIONS_STORY = {
  ...STORY_VIEW,
  superseded: true,
  situation: 'superseded — nobody shelves books any more',
  view: 'story',
  criteria_at: 2,
  sections: [
    { heading: 'Superseded', text: '- Not built: nobody shelves books any more; the\n  librarian decided so.', kind: 'superseded' },
    { heading: 'Story', text: 'As a reader I want to add a book, so that it stands on my shelf.', kind: '' },
    { heading: 'Notes', text: '- From the reading group.', kind: '' },
  ],
}
const SECTIONS_EPIC = {
  ...EPIC_VIEW,
  situation: '0 of 1 delivered · 1 superseded',
  view: 'epic',
  stories_at: 1,
  sections: [
    { heading: 'Intent', text: 'Readers lose track of the books they lent.', kind: '' },
    { heading: 'Journey', text: '- open: a reader adds a book and finds it again', kind: '' },
  ],
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`a detail opens with what is up and the view the factory names; sections in its order (${surface})`, async ($, on) => {
    on('session.root', async () => ({ value: ROOT }))
    on('fs.exists', async () => ({ value: true }))
    on('fs.list', async () => ({ value: [] }))
    on('fs.read', async (_, e) => (FILES[e.path] === undefined ? { deny: 'missing' } : { value: FILES[e.path] as string }))
    on('process.run', async (_: unknown, e: { argv: readonly string[] }) => {
      const out = e.argv.includes('--epic') ? SECTIONS_EPIC : e.argv.includes('--story') ? SECTIONS_STORY : e.argv.includes('decisions') ? { records: [] } : e.argv.includes('--list') ? { topics: [] } : DETAIL_STATUS
      return { value: { exitCode: 0, stdout: JSON.stringify(out), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    })
    on('clock.now', async () => ({ value: Date.parse('2026-09-23T17:30:00Z') }))
    on('clock.every', async () => ({ value: { cancel: () => {} } }) as never)
    on('ui.open', async () => ({ value: { isPlaced: true } }) as never)
    on('ui.status', async () => ({ value: undefined }) as never)
    on('command.list', async () => ({ value: [] }) as never)

    await $.command.run({ command: 'factory-cockpit', args: '' } as never)
    const pane = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface, component: 'Pane', requestId: 'factory-cockpit', props: { title: 'Factory', isFocused: true } as never })

    // the epic: its line, its sections in the factory's order — the view it names first, the stories one press away
    await pane.press({ key: 'epic-books' })
    expect(await pane.find({ text: '0 of 1 delivered · 1 superseded' })).toBeDefined()
    expect(await pane.find({ text: /Readers lose track of the books they lent/ })).toBeDefined()
    expect(await pane.find({ text: 'JOURNEY' })).toBeDefined()
    expect(await pane.find({ key: 'story-add-book' })).toBeUndefined()
    await pane.press({ key: 'view-stories' })
    expect(await pane.find({ key: 'story-add-book' })).toBeDefined()
    expect(await pane.find({ text: /Readers lose track/ })).toBeUndefined()

    // the story: what is up in one line, the reason it is not built framed first, a wrapped line kept, the
    // criteria where they stand, the notes after them; the pipeline one press away
    await pane.press({ key: 'story-add-book' })
    expect(await pane.find({ text: 'superseded — nobody shelves books any more' })).toBeDefined()
    expect(await pane.find({ text: 'SUPERSEDED' })).toBeDefined()
    expect(await pane.find({ text: /librarian decided so/ })).toBeDefined()
    expect(await pane.find({ text: 'A new book stands on the shelf' })).toBeDefined()
    expect(await pane.find({ text: /From the reading group/ })).toBeDefined()
    expect(await pane.find({ text: /first delivery/ })).toBeUndefined()
    await pane.press({ key: 'view-pipeline' })
    expect(await pane.find({ text: /first delivery/ })).toBeDefined()
    expect(await pane.find({ text: 'SUPERSEDED' })).toBeUndefined()
    expect(await pane.find({ text: 'superseded — nobody shelves books any more' })).toBeDefined()
  })
}
