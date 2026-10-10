import { expect, test } from 'claude-code/testing'

import { filledCells, duration, gateBy, isHistory, isRefusal, isSelfCheck, moment, parseJournal, recommendedOption, recordOptions, rounds, stagesOf, touchesFactory, wrapWords } from '../hooks/parse'

test('a factory command or skill refreshes the view, other calls do not', () => {
  expect(touchesFactory({ tool: 'Bash', command: 'bash .agents/factory/factory.sh run' } as { tool: string })).toBe(true)
  expect(touchesFactory({ tool: 'Skill', skill: 'dca-factory:factory-run' } as { tool: string })).toBe(true)
  expect(touchesFactory({ tool: 'Bash', command: 'git status' } as { tool: string })).toBe(false)
})

test('reads the stages, rounds, gates and the open stage from a journal', () => {
  const journal = [
    '2026-09-23T17:24:53Z\tstage-start\ttest\ttool=claude',
    '2026-09-23T17:27:41Z\tusage\ttest\ttool=claude\tcost=0.7783',
    '2026-09-23T17:27:41Z\tstage-end\ttest\texit=0',
    '2026-09-23T17:28:07Z\tgate\ttest\texit=1',
    '2026-09-23T17:28:07Z\tstage-start\ttest\ttool=claude',
    '2026-09-23T17:29:04Z\tstage-end\ttest\texit=0',
    '2026-09-23T17:29:32Z\tgate\ttest\texit=0',
    '2026-09-23T17:29:32Z\tstage-start\tbuild\ttool=claude',
  ].join('\n')

  const [test1, build] = stagesOf(parseJournal(journal))

  expect(test1).toEqual({ stage: 'test', rounds: 2, gates: [false, true], seconds: 225, cost: 0.7783, tokens: 0, runningSince: null })
  expect(build?.runningSince).toBe('2026-09-23T17:29:32Z')
})

test('a journal with seq, wrote and outdated lines: only stages and verdict gates count', () => {
  const journal = [
    '2026-10-10T08:00:00Z\tstage-start\tbuilder\ttool=claude\tseq=1',
    '2026-10-10T08:05:00Z\tgate\tbuild\texit=1\tfail=tests\tby=builder\tseq=2',
    '2026-10-10T08:06:00Z\twrote\tbuilder\tsha=abc123\tseq=3',
    '2026-10-10T08:06:01Z\twrote\tbuilder\tsha=abc123\tsame=1\tseq=4',
    '2026-10-10T08:07:00Z\tstage-end\tbuilder\texit=0\tseq=5',
    '2026-10-10T08:07:30Z\tgate\tbuilder\texit=0\tby=runner\tseq=6',
    '2026-10-10T08:08:00Z\toutdated\tjudge\tseq=7',
  ].join('\n')
  const events = parseJournal(journal)

  expect(events[1]?.fields).toEqual({ exit: '1', fail: 'tests', by: 'builder', seq: '2' })
  expect(stagesOf(events)).toEqual([{ stage: 'builder', rounds: 1, gates: [true], seconds: 420, cost: 0, tokens: 0, runningSince: null }])
  expect(events.filter(isHistory).map(event => event.kind)).toEqual(['stage-start', 'gate', 'stage-end', 'gate'])
  expect(events.filter(isSelfCheck).map(gateBy)).toEqual(['builder'])
})

test('only the runner\'s refusal is a refusal to announce — older journals have no by field', () => {
  const [old, runner, stage, session, passed] = parseJournal([
    '2026-10-10T08:00:00Z\tgate\ttest\texit=1',
    '2026-10-10T08:00:00Z\tgate\ttest\texit=1\tby=runner\tseq=1',
    '2026-10-10T08:00:00Z\tgate\ttest\texit=1\tby=test\tseq=2',
    '2026-10-10T08:00:00Z\tgate\ttest\texit=1\tby=session\tseq=3',
    '2026-10-10T08:00:00Z\tgate\ttest\texit=0\tby=runner\tseq=4',
  ].join('\n'))

  expect([old, runner, stage, session, passed].map(event => isRefusal(event!))).toEqual([true, true, false, false, false])
})

test('formats durations', () => {
  expect(duration(42)).toBe('42 s')
  expect(duration(161)).toBe('2 min 41 s')
  expect(duration(120)).toBe('2 min')
  expect(duration(3720)).toBe('1 h 2 min')
})

test('formats dates and times as UTC, the way the journal writes them', () => {
  expect(moment('2026-09-28T07:51:31.719Z')).toBe('28.09.2026 07:51 UTC')
  expect(rounds(1)).toBe('1 round')
  expect(rounds(2)).toBe('2 rounds')
})

test('a progress fills its share of the cells, none for an empty whole', () => {
  expect(filledCells(3, 5, 10)).toBe(6)
  expect(filledCells(0, 0, 4)).toBe(0)
  expect(filledCells(9, 5, 10)).toBe(10)
})

test('a write under project/ or the run folder refreshes the view, a write elsewhere does not', () => {
  expect(touchesFactory({ tool: 'Write', file_path: '/p/project/epics/books/epic.md' } as { tool: string })).toBe(true)
  expect(touchesFactory({ tool: 'Edit', file_path: '/p/.dca-factory/runs/a/plan.md' } as { tool: string })).toBe(true)
  expect(touchesFactory({ tool: 'Write', file_path: '/p/src/Main.java' } as { tool: string })).toBe(false)
})

test('a wide cell wraps by words, and a word longer than the cell is cut', () => {
  expect(wrapWords('BookAdded — each added book is the evidence', 16)).toEqual(['BookAdded — each', 'added book is', 'the evidence'])
  expect(wrapWords('averyveryverylongword', 8)).toEqual(['averyver', 'yverylon', 'gword'])
  expect(wrapWords('', 8)).toEqual([''])
})

test('reads a decision record\'s options and the one its recommendation names', () => {
  const record = ['# Q', '', '## Options', '- a: one way', '- b: another,', '  on two lines', '', '## Recommendation', 'b — because', '', '## Answer'].join('\n')
  const options = recordOptions(record)
  expect(options).toEqual([{ key: 'a', text: 'one way' }, { key: 'b', text: 'another, on two lines' }])
  expect(recommendedOption(record, options)).toBe('b')
  expect(recommendedOption('## Recommendation\nnone of them', options)).toBe(null)
  expect(recordOptions('# no options here')).toEqual([])
})
