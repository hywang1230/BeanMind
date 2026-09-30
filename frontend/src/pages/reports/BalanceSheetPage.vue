<template>
  <section class="page secondary-page balance-sheet-page">
    <van-nav-bar title="资产负债表" left-arrow @click-left="router.back()" />
    <header class="page-header">
      <van-cell-group inset>
        <MonthPicker v-model="month" label="截止月份" />
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
import MonthPicker from '../../components/MonthPicker.vue'
import { formatAmountDisplay } from '../../utils/decimal'
import { monthEnd, reportMonth } from '../../utils/reportMonth'
import ReportTreeSection from './ReportTreeSection.vue'

const route = useRoute()
const router = useRouter()
const month = ref(queryMonth())
const data = ref<BalanceSheetResponse | null>(null)
const loading = ref(false)
const error = ref('')

function fmt(value: string) {
  return formatAmountDisplay(value, 2)
}

function applyDate() {
  const { as_of_date: _legacyDate, ...query } = route.query
  router.replace({ query: { ...query, month: month.value } })
}

function queryMonth() {
  return reportMonth(route.query.month || route.query.as_of_date)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await reportsApi.getBalanceSheet({ as_of_date: monthEnd(queryMonth()) })
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
    query: { account, end_date: data.value?.as_of_date || monthEnd(queryMonth()) },
  })
}

watch(
  () => [route.query.month, route.query.as_of_date],
  () => {
    month.value = queryMonth()
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
