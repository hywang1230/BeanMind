import { describe, expect, it } from 'vitest'

import {
  addAmounts,
  formatAmountDisplay,
  isValidAmount,
  negateAmount,
  normalizeAmountInput,
  quantizeAmount,
  subAmounts,
} from './decimal'

describe('decimal utils', () => {
  it('normalizes progressive money input without Number conversion', () => {
    expect(normalizeAmountInput('123.456789123456789x')).toBe('123.456789123456789')
    expect(normalizeAmountInput('01.2')).toBe('1.2')
    expect(normalizeAmountInput('.5')).toBe('0.5')
  })

  it('adds and subtracts high precision decimal strings', () => {
    expect(addAmounts('0.1', '0.2')).toBe('0.3')
    expect(addAmounts('1000.00', '-0.12')).toBe('999.88')
    expect(subAmounts('1000.00', '0.12')).toBe('999.88')
    expect(subAmounts('10.00', '10.00')).toBe('0')
    expect(negateAmount('30.00')).toBe('-30')
  })

  it('quantizes with half-up rounding and fixed scale', () => {
    expect(quantizeAmount('30', 2)).toBe('30.00')
    expect(quantizeAmount('-0.3', 2)).toBe('-0.30')
    expect(quantizeAmount('999.876543212', 2)).toBe('999.88')
    expect(quantizeAmount('0.125', 2)).toBe('0.13')
    expect(quantizeAmount('0.124', 2)).toBe('0.12')
  })

  it('formats display amounts with half-up rounding', () => {
    expect(formatAmountDisplay('80.123456788')).toBe('80.12')
    expect(formatAmountDisplay('0.123456789')).toBe('0.12')
    expect(formatAmountDisplay('999.876543212')).toBe('999.88')
  })

  it('validates amount strings', () => {
    expect(isValidAmount('0', { allowZero: false })).toBe(false)
    expect(isValidAmount('-1', { allowNegative: false })).toBe(false)
    expect(isValidAmount('12.34')).toBe(true)
  })
})
