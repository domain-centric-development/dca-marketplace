import { expect, test } from 'claude-code/testing'
import type { TestBody } from 'claude-code/testing'

// Beside the pane: the note the model reads with a prompt, the tool it asks the factory with, the status printed into
// the transcript and what moved since the last session.
const ROOT = '/p'
const TOOL = 'mcp__dca-factory-cockpit__factory_status'
const ROW = {
  story: 'add-book', title: 'Add a book', epic: 'books', mark: 'question', state: 'question', stage: 'plan', passes: 1,
  started: '2026-10-06T08:00:00Z', delivered: '', seconds: 60, tokens: 0, cost: 0, priced: 0, done: false,
}
const STATUS = {
  project: 'books-app',
  waiting: [{ mark: 'question', story: 'add-book', what: 'plan asks a question', action: { text: '', skill: '/factory-decisions', shell: '' } }],
  running: [{ story: 'lend-book', stage: 'builder', since: '2026-10-06T08:00:00Z', interrupted: false, ago: '3 min', part: 'test' }],
  epics: [{ epic: 'books', rows: [ROW], delivered: 1, total: 3, tokens: 0, seconds: 60, title: 'Keep track of books', goal: '', metric: '', discovery: '' }],
  description: [],
  rows: [ROW, { ...ROW, story: 'shelve-book', mark: 'done', state: 'delivered', done: true }],
  queue: { ready: ['sort-books'], blocked: 0, drafts: 0 },
  next: { text: 'sort-books starts once add-book has its answer.', action: { text: '', skill: '', shell: '' } },
  journeys: [],
  findings: [{ story: 'add-book', where: 'a', severity: 'minor', defect: 'd', file: 'f', action: { text: '', skill: '', shell: '' } }],
  extra: [],
  delivered: 1,
  total: 3,
  tokens: 2_000_000,
  seconds: 60,
}
const STORY = { story: 'add-book', context: 'reading', criteria: 2, accepted_by: '', passes: [], stages: {} }

function wire(on: Parameters<TestBody>[1], status: unknown, asked: string[][] = []) {
  on('session.root', async () => ({ value: ROOT }))
  on('fs.exists', async () => ({ value: true }))
  on('fs.list', async () => ({ value: [] }))
  on('fs.read', async () => ({ deny: 'missing' }))
  on('process.run', async (_: unknown, e: { argv: readonly string[] }) => {
    asked.push([...e.argv.slice(2)])
    const out = e.argv.includes('decisions') ? { records: [] } : e.argv.includes('--list') ? { topics: [] } : e.argv.includes('--story') ? STORY : status
    return { value: { exitCode: 0, stdout: JSON.stringify(out), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('clock.now', async () => ({ value: Date.parse('2026-10-06T08:03:00Z') }))
  on('clock.every', async () => ({ value: { cancel: () => {} } }) as never)
  on('ui.open', async () => ({ value: { isPlaced: true } }) as never)
  on('ui.status', async () => ({ value: undefined }) as never)
  on('command.list', async () => ({ value: [] }) as never)
  on('command.register', async () => ({ value: { command: 'factory-cockpit' } }) as never)
  on('tool.register', async () => ({ value: { tool: TOOL } }) as never)
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }) as never)
  on('ui.render', async ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>the engine's row</Text>
  })
}

test('the model reads where the factory stands beside a prompt, and again only when it changed', async ($, on) => {
  wire(on, STATUS)
  on('prompt.submit', (_, e) => ({ text: e.text, context: e.context }))
  await $.command.run({ command: 'factory-cockpit', args: '' } as never)

  const first = (await $.prompt.submit({ text: 'what now?', wait: false } as never)) as { context?: string[] }
  expect(first.context?.[0]).toContain('- waits for the person: add-book — plan asks a question')
  expect(first.context?.[0]).toContain('- running: lend-book · builder · test')
  const second = (await $.prompt.submit({ text: 'and now?', wait: false } as never)) as { context?: string[] }
  expect(second.context ?? []).toEqual([])
})

test('the tool answers with the factory, cut to what a question needs unless the whole is asked for', async ($, on) => {
  const asked: string[][] = []
  wire(on, STATUS, asked)
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true } as never)

  const short = JSON.parse(((await $.tool.call({ tool: TOOL } as never)) as { result: string }).result)
  expect(short.waiting[0].story).toBe('add-book')
  expect(short.findings).toBe(1)
  expect(short.rows).toBeUndefined()
  const whole = JSON.parse(((await $.tool.call({ tool: TOOL, full: true } as never)) as { result: string }).result)
  expect(whole.rows.length).toBe(2)
  const story = JSON.parse(((await $.tool.call({ tool: TOOL, story: 'add-book' } as never)) as { result: string }).result)
  expect(story.context).toBe('reading')
  expect(asked.at(-1)).toEqual(['status', '--story', 'add-book', '--format', 'json', '--live'])
})

for (const surface of ['terminal', 'desktop'] as const) {
  test(`/factory-cockpit status prints where it stands and draws it as it stood (${surface})`, async ($, on) => {
    wire(on, STATUS)
    const printed = (await $.command.run({ command: 'factory-cockpit', args: 'status' } as never)) as { text: string }
    expect(printed.text).toMatch(/^Factory status at 2026-10-06T08:03:00.000Z — books-app: 1 of 3 stories delivered/)
    expect(printed.text).toContain('- ready: sort-books')

    const row = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface, component: 'CommandOutput', props: { command: 'factory-cockpit', args: 'status', text: printed.text, isErrored: false } as never })
    expect(await row.find({ text: 'FACTORY' })).toBeDefined()
    expect(await row.find({ text: /add-book — plan asks a question/ })).toBeDefined()
    expect(await row.find({ text: /lend-book · builder · test/ })).toBeDefined()
    expect(await row.find({ text: /ready: sort-books/ })).toBeDefined()

    // the command's other rows, and a status this session did not read, keep the engine's
    const other = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface, component: 'CommandOutput', props: { command: 'factory-cockpit', args: '', text: 'Factory cockpit opened.', isErrored: false } as never })
    expect(await other.find({ text: "the engine's row" })).toBeDefined()
    const resumed = await $.ui.mount({ plugin: 'dca-factory-cockpit', surface, component: 'CommandOutput', props: { command: 'factory-cockpit', args: 'status', text: 'Factory status at 2026-01-01T00:00:00.000Z — old', isErrored: false } as never })
    expect(await resumed.find({ text: "the engine's row" })).toBeDefined()
  })
}

test('a new session says what moved since the last one looked', async ($, on) => {
  const toasts: string[] = []
  wire(on, STATUS)
  on('ui.toast', async (_: unknown, e: { text: string }) => {
    toasts.push(e.text)
    return { value: undefined } as never
  })
  // the store as the engine keeps it across sessions: what the last one saw
  const store = new Map<string, unknown>([['seen:/p', { at: '2026-10-05T17:00:00Z', delivered: [], waiting: [] }]])
  on('store.get', async (_: unknown, e: { key: string }) => ({ value: store.get(e.key) }) as never)
  on('store.set', async (_: unknown, e: { key: string; value: unknown }) => {
    store.set(e.key, e.value)
    return { value: undefined } as never
  })
  await $.command.run({ command: 'factory-cockpit', args: '' } as never)
  expect(toasts).toContain('factory since 05.10.2026 17:00 UTC: 1 delivered (shelve-book) · 1 new for you (add-book)')
  expect((store.get('seen:/p') as { delivered: string[] }).delivered).toEqual(['shelve-book'])
})
