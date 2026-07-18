<template>
  <section class="page page-with-pull budgets-page">
    <div class="page-scroll">
    <van-pull-refresh v-model="refreshing" class="page-pull-refresh" pulling-text="下拉刷新" loosing-text="释放刷新" loading-text="刷新中..." success-text="刷新成功" @refresh="onRefresh">
    <header class="page-header"><h1>月度预算</h1><MonthPicker v-model="month" @change="onMonthChange" /></header>
    <div v-if="loading" class="state-card"><van-loading>加载中</van-loading></div>
    <van-empty v-else-if="error && !budget" image="error" :description="error"><van-button size="small" type="primary" @click="() => load()">重试</van-button></van-empty>
    <template v-else>
      <div class="finance-card budget-summary page-section">
        <div class="budget-total"><span>总预算</span><strong>{{ currency }} {{ total }}</strong></div>
        <div v-if="budget" class="budget-stats">
          <span>已用<strong>{{ currency }} {{ budget.spent || '0' }}</strong></span>
          <span>剩余<strong class="income">{{ currency }} {{ budget.remaining || total }}</strong></span>
        </div>
      </div>

      <!-- 查看态：只读展示 -->
      <template v-if="!editing">
        <van-cell-group v-for="(item, index) in items" :key="`view-${index}`" inset class="page-section budget-item" :class="`risk-${(item.risk || 'NORMAL').toLowerCase()}`">
          <van-cell :title="item.name || '未命名'" :label="patternsLabel(item)">
            <template #value><strong>{{ currency }} {{ item.amount }}</strong></template>
          </van-cell>
          <van-cell v-if="item.spent !== undefined" title="执行" :label="`${item.spent} / ${item.amount}`">
            <template #value><van-tag :type="riskType(item.risk)">{{ riskText(item.risk) }}</van-tag></template>
          </van-cell>
          <div v-if="item.usage_rate !== undefined && item.usage_rate !== null" class="budget-progress">
            <van-progress :percentage="progress(item.usage_rate)" :color="riskColor(item.risk)" :show-pivot="false" stroke-width="8" />
            <span :class="item.risk === 'EXCEEDED' ? 'expense' : item.risk === 'WARNING' ? 'warning' : 'income'">{{ percentage(item.usage_rate) }}%</span>
          </div>
        </van-cell-group>
        <van-empty v-if="!items.length" description="本月尚未设置预算" />
        <div class="budget-actions">
          <van-button block type="primary" @click="startEdit">编辑预算</van-button>
        </div>
      </template>

      <!-- 编辑态：表单操作 -->
      <template v-else>
        <van-cell-group v-for="(item, index) in items" :key="`edit-${index}`" inset class="page-section budget-item" :class="`risk-${(item.risk || 'NORMAL').toLowerCase()}`">
          <van-field v-model="item.name" label="分类" placeholder="例如：餐饮" />
          <AccountPicker
            :model-value="''"
            :selected-accounts="patternsOf(item)"
            :accounts="accounts"
            label="账户"
            :prefixes="['Expenses']"
            placeholder="请选择大类或账户（可多选）"
            allow-parent-select
            :error="accountError"
            @update:model-value="addPattern(item, $event)"
            @remove="removePattern(item, $event)"
          />
          <van-field v-model="item.amount" label="额度" inputmode="decimal" />
          <van-cell v-if="item.spent !== undefined" title="执行" :label="`${item.spent} / ${item.amount}`">
            <template #value><van-tag :type="riskType(item.risk)">{{ riskText(item.risk) }}</van-tag></template>
          </van-cell>
          <div v-if="item.usage_rate !== undefined && item.usage_rate !== null" class="budget-progress">
            <van-progress :percentage="progress(item.usage_rate)" :color="riskColor(item.risk)" :show-pivot="false" stroke-width="8" />
            <span :class="item.risk === 'EXCEEDED' ? 'expense' : item.risk === 'WARNING' ? 'warning' : 'income'">{{ percentage(item.usage_rate) }}%</span>
          </div>
          <van-button block plain type="danger" size="small" @click="removeItem(index)">删除分类</van-button>
        </van-cell-group>
        <van-empty v-if="!items.length" description="本月尚未设置预算" />
        <div class="budget-actions budget-actions-edit">
          <div class="budget-actions-row">
            <van-button plain type="primary" @click="addItem">新增分类</van-button>
            <van-button plain @click="copyPrevious">复制上月</van-button>
          </div>
          <div class="budget-actions-row">
            <van-button plain @click="cancelEdit">取消</van-button>
            <van-button type="primary" :loading="saving" @click="save">保存预算</van-button>
          </div>
        </div>
      </template>

      <van-notice-bar v-if="error" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ error }}</van-notice-bar>
    </template>
    </van-pull-refresh>

    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { showConfirmDialog, showSuccessToast } from 'vant'
