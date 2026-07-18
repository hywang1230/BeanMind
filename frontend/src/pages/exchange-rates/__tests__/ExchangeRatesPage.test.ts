import { flushPromises, mount } from '@vue/test-utils'
import Vant, { showConfirmDialog } from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { currenciesApi } from '../../../api/currencies'
import { exchangeRatesApi } from '../../../api/exchangeRates'
import ExchangeRatesPage from '../ExchangeRatesPage.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ back: vi.fn() }) }))
vi.mock('vant', async () => {
  const actual = await vi.importActual<typeof import('vant')>('vant')
  return {
    ...actual,
    showConfirmDialog: vi.fn(),
    showToast: vi.fn(),
  }
})
vi.mock('../../../api/exchangeRates', () => ({
  exchangeRatesApi: {
    getExchangeRates: vi.fn(),
    getExchangeRateHistory: vi.fn(),
    createExchangeRate: vi.fn(),
    updateExchangeRate: vi.fn(),
    deleteExchangeRate: vi.fn(),
  },
}))
vi.mock('../../../api/currencies', () => ({
  currenciesApi: {
    list: vi.fn(),
  },
}))

const sampleRate = {
  currency: 'USD',
  rate: '7.123456789',
  quote_currency: 'CNY',
  effective_date: '2026-07-01',
  currency_pair: 'USD/CNY',
}

const catalog = [
  { code: 'CNY', name: '人民币', symbol: '¥', enabled: true, sort_order: 0 },
  { code: 'USD', name: '美元', symbol: '$', enabled: true, sort_order: 1 },
]

function mountPage() {
  return mount(ExchangeRatesPage, {
    global: {
      plugins: [Vant],
      stubs: {
        DatePickerField: {
          props: ['modelValue', 'label'],
          template: '<div class="date-picker-stub">{{ label }}:{{ modelValue }}</div>',
        },
      },
    },
  })
}

