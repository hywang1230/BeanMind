<template>
  <section class="page dashboard-page">
    <header class="page-header">
      <h1>财务首页</h1>
      <input v-model="month" type="month" @change="load" />
    </header>
    <div v-if="loading" class="state-card"><van-loading>加载中</van-loading></div>
    <van-empty v-else-if="error" image="error" :description="error">
      <van-button type="primary" size="small" @click="load">重试</van-button>
    </van-empty>
    <template v-else-if="data">
      <div class="metric-grid page-section">
        <div class="metric"><div class="metric-label">净资产</div><div class="metric-value">{{ money(data.net_worth) }}</div></div>
        <div class="metric"><div class="metric-label">本月结余</div><div class="metric-value" :class="data.net_income.startsWith('-') ? 'negative' : 'positive'">{{ money(data.net_income) }}</div></div>
        <div class="metric"><div class="metric-label">收入</div><div class="metric-value positive">{{ money(data.income) }}</div></div>
        <div class="metric"><div class="metric-label">支出</div><div class="metric-value negative">{{ money(data.expense) }}</div></div>
        <div class="metric"><div class="metric-label">资产</div><div class="metric-value">{{ money(data.assets) }}</div></div>
        <div class="metric"><div class="metric-label">负债</div><div class="metric-value">{{ money(data.liabilities) }}</div></div>
      </div>
      <van-cell-group inset class="page-section">
        <van-cell title="预算风险" :value="riskText" is-link to="/budgets" />
        <van-cell title="月度复盘" :value="data.review_status" is-link :to="`/reviews/${month}`" />
      </van-cell-group>
      <van-notice-bar v-if="data.missing_exchange_rates.length" color="#ad6800" background="#fff7e6">
        缺少汇率：{{ data.missing_exchange_rates.join('、') }}，相关金额未合并
      </van-notice-bar>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { dashboardApi, type Dashboard } from '../../api/dashboard'
import type { ApiError } from '../../api/client'

const month = ref(new Date().toISOString().slice(0, 7))
const data = ref<Dashboard | null>(null)
const loading = ref(false)
const error = ref('')
const riskText = computed(() => ({ NORMAL: '正常', WARNING: '接近额度', EXCEEDED: '已超支' }[data.value?.budget_risk || 'NORMAL']))
function money(value: string) { return `${data.value?.currency || 'CNY'} ${value}` }
async function load() {
  loading.value = true; error.value = ''
  try { data.value = await dashboardApi.get(month.value) }
  catch (reason) { error.value = (reason as ApiError).message }
  finally { loading.value = false }
}
onMounted(load)
</script>
