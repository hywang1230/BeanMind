import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { dashboardApi, type Dashboard } from '../../api/dashboard'
import DashboardPage from './DashboardPage.vue'

vi.mock('../../api/dashboard', () => ({ dashboardApi: { get: vi.fn() } }))

const dashboard: Dashboard = {
  month: '2026-07', currency: 'CNY', income: '1000.019', expense: '200.014',
  net_income: '800.005', assets: '5000.999', liabilities: '1000.001', net_worth: '4000.125',
  budget_risk: 'WARNING', review_status: 'READY', missing_exchange_rates: ['USD'],
}

describe('DashboardPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('formats amounts to two decimals and renders the complete dashboard structure', async () => {
    vi.mocked(dashboardApi.get).mockResolvedValue(dashboard)
    const wrapper = mount(DashboardPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('¥4,000.13')
    expect(wrapper.text()).toContain('¥1,000.02')
    expect(wrapper.text()).not.toContain('4000.125')
    expect(wrapper.text()).toContain('接近额度')
    expect(wrapper.text()).toContain('缺少汇率')
    expect(wrapper.text()).toContain('USD')
    expect(wrapper.text()).toContain('快捷入口')
    expect(wrapper.text()).toContain('账户')
    expect(wrapper.text()).toContain('报表')
    expect(wrapper.text()).toContain('记一笔')
  })

  it('shows a retry action when loading fails', async () => {
    vi.mocked(dashboardApi.get).mockRejectedValue({ message: '投影恢复中' })
    const wrapper = mount(DashboardPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('投影恢复中')
    expect(wrapper.text()).toContain('重试')
  })

  it('only shows the exchange-rate warning when the API reports a real risk', async () => {
    vi.mocked(dashboardApi.get).mockResolvedValue({ ...dashboard, missing_exchange_rates: [] })
    const wrapper = mount(DashboardPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('缺少汇率')
    expect(wrapper.text()).not.toContain('USD')
  })
})
