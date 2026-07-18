<template>
  <section class="page page-with-pull transactions-page">
    <div class="page-scroll" @scroll.passive="onScroll">
    <van-pull-refresh v-model="refreshing" class="page-pull-refresh" pulling-text="下拉刷新" loosing-text="释放刷新" loading-text="刷新中..." success-text="刷新成功" @refresh="onRefresh">
    <header class="page-header"><h1>流水</h1></header>
    <div class="filter-panel page-section">
      <van-search v-model="filters.description" placeholder="搜索交易方或备注" @search="applyFilters" @clear="applyFilters" />
      <van-cell-group inset class="filter-fields">
      <SelectPickerField v-model="filters.transaction_type" label="类型" :options="transactionTypeOptions" @change="applyFilters" />
      <DateRangePickerField v-model:start-date="filters.start_date" v-model:end-date="filters.end_date" @change="applyFilters" />
      <AccountPicker v-model="filters.account" :accounts="accounts" label="账户" clearable :error="accountError" @change="applyFilters" />
      </van-cell-group>
    </div>
    <div v-if="loading && !items.length" class="state-card"><van-loading>加载中</van-loading></div>
    <van-empty v-else-if="error && !items.length" image="error" :description="error"><van-button type="primary" size="small" @click="load(true)">重试</van-button></van-empty>
    <van-empty v-else-if="!items.length" description="暂无交易"><van-button type="primary" size="small" to="/transactions/new">开始记账</van-button></van-empty>
    <van-cell-group v-else inset class="transaction-list">
      <van-cell v-for="item in items" :key="item.id" is-link :to="`/transactions/${item.id}`" :class="`transaction-${item.transaction_type}`">
        <template #icon><span class="transaction-icon">{{ item.transaction_type === 'income' ? '收' : item.transaction_type === 'expense' ? '支' : '转' }}</span></template>
        <template #title><span class="transaction-title">{{ summary(item) }}</span></template>
        <template #label>
          <div class="transaction-meta">
            <span>{{ item.date }}</span>
            <span v-if="note(item)" class="transaction-note">{{ note(item) }}</span>
          </div>
        </template>
        <template #value><span :class="amountClass(item)">{{ amount(item) }}</span></template>
      </van-cell>
    </van-cell-group>
    <div v-if="items.length" class="list-footer">
      <van-loading v-if="loadingMore" size="20px">加载中</van-loading>
      <div v-else-if="error" class="load-more-error">
        <span>{{ error }}</span>
        <van-button size="small" plain type="primary" @click="loadMore">重试</van-button>
      </div>
      <span v-else-if="hasMore" class="muted">继续上滑加载更多</span>
      <span v-else class="muted">没有更多了</span>
    </div>
    </van-pull-refresh>

    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { accountsApi, type Account } from '../../api/accounts'
import { transactionsApi, type Transaction, type TransactionsQuery } from '../../api/transactions'
import type { ApiError } from '../../api/client'
import AccountPicker from '../../components/AccountPicker.vue'
import DateRangePickerField from '../../components/DateRangePickerField.vue'
import SelectPickerField from '../../components/SelectPickerField.vue'
import { accountShortLabel } from '../../utils/accountTree'

defineOptions({ name: 'TransactionsPage' })

