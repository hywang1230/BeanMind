import { describe, expect, it } from 'vitest'

import {
  appendAmountKey,
  evaluateAmountExpression,
  expressionFromModel,
  stripTrailingOperators,
} from './amountExpression'

describe('amountExpression', () => {
  it('appends digits and a single decimal point per segment', () => {
    let expr = ''
    for (const key of ['1', '2', '.', '5', '.'] as const) {
      expr = appendAmountKey(expr, key)
    }
    expect(expr).toBe('12.5')
  })

  it('replaces consecutive operators and evaluates left to right', () => {
    let expr = ''
    for (const key of ['1', '2', '+', '-', '3'] as const) {
      expr = appendAmountKey(expr, key)
    }
    expect(expr).toBe('12-3')
    expect(evaluateAmountExpression(expr)).toBe('9.00')
  })

  it('evaluates simple addition and subtraction', () => {
    expect(evaluateAmountExpression('12+3')).toBe('15.00')
    expect(evaluateAmountExpression('12.5-0.5')).toBe('12.00')
  })

  it('avoids binary float artifacts for 0.1+0.2', () => {
    expect(evaluateAmountExpression('0.1+0.2')).toBe('0.30')
  })

  it('strips trailing operators before evaluation', () => {
    expect(stripTrailingOperators('12+')).toBe('12')
    expect(evaluateAmountExpression('12+')).toBe('12.00')
  })

  it('delete removes the last character', () => {
    expect(appendAmountKey('12+3', 'delete')).toBe('12+')
    expect(appendAmountKey('12+', 'delete')).toBe('12')
  })

  it('clamps negative results when allowNegative is false', () => {
    expect(evaluateAmountExpression('1-5', { allowNegative: false })).toBe('0.00')
  })

  it('keeps negative results when allowNegative is true', () => {
    expect(evaluateAmountExpression('1-5', { allowNegative: true })).toBe('-4.00')
  })

  it('supports negative amounts by default (main parity)', () => {
    expect(appendAmountKey('', '-')).toBe('-')
    expect(evaluateAmountExpression('1-5')).toBe('-4.00')
    expect(evaluateAmountExpression('-4+1')).toBe('-3.00')
  })

  it('allows leading minus only when negatives are permitted', () => {
    expect(appendAmountKey('', '-', { allowNegative: false })).toBe('')
    expect(appendAmountKey('', '-', { allowNegative: true })).toBe('-')
    expect(evaluateAmountExpression('-4+1', { allowNegative: true })).toBe('-3.00')
  })

  it('returns empty string for blank expressions', () => {
    expect(evaluateAmountExpression('')).toBe('')
    expect(evaluateAmountExpression('+')).toBe('')
    expect(evaluateAmountExpression('-')).toBe('')
  })

  it('seeds expression from model and blanks zero placeholders', () => {
    expect(expressionFromModel('30.00')).toBe('30.00')
    expect(expressionFromModel('0')).toBe('')
    expect(expressionFromModel('0.00')).toBe('')
    expect(expressionFromModel('')).toBe('')
  })
})
