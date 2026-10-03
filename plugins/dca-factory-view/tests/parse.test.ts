import { expect, test } from 'claude-code/testing'

import { bar, duration, moment, parseJournal, rounds, stagesOf, touchesFactory } from '../hooks/parse'

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

test('draws a progress bar of a given width', () => {
  expect(bar(3, 5, 10)).toBe('██████░░░░')
  expect(bar(0, 0, 4)).toBe('░░░░')
})

test('a write under project/ or the run folder refreshes the view, a write elsewhere does not', () => {
  expect(touchesFactory({ tool: 'Write', file_path: '/p/project/epics/books/epic.md' } as { tool: string })).toBe(true)
  expect(touchesFactory({ tool: 'Edit', file_path: '/p/.dca-factory/runs/a/plan.md' } as { tool: string })).toBe(true)
  expect(touchesFactory({ tool: 'Write', file_path: '/p/src/Main.java' } as { tool: string })).toBe(false)
})