const route = useRoute(); const router = useRouter()
function filtersFromRoute() {
  return {
    description: String(route.query.description || ''),
    transaction_type: String(route.query.transaction_type || ''),
    start_date: String(route.query.start_date || ''),
    end_date: String(route.query.end_date || ''),
    account: String(route.query.account || ''),
  }
}
const filters = reactive(filtersFromRoute())
let loadedFiltersKey = JSON.stringify(filtersFromRoute())
const transactionTypeOptions = [
  { text: '全部', value: '' },
  { text: '支出', value: 'expense' },
  { text: '收入', value: 'income' },
  { text: '转账', value: 'transfer' },
]
const items = ref<Transaction[]>([]); const cursor = ref<string | null>(null); const hasMore = ref(false)
const loading = ref(false); const loadingMore = ref(false); const refreshing = ref(false); const error = ref('')
const accounts = ref<Account[]>([]); const accountError = ref('')
function query(): TransactionsQuery { return { limit: 20, description: filters.description || undefined, transaction_type: filters.transaction_type as TransactionsQuery['transaction_type'] || undefined, start_date: filters.start_date || undefined, end_date: filters.end_date || undefined, account: filters.account || undefined } }
async function load(reset = true, options: { silent?: boolean } = {}) {
  if (!options.silent) loading.value = true
  error.value = ''
  try {
    const page = await transactionsApi.getTransactions(query())
    items.value = page.items
    cursor.value = page.next_cursor
    hasMore.value = page.has_more
  } catch (reason) {
    error.value = (reason as ApiError).message
    if (reset) items.value = []
  } finally {
    if (!options.silent) loading.value = false
  }
}
async function loadAccounts() { accountError.value = ''; try { accounts.value = await accountsApi.getAccounts() } catch (reason) { accountError.value = (reason as ApiError).message } }
async function loadMore() { if (!cursor.value || loadingMore.value) return; loadingMore.value = true; error.value = ''; try { const page = await transactionsApi.getTransactions({ ...query(), cursor: cursor.value }); items.value.push(...page.items); cursor.value = page.next_cursor; hasMore.value = page.has_more } catch (reason) { error.value = (reason as ApiError).message } finally { loadingMore.value = false } }
function onScroll(event: Event) {
  const target = event.currentTarget as HTMLElement
  if (target.scrollHeight - target.scrollTop - target.clientHeight <= 120) loadMore()
}
async function onRefresh() {
  try { await Promise.all([load(true, { silent: true }), loadAccounts()]) }
  finally { refreshing.value = false }
}
function applyFilters() { const query = Object.fromEntries(Object.entries(filters).filter(([, value]) => value)); router.replace({ path: '/transactions', query }) }
watch(() => route.query, () => {
  if (route.path !== '/transactions') return
  const nextFilters = filtersFromRoute()
  Object.assign(filters, nextFilters)
  const nextFiltersKey = JSON.stringify(nextFilters)
  if (nextFiltersKey === loadedFiltersKey) return
  loadedFiltersKey = nextFiltersKey
  load(true)
})
function summary(item: Transaction) {
  const ledgerNames = accounts.value.map((account) => account.name)
  if (item.transaction_type === 'transfer') {
    const names = [...new Set(
      item.postings.map((posting) => accountShortLabel(posting.account, ledgerNames)),
    )]
    return names.join('，') || '转账'
  }
  const prefix = item.transaction_type === 'expense' ? 'Expenses:' : item.transaction_type === 'income' ? 'Income:' : ''
  if (!prefix) return '转账'
  const names = [...new Set(
    item.postings
      .filter((posting) => posting.account.startsWith(prefix))
      .map((posting) => accountShortLabel(posting.account, ledgerNames)),
  )]
  return names.join('，') || '转账'
}
function note(item: Transaction) {
  return item.description?.trim() || ''
}
function amount(item: Transaction) { return item.display_amounts.map(value => `${value.currency} ${value.amount}`).join(' / ') }
function amountClass(item: Transaction) {
  const values = item.display_amounts.map(value => value.amount.trim()).filter(value => !/^-?0(?:\.0+)?$/.test(value))
  const hasNegative = values.some(value => value.startsWith('-'))
  const hasPositive = values.some(value => !value.startsWith('-'))
  return hasNegative === hasPositive ? '' : hasNegative ? 'negative' : 'positive'
}
onMounted(() => { load(true); loadAccounts() })
</script>

<style scoped>
.filter-panel { padding: 10px; border: 1px solid var(--bm-border); border-radius: var(--bm-radius); background: var(--bm-surface); }
.filter-panel :deep(.van-search) { margin: 0; border: 0; padding: 2px 0 10px; }
.filter-fields { margin: 0; border: 0; }
.transaction-list :deep(.van-cell) { align-items: center; padding-top: 14px; padding-bottom: 14px; }
.transaction-list :deep(.van-cell__title) { flex: 1; min-width: 0; overflow: hidden; }
.transaction-title {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  word-break: keep-all;
}
.transaction-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.transaction-note {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--bm-muted);
}
.transaction-icon { display: inline-grid; width: 38px; height: 38px; margin-right: 12px; place-items: center; border-radius: 50%; background: var(--bm-primary); color: white; font-weight: 700; }
.transaction-expense .transaction-icon { background: var(--bm-expense); }
.transaction-income .transaction-icon { background: var(--bm-income); }
.transaction-list :deep(.van-cell__value) {
  flex: 0 0 auto;
  max-width: 42%;
  font-weight: 700;
  white-space: nowrap;
}
.list-footer {
  padding: 16px;
  text-align: center;
}
.load-more-error { display: flex; align-items: center; justify-content: center; gap: 10px; color: var(--bm-expense); }
</style>
