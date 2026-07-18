<template>
  <section class="page secondary-page reports-page">
    <van-nav-bar title="报表" left-arrow @click-left="router.back()" />
    <div class="report-month">
      <MonthPicker v-model="month" />
    </div>

    <h2 class="section-title">报表入口</h2>
    <van-cell-group inset class="entry-group">
      <van-cell title="资产负债表" label="查看截至某日的资产、负债与权益" is-link to="/reports/balance-sheet" />
      <van-cell title="利润表" label="查看指定期间的收入、支出与结余" is-link :to="incomeStatementLink" />
      <van-cell title="月度复盘" label="总结本月收支并生成下月建议" is-link :to="`/reviews/${month}`" />
    </van-cell-group>

    <section class="trend-card" data-testid="cashflow-trend-card">
      <div class="section-head">
        <h2>近 12 个月收支趋势</h2>
        <span class="muted">截至 {{ month }}</span>
      </div>

      <van-notice-bar
        v-if="trendData?.missing_exchange_rates?.length"
        class="trend-warning"
        color="var(--bm-warn)"
        background="var(--bm-warn-soft)"
        left-icon="warning-o"
        data-testid="cashflow-trend-missing-rates"
      >
        部分月份缺少汇率，趋势不完整
      </van-notice-bar>

      <div v-if="trendLoading && !trendData" class="state-card" data-testid="cashflow-trend-loading">
        <van-loading size="20px">加载趋势…</van-loading>
      </div>
      <van-empty
        v-else-if="trendError && !trendData"
        image="error"
        :description="trendError"
        data-testid="cashflow-trend-error"
      >
        <van-button size="small" type="primary" @click="loadTrend">重试趋势</van-button>
      </van-empty>
      <template v-else-if="trendData">
        <van-notice-bar
          v-if="trendError"
          color="var(--bm-expense)"
          background="var(--bm-danger-soft)"
          data-testid="cashflow-trend-soft-error"
        >
          {{ trendError }}
          <template #right-icon>
            <van-button size="mini" plain type="primary" @click="loadTrend">重试</van-button>
          </template>
        </van-notice-bar>
        <MonthlyCashflowTrendChart
          :key="trendData.end_month"
          :points="trendData.points"
          :currency="trendData.currency"
        />
      </template>
    </section>

    <div v-if="loading" class="state-card"><van-loading /></div>
    <van-empty v-else-if="error" image="error" :description="error">
      <van-button @click="load">重试</van-button>
    </van-empty>
    <template v-else-if="balance && income">
      <h2 class="section-title">资产概览</h2>
      <van-cell-group inset>
        <van-cell title="净资产" :value="formatMoney(balance.net_worth_cny)" />
        <van-cell title="资产" :value="formatMoney(balance.total_assets_cny)" />
        <van-cell title="负债" :value="formatMoney(balance.total_liabilities_cny)" />
      </van-cell-group>
      <h2 class="section-title">收支概览</h2>
      <van-cell-group inset>
        <van-cell title="收入"><template #value><span class="income">{{ formatMoney(income.total_income_cny) }}</span></template></van-cell>
        <van-cell title="支出"><template #value><span class="expense">{{ formatMoney(income.total_expenses_cny) }}</span></template></van-cell>
        <van-cell title="结余" :value="formatMoney(income.net_profit_cny)" />
      </van-cell-group>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { ApiError } from '../../api/client'
import {
  reportsApi,
  type BalanceSheetResponse,
  type IncomeStatementResponse,
  type MonthlyCashflowTrendResponse,
} from '../../api/reports'
import MonthPicker from '../../components/MonthPicker.vue'
import MonthlyCashflowTrendChart from '../../components/MonthlyCashflowTrendChart.vue'
import { formatAmountDisplay } from '../../utils/decimal'

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function monthDates(value: string) {
  const parts = value.split('-')
  const year = Number(parts[0])
  const mon = Number(parts[1])
  if (!Number.isFinite(year) || !Number.isFinite(mon)) {
    return { start_date: `${value}-01`, end_date: `${value}-01` }
  }
  const end = new Date(year, mon, 0).getDate()
  return {
    start_date: `${value}-01`,
    end_date: `${value}-${String(end).padStart(2, '0')}`,
  }
}

const router = useRouter()
const month = ref(currentMonth())
const balance = ref<BalanceSheetResponse | null>(null)
const income = ref<IncomeStatementResponse | null>(null)
const loading = ref(false)
const error = ref('')

const trendData = ref<MonthlyCashflowTrendResponse | null>(null)
const trendLoading = ref(false)
const trendError = ref('')

const incomeStatementLink = computed(() => {
  const dates = monthDates(month.value)
  return `/reports/income-statement?start_date=${dates.start_date}&end_date=${dates.end_date}`
})

function formatMoney(value: string): string {
  return formatAmountDisplay(value, 2)
}

async function loadTrend() {
  trendLoading.value = true
  trendError.value = ''
  try {
    trendData.value = await reportsApi.getMonthlyCashflowTrend({ end_month: month.value })
  } catch (reason) {
    const err = reason as ApiError
    trendError.value = err.code === 'LEDGER_PROJECTION_DIRTY'
      ? '账本投影未就绪，请稍后重试趋势'
      : (err.message || '趋势加载失败')
    // 保留已有趋势数据时仅提示，不遮挡整页
    if (!trendData.value) trendData.value = null
  } finally {
    trendLoading.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const dates = monthDates(month.value)
    const [bs, is] = await Promise.all([
      reportsApi.getBalanceSheet({ as_of_date: dates.end_date }),
      reportsApi.getIncomeStatement(dates),
    ])
    balance.value = bs
    income.value = is
  } catch (reason) {
    const err = reason as ApiError
    error.value = err.message || '报表加载失败'
    balance.value = null
    income.value = null
  } finally {
    loading.value = false
  }
}

watch(month, () => {
  // 切换月份时清空旧趋势选中态（通过 key 重置组件）并独立刷新
  trendData.value = null
  void load()
  void loadTrend()
})

onMounted(() => {
  void load()
  void loadTrend()
})
</script>

<style scoped>
.report-month {
  display: flex;
  justify-content: center;
  margin: 4px 0 14px;
}
.entry-group, .van-cell-group { margin-bottom: 12px; }
.trend-card {
  margin: 0 0 14px;
  padding: 14px;
  border: 1px solid var(--bm-border);
  border-radius: 14px;
  background: var(--bm-surface);
  box-shadow: var(--bm-card-shadow);
  display: grid;
  gap: 10px;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.section-head h2 {
  margin: 0;
  font-size: 16px;
}
.muted { color: var(--bm-muted); font-size: 12px; }
.trend-warning { border-radius: 10px; }
.state-card { padding: 24px; display: flex; justify-content: center; }
.income { color: var(--bm-income, #07c160); }
.expense { color: var(--bm-expense, #ee0a24); }
</style>
