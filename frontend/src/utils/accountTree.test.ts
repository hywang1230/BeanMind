import { describe, expect, it } from 'vitest'
import { accountLeafLabel, accountShortLabel } from './accountTree'

const ledger = [
  'Expenses:JT-家庭:其他',
  'Expenses:JT-交通:其他',
  'Expenses:JT-家庭:电费',
  'Expenses:JT-交通:电费',
  'Expenses:FS-服饰:衣服',
  'Assets:ZJ-资金:现金',
  'Expenses:QT-其他',
]

describe('accountShortLabel', () => {
  it('shows leaf only for unique non-其他 names', () => {
    expect(accountShortLabel('Expenses:FS-服饰:衣服', ledger)).toBe('衣服')
    expect(accountShortLabel('Assets:ZJ-资金:现金', ledger)).toBe('现金')
  })

  it('includes parent when leaf is 其他', () => {
    expect(accountShortLabel('Expenses:JT-家庭:其他', ledger)).toBe('JT-家庭:其他')
    expect(accountShortLabel('Expenses:JT-交通:其他', ledger)).toBe('JT-交通:其他')
  })

  it('includes parent when leaf collides across accounts', () => {
    expect(accountShortLabel('Expenses:JT-家庭:电费', ledger)).toBe('JT-家庭:电费')
    expect(accountShortLabel('Expenses:JT-交通:电费', ledger)).toBe('JT-交通:电费')
  })

  it('keeps top-level and QT-其他 readable', () => {
    expect(accountShortLabel('Expenses', ledger)).toBe('Expenses')
    expect(accountShortLabel('Expenses:QT-其他', ledger)).toBe('QT-其他')
  })

  it('falls back to parent for 其他 without full name list', () => {
    expect(accountShortLabel('Expenses:YL-娱乐:其他')).toBe('YL-娱乐:其他')
  })
})

describe('accountLeafLabel', () => {
  it('returns last segment', () => {
    expect(accountLeafLabel('Expenses:JT-家庭:其他')).toBe('其他')
  })
})