import { accountsApi, type Account } from '../../api/accounts'
import { budgetsApi, type BudgetItem, type MonthlyBudget } from '../../api/budgets'
import type { ApiError } from '../../api/client'
import AccountPicker from '../../components/AccountPicker.vue'
import MonthPicker from '../../components/MonthPicker.vue'

const month = ref(new Date().toISOString().slice(0, 7))
const budget = ref<MonthlyBudget|null>(null); const items = ref<BudgetItem[]>([])
const currency = computed(() => budget.value?.currency || '')
const accounts = ref<Account[]>([])
const loading = ref(false); const refreshing = ref(false); const saving = ref(false); const error = ref(''); const accountError = ref('')
const editing = ref(false)

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
function patternsOf(item: BudgetItem) {
  return String(item.account_pattern || '')
    .replace(/，/g, ',')
    .split(',')
    .map((part) => part.trim().replace(/^:+|:+$/g, ''))
    .filter(Boolean)
}
function patternsLabel(item: BudgetItem) {
  const patterns = patternsOf(item)
  return patterns.length ? patterns.join(' · ') : '未选账户'
}
function setPatterns(item: BudgetItem, patterns: string[]) {
  item.account_pattern = patterns.join(',')
}
function patternsOverlap(first: string, second: string): boolean {
  return first === second || first.startsWith(`${second}:`) || second.startsWith(`${first}:`)
}

