<template>
  <section class="page secondary-page income-statement-page">
    <van-nav-bar title="利润表" left-arrow @click-left="router.back()" />
    <header class="page-header">
      <van-cell-group inset>
        <DateRangePickerField v-model:start-date="startDate" v-model:end-date="endDate" />
      </van-cell-group>
      <van-button block size="small" type="primary" @click="applyDate">查询</van-button>
    </header>

    <div v-if="loading" class="state-card"><van-loading /></div>
    <van-empty v-else-if="error" image="error" :description="error">
      <van-button @click="load">重试</van-button>
    </van-empty>
    <template v-else-if="data">
      <van-cell-group inset class="summary-card">
        <van-cell title="总收入" :value="fmt(data.total_income_cny)" />
        <van-cell title="总支出" :value="fmt(data.total_expenses_cny)" />
        <van-cell title="净利润" :value="fmt(data.net_profit_cny)" />
      </van-cell-group>

      <ReportTreeSection
        title="收入"
        :items="toTreeItems(data.income?.items || [])"
        amount-key="amounts"
        show-percentage
        @open="openAccount"
      />
      <ReportTreeSection
        title="支出"
        :items="toTreeItems(data.expenses?.items || [])"
        amount-key="amounts"
        show-percentage
        @open="openAccount"
      />
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ApiError } from '../../api/client'
import { reportsApi, type IncomeExpenseItem, type IncomeStatementResponse } from '../../api/reports'
import DateRangePickerField from '../../components/DateRangePickerField.vue'
import { formatAmountDisplay } from '../../utils/decimal'
import ReportTreeSection, { type TreeItem } from './ReportTreeSection.vue'

const route = useRoute()
const router = useRouter()
const today = new Date()
const month = today.toISOString().slice(0, 7)
const defaultEnd = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate()
const startDate = ref(String(route.query.start_date || `${month}-01`))
const endDate = ref(String(route.query.end_date || `${month}-${String(defaultEnd).padStart(2, '0')}`))
const data = ref<IncomeStatementResponse | null>(null)
const loading = ref(false)
const error = ref('')

function fmt(value: string) {
  return formatAmountDisplay(value, 2)
}

function toTreeItems(items: IncomeExpenseItem[]): TreeItem[] {
  return items.map((item) => ({
    account: item.account,
    display_name: item.display_name,
    balances: item.amounts,
    total_cny: item.total_cny,
    percentage: item.percentage,
    children: toTreeItems(item.children || []),
    depth: item.depth,
  }))
}

function applyDate() {
  router.replace({
    query: {
      ...route.query,
      start_date: startDate.value,
      end_date: endDate.value,
    },
  })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await reportsApi.getIncomeStatement({
      start_date: startDate.value,
      end_date: endDate.value,
    })
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
    query: {
      account,
      start_date: startDate.value,
      end_date: endDate.value,
    },
  })
}

watch(
  () => [route.query.start_date, route.query.end_date],
  () => {
    if (route.query.start_date) startDate.value = String(route.query.start_date)
    if (route.query.end_date) endDate.value = String(route.query.end_date)
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
