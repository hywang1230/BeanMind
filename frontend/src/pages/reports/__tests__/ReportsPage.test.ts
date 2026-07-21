import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { reportsApi } from '../../../api/reports'
import MonthPicker from '../../../components/MonthPicker.vue'
import ReportsPage from '../ReportsPage.vue'

const back = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), back }),
}))
vi.mock('../../../api/reports', () => ({
  reportsApi: {
    getBalanceSheet: vi.fn(),
    getIncomeStatement: vi.fn(),
    getMonthlyCashflowTrend: vi.fn(),
    getDailyNetSpending: vi.fn(),
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

function calendarFor(month: string, options?: {
  empty?: boolean
  missing?: { date: string; currencies: string[] }[]
}) {
  const [y, m] = month.split('-').map(Number)
  const last = new Date(y!, m!, 0).getDate()
  const days = Array.from({ length: last }, (_, idx) => {
    const day = idx + 1
    const date = `${month}-${String(day).padStart(2, '0')}`
    if (!options?.empty && day === 15) {
      return {
        date,
        income: '0',
        expense: '-88.88',
        net_spending: '-88.88',
        has_activity: true,
      }
    }
    return {
      date,
      income: '0',
      expense: '0',
      net_spending: '0',
      has_activity: false,
    }
  })
  return {
    month,
    currency: 'CNY',
    days,
    missing_exchange_rates: options?.missing || [],
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
    vi.mocked(reportsApi.getDailyNetSpending).mockImplementation(async (params?: { month?: string }) => {
      const month = params?.month || '2026-07'
      return calendarFor(month)
    })
  })

  it('loads month summary, calendar and 12-month trend on first paint', async () => {
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(reportsApi.getBalanceSheet).toHaveBeenCalled()
    expect(reportsApi.getIncomeStatement).toHaveBeenCalled()
    expect(reportsApi.getMonthlyCashflowTrend).toHaveBeenCalledWith(
      expect.objectContaining({ end_month: expect.stringMatching(/^\d{4}-\d{2}$/) }),
    )
    expect(reportsApi.getDailyNetSpending).toHaveBeenCalledWith(
      expect.objectContaining({ month: expect.stringMatching(/^\d{4}-\d{2}$/) }),
    )
    expect(wrapper.text()).toContain('80.12')
    expect(wrapper.text()).toContain('0.12')
    expect(wrapper.text()).toContain('999.88')
    expect(wrapper.text()).toContain('每日收支')
    expect(wrapper.text()).toContain('近 12 个月收支趋势')
    expect(wrapper.find('[data-testid="daily-net-calendar"]').exists()).toBe(true)
    // 月份选择器在报表入口（月度复盘）之后、数据区之前
    const html = wrapper.html()
    expect(html.indexOf('月度复盘')).toBeGreaterThan(-1)
    expect(html.indexOf('data-testid="report-month-picker"')).toBeGreaterThan(html.indexOf('月度复盘'))
    expect(html.indexOf('data-testid="daily-net-calendar-card"')).toBeGreaterThan(
      html.indexOf('data-testid="report-month-picker"'),
    )
    expect(wrapper.find('[data-testid="cashflow-trend-chart"]').exists()).toBe(true)
  })

  it('refreshes trend and calendar when month changes', async () => {
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    const monthInput = wrapper.findComponent(MonthPicker)
    expect(monthInput.exists()).toBe(true)
    await monthInput.vm.$emit('update:modelValue', '2025-12')
    await flushPromises()
    expect(reportsApi.getMonthlyCashflowTrend).toHaveBeenCalledWith({ end_month: '2025-12' })
    expect(reportsApi.getDailyNetSpending).toHaveBeenCalledWith({ month: '2025-12' })
  })

  it('keeps summary visible when trend fails', async () => {
    vi.mocked(reportsApi.getMonthlyCashflowTrend).mockRejectedValue({ message: '趋势加载失败' })
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('80.12')
    expect(wrapper.text()).toContain('趋势加载失败')
    expect(wrapper.text()).toContain('重试趋势')
    expect(wrapper.find('[data-testid="daily-net-calendar"]').exists()).toBe(true)
  })

  it('keeps summary and trend visible when calendar fails first load', async () => {
    vi.mocked(reportsApi.getDailyNetSpending).mockRejectedValue({ message: '日历加载失败' })
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('80.12')
    expect(wrapper.find('[data-testid="cashflow-trend-chart"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="daily-net-calendar-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('重试日历')
  })

  it('retries calendar independently', async () => {
    vi.mocked(reportsApi.getDailyNetSpending)
      .mockRejectedValueOnce({ message: '日历暂时不可用' })
      .mockResolvedValueOnce(calendarFor('2026-07'))
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('日历暂时不可用')
    const retry = wrapper.findAll('button').find((btn) => btn.text().includes('重试日历'))
    expect(retry).toBeTruthy()
    await retry!.trigger('click')
    await flushPromises()
    expect(reportsApi.getDailyNetSpending).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="daily-net-calendar"]').exists()).toBe(true)
  })

  it('shows soft error while keeping previous calendar data', async () => {
    vi.mocked(reportsApi.getDailyNetSpending)
      .mockResolvedValueOnce(calendarFor('2026-07'))
      .mockRejectedValueOnce({ message: '刷新失败' })

    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="daily-net-calendar"]').exists()).toBe(true)

    const setupState = (wrapper.vm as any).$.setupState
    expect(setupState?.loadCalendar).toBeTypeOf('function')
    await setupState.loadCalendar()
    await flushPromises()
    expect(wrapper.find('[data-testid="daily-net-calendar"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="daily-net-calendar-soft-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('刷新失败')
    expect(wrapper.find('[data-testid="cashflow-trend-chart"]').exists()).toBe(true)
  })

  it('shows empty calendar state when month has no activity', async () => {
    vi.mocked(reportsApi.getDailyNetSpending).mockResolvedValue(calendarFor('2026-07', { empty: true }))
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="daily-net-calendar-empty"]').exists()).toBe(true)
  })

  it('discards stale calendar response after month switch', async () => {
    let resolveSlow!: (value: any) => void
    const slow = new Promise((resolve) => {
      resolveSlow = resolve
    })
    vi.mocked(reportsApi.getDailyNetSpending)
      .mockReturnValueOnce(slow as any)
      .mockResolvedValueOnce(calendarFor('2025-12'))

    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    const monthInput = wrapper.findComponent(MonthPicker)
    await monthInput.vm.$emit('update:modelValue', '2025-12')
    await flushPromises()
    expect(wrapper.find('[data-testid="daily-net-calendar"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('2025-12')

    // 晚到的旧月份响应不得覆盖
    resolveSlow(calendarFor('2026-07'))
    await flushPromises()
    expect(reportsApi.getDailyNetSpending).toHaveBeenCalledWith({ month: '2025-12' })
    // 仍展示 12 月数据：活动日 15 号 expense 88.88
    expect(wrapper.find('[data-testid="daily-net-calendar"]').exists()).toBe(true)
    expect(wrapper.find('button[data-date="2025-12-15"]').exists()).toBe(true)
    expect(wrapper.find('button[data-date="2026-07-15"]').exists()).toBe(false)
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

  it('shows calendar missing exchange rate warning', async () => {
    vi.mocked(reportsApi.getDailyNetSpending).mockResolvedValue(
      calendarFor('2026-07', { missing: [{ date: '2026-07-15', currencies: ['EUR'] }] }),
    )
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="daily-net-calendar-missing-rates"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('部分日期缺少汇率，日历不完整')
  })

  it('shows a retryable error for monthly summary', async () => {
    vi.mocked(reportsApi.getBalanceSheet).mockRejectedValue({ message: '报表加载失败' })
    vi.mocked(reportsApi.getIncomeStatement).mockRejectedValue({ message: '报表加载失败' })
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('报表加载失败')
    expect(wrapper.text()).toContain('重试')
  })

  it('shows secondary nav bar with back action', async () => {
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('报表')
    const nav = wrapper.find('.van-nav-bar')
    expect(nav.exists()).toBe(true)
    expect(nav.find('.van-nav-bar__left').exists()).toBe(true)
    await nav.find('.van-nav-bar__left').trigger('click')
    expect(back).toHaveBeenCalled()
  })

  it('links monthly review to reviews route with selected month', async () => {
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    const monthInput = wrapper.findComponent(MonthPicker)
    await monthInput.vm.$emit('update:modelValue', '2025-12')
    await flushPromises()
    const cell = wrapper.findAllComponents({ name: 'VanCell' }).find((c) => c.props('title') === '月度复盘')
    expect(cell).toBeTruthy()
    expect(cell!.props('to')).toBe('/reviews/2025-12')
  })

  it('shows report entry labels and summary section titles', async () => {
    const wrapper = mount(ReportsPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('查看截至某日的资产、负债与权益')
    expect(wrapper.text()).toContain('查看指定期间的收入、支出与结余')
    expect(wrapper.text()).toContain('总结本月收支并生成下月建议')
    expect(wrapper.text()).toContain('资产概览')
    expect(wrapper.text()).toContain('收支概览')
  })
})
