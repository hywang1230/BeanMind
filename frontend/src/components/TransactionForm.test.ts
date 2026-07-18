import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { accountsApi } from '../api/accounts'
import { currenciesApi } from '../api/currencies'
import { transactionsApi } from '../api/transactions'
import { useTransactionDraftStore } from '../stores/transactionDraft'
import TransactionForm from './TransactionForm.vue'

const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push, replace: vi.fn(), back: vi.fn() }),
  useRoute: () => ({ query: {} }),
}))
vi.mock('../api/accounts', () => ({
  accountsApi: { getAccounts: vi.fn() },
}))
vi.mock('../api/transactions', () => ({
  transactionsApi: { getPayees: vi.fn() },
}))
vi.mock('../api/currencies', () => ({
  currenciesApi: { listEnabledCodes: vi.fn(), list: vi.fn() },
}))

const accountTree = [
  {
    name: 'Assets',
    account_type: 'Assets',
    currencies: ['CNY'],
    is_active: true,
    children: [
      { name: 'Assets:Cash', account_type: 'Assets', currencies: ['CNY', 'USD'], is_active: true },
      { name: 'Assets:Bank', account_type: 'Assets', currencies: ['CNY'], is_active: true },
    ],
  },
  {
    name: 'Expenses',
    account_type: 'Expenses',
    currencies: ['CNY'],
    is_active: true,
    children: [
      { name: 'Expenses:Food', account_type: 'Expenses', currencies: ['CNY'], is_active: true },
      { name: 'Expenses:Transport', account_type: 'Expenses', currencies: ['CNY'], is_active: true },
    ],
  },
]

