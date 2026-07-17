<template>
  <section class="page monthly-review-page">
    <van-nav-bar title="月度复盘" left-arrow @click-left="router.back()" />
    <header class="review-month"><MonthPicker v-model="month" @change="changeMonth" /></header>
    <div v-if="loading" class="state-card"><van-loading>加载中</van-loading></div>
    <van-empty v-else-if="error && !review" image="error" :description="error"><van-button @click="load">重试</van-button></van-empty>
    <template v-else-if="review">
      <div class="review-status" :class="`status-${review.status.toLowerCase()}`">{{ statusText(review.status) }}<span v-if="review.generated_at"> · {{ review.generated_at }}</span></div>
      <van-notice-bar v-if="review.status === 'DISABLED'">LLM 未启用，确定性财务事实仍可查看</van-notice-bar>
      <van-notice-bar v-else-if="review.status === 'FAILED'" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ review.last_error || '生成失败，可在下方重试' }}</van-notice-bar>
      <h2 class="section-heading">本月事实</h2>
      <div class="finance-card review-facts page-section">
        <div><span>收入</span><strong class="income">{{ fact('income') }}</strong></div>
        <div><span>支出</span><strong class="expense">{{ fact('expense') }}</strong></div>
        <div><span>预算风险项</span><strong>{{ String(review.facts.risk_items?.length || 0) }}</strong></div>
      </div>
      <div v-if="review.monthly_summary" class="finance-card review-summary page-section"><h2>复盘总结</h2><p>{{ review.monthly_summary }}</p></div>
      <div v-if="review.next_month_suggestions.length" class="finance-card suggestions page-section"><h2>下月建议</h2><ol><li v-for="item in review.next_month_suggestions" :key="item">{{ item }}</li></ol></div>
      <div class="review-actions"><van-button block :plain="Boolean(review.monthly_summary)" type="primary" :loading="review.status==='PROCESSING'" :disabled="review.status==='DISABLED'" @click="generate">{{ review.monthly_summary ? '重新生成' : '生成复盘' }}</van-button></div>
      <van-notice-bar v-if="error" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ error }}</van-notice-bar>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'; import { useRoute,useRouter } from 'vue-router'; import { monthlyReviewsApi,type MonthlyReview } from '../../api/monthlyReviews'; import type { ApiError } from '../../api/client'; import MonthPicker from '../../components/MonthPicker.vue'
const route=useRoute();const router=useRouter();const month=ref(String(route.params.month));const review=ref<MonthlyReview|null>(null);const loading=ref(false);const error=ref('');let timer:number|undefined
function fact(name:'income'|'expense'){const values=review.value?.facts.current?.[name]||{};return Object.entries(values).map(([currency,value])=>`${currency} ${value}`).join(' / ')||'0'}
function statusText(status:MonthlyReview['status']){return ({DISABLED:'模型未启用',NOT_GENERATED:'尚未生成',PROCESSING:'生成中',READY:'已生成',FAILED:'生成失败'} as const)[status]}
async function load(){loading.value=true;error.value='';try{review.value=await monthlyReviewsApi.get(month.value);schedule()}catch(reason){error.value=(reason as ApiError).message}finally{loading.value=false}}
async function generate(){error.value='';try{review.value=await monthlyReviewsApi.generate(month.value,Boolean(review.value?.monthly_summary));schedule()}catch(reason){error.value=(reason as ApiError).message}}
function schedule(){if(timer)window.clearTimeout(timer);if(review.value?.status==='PROCESSING')timer=window.setTimeout(async()=>{try{review.value=await monthlyReviewsApi.get(month.value);schedule()}catch(reason){error.value=(reason as ApiError).message}},1000)}
function changeMonth(){router.replace(`/reviews/${month.value}`);load()}
onMounted(load);onBeforeUnmount(()=>{if(timer)window.clearTimeout(timer)})
</script>

<style scoped>
.review-month{display:flex;justify-content:center;margin:-6px 0 18px}.review-status{display:inline-flex;align-items:center;margin-bottom:16px;padding:7px 12px;border:1px solid var(--bm-border);border-radius:999px;color:var(--bm-muted);font-size:13px}.review-status::before{width:8px;height:8px;margin-right:8px;border-radius:50%;background:var(--bm-faint);content:''}.status-ready::before{background:var(--bm-primary)}.status-failed::before{background:var(--bm-expense)}.status-processing::before{background:var(--bm-warn)}.review-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));padding:18px 4px;text-align:center}.review-facts>div{min-width:0;padding:0 8px;border-right:1px solid var(--bm-border)}.review-facts>div:last-child{border-right:0}.review-facts span,.review-facts strong{display:block}.review-facts span{color:var(--bm-muted);font-size:13px}.review-facts strong{margin-top:10px;font-size:16px;word-break:break-word}.review-summary h2,.suggestions h2{margin:0 0 14px;font-size:18px}.review-summary p{margin:0;line-height:1.8;white-space:pre-wrap}.suggestions ol{display:grid;gap:12px;margin:0;padding-left:26px}.suggestions li{padding-left:4px;line-height:1.6}.suggestions li::marker{color:var(--bm-primary);font-weight:700}.review-actions{margin:18px 0}.review-actions :deep(.van-button){height:46px;border-radius:10px}
</style>
