<template>
  <section class="page secondary-page balance-sheet-page">
    <van-nav-bar title="资产负债表" left-arrow @click-left="router.back()" />
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
      <van-cell-group inset class="summary-card">
        <van-cell title="净资产" :value="fmt(data.net_worth_cny)" />
        <van-cell title="总资产" :value="fmt(data.total_assets_cny)" />
        <van-cell title="总负债" :value="fmt(data.total_liabilities_cny)" />
        <van-cell title="总权益" :value="fmt(data.total_equity_cny)" />
      </van-cell-group>

      <ReportTreeSection
        title="资产"
        :items="data.assets?.accounts || []"
        amount-key="balances"
        @open="openAccount"
      />
      <ReportTreeSection
        title="负债"
        :items="data.liabilities?.accounts || []"
        amount-key="balances"
        @open="openAccount"
      />
      <ReportTreeSection
        title="权益"
        :items="data.equity?.accounts || []"
        amount-key="balances"
        @open="openAccount"
      />
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ApiError } from '../../api/client'
import { reportsApi, type BalanceSheetResponse } from '../../api/reports'
import DatePickerField from '../../components/DatePickerField.vue'
import { formatAmountDisplay } from '../../utils/decimal'
import ReportTreeSection from './ReportTreeSection.vue'

const route = useRoute()
const router = useRouter()
const asOfDate = ref(String(route.query.as_of_date || new Date().toISOString().slice(0, 10)))
const data = ref<BalanceSheetResponse | null>(null)
const loading = ref(false)
const error = ref('')

function fmt(value: string) {
  return formatAmountDisplay(value, 2)
}

function applyDate() {
  router.replace({ query: { ...route.query, as_of_date: asOfDate.value } })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await reportsApi.getBalanceSheet({ as_of_date: asOfDate.value })
  } catch (reason) {
    const err = reason as ApiError
    error.value = err.code === 'MISSING_EXCHANGE_RATE'
      ? `${err.message}（缺少汇率）`
      : err.message
    data.value = null
  } finally {
    loading.value = false
  }
}

function openAccount(account: string) {
  router.push({
    path: '/reports/account-detail',
    query: { account, end_date: asOfDate.value },
  })
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
.page-header :deep(.van-cell-group--inset) {
  margin-left: 0;
  margin-right: 0;
}
.summary-card { margin-top: 8px; }
</style>
