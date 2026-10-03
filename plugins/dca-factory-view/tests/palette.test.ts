import { expect, test } from 'claude-code/testing'

import { C, MARK_COLOR, applyPalette } from '../hooks/components'

test('a light theme draws on the site\'s paper, a dark one on its deep navy — the marks follow', () => {
  applyPalette(true)
  expect([C.bg, C.text, C.accent]).toEqual(['#f7f6f3', '#1c2433', '#0d6b70'])
  expect(MARK_COLOR.done).toBe(C.done)
  applyPalette(false)
  expect([C.bg, C.text, C.accent]).toEqual(['#171d29', '#e8eaf0', '#148f96'])
  expect(MARK_COLOR.waiting ?? MARK_COLOR.question).toBe(C.wait)
})
