import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Vant, { showConfirmDialog } from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { transactionsApi } from '../../api/transactions'
import { useTransactionDraftStore } from '../../stores/transactionDraft'
import TransactionForm from '../../components/TransactionForm.vue'
import TransactionWriteStatus from '../../components/TransactionWriteStatus.vue'
import AddTransactionPage from './AddTransactionPage.vue'
import EditTransactionPage from './EditTransactionPage.vue'
import TransactionDetailPage from './TransactionDetailPage.vue'

const replace = vi.fn()
const back = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ replace, back }), useRoute: () => ({ params: { id: 'one' } }) }))
vi.mock('vant', async importOriginal => ({ ...await importOriginal<typeof import('vant')>(), showConfirmDialog: vi.fn() }))
vi.mock('../../api/transactions', async importOriginal => ({
  ...await importOriginal<typeof import('../../api/transactions')>(),
  transactionsApi: { createTransaction: vi.fn(), updateTransaction: vi.fn(), deleteTransaction: vi.fn(), getTransaction: vi.fn(), getTransactions: vi.fn() },
}))
const transaction = { id: 'one', date: '2026-09-26', description: 'original', postings: [], display_amounts: [] }
const payload = { date: '2026-09-26', description: 'draft', postings: [] }
const unknown = { code: 'TRANSACTION_RESULT_UNCONFIRMED', message: '未能确认操作结果，请刷新核对，勿重复提交' }
function setup() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useTransactionDraftStore()
  store.createEmpty()
  store.updateDraft({ description: 'draft', amount: '12' })
  const global = { plugins: [Vant, pinia], stubs: { TransactionForm: { name: 'TransactionForm', props: ['disabled', 'loading'], emits: ['submit'], template: '<div class="form-stub" />' } } }
  return { store, global }
}
function button(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAll('button').find(node => node.text().includes(text))!
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(transactionsApi.getTransaction).mockResolvedValue(transaction)
  vi.mocked(transactionsApi.getTransactions).mockResolvedValue({ items: [transaction], has_more: false, next_cursor: null })
  vi.mocked(showConfirmDialog).mockResolvedValue(undefined)
})

describe('unconfirmed transaction writes', () => {
  it.each([
    ['create', AddTransactionPage, 'createTransaction'],
    ['edit:one', EditTransactionPage, 'updateTransaction'],
  ] as const)('%s retains draft and never replays on remount', async (operation, page, method) => {
    const { store, global } = setup()
    store.updateDraft({ mode: operation })
    let reject!: (reason: unknown) => void
    vi.mocked(transactionsApi[method]).mockImplementation(() => new Promise((_, fail) => { reject = fail }))
    const wrapper = mount(page, { global })
    await flushPromises()
    const form = wrapper.findComponent(TransactionForm)
    form.vm.$emit('submit', payload)
    form.vm.$emit('submit', payload)
    expect(transactionsApi[method]).toHaveBeenCalledTimes(1)
    reject(unknown)
    await flushPromises()
    expect(store.draft?.description).toBe('draft')
    expect(store.unconfirmed).toBe(operation)
    expect(form.props('disabled')).toBe(true)
    form.vm.$emit('submit', payload)
    expect(transactionsApi[method]).toHaveBeenCalledTimes(1)
    expect(replace).not.toHaveBeenCalled()
    await button(wrapper, '只读核对').trigger('click')
    await flushPromises()
    expect(store.unconfirmed).toBe(operation)
    expect(store.draft?.amount).toBe('12')
    await button(wrapper, '我已核对').trigger('click')
    await flushPromises()
    expect(store.unconfirmed).toBeNull()
    wrapper.unmount()
    mount(page, { global })
    await flushPromises()
    expect(transactionsApi[method]).toHaveBeenCalledTimes(1)
  })

  it('retains deletion context and does not turn DIRTY into success; user can explicitly leave after checking', async () => {
    const { store, global } = setup()
    vi.mocked(transactionsApi.deleteTransaction).mockRejectedValue(unknown)
    const wrapper = mount(TransactionDetailPage, { global })
    await flushPromises()
    await button(wrapper, '删除交易').trigger('click')
    await flushPromises()
    expect(store.unconfirmed).toBe('delete:one')
    vi.mocked(transactionsApi.getTransaction).mockRejectedValue({ status: 503, message: '投影未就绪' })
    await button(wrapper, '只读核对').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(TransactionWriteStatus).text()).toContain('操作结果仍未确认')
    expect(transactionsApi.deleteTransaction).toHaveBeenCalledTimes(1)
    expect(store.unconfirmed).toBe('delete:one')
    expect(replace).not.toHaveBeenCalled()
    await button(wrapper, '我已核对').trigger('click')
    await flushPromises()
    expect(store.unconfirmed).toBeNull()
    expect(showConfirmDialog).toHaveBeenLastCalledWith(expect.objectContaining({ message: expect.stringContaining('不代表原请求失败') }))
    expect(transactionsApi.deleteTransaction).toHaveBeenCalledTimes(1)
  })

  it('canceled delete confirmation sends no request', async () => {
    const { store, global } = setup()
    vi.mocked(showConfirmDialog).mockRejectedValue('cancel')
    const wrapper = mount(TransactionDetailPage, { global })
    await flushPromises()
    await button(wrapper, '删除交易').trigger('click')
    await flushPromises()
    expect(transactionsApi.deleteTransaction).not.toHaveBeenCalled()
    expect(store.unconfirmed).toBeNull()
    expect(store.pendingWrite).toBe(false)
  })
})
