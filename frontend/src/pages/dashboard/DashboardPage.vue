<template>
  <section class="page page-with-pull dashboard-page">
    <div class="page-scroll">
    <van-pull-refresh v-model="refreshing" class="page-pull-refresh" pulling-text="下拉刷新" loosing-text="释放刷新" loading-text="刷新中..." success-text="刷新成功" @refresh="onRefresh">
    <header class="page-header">
      <h1>本月总览</h1>
      <MonthPicker v-model="month" @change="() => load()" />
    </header>
    <div v-if="loading" class="state-card"><van-loading>加载中</van-loading></div>
    <van-empty v-else-if="error" image="error" :description="error">
      <van-button type="primary" size="small" @click="() => load()">重试</van-button>
    </van-empty>
    <template v-else-if="data">
      <div class="finance-card net-worth-card page-section">
        <div class="metric-label net-worth-label">净资产</div>
        <div class="net-worth-value">{{ money(data.net_worth) }}</div>
        <div class="asset-summary">
          <span>资产 {{ money(data.assets) }}</span><i>·</i><span>负债 {{ money(data.liabilities) }}</span>
        </div>
      </div>
      <div class="finance-card cashflow-card page-section">
        <div><span class="metric-label">收入</span><strong class="income">{{ money(data.income) }}</strong></div>
        <div><span class="metric-label">支出</span><strong class="expense">{{ money(data.expense) }}</strong></div>
        <div><span class="metric-label">结余</span><strong :class="data.net_income.startsWith('-') ? 'expense' : 'income'">{{ money(data.net_income) }}</strong></div>
      </div>
      <h2 class="section-heading">本月关注</h2>
      <van-cell-group inset class="attention-list page-section">
        <van-cell title="预算风险" is-link to="/budgets">
          <template #icon><span class="attention-icon" :class="data.budget_risk === 'NORMAL' ? 'safe' : 'risky'">!</span></template>
          <template #value><van-tag :type="riskTagType">{{ riskText }}</van-tag></template>
        </van-cell>
        <van-cell title="月度复盘" is-link :to="`/reviews/${month}`">
          <template #icon><span class="attention-icon safe"><van-icon name="description-o" /></span></template>
          <template #value><van-tag plain type="success">{{ reviewStatusText }}</van-tag></template>
        </van-cell>
        <van-cell v-if="data.missing_exchange_rates.length" title="缺少汇率" is-link to="/exchange-rates">
          <template #icon><span class="attention-icon rate"><van-icon name="gold-coin-o" /></span></template>
          <template #value><strong class="warning">{{ data.missing_exchange_rates.join('、') }}</strong></template>
        </van-cell>
      </van-cell-group>
      <h2 class="section-heading">快捷入口</h2>
      <div class="finance-card quick-actions">
        <van-button plain class="quick-action" icon="balance-list-o" to="/accounts">账户</van-button>
        <van-button plain class="quick-action" icon="bar-chart-o" to="/reports">报表</van-button>
        <van-button type="primary" class="quick-action primary-action" icon="edit" to="/transactions/new">记一笔</van-button>
      </div>
    </template>
    </van-pull-refresh>

    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { dashboardApi, type Dashboard } from '../../api/dashboard'
import type { ApiError } from '../../api/client'
import MonthPicker from '../../components/MonthPicker.vue'

const month = ref(new Date().toISOString().slice(0, 7))
const data = ref<Dashboard | null>(null)
const loading = ref(false)
const refreshing = ref(false)
const error = ref('')
const riskText = computed(() => ({ NORMAL: '正常', WARNING: '接近额度', EXCEEDED: '已超支' }[data.value?.budget_risk || 'NORMAL']))
const riskTagType = computed(() => data.value?.budget_risk === 'EXCEEDED' ? 'danger' : data.value?.budget_risk === 'WARNING' ? 'warning' : 'success')
const reviewStatusText = computed(() => ({
  READY: '已生成',
  NOT_GENERATED: '可生成',
  PROCESSING: '生成中',
  FAILED: '可重试',
  DISABLED: '未启用',
}[data.value?.review_status || 'NOT_GENERATED'] || data.value?.review_status || '可生成'))

