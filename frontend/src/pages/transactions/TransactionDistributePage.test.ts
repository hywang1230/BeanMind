import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { transactionsApi } from '../../api/transactions'
import { useTransactionDraftStore } from '../../stores/transactionDraft'
import TransactionDistributePage from './TransactionDistributePage.vue'

const push = vi.fn()
const replace = vi.fn()
const back = vi.fn()
let query: Record<string, string> = { side: 'to' }

vi.mock('vue-router', () => ({
  useRouter: () => ({ push, replace, back }),
  useRoute: () => ({ query }),
}))
vi.mock('../../api/transactions', () => ({
  transactionsApi: {
    createTransaction: vi.fn(),
    updateTransaction: vi.fn(),
  },
}))

describe('TransactionDistributePage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    query = { side: 'to' }
  })

  it('shows empty recovery when draft missing', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(TransactionDistributePage, {
      global: { plugins: [Vant, pinia] },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('没有可分配的草稿')
  })

  it('saves multi-category expense after amounts balance', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const draft = useTransactionDraftStore()
    draft.setDraft({
      mode: 'create',
      type: 'expense',
      date: '2026-07-01',
      payee: '',
      description: 'split',
      currency: 'CNY',
      amount: '30.00',
      fromAccounts: ['Assets:Cash'],
      toAccounts: ['Expenses:Food', 'Expenses:Transport'],
      fromLines: [],
      toLines: [],
    })
    vi.mocked(transactionsApi.createTransaction).mockResolvedValue({ id: 'tx-1' } as never)

    const wrapper = mount(TransactionDistributePage, {
      global: { plugins: [Vant, pinia] },
    })
    await flushPromises()

    const inputs = wrapper.findAll('input')
    // two amount fields for two categories
    expect(inputs.length).toBeGreaterThanOrEqual(2)
    await inputs[0]!.setValue('10.00')
    await inputs[1]!.setValue('20.00')
    await wrapper.vm.$nextTick()

    await wrapper.find('.van-nav-bar__right .van-button').trigger('click')
    await flushPromises()

    expect(transactionsApi.createTransaction).toHaveBeenCalledWith(
      expect.objectContaining({
        postings: expect.arrayContaining([
          expect.objectContaining({ account: 'Expenses:Food', amount: '10.00' }),
          expect.objectContaining({ account: 'Expenses:Transport', amount: '20.00' }),
          expect.objectContaining({ account: 'Assets:Cash', amount: '-30.00' }),
        ]),
      }),
    )
    expect(replace).toHaveBeenCalledWith('/transactions/tx-1')
  })
})
