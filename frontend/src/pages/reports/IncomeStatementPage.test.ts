import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MonthPicker from '../../components/MonthPicker.vue'

import { reportsApi } from '../../api/reports'
import IncomeStatementPage from './IncomeStatementPage.vue'

const replace = vi.fn()
const push = vi.fn()
const route = reactive<{ query: Record<string, string> }>({ query: { start_date: '2026-07-01', end_date: '2026-07-31' } })
vi.mock('vue-router', () => ({
  useRouter: () => ({ back: vi.fn(), replace, push }),
  useRoute: () => route,
}))
vi.mock('../../api/reports', () => ({
  reportsApi: { getIncomeStatement: vi.fn() },
}))

describe('IncomeStatementPage', () => {
  const wrappers: Array<ReturnType<typeof mount>> = []
  function mountPage() {
    const wrapper = mount(IncomeStatementPage, { global: { plugins: [Vant] } })
    wrappers.push(wrapper)
    return wrapper
  }
  beforeEach(() => {
    vi.clearAllMocks()
    route.query = { start_date: '2026-07-01', end_date: '2026-07-31' }
  })
  afterEach(() => wrappers.splice(0).forEach(wrapper => wrapper.unmount()))

  it('loads income statement by closed date range and shows net profit', async () => {
    vi.mocked(reportsApi.getIncomeStatement).mockResolvedValue({
      start_date: '2026-07-01',
      end_date: '2026-07-31',
      income: {
        name: 'Income',
        type: 'Income',
        total_cny: '1000.00',
        totals_by_currency: { CNY: '1000.00' },
        items: [
          {
            account: 'Income:Salary',
            display_name: 'Salary',
            amounts: { CNY: '1000.00' },
            total_cny: '1000.00',
            percentage: '65.21739130434783',
            depth: 1,
            children: [],
          },
        ],
      },
      expenses: {
        name: 'Expenses',
        type: 'Expenses',
        total_cny: '0.12',
        totals_by_currency: { CNY: '0.12' },
        items: [],
      },
      total_income_cny: '1000.00',
      total_expenses_cny: '0.12',
      net_profit_cny: '999.88',
      exchange_rates: { CNY: '1' },
      currencies: ['CNY'],
    })

    const wrapper = mountPage()
    await flushPromises()
    expect(reportsApi.getIncomeStatement).toHaveBeenCalledWith({
      start_date: '2026-07-01',
      end_date: '2026-07-31',
    })
    expect(wrapper.text()).toContain('999.88')
    expect(wrapper.text()).toContain('收入')
    expect(wrapper.text()).toContain('支出')
    expect(wrapper.text()).toContain('65.22%')
    expect(wrapper.text()).not.toContain('65.21739130434783')
    // Draft filters do not change the interval used by the displayed report's drilldown.
    await wrapper.findAllComponents(MonthPicker)[1]!.vm.$emit('update:modelValue', '2026-08')
    await wrapper.find('.tree-section .van-cell').trigger('click')
    expect(push).toHaveBeenCalledWith({
      path: '/reports/account-detail',
      query: { account: 'Income:Salary', start_date: '2026-07-01', end_date: '2026-07-31' },
    })
  })

  it('shows error state for dirty projection or missing rates', async () => {
    vi.mocked(reportsApi.getIncomeStatement).mockRejectedValue({ message: '投影未就绪' })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('投影未就绪')
  })

  it('expands legacy mid-month dates and restores month filters on navigation', async () => {
    route.query = { start_date: '2023-12-15', end_date: '2024-02-10' }
    vi.mocked(reportsApi.getIncomeStatement).mockRejectedValue({ message: 'test error' })
    const wrapper = mountPage()
    await flushPromises()
    expect(reportsApi.getIncomeStatement).toHaveBeenLastCalledWith({
      start_date: '2023-12-01', end_date: '2024-02-29',
    })
    const pickers = wrapper.findAllComponents(MonthPicker)
    expect(pickers.map(picker => picker.props('modelValue'))).toEqual(['2023-12', '2024-02'])
    await pickers[0]!.vm.$emit('update:modelValue', '2026-04')
    await pickers[1]!.vm.$emit('update:modelValue', '2026-07')
    await wrapper.find('.page-header > .van-button').trigger('click')
    expect(replace).toHaveBeenCalledWith({ query: { start_month: '2026-04', end_month: '2026-07' } })
    route.query = { start_month: '2026-04', end_month: '2026-07' }
    await flushPromises()
    expect(reportsApi.getIncomeStatement).toHaveBeenLastCalledWith({
      start_date: '2026-04-01', end_date: '2026-07-31',
    })
    route.query = { start_month: '2023-12', end_month: '2024-02' }
    await flushPromises()
    expect(pickers.map(picker => picker.props('modelValue'))).toEqual(['2023-12', '2024-02'])
  })

  it('rejects reversed month ranges before querying and allows correction', async () => {
    route.query = { start_month: '2026-08', end_month: '2026-07' }
    const wrapper = mountPage()
    await flushPromises()
    expect(reportsApi.getIncomeStatement).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('开始月份不能晚于结束月份')
    await wrapper.find('.page-header > .van-button').trigger('click')
    expect(replace).not.toHaveBeenCalled()
    await wrapper.findAllComponents(MonthPicker)[1]!.vm.$emit('update:modelValue', '2026-08')
    await wrapper.find('.page-header > .van-button').trigger('click')
    expect(replace).toHaveBeenCalledWith({ query: { start_month: '2026-08', end_month: '2026-08' } })
  })
})