function money(value: string) {
  const currency = data.value?.currency || 'CNY'
  const normalized = value.trim()
  const negative = normalized.startsWith('-')
  const magnitude = negative ? normalized.slice(1) : normalized
  if (!/^\d+(?:\.\d+)?$/.test(magnitude)) return `${currency} ${value}`
  const [integer = '0', fraction = ''] = magnitude.split('.')
  const twoDigits = fraction.padEnd(2, '0').slice(0, 2)
  const thirdDigit = fraction[2] || '0'
  let cents = BigInt(integer) * 100n + BigInt(twoDigits)
  if (thirdDigit >= '5') cents += 1n
  const whole = (cents / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const decimal = (cents % 100n).toString().padStart(2, '0')
  const sign = negative && cents !== 0n ? '-' : ''
  return currency === 'CNY' ? `${sign}¥${whole}.${decimal}` : `${sign}${currency} ${whole}.${decimal}`
}
async function load(options: { silent?: boolean } = {}) {
  if (!options.silent) loading.value = true
  error.value = ''
  try { data.value = await dashboardApi.get(month.value) }
  catch (reason) { error.value = (reason as ApiError).message }
  finally { if (!options.silent) loading.value = false }
}
async function onRefresh() {
  try { await load({ silent: true }) }
  finally { refreshing.value = false }
}
onMounted(() => { load() })
</script>

<style scoped>
.dashboard-page { padding: 18px 16px 24px; }
.dashboard-page .page-header { margin-bottom: 22px; }
.dashboard-page .page-header h1 { flex: 1; font-size: 30px; font-weight: 750; white-space: nowrap; }
.net-worth-card { min-width: 0; padding: 24px 22px 23px; border-radius: 16px; }
.net-worth-label { display: flex; align-items: center; gap: 5px; font-size: 16px; }
.net-worth-value { margin-top: 14px; overflow: hidden; font-size: clamp(29px, 9.2vw, 40px); font-weight: 750; letter-spacing: -.035em; line-height: 1.15; white-space: nowrap; }
.asset-summary { display: flex; min-width: 0; margin-top: 18px; align-items: center; gap: 8px; color: var(--bm-muted); font-size: clamp(12px, 3.6vw, 15px); white-space: nowrap; }
.asset-summary span { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.asset-summary i { flex: none; color: var(--bm-faint); font-style: normal; }
.cashflow-card { display: grid; min-height: 108px; grid-template-columns: repeat(3, minmax(0, 1fr)); align-items: center; padding: 18px 4px; border-radius: 16px; text-align: center; }
.cashflow-card > div { min-width: 0; padding: 2px 5px; border-right: 1px solid var(--bm-border); }
.cashflow-card > div:last-child { border-right: 0; }
.cashflow-card span, .cashflow-card strong { display: block; }
.cashflow-card .metric-label { font-size: 15px; }
.cashflow-card strong { overflow: hidden; margin-top: 10px; font-size: clamp(13px, 4vw, 17px); line-height: 1.2; text-overflow: ellipsis; white-space: nowrap; }
.dashboard-page .section-heading { margin: 26px 2px 13px; font-size: 20px; }
.attention-list { margin-right: 0; margin-left: 0; border-radius: 16px; box-shadow: 0 3px 14px rgba(31, 35, 41, .035); }
.attention-icon { display: inline-grid; width: 30px; height: 30px; margin-right: 12px; place-items: center; border-radius: 50%; color: white; font-weight: 700; }
.attention-icon.safe { background: var(--bm-primary); }
.attention-icon.risky { background: var(--bm-expense); }
.attention-icon.rate { background: #f59e0b; }
.attention-list :deep(.van-cell) { align-items: center; min-height: 64px; padding: 14px 16px; }
.attention-list :deep(.van-cell__title) { font-size: 16px; }
.attention-list :deep(.van-cell__value) { display: flex; flex: none; align-items: center; margin-left: 10px; }
.quick-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; padding: 10px; border-radius: 16px; }
.quick-action { display: flex; height: 94px; flex-direction: column; gap: 8px; border-color: var(--bm-border); border-radius: 12px; color: var(--bm-text); font-size: 16px; }
.quick-action :deep(.van-button__icon) { margin: 0; color: var(--bm-primary); font-size: 28px; }
.quick-action :deep(.van-button__content) { flex-direction: column; gap: 8px; }
.quick-action.primary-action { color: white; }
.quick-action.primary-action :deep(.van-button__icon) { color: white; }
@media (max-width: 380px) {
  .dashboard-page .page-header h1 { font-size: 27px; }
  .cashflow-card strong { font-size: 13px; }
  .quick-actions { gap: 8px; padding: 10px; }
}
</style>