describe('ExchangeRatesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(currenciesApi.list).mockResolvedValue(catalog)
    vi.mocked(exchangeRatesApi.getExchangeRateHistory).mockResolvedValue([sampleRate])
  })

  it('renders catalog-enabled rates without losing decimal precision', async () => {
    vi.mocked(exchangeRatesApi.getExchangeRates).mockResolvedValue([
      sampleRate,
      {
        currency: 'EUR',
        rate: '7.8',
        quote_currency: 'CNY',
        effective_date: '2026-07-02',
        currency_pair: 'EUR/CNY',
      },
    ])
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('USD/CNY')
    expect(wrapper.text()).toContain('7.123456789')
    expect(wrapper.text()).toContain('币种目录')
    expect(wrapper.text()).toContain('主货币：CNY')
    expect(wrapper.text()).not.toContain('EUR/CNY')
    expect(currenciesApi.list).toHaveBeenCalledWith(true)
  })

  it('shows enabled foreign rates from catalog', async () => {
    vi.mocked(currenciesApi.list).mockResolvedValue([
      ...catalog,
      { code: 'EUR', name: '欧元', symbol: '€', enabled: true, sort_order: 2 },
    ])
    vi.mocked(exchangeRatesApi.getExchangeRates).mockResolvedValue([
      sampleRate,
      {
        currency: 'EUR',
        rate: '7.8',
        quote_currency: 'CNY',
        effective_date: '2026-07-02',
        currency_pair: 'EUR/CNY',
      },
    ])
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('USD/CNY')
    expect(wrapper.text()).toContain('EUR/CNY')
  })

  it('shows empty state with add action', async () => {
    vi.mocked(exchangeRatesApi.getExchangeRates).mockResolvedValue([])
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('账本中暂无汇率')
    expect(wrapper.text()).toContain('添加汇率')
  })

  it('shows a retryable error', async () => {
    vi.mocked(exchangeRatesApi.getExchangeRates).mockRejectedValue({ message: '汇率加载失败' })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('汇率加载失败')
    expect(wrapper.text()).toContain('重试')

    vi.mocked(exchangeRatesApi.getExchangeRates).mockResolvedValue([sampleRate])
    const retry = wrapper.findAll('button').find((btn) => btn.text() === '重试')
    expect(retry).toBeTruthy()
    await retry!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('USD/CNY')
  })

  it('opens create form with selectable catalog currency', async () => {
    vi.mocked(exchangeRatesApi.getExchangeRates).mockResolvedValue([sampleRate])
    const wrapper = mountPage()
    await flushPromises()
    const addButtons = wrapper.findAll('button').filter((btn) => btn.text() === '添加')
    expect(addButtons.length).toBeGreaterThan(0)
    await addButtons[0]!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('添加汇率')
    expect(wrapper.text()).toContain('源货币')
    expect(wrapper.text()).toContain('Beancount 预览')
    expect(wrapper.text()).toContain('price USD')
  })

  it('creates a rate with default source currency and refreshes list', async () => {
    const created = {
      currency: 'USD',
      rate: '7.8',
      quote_currency: 'CNY',
      effective_date: '2026-07-02',
      currency_pair: 'USD/CNY',
    }
    vi.mocked(exchangeRatesApi.getExchangeRates)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([created])
    vi.mocked(exchangeRatesApi.createExchangeRate).mockResolvedValue(created)
    vi.mocked(exchangeRatesApi.getExchangeRateHistory).mockResolvedValue([created])

    const wrapper = mountPage()
    await flushPromises()
    await wrapper.findAll('button').find((btn) => btn.text() === '添加')!.trigger('click')
    await flushPromises()

    const rateInput = wrapper.find('input[placeholder="如 7.1234"]')
    await rateInput.setValue('7.8')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(exchangeRatesApi.createExchangeRate).toHaveBeenCalledWith(
      expect.objectContaining({
        currency: 'USD',
        rate: '7.8',
        quote_currency: 'CNY',
      }),
    )
    expect(exchangeRatesApi.getExchangeRates).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('USD/CNY')
  })

  it('keeps original list when save fails', async () => {
    vi.mocked(exchangeRatesApi.getExchangeRates).mockResolvedValue([sampleRate])
    vi.mocked(exchangeRatesApi.createExchangeRate).mockRejectedValue({ message: '同日汇率已存在' })

    const wrapper = mountPage()
    await flushPromises()
    await wrapper.findAll('button').find((btn) => btn.text() === '添加')!.trigger('click')
    await flushPromises()

    await wrapper.find('input[placeholder="如 7.1234"]').setValue('8.1')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('同日汇率已存在')
    expect(wrapper.text()).toContain('USD/CNY')
    expect(wrapper.text()).toContain('7.123456789')
    expect(exchangeRatesApi.getExchangeRates).toHaveBeenCalledTimes(1)
  })

  it('opens detail history and cancels delete', async () => {
    vi.mocked(exchangeRatesApi.getExchangeRates).mockResolvedValue([sampleRate])
    vi.mocked(showConfirmDialog).mockRejectedValue('cancel')

    const wrapper = mountPage()
    await flushPromises()
    await wrapper.find('.van-cell').trigger('click')
    await flushPromises()

    expect(exchangeRatesApi.getExchangeRateHistory).toHaveBeenCalledWith('USD', 'CNY')
    expect(wrapper.text()).toContain('历史汇率')
    expect(wrapper.text()).toContain('2026-07-01')

    const deleteButtons = wrapper.findAll('button').filter((btn) => btn.text().includes('删除'))
    await deleteButtons[0]!.trigger('click')
    await flushPromises()

    expect(showConfirmDialog).toHaveBeenCalled()
    expect(exchangeRatesApi.deleteExchangeRate).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('USD/CNY')
  })

  it('deletes after confirmation and refreshes', async () => {
    vi.mocked(exchangeRatesApi.getExchangeRates)
      .mockResolvedValueOnce([sampleRate])
      .mockResolvedValueOnce([])
    vi.mocked(showConfirmDialog).mockResolvedValue('confirm' as never)
    vi.mocked(exchangeRatesApi.deleteExchangeRate).mockResolvedValue({ message: 'ok' })
    vi.mocked(exchangeRatesApi.getExchangeRateHistory).mockResolvedValueOnce([sampleRate]).mockResolvedValueOnce([])

    const wrapper = mountPage()
    await flushPromises()
    await wrapper.find('.van-cell').trigger('click')
    await flushPromises()

    const deleteButtons = wrapper
      .findAll('button')
      .filter((btn) => btn.text().includes('删除最新') || btn.text() === '删除最新')
    await deleteButtons[0]!.trigger('click')
    await flushPromises()

    expect(exchangeRatesApi.deleteExchangeRate).toHaveBeenCalledWith('USD', '2026-07-01', 'CNY')
    expect(exchangeRatesApi.getExchangeRates).toHaveBeenCalledTimes(2)
  })
})
