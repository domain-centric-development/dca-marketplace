import { expect, test } from 'claude-code/testing'

import { COL, epicCells, pairsPerRow } from '../hooks/components'
import { LINE_CAP, appendLines, createLatch, displayWidth, exitWord, fit, keepRefresh, rowSignature, wrapWords } from '../hooks/parse'

test('the latch is taken once: a second press while the first starts gets nothing', () => {
  const latch = createLatch()
  expect(latch.take()).toBe(true)
  expect(latch.take()).toBe(false)
  expect(latch.isHeld()).toBe(true)
  latch.release()
  expect(latch.isHeld()).toBe(false)
  expect(latch.take()).toBe(true)
})

test('a refresh asked for during one is kept as one — full and loud when any request was', () => {
  expect(keepRefresh(null, true, true)).toEqual({ isQuiet: true, isLive: true })
  expect(keepRefresh({ isQuiet: true, isLive: true }, false, false)).toEqual({ isQuiet: false, isLive: false })
  expect(keepRefresh({ isQuiet: false, isLive: false }, true, true)).toEqual({ isQuiet: false, isLive: false })
})

test('the worker ends in a word: the exit code, or the stop from the cockpit', () => {
  expect(exitWord(0)).toBe('ran through')
  expect(exitWord(3)).toBe('stopped for a decision — see Decide')
  expect(exitWord(7)).toBe('ended (7)')
  expect(exitWord(null)).toBe('ended (signal)')
  expect(exitWord(null, true)).toBe('stopped from the cockpit')
  expect(exitWord(0, true)).toBe('stopped from the cockpit')
})

test('an epic draws the same cells in every table: mark, count, drafts, outcome, journey', () => {
  const open = epicCells({ epic: 'books', title: 'Keep track of books', metric: 'BookAdded', delivered: 1, total: 3, tokens: 2_500, rows: [{ story: 'a', state: 'draft' }, { story: 'b', state: 'delivered' }, { story: 'c', state: 'ready' }] })
  expect(open.kind).toBe('none')
  expect(open.mark.text).toBe('·')
  expect(open.count.text).toBe('1 of 3')
  expect(open.drafts.text).toBe('1')
  expect(open.draftRows.map(row => row.story)).toEqual(['a'])
  expect(open.outcome.text).toBe('BookAdded')
  expect(open.journey.text).toBe('—')
  expect(open.meta).toBe('1 of 3 delivered · 2.5 k tokens')

  const empty = epicCells({ epic: 'reminders', delivered: 0, total: 0, tokens: 0, rows: [] })
  expect(empty.kind).toBe('empty')
  expect(empty.mark.text).toBe('○')
  expect(empty.title.text).toBe('reminders')
  expect(empty.outcome.text).toBe('—')

  const done = epicCells({ epic: 'books', delivered: 2, total: 2, tokens: 0, rows: [] }, { epic: 'books', text: 'delivered, unguarded — its journey is still open' })
  expect(done.kind).toBe('done')
  expect(done.mark.text).toBe('✓')
  expect(done.journey.text).toBe('◇ delivered, unguarded — its journey is still open')
})

test('widths count cells, not code units: wide glyphs take two, marks one', () => {
  expect(displayWidth('add-book')).toBe(8)
  expect(displayWidth('✓ ▶ ◇ ━ ─')).toBe(9)
  expect(displayWidth('書籍')).toBe(4)
  expect(displayWidth('📚 books')).toBe(8)
  expect(fit('書籍を追加', 5)).toBe('書籍…')
  expect(fit('short', 10)).toBe('short')
  expect(wrapWords('書籍を追加する', 4)).toEqual(['書籍', 'を追', '加す', 'る'])
})

test('the output keeps whole lines and cuts one that never breaks', () => {
  expect(appendLines(['a', 'b'], 'c\nd', 3)).toEqual(['a', 'bc', 'd'])
  const long = appendLines([], 'x'.repeat(LINE_CAP + 50), 10)
  expect(long.length).toBe(1)
  expect(long[0]?.length).toBe(LINE_CAP)
  expect(long[0]?.endsWith('…')).toBe(true)
})

test('an action column counts the link\'s chevron; labelled pairs fit the pane', () => {
  expect(COL.action(7).width).toBe(9)
  expect(pairsPerRow(100)).toBe(2)
  expect(pairsPerRow(80)).toBe(1)
  expect(pairsPerRow(140)).toBe(3)
})

test('a story is read again only when its row moved', () => {
  const row = { state: 'ready', stage: 'plan', passes: 1, done: false, delivered: '' }
  expect(rowSignature(row)).toBe(rowSignature({ ...row }))
  expect(rowSignature(row)).not.toBe(rowSignature({ ...row, stage: 'test' }))
  expect(rowSignature(row)).not.toBe(rowSignature({ ...row, done: true, delivered: '2026-10-03T10:00:00Z' }))
})
