import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { exchangeRatesApi } from '../../../api/exchangeRates'
import ExchangeRatesPage from '../ExchangeRatesPage.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ back: vi.fn() }) }))
vi.mock('../../../api/exchangeRates', () => ({
  exchangeRatesApi: { getExchangeRates: vi.fn() },
}))

describe('ExchangeRatesPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders retained rates without losing decimal precision', async () => {
    vi.mocked(exchangeRatesApi.getExchangeRates).mockResolvedValue([{
      currency: 'USD', rate: '7.123456789', quote_currency: 'CNY',
      effective_date: '2026-07-01', currency_pair: 'USD/CNY',
    }])
    const wrapper = mount(ExchangeRatesPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('USD/CNY')
    expect(wrapper.text()).toContain('7.123456789')
    expect(wrapper.text()).toContain('Beancount 账本为真值')
  })

  it('shows a retryable error', async () => {
    vi.mocked(exchangeRatesApi.getExchangeRates).mockRejectedValue({ message: '汇率加载失败' })
    const wrapper = mount(ExchangeRatesPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('汇率加载失败')
    expect(wrapper.text()).toContain('重试')
  })
})
