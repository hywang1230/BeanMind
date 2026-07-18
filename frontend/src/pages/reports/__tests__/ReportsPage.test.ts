import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { reportsApi } from '../../../api/reports'
import MonthPicker from '../../../components/MonthPicker.vue'
import ReportsPage from '../ReportsPage.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('../../../api/reports', () => ({
  reportsApi: {
    getBalanceSheet: vi.fn(),
    getIncomeStatement: vi.fn(),
    getMonthlyCashflowTrend: vi.fn(),
  },
}))

function zeroTrend(endMonth = '2026-07') {
  const parts = endMonth.split('-')
  const y = Number(parts[0] || '2026')
  const m = Number(parts[1] || '7')
  const points: { month: string; income: string; expense: string; net_income: string }[] = []
  for (let i = 11; i >= 0; i -= 1) {
    const date = new Date(y, m - 1 - i, 1)
    const month = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
    points.push({ month, income: '0', expense: '0', net_income: '0' })
  }
  return {
    start_month: points[0]!.month,
    end_month: endMonth,
    currency: 'CNY',
    points,
    missing_exchange_rates: [] as { month: string; currencies: string[] }[],
  }
}

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(reportsApi.getBalanceSheet).mockResolvedValue({
      as_of_date: '2026-07-31',
      net_worth_cny: '999.876543212',
      total_assets_cny: '1000',
      total_liabilities_cny: '0.123456789',
    } as any)
    vi.mocked(reportsApi.getIncomeStatement).mockResolvedValue({
      start_date: '2026-07-01',
      end_date: '2026-07-31',
      total_income_cny: '80.123456788',
      total_expenses_cny: '0.123456789',
      net_profit_cny: '80',
    } as any)
    vi.mocked(reportsApi.getMonthlyCashflowTrend).mockResolvedValue({
      ...zeroTrend('2026-07'),
      points: zeroTrend('2026-07').points.map((point, index) =>
        index === 11
          ? { ...point, income: '1200.50', expense: '300.25', net_income: '900.25' }
          : point,
      ),
    })
  })

  it('loads month summary and 12-month trend on first paint', async () => {
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(reportsApi.getBalanceSheet).toHaveBeenCalled()
    expect(reportsApi.getIncomeStatement).toHaveBeenCalled()
    expect(reportsApi.getMonthlyCashflowTrend).toHaveBeenCalledWith(
      expect.objectContaining({ end_month: expect.stringMatching(/^\d{4}-\d{2}$/) }),
    )
    expect(wrapper.text()).toContain('80.12')
    expect(wrapper.text()).toContain('0.12')
    expect(wrapper.text()).toContain('999.88')
    expect(wrapper.text()).toContain('近 12 个月收支趋势')
    expect(wrapper.find('[data-testid="cashflow-trend-chart"]').exists()).toBe(true)
  })

  it('refreshes trend when month changes', async () => {
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    const monthInput = wrapper.findComponent(MonthPicker)
    expect(monthInput.exists()).toBe(true)
    await monthInput.vm.$emit('update:modelValue', '2025-12')
    await flushPromises()
    expect(reportsApi.getMonthlyCashflowTrend).toHaveBeenCalledWith({ end_month: '2025-12' })
  })

  it('keeps summary visible when trend fails', async () => {
    vi.mocked(reportsApi.getMonthlyCashflowTrend).mockRejectedValue({ message: '趋势加载失败' })
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('80.12')
    expect(wrapper.text()).toContain('趋势加载失败')
    expect(wrapper.text()).toContain('重试趋势')
  })

  it('retries trend independently', async () => {
    vi.mocked(reportsApi.getMonthlyCashflowTrend)
      .mockRejectedValueOnce({ message: '趋势暂时不可用' })
      .mockResolvedValueOnce({
        ...zeroTrend('2026-07'),
        points: zeroTrend('2026-07').points.map((point, index) =>
          index === 11
            ? { ...point, income: '10', expense: '2', net_income: '8' }
            : point,
        ),
      })
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('趋势暂时不可用')
    const retry = wrapper.findAll('button').find((btn) => btn.text().includes('重试趋势'))
    expect(retry).toBeTruthy()
    await retry!.trigger('click')
    await flushPromises()
    expect(reportsApi.getMonthlyCashflowTrend).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="cashflow-trend-chart"]').exists()).toBe(true)
  })

  it('shows empty trend state when all months are zero', async () => {
    vi.mocked(reportsApi.getMonthlyCashflowTrend).mockResolvedValue(zeroTrend('2026-07'))
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="cashflow-trend-empty"]').exists()).toBe(true)
  })

  it('shows missing exchange rate warning without hiding the chart', async () => {
    const trend = zeroTrend('2026-07')
    trend.missing_exchange_rates = [{ month: '2026-02', currencies: ['USD'] }]
    trend.points = trend.points.map((point, index) =>
      index === 11
        ? { ...point, income: '100', expense: '20', net_income: '80' }
        : point,
    )
    vi.mocked(reportsApi.getMonthlyCashflowTrend).mockResolvedValue(trend)
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="cashflow-trend-missing-rates"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('部分月份缺少汇率，趋势不完整')
    expect(wrapper.find('[data-testid="cashflow-trend-chart"]').exists()).toBe(true)
  })

  it('shows a retryable error for monthly summary', async () => {
    vi.mocked(reportsApi.getBalanceSheet).mockRejectedValue({ message: '报表加载失败' })
    vi.mocked(reportsApi.getIncomeStatement).mockRejectedValue({ message: '报表加载失败' })
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('报表加载失败')
    expect(wrapper.text()).toContain('重试')
  })
})
