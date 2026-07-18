import { flushPromises, mount } from '@vue/test-utils'
import Vant, { showConfirmDialog } from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { currenciesApi } from '../../../api/currencies'
import CurrenciesPage from '../CurrenciesPage.vue'

const back = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ back, push: vi.fn() }),
}))
vi.mock('../../../api/currencies', () => ({
  currenciesApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}))
vi.mock('vant', async () => {
  const actual = await vi.importActual<typeof import('vant')>('vant')
  return {
    ...actual,
    showConfirmDialog: vi.fn(),
    showToast: vi.fn(),
  }
})

describe('CurrenciesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(currenciesApi.list).mockResolvedValue([
      {
        code: 'CNY',
        name: '人民币',
        symbol: '¥',
        enabled: true,
        sort_order: 0,
        in_use: true,
        is_operating: true,
      },
      {
        code: 'EUR',
        name: '欧元',
        symbol: '€',
        enabled: true,
        sort_order: 2,
        in_use: false,
        is_operating: false,
      },
    ])
    vi.mocked(showConfirmDialog).mockResolvedValue('confirm' as never)
    vi.mocked(currenciesApi.delete).mockResolvedValue(undefined)
  })

  it('renders catalog list', async () => {
    const wrapper = mount(CurrenciesPage, { global: { plugins: [Vant] } })
    await flushPromises()
    expect(wrapper.text()).toContain('币种管理')
    expect(wrapper.text()).toContain('CNY')
    expect(wrapper.text()).toContain('人民币')
    expect(wrapper.text()).toContain('EUR')
  })

  it('marks operating currency and disables switch/hide delete for in-use', async () => {
    const wrapper = mount(CurrenciesPage, { global: { plugins: [Vant] } })
    await flushPromises()

    expect(wrapper.text()).toContain('主币种')
    expect(wrapper.text()).toContain('使用中')
    expect(wrapper.text()).toContain('已使用不可关闭/删除')

    const switches = wrapper.findAllComponents({ name: 'VanSwitch' })
    expect(switches.length).toBe(2)
    expect(switches[0].props('disabled')).toBe(true)
    expect(switches[1].props('disabled')).toBe(false)

    const deleteButtons = wrapper
      .findAll('button')
      .filter((button) => button.text().includes('删除'))
    expect(deleteButtons).toHaveLength(1)
  })

  it('deletes unused currency after confirmation', async () => {
    vi.mocked(currenciesApi.list)
      .mockResolvedValueOnce([
        {
          code: 'EUR',
          name: '欧元',
          symbol: '€',
          enabled: true,
          sort_order: 2,
          in_use: false,
        },
      ])
      .mockResolvedValueOnce([])

    const wrapper = mount(CurrenciesPage, { global: { plugins: [Vant] } })
    await flushPromises()

    const deleteButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('删除'))
    expect(deleteButton).toBeTruthy()
    await deleteButton!.trigger('click')
    await flushPromises()

    expect(showConfirmDialog).toHaveBeenCalled()
    expect(currenciesApi.delete).toHaveBeenCalledWith('EUR')
    expect(currenciesApi.list).toHaveBeenCalledTimes(2)
  })
})
