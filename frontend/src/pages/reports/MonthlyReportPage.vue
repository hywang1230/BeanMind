<template>
  <section class="page monthly-review-page">
    <van-nav-bar title="月度复盘" left-arrow @click-left="router.back()" />
    <header class="page-header"><h1>{{ month }}</h1><input v-model="month" type="month" @change="changeMonth" /></header>
    <div v-if="loading" class="state-card"><van-loading>加载中</van-loading></div>
    <van-empty v-else-if="error && !review" image="error" :description="error"><van-button @click="load">重试</van-button></van-empty>
    <template v-else-if="review">
      <van-notice-bar v-if="review.status === 'DISABLED'">LLM 未启用，确定性财务事实仍可查看</van-notice-bar>
      <van-notice-bar v-else-if="review.status === 'FAILED'" color="#c92a2a" background="#fff1f0">{{ review.last_error || '生成失败' }}</van-notice-bar>
      <van-cell-group inset class="page-section">
        <van-cell title="状态" :value="review.status" />
        <van-cell title="本月收入" :value="fact('income')" />
        <van-cell title="本月支出" :value="fact('expense')" />
        <van-cell title="预算风险项" :value="String(review.facts.risk_items?.length || 0)" />
      </van-cell-group>
      <div v-if="review.monthly_summary" class="metric page-section"><div class="metric-label">复盘总结</div><p>{{ review.monthly_summary }}</p></div>
      <van-cell-group v-if="review.next_month_suggestions.length" inset class="page-section"><van-cell v-for="item in review.next_month_suggestions" :key="item" title="下月建议" :label="item" /></van-cell-group>
      <div style="margin:16px"><van-button block type="primary" :loading="review.status==='PROCESSING'" :disabled="review.status==='DISABLED'" @click="generate">{{ review.monthly_summary ? '重新生成' : '生成复盘' }}</van-button></div>
      <van-notice-bar v-if="error" color="#c92a2a" background="#fff1f0">{{ error }}</van-notice-bar>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'; import { useRoute,useRouter } from 'vue-router'; import { monthlyReviewsApi,type MonthlyReview } from '../../api/monthlyReviews'; import type { ApiError } from '../../api/client'
const route=useRoute();const router=useRouter();const month=ref(String(route.params.month));const review=ref<MonthlyReview|null>(null);const loading=ref(false);const error=ref('');let timer:number|undefined
function fact(name:'income'|'expense'){const values=review.value?.facts.current?.[name]||{};return Object.entries(values).map(([currency,value])=>`${currency} ${value}`).join(' / ')||'0'}
async function load(){loading.value=true;error.value='';try{review.value=await monthlyReviewsApi.get(month.value);schedule()}catch(reason){error.value=(reason as ApiError).message}finally{loading.value=false}}
async function generate(){error.value='';try{review.value=await monthlyReviewsApi.generate(month.value,Boolean(review.value?.monthly_summary));schedule()}catch(reason){error.value=(reason as ApiError).message}}
function schedule(){if(timer)window.clearTimeout(timer);if(review.value?.status==='PROCESSING')timer=window.setTimeout(async()=>{try{review.value=await monthlyReviewsApi.get(month.value);schedule()}catch(reason){error.value=(reason as ApiError).message}},1000)}
function changeMonth(){router.replace(`/reviews/${month.value}`);load()}
onMounted(load);onBeforeUnmount(()=>{if(timer)window.clearTimeout(timer)})
</script>
