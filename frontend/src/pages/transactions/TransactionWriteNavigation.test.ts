import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Vant from 'vant'
import { beforeEach, expect, it, vi } from 'vitest'
import router from '../../router'
import { transactionsApi } from '../../api/transactions'
import { useTransactionDraftStore } from '../../stores/transactionDraft'
import TransactionForm from '../../components/TransactionForm.vue'
import EditTransactionPage from './EditTransactionPage.vue'
import TransactionDetailPage from './TransactionDetailPage.vue'
import TransactionDistributePage from './TransactionDistributePage.vue'
vi.mock('vant', async original => ({ ...await original<typeof import('vant')>(), showConfirmDialog: vi.fn().mockResolvedValue(undefined) }))
vi.mock('../../api/transactions', async original => ({
  ...await original<typeof import('../../api/transactions')>(),
  transactionsApi: { getTransaction: vi.fn(), updateTransaction: vi.fn(), deleteTransaction: vi.fn(), createTransaction: vi.fn() },
}))
const pinia = createPinia()
const saved = { id: 'one', date: '2026-09-26', postings: [], display_amounts: [] }
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('scrollTo', vi.fn())
  setActivePinia(pinia)
  useTransactionDraftStore().$reset()
  vi.mocked(transactionsApi.getTransaction).mockResolvedValue(saved)
  vi.mocked(transactionsApi.updateTransaction).mockResolvedValue(saved)
  vi.mocked(transactionsApi.deleteTransaction).mockResolvedValue(undefined)
  vi.mocked(transactionsApi.createTransaction).mockResolvedValue(saved)
})
it.each(['edit', 'delete', 'distribute'] as const)('allows %s success navigation through the real guard', async mode => {
  setActivePinia(pinia)
  const store = useTransactionDraftStore()
  store.createEmpty('create')
  store.updateDraft({ amount: '10', fromAccounts: ['Assets:Cash'], toAccounts: ['Expenses:Food', 'Expenses:Other'] })
  const path = mode === 'edit' ? '/transactions/one/edit' : mode === 'delete' ? '/transactions/one' : '/transactions/distribute?side=to'
  await router.push(path)
  const page = mode === 'edit' ? EditTransactionPage : mode === 'delete' ? TransactionDetailPage : TransactionDistributePage
  const wrapper = mount(page, { global: { plugins: [pinia, router, Vant], stubs: { TransactionForm: { name: 'TransactionForm', emits: ['submit'], template: '<div />' } } } })
  await flushPromises()
  if (mode === 'edit') wrapper.findComponent(TransactionForm).vm.$emit('submit', { date: '2026-09-26', postings: [] })
  else if (mode === 'delete') await wrapper.find('.detail-actions button').trigger('click')
  else await wrapper.find('.van-nav-bar__right button').trigger('click')
  await flushPromises()
  expect(store.pendingWrite).toBe(false)
  await vi.waitFor(() => expect(router.currentRoute.value.path).toBe(mode === 'edit' ? '/transactions/one' : mode === 'delete' ? '/transactions' : '/transactions/new'))
  wrapper.unmount()
})
it('keeps draft and route during pending and unconfirmed writes until explicit release', async () => {
  setActivePinia(pinia)
  const store = useTransactionDraftStore()
  await router.push('/transactions/new')
  store.createEmpty()
  store.updateDraft({ description: 'keep' })
  store.pendingWrite = true
  await router.push('/transactions/other/edit')
  expect(router.currentRoute.value.path).toBe('/transactions/new')
  store.pendingWrite = false
  store.unconfirmed = 'create'
  await router.push('/transactions/other/edit')
  expect(router.currentRoute.value.path).toBe('/transactions/new')
  expect(store.draft?.description).toBe('keep')
  store.unconfirmed = null
  await router.push('/settings')
  expect(router.currentRoute.value.path).toBe('/settings')
})
