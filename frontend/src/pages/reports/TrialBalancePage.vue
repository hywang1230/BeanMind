<template>
  <section class="page secondary-page trial-balance-page">
    <van-nav-bar title="试算表" left-arrow @click-left="router.back()" />
    <header class="page-header">
      <van-cell-group inset>
        <DatePickerField v-model="asOfDate" label="截止日期" />
      </van-cell-group>
      <van-button block size="small" type="primary" @click="applyDate">查询</van-button>
    </header>

    <div v-if="loading" class="state-card"><van-loading /></div>
    <van-empty v-else-if="error" image="error" :description="error">
      <van-button @click="load">重试</van-button>
    </van-empty>
    <template v-else-if="data">
      <van-notice-bar v-if="data.ledger_error_count" color="var(--bm-warn)" background="var(--bm-warn-soft)">
        账本加载发现 {{ data.ledger_error_count }} 项错误，请先核查账本；以下金额不能视为已核对通过。
      </van-notice-bar>
      <van-cell-group inset class="summary-card">
        <van-cell title="五类折算合计" :value="fmt(data.signed_sum_cny)" />
        <van-cell
          v-for="category in data.categories"
          :key="category.type"
          :title="category.name"
          :label="originalAmounts(category.totals_by_currency)"
          :value="fmt(category.total_cny)"
        />
      </van-cell-group>
      <p class="report-note">借方为正、贷方为负。折算合计非零可能与跨币种交易的截止日汇率有关，不能单凭此数判断账本错误。</p>
      <van-cell title="查看资产负债表" is-link @click="openBalanceSheet" />
      <ReportTreeSection
        v-for="category in data.categories"
        :key="category.type"
        :title="`${category.name}账户`"
        :items="category.accounts"
        @open="openAccount"
      />
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ApiError } from '../../api/client'
import { reportsApi, type TrialBalanceResponse } from '../../api/reports'
import DatePickerField from '../../components/DatePickerField.vue'
import { formatAmountDisplay } from '../../utils/decimal'
import ReportTreeSection from './ReportTreeSection.vue'

const route = useRoute()
const router = useRouter()
const asOfDate = ref(String(route.query.as_of_date || new Date().toISOString().slice(0, 10)))
const data = ref<TrialBalanceResponse | null>(null)
const loading = ref(false)
const error = ref('')
let loadSequence = 0

function fmt(value: string) {
  return formatAmountDisplay(value, 2)
}

function originalAmounts(amounts: Record<string, string>) {
  return Object.entries(amounts)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([currency, value]) => `${currency} ${fmt(value)}`)
    .join(' · ')
}

function applyDate() {
  router.replace({ query: { ...route.query, as_of_date: asOfDate.value } })
}

async function load() {
  const sequence = ++loadSequence
  const requestedDate = asOfDate.value
  loading.value = true
  error.value = ''
  try {
    const result = await reportsApi.getTrialBalance({ as_of_date: requestedDate })
    if (sequence === loadSequence) data.value = result
  } catch (reason) {
    if (sequence !== loadSequence) return
    const err = reason as ApiError
    error.value = err.code === 'MISSING_EXCHANGE_RATE'
      ? `${err.message}（缺少汇率）`
      : err.message
    data.value = null
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

function openAccount(account: string) {
  if (!data.value) return
  router.push({ path: '/reports/account-detail', query: { account, end_date: data.value.as_of_date } })
}

function openBalanceSheet() {
  if (!data.value) return
  router.push({ path: '/reports/balance-sheet', query: { as_of_date: data.value.as_of_date } })
}

watch(
  () => route.query.as_of_date,
  (value) => {
    if (value) asOfDate.value = String(value)
    load()
  },
)
onMounted(load)
</script>

<style scoped>
.page-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
  align-items: stretch;
  justify-content: stretch;
  padding: 8px 0 0;
  margin-bottom: 16px;
}
.page-header :deep(.van-cell-group--inset) { margin-left: 0; margin-right: 0; }
.summary-card { margin-top: 8px; }
.report-note { margin: 12px 16px; color: var(--bm-muted, #888); font-size: 12px; line-height: 1.5; }
</style>
