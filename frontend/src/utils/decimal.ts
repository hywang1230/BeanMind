/**
 * Decimal string arithmetic for money amounts.
 * No number/float accumulation; no toFixed for financial math.
 */

export type DecimalParts = {
  negative: boolean
  digits: string // integer digits representing value * 10^scale
  scale: number
}

function strip(value: string): string {
  return String(value ?? '').trim().replace(/,/g, '')
}

export function isValidAmount(value: string, { allowNegative = true, allowZero = true } = {}): boolean {
  const raw = strip(value)
  if (!raw) return false
  if (!/^-?(?:0|[1-9]\d*)(?:\.\d+)?$/.test(raw)) return false
  if (!allowNegative && raw.startsWith('-')) return false
  if (!allowZero && isZero(raw)) return false
  return true
}

export function normalizeAmount(value: string): string {
  const raw = strip(value)
  if (!raw) return ''
  let sign = ''
  let body = raw
  if (body.startsWith('-')) {
    sign = '-'
    body = body.slice(1)
  }
  body = body.replace(/[^\d.]/g, '')
  const firstDot = body.indexOf('.')
  if (firstDot !== -1) {
    body = body.slice(0, firstDot + 1) + body.slice(firstDot + 1).replace(/\./g, '')
  }
  if (body.includes('.')) {
    const parts = body.split('.')
    const i = parts[0] ?? '0'
    const f = parts[1] ?? ''
    const intPart = i.replace(/^0+(?=\d)/, '') || '0'
    body = `${intPart}.${f}`
  } else if (body !== '') {
    body = body.replace(/^0+(?=\d)/, '') || '0'
  }
  if (body === '' || body === '.') return sign ? '-' : ''
  if (body === '0' || body === '0.' || /^0\.0*$/.test(body)) {
    return body.endsWith('.') ? '0.' : body.includes('.') ? body : '0'
  }
  return sign + body
}

/** Input-friendly normalization: strip illegal chars, keep trailing dot. */
export function normalizeAmountInput(value: string): string {
  const raw = strip(value)
  if (!raw) return ''
  let sign = ''
  let body = raw
  if (body.startsWith('-')) {
    sign = '-'
    body = body.slice(1)
  }
  body = body.replace(/[^\d.]/g, '')
  const firstDot = body.indexOf('.')
  if (firstDot !== -1) {
    body = body.slice(0, firstDot + 1) + body.slice(firstDot + 1).replace(/\./g, '')
  }
  if (body.startsWith('.')) body = `0${body}`
  if (/^0\d/.test(body) && !body.startsWith('0.')) {
    body = body.replace(/^0+/, '') || '0'
  }
  return sign + body
}

export function parseDecimal(value: string): DecimalParts {
  const normalized = normalizeAmount(value)
  if (!normalized || normalized === '-' || normalized === '.' || normalized === '-.') {
    throw new Error(`非法金额: ${value}`)
  }
  const negative = normalized.startsWith('-')
  const body = negative ? normalized.slice(1) : normalized
  const [intPartRaw, fracPartRaw = ''] = body.split('.')
  const intPart = intPartRaw || '0'
  const fracPart = fracPartRaw
  const digits = `${intPart}${fracPart}`.replace(/^0+(?=\d)/, '') || '0'
  return { negative: digits === '0' ? false : negative, digits, scale: fracPart.length }
}

function align(a: DecimalParts, b: DecimalParts): { aInt: bigint; bInt: bigint; scale: number; aNeg: boolean; bNeg: boolean } {
  const scale = Math.max(a.scale, b.scale)
  const aInt = BigInt(a.digits) * 10n ** BigInt(scale - a.scale)
  const bInt = BigInt(b.digits) * 10n ** BigInt(scale - b.scale)
  return { aInt, bInt, scale, aNeg: a.negative, bNeg: b.negative }
}

function signed(int: bigint, neg: boolean): bigint {
  return neg ? -int : int
}

