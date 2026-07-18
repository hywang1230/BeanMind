import { mount } from '@vue/test-utils'
import Vant from 'vant'
import { describe, expect, it } from 'vitest'

import MonthlyCashflowTrendChart from '../MonthlyCashflowTrendChart.vue'
import type { MonthlyCashflowPoint } from '../../api/reports'

function makePoints(overrides: Partial<Record<string, Partial<MonthlyCashflowPoint>>> = {}): MonthlyCashflowPoint[] {
  const months = [
    '2025-08', '2025-09', '2025-10', '2025-11', '2025-12', '2026-01',
    '2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07',
  ]
  return months.map((month) => ({
    month,
    income: '0',
    expense: '0',
    net_income: '0',
    ...(overrides[month] || {}),
  }))
}

describe('MonthlyCashflowTrendChart', () => {
  it('defaults to the latest month and shows decimal string amounts', async () => {
    const points = makePoints({
      '2026-07': {
        income: '12000.125',
        expense: '6800.505',
        net_income: '5199.62',
      },
    })
    const wrapper = mount(MonthlyCashflowTrendChart, {
      props: { points, currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    expect(wrapper.text()).toContain('2026-07')
    expect(wrapper.text()).toContain('12000.13')
    expect(wrapper.text()).toContain('6800.51')
    expect(wrapper.find('[role="img"]').attributes('aria-label')).toContain('2026-07')
  })

  it('supports keyboard and click month selection', async () => {
    const points = makePoints({
      '2026-06': { income: '100', expense: '40', net_income: '60' },
      '2026-07': { income: '200', expense: '50', net_income: '150' },
    })
    const wrapper = mount(MonthlyCashflowTrendChart, {
      props: { points, currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    const buttons = wrapper.findAll('button.month-hit')
    expect(buttons.length).toBe(12)
    await buttons[10]!.trigger('click')
    expect(wrapper.get('[data-testid="cashflow-trend-detail"]').text()).toContain('2026-06')
    const last = buttons[11]!
    await last.trigger('focus')
    await last.trigger('keydown.left')
    expect(wrapper.text()).toMatch(/2026-0[67]/)
  })

  it('renders empty state when all months are zero', () => {
    const wrapper = mount(MonthlyCashflowTrendChart, {
      props: { points: makePoints(), currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    expect(wrapper.find('[data-testid="cashflow-trend-empty"]').exists()).toBe(true)
    expect(wrapper.find('svg.chart-svg').exists()).toBe(false)
  })

  it('keeps zero baseline within chart bounds for negative net income', () => {
    const points = makePoints({
      '2026-07': { income: '10', expense: '100', net_income: '-90' },
    })
    const wrapper = mount(MonthlyCashflowTrendChart, {
      props: { points, currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    const bounds = (wrapper.vm as any).bounds as { min: number; max: number }
    expect(bounds.min).toBeLessThan(0)
    expect(bounds.max).toBeGreaterThan(0)
    expect(wrapper.find('line.axis-line').exists()).toBe(true)
  })

  it('keeps small months visible after all-zero months under large peaks', () => {
    const points = makePoints({
      '2026-02': { income: '106113', expense: '17211', net_income: '88901' },
      '2026-05': { income: '0', expense: '0', net_income: '0' },
      '2026-06': { income: '0', expense: '0', net_income: '0' },
      '2026-07': { income: '1000', expense: '110', net_income: '890' },
    })
    const wrapper = mount(MonthlyCashflowTrendChart, {
      props: { points, currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    const vm = wrapper.vm as any
    const zeroY = vm.zeroY as number
    const incomeY = vm.yFromValue(1000) as number
    const expenseY = vm.yFromValue(110) as number
    const netY = vm.yFromValue(890) as number
    // 小额不应再贴死零轴；收入/净收入应明显高于支出
    expect(zeroY - incomeY).toBeGreaterThan(8)
    expect(zeroY - netY).toBeGreaterThan(6)
    expect(zeroY - expenseY).toBeGreaterThan(2)
    expect(incomeY).toBeLessThan(netY)
    expect(netY).toBeLessThan(expenseY)
    expect(expenseY).toBeLessThan(zeroY)
  })
})
