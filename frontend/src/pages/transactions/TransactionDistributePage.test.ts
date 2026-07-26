import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { transactionsApi } from '../../api/transactions'
import MoneyInput from '../../components/MoneyInput.vue'
import {
  useTransactionDraftStore,
  type TransactionDraft,
} from '../../stores/transactionDraft'
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

function baseDraft(partial: Partial<TransactionDraft> = {}): TransactionDraft {
  return {
    mode: 'create',
    type: 'expense',
    date: '2026-07-01',
    payee: '',
    description: 'split',
    currency: 'CNY',
    amount: '100.00',
    fromAccounts: ['Assets:Cash'],
    toAccounts: ['Expenses:Food', 'Expenses:Transport', 'Expenses:Other'],
    fromLines: [],
    toLines: [],
    ...partial,
  }
}

function mountWithDraft(partial: Partial<TransactionDraft> = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const draft = useTransactionDraftStore()
  draft.setDraft(baseDraft(partial))
  const wrapper = mount(TransactionDistributePage, {
    global: { plugins: [Vant, pinia] },
  })
  return { wrapper, draft, pinia }
}

function moneyInputs(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAllComponents(MoneyInput)
}

function moneyValues(wrapper: ReturnType<typeof mount>): string[] {
  return moneyInputs(wrapper).map((input) => String(input.props('modelValue')))
}

async function commitAmount(wrapper: ReturnType<typeof mount>, index: number, value: string) {
  await moneyInputs(wrapper)[index]!.vm.$emit('update:modelValue', value)
  await wrapper.vm.$nextTick()
}

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

  it('uses compact MoneyInput fields and saves after redistributing the untouched category', async () => {
    const { wrapper } = mountWithDraft({
      amount: '30.00',
      toAccounts: ['Expenses:Food', 'Expenses:Transport'],
    })
    vi.mocked(transactionsApi.createTransaction).mockResolvedValue({ id: 'tx-1' } as never)
    await flushPromises()

    expect(moneyInputs(wrapper)).toHaveLength(2)
    expect(moneyInputs(wrapper).every((input) => input.props('variant') === 'field')).toBe(true)
    expect(moneyValues(wrapper)).toEqual(['15.00', '15.00'])

    await commitAmount(wrapper, 0, '10.00')
    expect(moneyValues(wrapper)).toEqual(['10.00', '20.00'])

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
    expect(replace).toHaveBeenCalledWith('/transactions/new')
  })

  it('locks manually edited categories regardless of list order', async () => {
    const { wrapper } = mountWithDraft()
    await flushPromises()

    expect(moneyValues(wrapper)).toEqual(['33.33', '33.33', '33.34'])
    await commitAmount(wrapper, 2, '20.00')
    expect(moneyValues(wrapper)).toEqual(['40.00', '40.00', '20.00'])

    await commitAmount(wrapper, 0, '30.00')
    expect(moneyValues(wrapper)).toEqual(['30.00', '50.00', '20.00'])
  })

  it('uses exact cents and gives the last untouched category the residual', async () => {
    const { wrapper } = mountWithDraft({ amount: '0.30' })
    await flushPromises()

    expect(moneyValues(wrapper)).toEqual(['0.10', '0.10', '0.10'])
    await commitAmount(wrapper, 2, '0.11')
    expect(moneyValues(wrapper)).toEqual(['0.09', '0.10', '0.11'])
    expect(wrapper.find('.ok').text()).toBe('0.00')
  })

  it('applies the same locking behavior to multiple funding accounts', async () => {
    query = { side: 'from' }
    const { wrapper } = mountWithDraft({
      fromAccounts: ['Assets:Cash', 'Assets:Bank', 'Liabilities:Card'],
      toAccounts: ['Expenses:Food'],
    })
    await flushPromises()

    await commitAmount(wrapper, 1, '20.00')
    expect(moneyValues(wrapper)).toEqual(['40.00', '20.00', '40.00'])
    await commitAmount(wrapper, 0, '30.00')
    expect(moneyValues(wrapper)).toEqual(['30.00', '20.00', '50.00'])
  })

  it('does not generate reverse amounts when locked values exceed the total', async () => {
    const { wrapper } = mountWithDraft()
    await flushPromises()

    await commitAmount(wrapper, 0, '120.00')
    expect(moneyValues(wrapper)).toEqual(['120.00', '', ''])
    expect(wrapper.find('.bad').text()).toBe('-20.00')
    expect(wrapper.find('.van-nav-bar__right .van-button').attributes('disabled')).toBeDefined()
  })

  it('keeps untouched values empty when a locked value consumes the full total', async () => {
    const { wrapper } = mountWithDraft()
    await flushPromises()

    await commitAmount(wrapper, 0, '100.00')
    expect(moneyValues(wrapper)).toEqual(['100.00', '', ''])
    expect(wrapper.find('.ok').text()).toBe('0.00')
    expect(wrapper.find('.van-nav-bar__right .van-button').attributes('disabled')).toBeDefined()
  })

  it('keeps automatic allocations in the direction of a negative total', async () => {
    const { wrapper } = mountWithDraft({ amount: '-100.00' })
    await flushPromises()

    expect(moneyValues(wrapper)).toEqual(['-33.33', '-33.33', '-33.34'])
    await commitAmount(wrapper, 2, '-20.00')
    expect(moneyValues(wrapper)).toEqual(['-40.00', '-40.00', '-20.00'])
    expect(wrapper.find('.ok').text()).toBe('0.00')
  })

  it('keeps empty and fully edited values locked without unsafe redistribution', async () => {
    const { wrapper } = mountWithDraft()
    await flushPromises()

    await commitAmount(wrapper, 0, '')
    expect(moneyValues(wrapper)).toEqual(['', '50.00', '50.00'])
    await commitAmount(wrapper, 1, '20.00')
    expect(moneyValues(wrapper)).toEqual(['', '20.00', '80.00'])
    await commitAmount(wrapper, 2, '70.00')
    expect(moneyValues(wrapper)).toEqual(['', '20.00', '70.00'])
    expect(wrapper.find('.van-nav-bar__right .van-button').attributes('disabled')).toBeDefined()
  })

  it('resets manual locks when the page is entered again', async () => {
    const { wrapper, draft, pinia } = mountWithDraft({
      toLines: [
        { account: 'Expenses:Food', amount: '30.00' },
        { account: 'Expenses:Transport', amount: '30.00' },
        { account: 'Expenses:Other', amount: '40.00' },
      ],
    })
    await flushPromises()

    await commitAmount(wrapper, 2, '20.00')
    expect(moneyValues(wrapper)).toEqual(['40.00', '40.00', '20.00'])
    draft.setSideLines('to', [
      { account: 'Expenses:Food', amount: '40.00' },
      { account: 'Expenses:Transport', amount: '40.00' },
      { account: 'Expenses:Other', amount: '20.00' },
    ])
    wrapper.unmount()

    const enteredAgain = mount(TransactionDistributePage, {
      global: { plugins: [Vant, pinia] },
    })
    await flushPromises()
    await commitAmount(enteredAgain, 0, '30.00')
    expect(moneyValues(enteredAgain)).toEqual(['30.00', '35.00', '35.00'])
  })
})