function fromSigned(value: bigint, scale: number): string {
  const negative = value < 0n
  let abs = value < 0n ? -value : value
  let digits = abs.toString()
  if (scale === 0) return negative ? `-${digits}` : digits
  if (digits.length <= scale) {
    digits = digits.padStart(scale + 1, '0')
  }
  const cut = digits.length - scale
  const intPart = digits.slice(0, cut)
  let frac = digits.slice(cut)
  frac = frac.replace(/0+$/, '')
  const body = frac ? `${intPart}.${frac}` : intPart
  if (body === '0' || body === '') return '0'
  return negative ? `-${body}` : body
}

export function addAmounts(...values: string[]): string {
  if (values.length === 0) return '0'
  let acc = parseDecimal(values[0] || '0')
  for (let i = 1; i < values.length; i += 1) {
    const next = parseDecimal(values[i] || '0')
    const { aInt, bInt, scale, aNeg, bNeg } = align(acc, next)
    const sum = signed(aInt, aNeg) + signed(bInt, bNeg)
    acc = parseDecimal(fromSigned(sum, scale))
  }
  return fromSigned(signed(BigInt(acc.digits), acc.negative), acc.scale)
}

export function subAmounts(left: string, right: string): string {
  return addAmounts(left, negateAmount(right))
}

export function compareAmount(left: string, right: string): number {
  const l = parseDecimal(left)
  const r = parseDecimal(right)
  const { aInt, bInt, aNeg, bNeg } = align(l, r)
  const diff = signed(aInt, aNeg) - signed(bInt, bNeg)
  if (diff === 0n) return 0
  return diff > 0n ? 1 : -1
}

export function isZero(value: string): boolean {
  try {
    const p = parseDecimal(value)
    return p.digits === '0'
  } catch {
    return false
  }
}

export function isPositive(value: string): boolean {
  try {
    const p = parseDecimal(value)
    return !p.negative && p.digits !== '0'
  } catch {
    return false
  }
}

export function absAmount(value: string): string {
  const p = parseDecimal(value)
  return fromSigned(BigInt(p.digits), p.scale)
}

export function negateAmount(value: string): string {
  const p = parseDecimal(value)
  if (p.digits === '0') return '0'
  return p.negative ? fromSigned(BigInt(p.digits), p.scale) : `-${fromSigned(BigInt(p.digits), p.scale)}`
}

/**
 * Quantize amount to fixed fractional scale with half-up rounding.
 * Keeps trailing zeros for stable API/posting equality.
 */
export function quantizeAmount(value: string, fractionDigits = 2): string {
  const p = parseDecimal(value)
  const sign = p.negative ? '-' : ''
  let digits = p.digits
  let scale = p.scale

  if (scale < fractionDigits) {
    digits = digits + '0'.repeat(fractionDigits - scale)
    scale = fractionDigits
  } else if (scale > fractionDigits) {
    const drop = scale - fractionDigits
    const head = digits.slice(0, Math.max(0, digits.length - drop)) || '0'
    const removed = digits.slice(Math.max(0, digits.length - drop))
    const roundUp = removed.length > 0 && removed[0]! >= '5'
    let intVal = BigInt(head || '0')
    if (roundUp) intVal += 1n
    digits = intVal.toString()
    scale = fractionDigits
  }

  if (fractionDigits === 0) {
    return digits === '0' ? '0' : sign + digits
  }
  if (digits.length <= fractionDigits) digits = digits.padStart(fractionDigits + 1, '0')
  const cut = digits.length - fractionDigits
  const body = `${digits.slice(0, cut)}.${digits.slice(cut)}`
  return digits.replace(/0/g, '') === '' ? (fractionDigits ? `0.${'0'.repeat(fractionDigits)}` : '0') : sign + body
}

/** Display helper: half-up round then fixed fraction digits. */
export function formatAmountDisplay(value: string, fractionDigits = 2): string {
  try {
    return quantizeAmount(value, fractionDigits)
  } catch {
    return value
  }
}