function addPattern(item: BudgetItem, name: string) {
  if (!name) return
  // 选择大类时自动去掉其子/祖先范围，避免保存时 OVERLAPPING_BUDGET_PATTERN
  const next = patternsOf(item).filter((pattern) => !patternsOverlap(pattern, name))
  next.push(name)
  setPatterns(item, next)
  if (!item.name.trim()) {
    const parts = name.split(':').filter(Boolean)
    item.name = parts[parts.length - 1] || name
  }
}
function removePattern(item: BudgetItem, name: string) {
  setPatterns(item, patternsOf(item).filter((pattern) => pattern !== name))
}
function addItem(){items.value.push({name:'',account_pattern:'',amount:'0',display_order:items.value.length})}
function isItemConfigured(item: BudgetItem): boolean {
  if (item.id) return true
  if (item.name.trim()) return true
  if (patternsOf(item).length > 0) return true
  const amount = (item.amount ?? '').trim()
  if (amount && !/^0+(\.0+)?$/.test(amount)) return true
  if (item.spent !== undefined || item.usage_rate !== undefined || item.risk) return true
  return false
}
async function removeItem(index: number) {
  const item = items.value[index]
  if (!item) return
  if (isItemConfigured(item)) {
    try {
      await showConfirmDialog({
        title: '删除分类',
        message: `确定删除「${item.name.trim() || '未命名'}」？删除后需保存才会生效。`,
      })
    } catch {
      return
    }
  }
  items.value.splice(index, 1)
}
function startEdit() {
  editing.value = true
}
async function cancelEdit() {
  editing.value = false
  await load()
}
function riskText(risk?:string){return ({NORMAL:'正常',WARNING:'接近额度',EXCEEDED:'已超支'} as Record<string,string>)[risk||'NORMAL']}
function riskType(risk?:string){return risk==='EXCEEDED'?'danger':risk==='WARNING'?'warning':'success'}
function riskColor(risk?:string){return risk==='EXCEEDED'?'var(--bm-expense)':risk==='WARNING'?'var(--bm-warn)':'var(--bm-primary)'}
function percentage(value:string){
  // usage_rate 是比率（如 4.666...），展示为固定 2 位小数的百分比
  const normalized=value.trim()
  if(!/^\d+(?:\.\d+)?$/.test(normalized))return '0.00'
  const [integer='0',fraction='']=normalized.split('.')
  const scale=fraction.length
  const num=BigInt(`${integer}${fraction}`||'0')
  // percent * 100（保留 2 位小数的整数缩放）：round_half_up(num * 10000 / 10^scale)
  const numerator=num*10000n
  const divisor=10n**BigInt(scale)
  const rounded=(numerator + divisor/2n)/divisor
  const whole=(rounded/100n).toString()
  const decimals=(rounded%100n).toString().padStart(2,'0')
  return `${whole}.${decimals}`
}
function progress(value:string){const parsed=Number(percentage(value));return Number.isFinite(parsed)?Math.min(100,Math.max(0,parsed)):0}
async function load(options: { silent?: boolean } = {}){
  if (!options.silent) loading.value = true
  error.value = ''
  try {
    budget.value = await budgetsApi.get(month.value)
    items.value = budget.value.items.map(item => ({ ...item }))
  } catch (reason) {
    error.value = (reason as ApiError).message
    budget.value = null
    items.value = []
  } finally {
    if (!options.silent) loading.value = false
  }
}
async function onMonthChange() {
  editing.value = false
  await load()
}
async function loadAccounts(){accountError.value='';try{accounts.value=await accountsApi.getAccounts()}catch(reason){accountError.value=(reason as ApiError).message}}
async function onRefresh() {
  try { await Promise.all([load({ silent: true }), loadAccounts()]) }
  finally { refreshing.value = false }
}
async function save(){
  saving.value=true
  error.value=''
  try{
    budget.value=await budgetsApi.save(month.value,items.value.map((item,index)=>({...item,display_order:index})))
    items.value=budget.value.items.map(item=>({...item}))
    editing.value=false
    showSuccessToast('预算已保存')
  }catch(reason){
    error.value=(reason as ApiError).message
  }finally{
    saving.value=false
  }
}
async function copyPrevious(){
  error.value=''
  try{
    if(items.value.length){
      await showConfirmDialog({title:'覆盖预算',message:'当前分类会被上月配置替换，是否继续？'})
      budget.value=await budgetsApi.copyPrevious(month.value,true)
    }else{
      budget.value=await budgetsApi.copyPrevious(month.value)
    }
    items.value=budget.value.items.map(item=>({...item}))
  }catch(reason){
    if((reason as string)!=='cancel'&&typeof reason==='object')error.value=(reason as ApiError).message
  }
}
onMounted(async () => {
  load()
  loadAccounts()
})
</script>

<style scoped>
.budget-summary{padding:4px 16px 18px}.budget-total{display:grid;gap:8px;padding:14px 0}.budget-total span{color:var(--bm-muted)}.budget-total strong{font-size:30px}.budget-stats{display:grid;grid-template-columns:1fr 1fr;gap:12px;border-top:1px solid var(--bm-border);padding-top:16px}.budget-stats span{display:grid;gap:6px;color:var(--bm-muted);font-size:13px}.budget-stats strong{color:var(--bm-text);font-size:16px}.budget-item{border-left:3px solid var(--bm-primary)}.budget-item.risk-warning{border-left-color:var(--bm-warn)}.budget-item.risk-exceeded{border-left-color:var(--bm-expense)}.budget-progress{display:grid;grid-template-columns:1fr auto;align-items:center;gap:12px;padding:2px 16px 14px}.budget-progress span{min-width:64px;text-align:right;font-weight:700}.budget-actions{display:grid;gap:12px;margin:16px 0;width:100%;box-sizing:border-box}
.budget-actions-edit{gap:10px}
.budget-actions-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.budget-actions-row :deep(.van-button),.budget-actions :deep(.van-button){height:44px}
.budget-actions-row :deep(.van-button){width:100%}
</style>
