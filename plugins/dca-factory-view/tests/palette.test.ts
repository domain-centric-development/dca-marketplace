import { expect, test } from 'claude-code/testing'

import { C, MARK_COLOR, applyPalette, sizeColumns } from '../hooks/components'

test('a light theme draws on the site\'s paper, a dark one on its deep navy — the marks follow', () => {
  applyPalette(true)
  expect([C.bg, C.text, C.accent]).toEqual(['#f7f6f3', '#1c2433', '#0d6b70'])
  expect(MARK_COLOR.done).toBe(C.done)
  applyPalette(false)
  expect([C.bg, C.text, C.accent]).toEqual(['#171d29', '#e8eaf0', '#148f96'])
  expect(MARK_COLOR.waiting ?? MARK_COLOR.question).toBe(C.wait)
})

test('wide columns share what the pane leaves, so every row of a table has the same widths', () => {
  const columns = sizeColumns(
    [{ name: 'id', width: 10 }, { name: 'title', width: 20, isWide: true }, { name: 'n', width: 4 }, { name: 'outcome', width: 18, isWide: true }],
    100,
  )
  // 100 − fixed 14 − bars 9 − frame 4 − gutter 2 = 71, split over two wide columns
  expect(columns.map(column => column.width)).toEqual([10, 35, 4, 35])
  expect(sizeColumns([{ name: 'title', width: 20, isWide: true }], 10)[0]?.width).toBe(20)
})
