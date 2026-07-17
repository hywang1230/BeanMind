import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { dashboardApi, type Dashboard } from '../../api/dashboard'
import DashboardPage from './DashboardPage.vue'

vi.mock('../../api/dashboard', () => ({ dashboardApi: { get: vi.fn() } }))

const dashboard: Dashboard = {
  month: '2026-07', currency: 'CNY', income: '1000.01', expense: '200.01',
  net_income: '800.00', assets: '5000', liabilities: '1000', net_worth: '4000',
  budget_risk: 'WARNING', review_status: 'READY', missing_exchange_rates: ['USD'],
}

describe('DashboardPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders exact string amounts and risk state', async () => {
    vi.mocked(dashboardApi.get).mockResolvedValue(dashboard)
    const wrapper = mount(DashboardPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('CNY 4000')
    expect(wrapper.text()).toContain('接近额度')
    expect(wrapper.text()).toContain('缺少汇率：USD')
  })

  it('shows a retry action when loading fails', async () => {
    vi.mocked(dashboardApi.get).mockRejectedValue({ message: '投影恢复中' })
    const wrapper = mount(DashboardPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('投影恢复中')
    expect(wrapper.text()).toContain('重试')
  })
})
