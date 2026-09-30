<template>
  <section class="page secondary-page income-statement-page">
    <van-nav-bar title="利润表" left-arrow @click-left="router.back()" />
    <header class="page-header">
      <van-cell-group inset>
        <MonthPicker v-model="startMonth" label="开始月份" />
        <MonthPicker v-model="endMonth" label="结束月份" />
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
import { showToast } from 'vant'
import type { ApiError } from '../../api/client'
import { reportsApi, type IncomeExpenseItem, type IncomeStatementResponse } from '../../api/reports'
import MonthPicker from '../../components/MonthPicker.vue'
import { formatAmountDisplay } from '../../utils/decimal'
import { monthEnd, monthStart, reportMonth } from '../../utils/reportMonth'
import ReportTreeSection, { type TreeItem } from './ReportTreeSection.vue'

const route = useRoute()
const router = useRouter()
const startMonth = ref(queryMonths().start)
const endMonth = ref(queryMonths().end)
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
  if (startMonth.value > endMonth.value) {
    showToast('开始月份不能晚于结束月份')
    return
  }
  const { start_date: _legacyStart, end_date: _legacyEnd, ...query } = route.query
  router.replace({
    query: {
      ...query,
      start_month: startMonth.value,
      end_month: endMonth.value,
    },
  })
}

function queryMonths() {
  return {
    start: reportMonth(route.query.start_month || route.query.start_date),
    end: reportMonth(route.query.end_month || route.query.end_date),
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const months = queryMonths()
    if (months.start > months.end) {
      error.value = '开始月份不能晚于结束月份'
      data.value = null
      return
    }
    data.value = await reportsApi.getIncomeStatement({
      start_date: monthStart(months.start),
      end_date: monthEnd(months.end),
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
      start_date: data.value?.start_date || monthStart(queryMonths().start),
      end_date: data.value?.end_date || monthEnd(queryMonths().end),
    },
  })
}

watch(
  () => [route.query.start_month, route.query.end_month, route.query.start_date, route.query.end_date],
  () => {
    startMonth.value = queryMonths().start
    endMonth.value = queryMonths().end
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
