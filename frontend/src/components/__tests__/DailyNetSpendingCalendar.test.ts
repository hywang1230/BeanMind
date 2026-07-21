import { mount } from '@vue/test-utils'
import Vant from 'vant'
import { describe, expect, it, vi } from 'vitest'

import DailyNetSpendingCalendar from '../DailyNetSpendingCalendar.vue'
import type { DailyNetSpendingDay } from '../../api/reports'

function buildMonth(month: string, overrides: Record<string, Partial<DailyNetSpendingDay>> = {}): DailyNetSpendingDay[] {
  const [y, m] = month.split('-').map(Number)
  const last = new Date(y!, m!, 0).getDate()
  const days: DailyNetSpendingDay[] = []
  for (let d = 1; d <= last; d += 1) {
    const date = `${month}-${String(d).padStart(2, '0')}`
    days.push({
      date,
      income: '0',
      expense: '0',
      net_spending: '0',
      has_activity: false,
      ...(overrides[date] || {}),
    })
  }
  return days
}

describe('DailyNetSpendingCalendar', () => {
  it('uses Monday-first grid and leading placeholders', () => {
    // 2025-01-01 is Wednesday -> 2 placeholders before day 1
    const days = buildMonth('2025-01', {
      '2025-01-02': { has_activity: true, expense: '-10', net_spending: '-10' },
    })
    const wrapper = mount(DailyNetSpendingCalendar, {
      props: { days, month: '2025-01', currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    const placeholders = wrapper.findAll('.day-cell.placeholder')
    expect(placeholders.length).toBe(2)
    expect(wrapper.text()).toContain('一')
    expect(wrapper.text()).toContain('日')
    expect(wrapper.find('[data-testid="daily-net-calendar-grid"]').exists()).toBe(true)
  })

  it('defaults to today in current month and shows detail decimal amounts', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-01-16T12:00:00'))
    const days = buildMonth('2025-01', {
      '2025-01-15': {
        has_activity: true,
        income: '10000.125',
        expense: '0',
        net_spending: '10000.125',
      },
      '2025-01-16': {
        has_activity: true,
        income: '0',
        expense: '-50.505',
        net_spending: '-50.505',
      },
    })
    const wrapper = mount(DailyNetSpendingCalendar, {
      props: { days, month: '2025-01', currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    const detail = wrapper.get('[data-testid="daily-net-calendar-detail"]')
    expect(detail.text()).toContain('2025-01-16')
    expect(detail.text()).toContain('-50.51')
    const selected = wrapper.find('button.day-cell.active')
    expect(selected.attributes('data-date')).toBe('2025-01-16')
    expect(selected.attributes('aria-label')).toContain('净结余')
    expect(getComputedStyle(selected.element).getPropertyValue('background') || selected.attributes('style')).toBeTruthy()
    vi.useRealTimers()
  })

  it('defaults to last active day for history months', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-21T12:00:00'))
    const days = buildMonth('2025-03', {
      '2025-03-05': { has_activity: true, expense: '-3', net_spending: '-3' },
      '2025-03-20': { has_activity: true, expense: '-8', net_spending: '-8' },
    })
    const wrapper = mount(DailyNetSpendingCalendar, {
      props: { days, month: '2025-03', currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    expect(wrapper.find('button.day-cell.active').attributes('data-date')).toBe('2025-03-20')
    vi.useRealTimers()
  })

  it('renders empty state without forced selection when month has no activity', () => {
    const days = buildMonth('2024-02')
    const wrapper = mount(DailyNetSpendingCalendar, {
      props: { days, month: '2024-02', currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    expect(wrapper.find('[data-testid="daily-net-calendar-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="daily-net-calendar-grid"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="daily-net-calendar-detail"]').exists()).toBe(false)
  })

  it('keeps zero-cancel activity visible and distinguishable from inactive days', async () => {
    const days = buildMonth('2025-05', {
      '2025-05-10': {
        has_activity: true,
        income: '20',
        expense: '-20',
        net_spending: '0',
      },
    })
    const wrapper = mount(DailyNetSpendingCalendar, {
      props: { days, month: '2025-05', currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    const zeroDay = wrapper.find('button[data-date="2025-05-10"]')
    expect(zeroDay.classes()).toContain('zero')
    expect(zeroDay.text()).toContain('0')
    expect(wrapper.text()).toContain('当日有收支分录，但合计恰好为零')
    const inactive = wrapper.find('button[data-date="2025-05-01"]')
    expect(inactive.classes()).toContain('inactive')
    expect(inactive.text().replace(/\s/g, '')).toBe('1')
  })

  it('supports keyboard and click day selection', async () => {
    const days = buildMonth('2025-06', {
      '2025-06-10': { has_activity: true, expense: '-10', net_spending: '-10' },
      '2025-06-11': { has_activity: true, expense: '-20', net_spending: '-20' },
      '2025-06-18': { has_activity: true, income: '5', net_spending: '5' },
    })
    const wrapper = mount(DailyNetSpendingCalendar, {
      props: { days, month: '2025-06', currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    const day10 = wrapper.get('button[data-date="2025-06-10"]')
    await day10.trigger('click')
    expect(wrapper.get('[data-testid="daily-net-calendar-detail"]').text()).toContain('2025-06-10')
    await day10.trigger('keydown.right')
    expect(wrapper.get('[data-testid="daily-net-calendar-detail"]').text()).toContain('2025-06-11')
    await wrapper.get('button[data-date="2025-06-11"]').trigger('keydown.down')
    expect(wrapper.get('[data-testid="daily-net-calendar-detail"]').text()).toContain('2025-06-18')
  })

  it('compresses extreme positive values with sqrt intensity', () => {
    const days = buildMonth('2025-07', {
      '2025-07-01': { has_activity: true, expense: '-10000', net_spending: '-10000' },
      '2025-07-02': { has_activity: true, expense: '-100', net_spending: '-100' },
      '2025-07-03': { has_activity: true, income: '10000', net_spending: '10000' },
      '2025-07-04': { has_activity: true, income: '100', net_spending: '100' },
    })
    const wrapper = mount(DailyNetSpendingCalendar, {
      props: { days, month: '2025-07', currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    const vm = wrapper.vm as any
    // days: 01/02 支出日(负)，03/04 收入日(正)
    const extremeNeg = vm.intensityPercent(days[0]) as number
    const smallNeg = vm.intensityPercent(days[1]) as number
    const extremePos = vm.intensityPercent(days[2]) as number
    const smallPos = vm.intensityPercent(days[3]) as number
    expect(extremePos).toBeGreaterThan(smallPos)
    expect(extremeNeg).toBeGreaterThan(smallNeg)
    // 线性约 1%，平方根后应明显大于线性比例
    expect(smallPos / extremePos).toBeGreaterThan(0.05)
    expect(wrapper.get('button[data-date="2025-07-01"]').attributes('style')).toContain('--bm-expense')
    expect(wrapper.get('button[data-date="2025-07-03"]').attributes('style')).toContain('--bm-income')
  })

  it('marks selected day when exchange rates are missing', async () => {
    const days = buildMonth('2025-08', {
      '2025-08-08': { has_activity: true, expense: '-12.34', net_spending: '-12.34' },
    })
    const wrapper = mount(DailyNetSpendingCalendar, {
      props: {
        days,
        month: '2025-08',
        currency: 'CNY',
        missingExchangeRates: [{ date: '2025-08-08', currencies: ['EUR', 'USD'] }],
      },
      global: { plugins: [Vant] },
    })
    expect(wrapper.get('[data-testid="daily-net-calendar-missing-day"]').text()).toContain('EUR')
    expect(wrapper.text()).toContain('结果不完整')
  })
})
