import { expect, test } from 'claude-code/testing'

const ROOT = '/p'
const ROW = {
  story: 'add-book', title: 'Add a book', epic: 'books', mark: 'running', state: 'running', stage: 'builder', passes: 1,
  started: '2026-10-06T08:00:00Z', delivered: '', seconds: 60, tokens: 0, cost: 0, priced: 0, done: false,
}
const STATUS = {
  project: 'books-app',
  waiting: [],
  running: [{ story: 'add-book', stage: 'builder', since: '2026-10-06T08:00:00Z', ago: '1 min' }],
  epics: [{ epic: 'books', rows: [ROW], delivered: 0, total: 1, tokens: 0, seconds: 60, title: 'Keep track of books', goal: 'one list', metric: 'BookAdded', discovery: '' }],
  description: [],
  rows: [ROW],
  next: { text: 'add-book is running.', action: { text: '', skill: '', shell: '' } },
  journeys: [],
  extra: [],
  delivered: 0,
  total: 1,
  tokens: 0,
  seconds: 60,
}
// what `factory.sh follow --once --format json` prints for a stage a shell or a bench started
const FOLLOW = { story: 'add-book', stage: 'builder', running: true, lines: ['· session started — some-model', '▸ Read plan.md', '  writing the first test'] }

for (const surface of ['terminal', 'desktop'] as const) {
  test(`the run tab shows what the running stage does, whoever started it (${surface})`, async ($, on) => {
    const asked: string[][] = []
    on('session.root', async () => ({ value: ROOT }))
    on('fs.exists', async () => ({ value: true }))
    on('fs.list', async () => ({ value: [] }))
    on('fs.read', async () => ({ deny: 'missing' }))
    on('process.run', async (_: unknown, e: { argv: readonly string[] }) => {
      asked.push([...e.argv.slice(2)])
      const out = e.argv.includes('follow') ? FOLLOW : e.argv.includes('decisions') ? { records: [] } : e.argv.includes('--list') ? { topics: [] } : STATUS
      return { value: { exitCode: 0, stdout: JSON.stringify(out), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    })
    on('clock.now', async () => ({ value: Date.parse('2026-10-06T08:01:00Z') }))
    on('clock.every', async () => ({ value: { cancel: () => {} } }) as never)
    on('ui.open', async () => ({ value: { isPlaced: true } }) as never)
    on('ui.status', async () => ({ value: undefined }) as never)
    on('ui.toast', async () => ({ value: undefined }) as never)
    on('command.list', async () => ({ value: [] }) as never)

    await $.command.run({ command: 'factory-cockpit', args: '' } as never)
    const pane = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface, component: 'Pane', requestId: 'factory-cockpit', props: { title: 'Factory', isFocused: true } as never })

    await pane.press({ key: 'tab-run' })
    expect(asked.some(argv => argv[0] === 'follow' && argv.includes('--once'))).toBe(true)
    expect(await pane.find({ text: /add-book · builder — running/ })).toBeDefined()
    expect(await pane.find({ text: /▸ Read plan\.md/ })).toBeDefined()
    expect(await pane.find({ text: /writing the first test/ })).toBeDefined()
  })
}
