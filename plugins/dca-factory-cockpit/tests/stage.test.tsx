import { expect, test } from 'claude-code/testing'

const ROOT = '/p'
const ROW = {
  story: 'add-book', title: 'Add a book', epic: 'books', mark: 'running', state: 'running', stage: 'builder', passes: 1,
  started: '2026-10-06T08:00:00Z', delivered: '', seconds: 60, tokens: 0, cost: 0, priced: 0, done: false,
}
const STATUS = {
  project: 'books-app',
  waiting: [],
  running: [{ story: 'add-book', stage: 'builder', since: '2026-10-06T08:00:00Z', ago: '1 min', part: 'test' }],
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
const STORY = {
  story: 'add-book', context: 'reading', criteria: 2, accepted_by: '',
  passes: [],
  stages: { builder: { runs: 1, seconds: 480, tokens: 4_800_000, cost: 3.02, models: ['some-model'], input: 108, output: 46_433, cache_write: 137_058, cache_read: 4_616_401, parts: [
    { stage: 'plan', runs: 1, seconds: 72, tokens: 668_330, cost: 0.67 },
    { stage: 'test', runs: 1, seconds: 238, tokens: 2_302_460, cost: 1.41, denied: 1 },
  ], denied: 1, denials: [{ stage: 'test', tool: 'Bash', command: 'for f in src/*.java; do cat $f; done' }] } },
}
const FOLLOW = { story: 'add-book', stage: 'builder', running: true, lines: ['· session started — some-model', '▸ Read plan.md', '  writing the first test'] }

for (const surface of ['terminal', 'desktop'] as const) {
  test(`the run tab shows what the running stage does, whoever started it (${surface})`, async ($, on) => {
    const asked: string[][] = []
    on('session.root', async () => ({ value: ROOT }))
    on('fs.exists', async () => ({ value: true }))
    on('fs.list', async (_: unknown, e: { path: string }) => ({
      value: e.path.endsWith('/add-book/.verify')
        ? [{ name: 'verifier.090000.out', kind: 'file', size: 0, mtimeMs: 2, isLink: false }, { name: 'builder.085007.out', kind: 'file', size: 0, mtimeMs: 1, isLink: false }]
        : [],
    }) as never)
    on('fs.read', async () => ({ deny: 'missing' }))
    on('process.run', async (_: unknown, e: { argv: readonly string[] }) => {
      asked.push([...e.argv.slice(2)])
      const out = e.argv.includes('--process') ? { story: 'add-book', stage: 'builder', running: false, lines: ['── plan', '▸ Write plan.md'] } : e.argv.includes('follow') ? FOLLOW : e.argv.includes('--story') ? STORY : e.argv.includes('decisions') ? { records: [] } : e.argv.includes('--list') ? { topics: [] } : STATUS
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
    // the shared builder's running stage is named, and the story shows its stages with their share of the cost
    expect(await pane.find({ text: /builder · te/ })).toBeDefined()
    await pane.press({ key: 'running-add-book' })
    expect(await pane.find({ text: /· test/ })).toBeDefined()
    expect(await pane.find({ text: /≈/ })).toBeDefined()
    // the tokens by class, not only their sum
    expect(await pane.find({ text: 'TOKENS PER STAGE' })).toBeDefined()
    expect(await pane.find({ text: 'cache read' })).toBeDefined()
    // a table's rules sit in boxes of their own: no text runs a rule across columns or pads a bar with spaces,
    // which a proportional font (Desktop) would shift off its column
    expect(await pane.find({ type: 'Text', text: /─┼─.*─┼─|┼──/ })).toBeUndefined()
    expect(await pane.find({ type: 'Text', text: / │ / })).toBeUndefined()
    // line glyphs join into rules only on the terminal's grid; elsewhere the columns are kept apart by space alone
    // (one bar stays on every surface: the one between the wordmark and the title in the head)
    const bars = (await pane.findAll({ type: 'Text', text: '│' })).length
    if (surface === 'terminal') expect(bars).toBeGreaterThan(1)
    else {
      expect(bars).toBe(1)
      expect(await pane.find({ type: 'Text', text: /┼/ })).toBeUndefined()
    }
    // a call the stage was denied is listed with the stage it fell in
    expect(await pane.find({ text: /builder · test/ })).toBeDefined()
    expect(await pane.find({ text: /for f in src/ })).toBeDefined()
    // a delivered stage's output stays readable: one link per process, oldest first, and its lines on a press
    expect(await pane.find({ text: 'verifier' })).toBeDefined()
    await pane.press({ key: 'output-builder' })
    expect(asked.some(argv => argv.includes('--process') && argv.includes('builder'))).toBe(true)
    expect(await pane.find({ text: /── plan/ })).toBeDefined()
    expect(await pane.find({ text: /Write plan\.md/ })).toBeDefined()
  })
}
