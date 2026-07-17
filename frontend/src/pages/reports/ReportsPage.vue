<template>
  <section class="page secondary-page reports-page">
    <van-nav-bar title="高级报表" left-arrow @click-left="router.back()" />
    <h2 class="section-title">按月查询</h2>
    <header class="page-header">
      <MonthPicker v-model="month" />
      <van-button size="small" @click="load">查询</van-button>
    </header>
    <div v-if="loading" class="state-card"><van-loading /></div>
    <van-empty v-else-if="error" image="error" :description="error">
      <van-button @click="load">重试</van-button>
    </van-empty>
    <template v-else>
      <h2 v-if="balance" class="section-title">资产概览</h2>
      <van-cell-group v-if="balance" inset class="page-section report-card">
        <van-cell title="净资产" :value="formatMoney(balance.net_worth_cny)" />
        <van-cell title="资产" :value="formatMoney(balance.total_assets_cny)" />
        <van-cell title="负债" :value="formatMoney(balance.total_liabilities_cny)" />
      </van-cell-group>
      <h2 v-if="income" class="section-title">收支概览</h2>
      <van-cell-group v-if="income" inset class="report-card">
        <van-cell title="收入"><template #value><span class="income">{{ formatMoney(income.total_income_cny) }}</span></template></van-cell>
        <van-cell title="支出"><template #value><span class="expense">{{ formatMoney(income.total_expenses_cny) }}</span></template></van-cell>
        <van-cell title="结余" :value="formatMoney(income.net_profit_cny)" />
      </van-cell-group>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import type { ApiError } from '../../api/client'
import MonthPicker from '../../components/MonthPicker.vue'
import {
  reportsApi,
  type BalanceSheetResponse,
  type IncomeStatementResponse,
} from '../../api/reports'

const router = useRouter()
const month = ref(new Date().toISOString().slice(0, 7))
const balance = ref<BalanceSheetResponse | null>(null)
const income = ref<IncomeStatementResponse | null>(null)
const loading = ref(false)
const error = ref('')

function range() {
  const parts = month.value.split('-')
  const year = Number(parts[0] || 0)
  const monthNumber = Number(parts[1] || 0)
  const end = new Date(year, monthNumber, 0).getDate()
  return {
    start_date: `${month.value}-01`,
    end_date: `${month.value}-${String(end).padStart(2, '0')}`,
  }
}

function formatMoney(value: string): string {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value))
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const dates = range()
    ;[balance.value, income.value] = await Promise.all([
      reportsApi.getBalanceSheet({ as_of_date: dates.end_date }),
      reportsApi.getIncomeStatement(dates),
    ])
  } catch (reason) {
    error.value = (reason as ApiError).message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>.report-card :deep(.van-cell__value){font-weight:700}</style>
