/**
 * Amount expression helpers for the bookkeeping calc keypad.
 * Only left-to-right + / - over decimal strings; no eval/Function/float.
 */

import { addAmounts, quantizeAmount, subAmounts } from './decimal'

export type AmountKey =
  | '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
  | '.' | '+' | '-' | 'delete'

export type EvaluateOptions = {
  allowNegative?: boolean
  fractionDigits?: number
}

function isOperator(char: string): char is '+' | '-' {
  return char === '+' || char === '-'
}

/** Current number segment after the last binary operator (leading '-' stays in the first segment). */
export function currentNumberSegment(expression: string): string {
  if (!expression) return ''
  let lastOp = -1
  for (let i = 0; i < expression.length; i += 1) {
    const ch = expression[i]!
    if (!isOperator(ch)) continue
    // Leading unary minus for the first operand is not a binary operator.
    if (i === 0) continue
    lastOp = i
  }
  return lastOp === -1 ? expression : expression.slice(lastOp + 1)
}

export function stripTrailingOperators(expression: string): string {
  let expr = expression
  while (expr.length > 0 && isOperator(expr.slice(-1))) {
    if (expr === '-') break
    expr = expr.slice(0, -1)
  }
  return expr
}

/**
 * Append one keypad action to the expression buffer.
 */
export function appendAmountKey(
  expression: string,
  key: AmountKey,
  { allowNegative = true }: { allowNegative?: boolean } = {},
): string {
  if (key === 'delete') {
    return expression.slice(0, -1)
  }

  if (key === '.') {
    const segment = currentNumberSegment(expression)
    if (segment.includes('.')) return expression
    if (segment === '' || segment === '-') return `${expression}0.`
    return `${expression}.`
  }

  if (key === '+' || key === '-') {
    if (expression === '') {
      if (key === '-' && allowNegative) return '-'
      return expression
    }
    if (expression === '-') {
      return expression
    }
    const last = expression.slice(-1)
    if (isOperator(last)) {
      return `${expression.slice(0, -1)}${key}`
    }
    return `${expression}${key}`
  }

  // digit 0-9
  return `${expression}${key}`
}

/**
 * Seed the expression from a committed model value.
 * Zero placeholders start blank so the user can type a fresh amount.
 */
export function expressionFromModel(modelValue: string): string {
  const raw = String(modelValue ?? '').trim()
  if (!raw) return ''
  if (raw === '0' || raw === '0.' || /^0\.0+$/.test(raw)) return ''
  return raw
}

/**
 * Evaluate a simple + / - expression left to right using decimal strings.
 * Empty / incomplete expressions return ''.
 */
export function evaluateAmountExpression(
  expression: string,
  { allowNegative = true, fractionDigits = 2 }: EvaluateOptions = {},
): string {
  const expr = stripTrailingOperators(String(expression ?? '').trim())
  if (!expr || expr === '-') return ''

  let index = 0
  let leadingNegative = false
  if (expr[index] === '-') {
    leadingNegative = true
    index += 1
  } else if (expr[index] === '+') {
    index += 1
  }

  const readNumber = (): string | null => {
    let raw = ''
    while (index < expr.length && /[0-9.]/.test(expr[index]!)) {
      raw += expr[index]
      index += 1
    }
    if (!raw || raw === '.') return null
    if (raw.endsWith('.')) raw = raw.slice(0, -1)
    if (!raw) return null
    return raw
  }

  const first = readNumber()
  if (first == null) return ''

  let acc = leadingNegative ? `-${first}` : first

  while (index < expr.length) {
    const op = expr[index]
    if (op == null || !isOperator(op)) break
    index += 1
    const next = readNumber()
    if (next == null) break
    acc = op === '+' ? addAmounts(acc, next) : subAmounts(acc, next)
  }

  let result = quantizeAmount(acc, fractionDigits)
  if (!allowNegative && result.startsWith('-')) {
    result = quantizeAmount('0', fractionDigits)
  }
  return result
}
