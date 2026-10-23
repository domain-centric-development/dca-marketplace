import { expect, test } from 'claude-code/testing'
import type { TestBody } from 'claude-code/testing'

const ROOT = '/p'
const ROW = {
  story: 'add-book', title: 'Add a book', epic: 'books', mark: 'question', state: 'question', stage: 'plan', passes: 1,
  started: '2026-10-06T08:00:00Z', delivered: '', seconds: 60, tokens: 0, cost: 0, priced: 0, done: false,
}
const QUIET = {
  project: 'books-app',
  waiting: [],
  running: [],
  epics: [{ epic: 'books', rows: [ROW], delivered: 0, total: 1, tokens: 0, seconds: 60, title: 'Keep track of books', goal: '', metric: '', discovery: '' }],
  description: [],
  rows: [ROW],
  next: { text: 'Every story is delivered — write the next one.', action: { text: '', skill: '', shell: '' } },
  journeys: [],
  extra: [],
  delivered: 0,
  total: 1,
  tokens: 0,
  seconds: 60,
}
const BUSY = {
  ...QUIET,
  waiting: [
    { mark: 'question', story: 'add-book', what: 'plan asks a question', action: { text: '', skill: '/factory-decisions', shell: '' } },
    { mark: 'look', story: 'sort-books', what: 'published — waits for its merge', action: { text: 'open the merge request from its branch', skill: '', shell: '' } },
  ],
  running: [{ story: 'lend-book', stage: 'builder', since: '2026-10-06T08:00:00Z', interrupted: false, ago: '3 min', part: 'test', activity: 'Edit LendBook.java' }],
}
const BAND = { hasSurvey: false, isWorking: false, maxRows: 12, bodyColumns: 100 }

function wire(on: Parameters<TestBody>[1], status: unknown, sent: string[], opened: string[]) {
  on('session.root', async () => ({ value: ROOT }))
  on('fs.exists', async () => ({ value: true }))
  on('fs.list', async () => ({ value: [] }))
  on('fs.read', async () => ({ deny: 'missing' }))
  on('process.run', async (_: unknown, e: { argv: readonly string[] }) => {
    const out = e.argv.includes('decisions') ? { records: [] } : e.argv.includes('--list') ? { topics: [] } : e.argv.includes('--story') ? null : status
    return { value: { exitCode: out ? 0 : 1, stdout: JSON.stringify(out), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('clock.now', async () => ({ value: Date.parse('2026-10-06T08:03:00Z') }))
  on('clock.every', async () => ({ value: { cancel: () => {} } }) as never)
  on('ui.open', async (_: unknown, e: { id: string }) => {
    opened.push(e.id)
    return { value: { isPlaced: true } } as never
  })
  on('ui.status', async () => ({ value: undefined }) as never)
  on('ui.toast', async () => ({ value: undefined }) as never)
  on('command.list', async () => ({ value: [{ name: 'dca-factory:factory-decisions' }] }) as never)
  // the engine's own band beneath the plugin
  on('ui.render', async ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>the engine's band</Text>
  })
  on('command.run', async (_: unknown, e: { command: string; args: string }) => {
    sent.push(`/${e.command}${e.args ? ` ${e.args}` : ''}`)
    return { text: '' } as never
  })
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`the band shows what waits and what runs, answers and opens the cockpit (${surface})`, async ($, on) => {
    const sent: string[] = []
    const opened: string[] = []
    wire(on, BUSY, sent, opened)
    await $.command.run({ command: 'factory-cockpit', args: '' } as never)
    opened.length = 0
    const band = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface, component: 'AbovePrompt', props: BAND as never })

    expect(await band.find({ text: 'FACTORY' })).toBeDefined()
    expect(await band.find({ text: /2 wait for you · 1 running/ })).toBeDefined()
    expect(await band.find({ text: /add-book — plan asks a question/ })).toBeDefined()
    // what the factory says in words only offers no answer
    expect(await band.find({ text: /waits for its merge — open the merge request/ })).toBeDefined()
    expect(await band.find({ key: 'band-answer-sort-books' })).toBeUndefined()
    expect(await band.find({ text: /lend-book · builder · test — 3 min — Edit LendBook.java/ })).toBeDefined()

    // an answer goes to the decisions skill; the band writes nothing
    await band.press({ key: 'band-answer-add-book' })
    expect(sent.at(-1)).toBe('/dca-factory:factory-decisions add-book')

    // the way into the pane: a story, the running output, the cockpit as it stood
    await band.press({ key: 'band-story-add-book' })
    await band.press({ key: 'band-output-lend-book' })
    await band.press({ key: 'band-cockpit' })
    expect(opened).toEqual(['factory-cockpit', 'factory-cockpit', 'factory-cockpit'])
  })
}

test('the band keeps to the rows it has and says how many more the cockpit holds', async ($, on) => {
  wire(on, BUSY, [], [])
  await $.command.run({ command: 'factory-cockpit', args: '' } as never)
  const band = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface: 'terminal', component: 'AbovePrompt', props: { ...BAND, maxRows: 5 } as never })
  expect(await band.find({ text: /1 more in the cockpit/ })).toBeDefined()
  expect(await band.find({ text: /lend-book/ })).toBeUndefined()
})

test('the band stays empty while nothing waits or runs', async ($, on) => {
  wire(on, QUIET, [], [])
  await $.command.run({ command: 'factory-cockpit', args: '' } as never)
  const quiet = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface: 'terminal', component: 'AbovePrompt', props: BAND as never })
  expect(await quiet.find({ text: 'FACTORY' })).toBeUndefined()
  expect(await quiet.find({ text: "the engine's band" })).toBeDefined()
})

test('a survey holds the band before the cockpit', async ($, on) => {
  wire(on, BUSY, [], [])
  await $.command.run({ command: 'factory-cockpit', args: '' } as never)
  const survey = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface: 'terminal', component: 'AbovePrompt', props: { ...BAND, hasSurvey: true } as never })
  expect(await survey.find({ text: 'FACTORY' })).toBeUndefined()
  expect(await survey.find({ text: "the engine's band" })).toBeDefined()
})