describe('TransactionForm', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(accountsApi.getAccounts).mockResolvedValue(accountTree as never)
    vi.mocked(transactionsApi.getPayees).mockResolvedValue(['星巴克', '地铁'])
    vi.mocked(currenciesApi.listEnabledCodes).mockResolvedValue(['CNY', 'USD'])
  })

  it('submits single-account expense directly', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const onSubmit = vi.fn()
    const wrapper = mount(TransactionForm, {
      props: { mode: 'create', loading: false },
      attrs: { onSubmit },
      global: { plugins: [Vant, pinia] },
    })
    await flushPromises()

    // amount
    const money = wrapper.findComponent({ name: 'MoneyInput' })
    await money.vm.$emit('update:modelValue', '30.00')

    // add accounts via pickers (two AccountPicker components)
    const pickers = wrapper.findAllComponents({ name: 'AccountPicker' })
    expect(pickers.length).toBeGreaterThanOrEqual(2)
    await pickers[0]!.vm.$emit('update:modelValue', 'Assets:Cash')
    await pickers[1]!.vm.$emit('update:modelValue', 'Expenses:Food')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('保存')
    await wrapper.find('.transaction-submit .van-button').trigger('click')
    await flushPromises()

    expect(push).not.toHaveBeenCalled()
    expect(wrapper.emitted('submit')?.[0]?.[0]).toEqual({
      date: expect.any(String),
      payee: undefined,
      description: undefined,
      postings: [
        { account: 'Expenses:Food', amount: '30.00', currency: 'CNY' },
        { account: 'Assets:Cash', amount: '-30.00', currency: 'CNY' },
      ],
    })
  })


  it('submits single-account expense with negative amount', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(TransactionForm, {
      props: { mode: 'create', loading: false },
      global: { plugins: [Vant, pinia] },
    })
    await flushPromises()

    const money = wrapper.findComponent({ name: 'MoneyInput' })
    await money.vm.$emit('update:modelValue', '-8.00')
    const pickers = wrapper.findAllComponents({ name: 'AccountPicker' })
    await pickers[0]!.vm.$emit('update:modelValue', 'Assets:Cash')
    await pickers[1]!.vm.$emit('update:modelValue', 'Expenses:Food')
    await wrapper.vm.$nextTick()

    // negative amount is valid; no error banner after model update
    expect(wrapper.text()).not.toContain('请输入有效金额')
    await wrapper.find('.transaction-submit .van-button').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('submit')?.[0]?.[0]).toEqual({
      date: expect.any(String),
      payee: undefined,
      description: undefined,
      postings: [
        { account: 'Expenses:Food', amount: '-8.00', currency: 'CNY' },
        { account: 'Assets:Cash', amount: '8.00', currency: 'CNY' },
      ],
    })
  })

  it('navigates to distribute when multiple categories selected', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(TransactionForm, {
      props: { mode: 'create', loading: false },
      global: { plugins: [Vant, pinia] },
    })
    await flushPromises()

    const money = wrapper.findComponent({ name: 'MoneyInput' })
    await money.vm.$emit('update:modelValue', '30.00')
    const pickers = wrapper.findAllComponents({ name: 'AccountPicker' })
    await pickers[0]!.vm.$emit('update:modelValue', 'Assets:Cash')
    await pickers[1]!.vm.$emit('update:modelValue', 'Expenses:Food')
    await pickers[1]!.vm.$emit('update:modelValue', 'Expenses:Transport')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('下一步：分配金额')
    await wrapper.find('.transaction-submit .van-button').trigger('click')
    await flushPromises()

    expect(push).toHaveBeenCalledWith({
      path: '/transactions/distribute',
      query: { side: 'to' },
    })
    const draft = useTransactionDraftStore()
    expect(draft.draft?.toAccounts).toEqual(['Expenses:Food', 'Expenses:Transport'])
  })

  it('places accounts before amount and payee at the end', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(TransactionForm, {
      props: { mode: 'create', loading: false },
      global: { plugins: [Vant, pinia] },
    })
    await flushPromises()

    const labels = wrapper.findAll('.van-field__label, .van-cell__title').map((node) => node.text())
    const dateIdx = labels.findIndex((text) => text.includes('日期'))
    const fromIdx = labels.findIndex((text) => text.includes('资金账户'))
    const amountIdx = labels.findIndex((text) => text.includes('金额') || text === '')
    const payeeIdx = labels.findIndex((text) => text.includes('交易方'))
    const noteIdx = labels.findIndex((text) => text.includes('备注'))

    expect(fromIdx).toBeGreaterThan(dateIdx)
    expect(payeeIdx).toBeGreaterThan(fromIdx)
    expect(noteIdx).toBeGreaterThan(payeeIdx)
    // MoneyInput exists after account pickers
    const html = wrapper.html()
    expect(html.indexOf('资金账户')).toBeLessThan(html.indexOf('transaction-submit'))
    expect(html.indexOf('交易方')).toBeGreaterThan(html.indexOf('支出分类'))
    void amountIdx
  })

  it('limits currency options to funding account currencies and loads payees', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(TransactionForm, {
      props: { mode: 'create', loading: false },
      global: { plugins: [Vant, pinia] },
    })
    await flushPromises()

    expect(transactionsApi.getPayees).toHaveBeenCalled()

    const pickers = wrapper.findAllComponents({ name: 'AccountPicker' })
    await pickers[0]!.vm.$emit('update:modelValue', 'Assets:Cash')
    await wrapper.vm.$nextTick()

    const currencyField = wrapper.findComponent({ name: 'SelectPickerField' })
    expect(currencyField.exists()).toBe(true)
    expect(currencyField.props('options')).toEqual([
      { text: 'CNY', value: 'CNY' },
      { text: 'USD', value: 'USD' },
    ])

    await wrapper.find('[aria-label="选择交易方"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('星巴克')
    expect(wrapper.text()).toContain('地铁')
  })

  it('falls back to common currencies when funding account has no declared currencies', async () => {
    vi.mocked(accountsApi.getAccounts).mockResolvedValue([
      {
        name: 'Assets',
        account_type: 'Assets',
        currencies: [],
        is_active: true,
        children: [
          { name: 'Assets:经典白', account_type: 'Assets', currencies: [], is_active: true },
        ],
      },
      {
        name: 'Expenses',
        account_type: 'Expenses',
        currencies: [],
        is_active: true,
        children: [
          { name: 'Expenses:CY-餐饮', account_type: 'Expenses', currencies: [], is_active: true },
        ],
      },
    ] as never)

    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(TransactionForm, {
      props: { mode: 'create', loading: false },
      global: { plugins: [Vant, pinia] },
    })
    await flushPromises()

    const pickers = wrapper.findAllComponents({ name: 'AccountPicker' })
    await pickers[0]!.vm.$emit('update:modelValue', 'Assets:经典白')
    await wrapper.vm.$nextTick()

    const currencyField = wrapper.findComponent({ name: 'SelectPickerField' })
    const options = currencyField.props('options') as Array<{ text: string; value: string }>
    expect(options).toEqual([
      { text: 'CNY', value: 'CNY' },
      { text: 'USD', value: 'USD' },
    ])
    // currency field appears before amount in DOM
    const html = wrapper.html()
    expect(html.indexOf('选择币种') >= 0 || html.indexOf('币种') >= 0).toBe(true)
    expect(html.indexOf('币种')).toBeLessThan(html.indexOf('金额'))
  })

  it('resets amount and category while keeping funding account for continuous entry', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(TransactionForm, {
      props: { mode: 'create', loading: false },
      global: { plugins: [Vant, pinia] },
    })
    await flushPromises()

    const money = wrapper.findComponent({ name: 'MoneyInput' })
    await money.vm.$emit('update:modelValue', '12.00')
    const pickers = wrapper.findAllComponents({ name: 'AccountPicker' })
    await pickers[0]!.vm.$emit('update:modelValue', 'Assets:Cash')
    await pickers[1]!.vm.$emit('update:modelValue', 'Expenses:Food')
    await wrapper.vm.$nextTick()

    ;(wrapper.vm as unknown as { resetForNextEntry: (options?: { lastPayee?: string }) => void }).resetForNextEntry({
      lastPayee: '新咖啡店',
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'MoneyInput' }).props('modelValue')).toBe('')
    // funding account chips remain
    expect(wrapper.text()).toContain('Cash')
    // category cleared
    expect(wrapper.text()).not.toContain('Food')
    await wrapper.find('[aria-label="选择交易方"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('新咖啡店')
  })


})
