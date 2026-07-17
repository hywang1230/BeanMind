<template>
  <section class="page budgets-page">
    <header class="page-header"><h1>月度预算</h1><input v-model="month" type="month" @change="load" /></header>
    <div v-if="loading" class="state-card"><van-loading>加载中</van-loading></div>
    <van-empty v-else-if="error && !budget" image="error" :description="error"><van-button size="small" type="primary" @click="load">重试</van-button></van-empty>
    <template v-else>
      <van-cell-group inset class="page-section">
        <van-field v-model="currency" label="币种" maxlength="16" />
        <van-cell title="总预算" :value="`${currency} ${total}`" />
        <van-cell v-if="budget" title="已用" :value="`${currency} ${budget.spent || '0'}`" />
        <van-cell v-if="budget" title="剩余" :value="`${currency} ${budget.remaining || total}`" />
      </van-cell-group>
      <van-cell-group v-for="(item, index) in items" :key="index" inset class="page-section">
        <van-field v-model="item.name" label="分类" placeholder="例如：餐饮" />
        <van-field v-model="item.account_pattern" label="账户范围" placeholder="Expenses:Food" />
        <van-field v-model="item.amount" label="额度" inputmode="decimal" />
        <van-cell v-if="item.spent !== undefined" title="执行" :label="`${item.spent} / ${item.amount}`">
          <template #value><van-tag :type="riskType(item.risk)">{{ riskText(item.risk) }}</van-tag></template>
        </van-cell>
        <van-button block plain type="danger" size="small" @click="items.splice(index, 1)">删除分类</van-button>
      </van-cell-group>
      <van-empty v-if="!items.length" description="本月尚未设置预算" />
      <div class="budget-actions">
        <van-button plain type="primary" @click="addItem">新增分类</van-button>
        <van-button plain @click="copyPrevious">复制上月</van-button>
        <van-button type="primary" :loading="saving" @click="save">保存预算</van-button>
      </div>
      <van-notice-bar v-if="error" color="#c92a2a" background="#fff1f0">{{ error }}</van-notice-bar>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { showConfirmDialog, showSuccessToast } from 'vant'
import { budgetsApi, type BudgetItem, type MonthlyBudget } from '../../api/budgets'
import type { ApiError } from '../../api/client'

const month = ref(new Date().toISOString().slice(0, 7)); const currency = ref('CNY')
const budget = ref<MonthlyBudget|null>(null); const items = ref<BudgetItem[]>([])
const loading = ref(false); const saving = ref(false); const error = ref('')
function addDecimalStrings(values: string[]): string {
  const normalized = values.map((value) => value.trim() || '0')
  const scale = Math.max(0, ...normalized.map((value) => value.split('.')[1]?.length ?? 0))
  const factor = 10n ** BigInt(scale)
  const sum = normalized.reduce((result, value) => {
    if (!/^-?\d+(\.\d+)?$/.test(value)) return result
    const [rawInteger, fraction = ''] = value.split('.')
    const integer = rawInteger ?? '0'
    const sign = integer.startsWith('-') ? -1n : 1n
    const units = BigInt(integer.replace('-', '')) * factor
      + BigInt(fraction.padEnd(scale, '0') || '0')
    return result + sign * units
  }, 0n)
  if (scale === 0) return sum.toString()
  const sign = sum < 0n ? '-' : ''
  const absolute = (sum < 0n ? -sum : sum).toString().padStart(scale + 1, '0')
  const integer = absolute.slice(0, -scale)
  const fraction = absolute.slice(-scale).replace(/0+$/, '')
  return `${sign}${integer}${fraction ? `.${fraction}` : ''}`
}

const total = computed(() => addDecimalStrings(items.value.map((item) => item.amount)))
function addItem(){items.value.push({name:'',account_pattern:'',amount:'0',display_order:items.value.length})}
function riskText(risk?:string){return ({NORMAL:'正常',WARNING:'接近额度',EXCEEDED:'已超支'} as Record<string,string>)[risk||'NORMAL']}
function riskType(risk?:string){return risk==='EXCEEDED'?'danger':risk==='WARNING'?'warning':'success'}
async function load(){loading.value=true;error.value='';try{budget.value=await budgetsApi.get(month.value,currency.value);items.value=budget.value.items.map(item=>({...item}))}catch(reason){error.value=(reason as ApiError).message;budget.value=null;items.value=[]}finally{loading.value=false}}
async function save(){saving.value=true;error.value='';try{budget.value=await budgetsApi.save(month.value,currency.value,items.value.map((item,index)=>({...item,display_order:index})));items.value=budget.value.items.map(item=>({...item}));showSuccessToast('预算已保存')}catch(reason){error.value=(reason as ApiError).message}finally{saving.value=false}}
async function copyPrevious(){error.value='';try{if(items.value.length){await showConfirmDialog({title:'覆盖预算',message:'当前分类会被上月配置替换，是否继续？'});budget.value=await budgetsApi.copyPrevious(month.value,currency.value,true)}else{budget.value=await budgetsApi.copyPrevious(month.value,currency.value)}items.value=budget.value.items.map(item=>({...item}))}catch(reason){if((reason as string)!=='cancel'&&typeof reason==='object')error.value=(reason as ApiError).message}}
onMounted(load)
</script>

<style scoped>.budget-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;margin:16px}</style>
