<template>
  <section class="page secondary-page report-account-detail-page">
    <van-nav-bar title="账户明细" left-arrow @click-left="router.back()" />

    <div v-if="loading && !detail" class="state-card"><van-loading /></div>
    <van-empty v-else-if="error && !detail" image="error" :description="error">
      <van-button @click="reload">重试</van-button>
    </van-empty>
    <template v-else-if="detail">
      <van-cell-group inset class="summary-card">
        <van-cell title="账户" :value="detail.account" />
        <van-cell title="期间" :value="`${detail.start_date} ~ ${detail.end_date}`" />
        <van-cell title="当前余额 CNY" :value="fmt(detail.current_balance_cny)" />
        <van-cell title="期初 CNY" :value="fmt(detail.opening_balance_cny)" />
        <van-cell title="本期变动 CNY" :value="fmt(detail.period_change_cny)" />
      </van-cell-group>

      <h2 class="section-title">交易</h2>
      <van-list
        v-model:loading="loadingMore"
        :finished="!hasMore"
        finished-text="没有更多了"
        @load="loadMore"
      >
        <van-cell
          v-for="(tx, index) in transactions"
          :key="`${tx.date}-${tx.description}-${index}`"
          :title="tx.description || tx.payee || '交易'"
          :label="`${tx.date} · ${(tx.counterpart_accounts || []).join(', ')}`"
          :value="`${tx.currency} ${fmt(tx.amount)}`"
          is-link
          @click="openTx(tx)"
        />
      </van-list>
      <van-notice-bar v-if="error" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ error }}</van-notice-bar>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onActivated, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ApiError } from '../../api/client'
import {
  reportsApi,
  type AccountDetailResponse,
  type AccountTransactionItem,
} from '../../api/reports'
import { formatAmountDisplay } from '../../utils/decimal'

const route = useRoute()
const router = useRouter()
const detail = ref<AccountDetailResponse | null>(null)
const transactions = ref<AccountTransactionItem[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const hasMore = ref(false)
const nextCursor = ref<string | null>(null)
const error = ref('')
const scrollY = ref(0)

function fmt(value: string) {
  return formatAmountDisplay(value, 2)
}

function queryParams() {
  return {
    account: String(route.query.account || ''),
    start_date: route.query.start_date ? String(route.query.start_date) : undefined,
    end_date: route.query.end_date ? String(route.query.end_date) : undefined,
  }
}

async function reload() {
  loading.value = true
  error.value = ''
  nextCursor.value = null
  transactions.value = []
  try {
    const params = queryParams()
    if (!params.account) {
      error.value = '缺少账户参数'
      return
    }
    const page = await reportsApi.getAccountDetail({ ...params, limit: 20 })
    detail.value = page
    transactions.value = page.transactions || []
    nextCursor.value = page.next_cursor || null
    hasMore.value = Boolean(page.has_more)
  } catch (reason) {
    const err = reason as ApiError
    error.value = err.code === 'LEDGER_PROJECTION_DIRTY'
      ? '账本投影未就绪，请稍后重试'
      : err.message
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function loadMore() {
  if (!hasMore.value || !nextCursor.value) {
    loadingMore.value = false
    return
  }
  try {
    const page = await reportsApi.getAccountDetail({
      ...queryParams(),
      cursor: nextCursor.value,
      limit: 20,
    })
    transactions.value = [...transactions.value, ...(page.transactions || [])]
    nextCursor.value = page.next_cursor || null
    hasMore.value = Boolean(page.has_more)
    if (page.current_balance_cny) detail.value = { ...detail.value!, ...page }
  } catch (reason) {
    error.value = (reason as ApiError).message
    hasMore.value = false
  } finally {
    loadingMore.value = false
  }
}

function openTx(tx: AccountTransactionItem) {
  scrollY.value = window.scrollY
  if (tx.id) router.push(`/transactions/${tx.id}`)
}

watch(
  () => [route.query.account, route.query.start_date, route.query.end_date],
  () => reload(),
)

onMounted(reload)
onActivated(() => {
  if (scrollY.value) window.scrollTo(0, scrollY.value)
})
</script>

<style scoped>
.summary-card { margin-top: 8px; }
.section-title { margin: 16px 16px 8px; font-size: 15px; }
</style>
