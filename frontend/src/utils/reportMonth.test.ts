import { afterEach, describe, expect, it, vi } from 'vitest'
import { currentMonth, monthEnd, monthStart, reportMonth } from './reportMonth'

describe('report months', () => {
  afterEach(() => vi.useRealTimers())

  it.each([
    ['2024-02', '2024-02-29'],
    ['2026-02', '2026-02-28'],
    ['2026-04', '2026-04-30'],
    ['2026-12', '2026-12-31'],
    ['2100-02', '2100-02-28'],
  ])('uses the full calendar month %s', (month, end) => {
    expect(monthStart(month)).toBe(`${month}-01`)
    expect(monthEnd(month)).toBe(end)
  })

  it('uses the local month at a UTC date boundary and restores legacy dates', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 8, 1, 0, 1))
    expect(currentMonth()).toBe('2026-09')
    expect(reportMonth(undefined)).toBe('2026-09')
    expect(reportMonth('2026-13')).toBe('2026-09')
    expect(reportMonth('2024-02-15')).toBe('2024-02')
  })
})
