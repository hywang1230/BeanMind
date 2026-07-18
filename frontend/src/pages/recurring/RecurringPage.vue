<template>
  <section class="page recurring-page">
    <van-nav-bar title="周期记账" left-arrow @click-left="router.back()">
      <template #right><van-button size="small" type="primary" @click="openCreate">新建规则</van-button></template>
    </van-nav-bar>
    <h2 class="section-title">自动记账规则</h2>

    <div v-if="loading && !rules.length" class="state-card"><van-loading>加载中</van-loading></div>
    <van-empty v-else-if="error && !rules.length" image="error" :description="error">
      <van-button size="small" type="primary" @click="loadRules">重试</van-button>
    </van-empty>
    <van-empty v-else-if="!rules.length" description="暂无周期任务">
      <van-button size="small" type="primary" @click="openCreate">创建规则</van-button>
    </van-empty>
    <van-cell-group v-else inset class="page-section rule-list">
      <div v-for="rule in rules" :key="rule.id" class="rule-card">
        <div class="rule-card-main">
          <div class="rule-card-title-row">
            <strong class="rule-card-name">{{ rule.name }}</strong>
            <van-tag :type="rule.is_active ? 'success' : 'default'">{{ rule.is_active ? '启用' : '停用' }}</van-tag>
          </div>
          <p class="rule-card-meta">{{ frequencyText(rule) }}</p>
          <p class="rule-card-meta">{{ rule.transaction_template.description }} · {{ rule.start_date }}{{ rule.end_date ? ` 至 ${rule.end_date}` : '' }}</p>
        </div>
        <div class="rule-actions">
          <van-button size="mini" @click="openEdit(rule)">编辑</van-button>
          <van-button size="mini" @click="toggleRule(rule)">{{ rule.is_active ? '停用' : '启用' }}</van-button>
          <van-button size="mini" type="primary" @click="executeRule(rule)">立即执行</van-button>
        </div>
      </div>
    </van-cell-group>
    <van-notice-bar v-if="error && rules.length" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ error }}</van-notice-bar>

    <van-popup v-model:show="showEditor" position="bottom" round :style="{ height: '88%' }">
      <div class="popup-page">
        <van-nav-bar :title="editingId ? '编辑周期规则' : '创建周期规则'" left-text="取消" @click-left="showEditor = false" />
        <van-form @submit="saveRule">
          <van-cell-group inset>
            <van-field v-model="draft.name" label="规则名称" placeholder="例如：每月房租" :rules="[{ required: true, message: '请输入规则名称' }]" />
            <SelectPickerField v-model="draft.frequency" label="频率" :options="frequencyOptions" />
            <van-field
              v-if="draft.frequency === 'weekly' || draft.frequency === 'biweekly'"
              :model-value="weekdaysDisplay"
              label="星期"
              placeholder="请选择"
              readonly
              is-link
              :rules="[{ validator: () => selectedWeekdays.length > 0 || '请选择星期' }]"
              @click="openWeekdayPicker"
            />
            <van-field
              v-if="draft.frequency === 'monthly'"
              :model-value="monthDaysDisplay"
              label="每月日期"
              placeholder="请选择"
              readonly
              is-link
              :rules="[{ validator: () => selectedMonthDays.length > 0 || '请选择每月日期' }]"
              @click="openMonthDayPicker"
            />
            <DatePickerField v-model="draft.start_date" label="开始日期" :rules="[{ required: true, message: '请选择开始日期' }]" />
            <DatePickerField v-model="draft.end_date" label="结束日期" />
            <van-field v-model="draft.transaction_template.description" label="交易描述" :rules="[{ required: true, message: '请输入交易描述' }]" />
          </van-cell-group>

          <van-cell-group inset class="page-section">
            <van-cell title="交易分录" :value="`${draft.transaction_template.postings.length} 条`" />
            <div v-for="(posting, index) in draft.transaction_template.postings" :key="index" class="posting-editor">
              <AccountPicker v-model="posting.account" :accounts="accounts" :label="`账户 ${index + 1}`" clearable :error="accountError" />
              <van-field v-model="posting.amount" label="金额" inputmode="decimal" placeholder="正负金额" />
              <SelectPickerField
                v-model="posting.currency"
                label="币种"
                :options="currencyOptionsFor(posting.currency)"
                placeholder="请选择币种"
              />
              <van-button v-if="draft.transaction_template.postings.length > 2" size="mini" type="danger" @click="removePosting(index)">删除分录</van-button>
            </div>
            <van-button block plain type="primary" @click="addPosting">添加分录</van-button>
          </van-cell-group>
          <van-notice-bar v-if="editorError" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ editorError }}</van-notice-bar>
          <div style="margin:16px"><van-button block round type="primary" native-type="submit" :loading="saving">{{ editingId ? '保存' : '创建' }}</van-button></div>
        </van-form>
      </div>
    </van-popup>

    <van-popup v-model:show="showWeekdayPicker" position="bottom" round>
      <div class="multi-picker">
        <van-nav-bar title="选择星期" left-text="取消" right-text="确定" @click-left="showWeekdayPicker = false" @click-right="confirmWeekdays" />
        <van-checkbox-group v-model="weekdayDraft" class="multi-picker-list">
          <van-cell
            v-for="option in weekdayOptions"
            :key="option.value"
            clickable
            :title="option.text"
            @click="toggleWeekdayDraft(option.value)"
          >
            <template #right-icon>
              <van-checkbox :name="option.value" @click.stop />
            </template>
          </van-cell>
        </van-checkbox-group>
      </div>
    </van-popup>

    <van-popup v-model:show="showMonthDayPicker" position="bottom" round :style="{ height: '70%' }">
      <div class="multi-picker multi-picker-scroll">
        <van-nav-bar title="选择每月日期" left-text="取消" right-text="确定" @click-left="showMonthDayPicker = false" @click-right="confirmMonthDays" />
        <van-checkbox-group v-model="monthDayDraft" class="multi-picker-list multi-picker-grid">
          <van-cell
            v-for="option in monthDayOptions"
            :key="option.value"
            clickable
            :title="option.text"
            @click="toggleMonthDayDraft(option.value)"
          >
            <template #right-icon>
              <van-checkbox :name="option.value" @click.stop />
            </template>
          </van-cell>
        </van-checkbox-group>
      </div>
    </van-popup>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { showFailToast, showSuccessToast } from 'vant'
import { useRouter } from 'vue-router'
import { accountsApi, type Account } from '../../api/accounts'
import type { ApiError } from '../../api/client'
import { recurringApi, type CreateRecurringRuleRequest, type RecurringRule } from '../../api/recurring'
import AccountPicker from '../../components/AccountPicker.vue'
import DatePickerField from '../../components/DatePickerField.vue'
import SelectPickerField from '../../components/SelectPickerField.vue'

const router = useRouter()
const rules = ref<RecurringRule[]>([])
const accounts = ref<Account[]>([])
const loading = ref(false)
const error = ref('')
const accountError = ref('')
const showEditor = ref(false)
const saving = ref(false)
const editorError = ref('')
const editingId = ref<string | number | null>(null)
const selectedWeekdays = ref<number[]>([1])
const selectedMonthDays = ref<number[]>([1])
const weekdayDraft = ref<number[]>([1])
const monthDayDraft = ref<number[]>([1])
const showWeekdayPicker = ref(false)
const showMonthDayPicker = ref(false)

const frequencyOptions = [
  { text: '每日', value: 'daily' }, { text: '每周', value: 'weekly' },
  { text: '双周', value: 'biweekly' }, { text: '每月', value: 'monthly' },
  { text: '每年', value: 'yearly' },
]


// 与记账表单一致：产品仅支持人民币、美元；编辑存量数据时保留当前币种可选。
const SUPPORTED_CURRENCIES = ['CNY', 'USD']

function currencyOptionsFor(current: string) {
  const values = current && !SUPPORTED_CURRENCIES.includes(current)
    ? [...SUPPORTED_CURRENCIES, current]
    : [...SUPPORTED_CURRENCIES]
  return values.map((currency) => ({ text: currency, value: currency }))
}
const weekdayOptions = [
  { text: '周一', value: 1 }, { text: '周二', value: 2 }, { text: '周三', value: 3 },
  { text: '周四', value: 4 }, { text: '周五', value: 5 }, { text: '周六', value: 6 }, { text: '周日', value: 7 },
]
const monthDayOptions = [
  ...Array.from({ length: 31 }, (_, index) => ({ text: `${index + 1}日`, value: index + 1 })),
  { text: '月末', value: -1 },
]

function initialDraft(): CreateRecurringRuleRequest {
  return {
    name: '', frequency: 'monthly', frequency_config: { month_days: [1] },
    transaction_template: {
      description: '',
      postings: [{ account: '', amount: '0', currency: 'CNY' }, { account: '', amount: '0', currency: 'CNY' }],
    },
    start_date: new Date().toISOString().slice(0, 10), end_date: '', is_active: true,
  }
}
const draft = ref(initialDraft())

const weekdaysDisplay = computed(() => formatWeekdays(selectedWeekdays.value))
const monthDaysDisplay = computed(() => formatMonthDays(selectedMonthDays.value))

function sortUnique(values: number[]): number[] {
  return [...new Set(values)].sort((a, b) => {
    if (a === -1) return 1
    if (b === -1) return -1
    return a - b
  })
}

function formatWeekdays(values: number[]): string {
  if (!values.length) return ''
  const labels = new Map(weekdayOptions.map(option => [option.value, option.text]))
  return sortUnique(values).map(value => labels.get(value) || String(value)).join('、')
}

function formatMonthDays(values: number[]): string {
  if (!values.length) return ''
  return sortUnique(values).map(value => value === -1 ? '月末' : `${value}日`).join('、')
}

function toggleDraft(target: typeof weekdayDraft, value: number) {
  const next = new Set(target.value)
  if (next.has(value)) next.delete(value)
  else next.add(value)
  target.value = sortUnique([...next])
}
function toggleWeekdayDraft(value: number) { toggleDraft(weekdayDraft, value) }
function toggleMonthDayDraft(value: number) { toggleDraft(monthDayDraft, value) }

function openWeekdayPicker() {
  weekdayDraft.value = sortUnique([...selectedWeekdays.value])
  showWeekdayPicker.value = true
}

function openMonthDayPicker() {
  monthDayDraft.value = sortUnique([...selectedMonthDays.value])
  showMonthDayPicker.value = true
}

function confirmWeekdays() {
  if (!weekdayDraft.value.length) {
    showFailToast('请至少选择一个星期')
    return
  }
  selectedWeekdays.value = sortUnique([...weekdayDraft.value])
  showWeekdayPicker.value = false
}

function confirmMonthDays() {
  if (!monthDayDraft.value.length) {
    showFailToast('请至少选择一个日期')
    return
  }
  selectedMonthDays.value = sortUnique([...monthDayDraft.value])
  showMonthDayPicker.value = false
}

function frequencyText(rule: RecurringRule): string {
  const names = { daily: '每日', weekly: '每周', biweekly: '双周', monthly: '每月', yearly: '每年' }
  if (rule.frequency === 'weekly' || rule.frequency === 'biweekly') {
    return `${names[rule.frequency]}：${formatWeekdays(rule.frequency_config.weekdays || []) || '未配置'}`
  }
  if (rule.frequency === 'monthly') {
    return `每月：${formatMonthDays(rule.frequency_config.month_days || []) || '未配置'}`
  }
  return names[rule.frequency]
}
async function loadRules() {
  loading.value = true; error.value = ''
  try { rules.value = await recurringApi.getRules() }
  catch (reason) { error.value = (reason as ApiError).message }
  finally { loading.value = false }
}
async function loadAccounts() {
  accountError.value = ''
  try { accounts.value = await accountsApi.getAccounts() }
  catch (reason) { accountError.value = (reason as ApiError).message }
}
function resetFrequencySelection(weekdays: number[] = [1], monthDays: number[] = [1]) {
  selectedWeekdays.value = sortUnique(weekdays.length ? weekdays : [1])
  selectedMonthDays.value = sortUnique(monthDays.length ? monthDays : [1])
}
function openCreate() {
  editingId.value = null
  draft.value = initialDraft()
  resetFrequencySelection([1], [1])
  editorError.value = ''
  showEditor.value = true
}
function openEdit(rule: RecurringRule) {
  editingId.value = rule.id
  const postings = (rule.transaction_template.postings || []).map(posting => ({
    account: posting.account || '',
    amount: String(posting.amount ?? '0'),
    currency: posting.currency || 'CNY',
  }))
  while (postings.length < 2) {
    postings.push({ account: '', amount: '0', currency: 'CNY' })
  }
  draft.value = {
    name: rule.name,
    frequency: rule.frequency,
    frequency_config: {
      weekdays: rule.frequency_config.weekdays ? [...rule.frequency_config.weekdays] : undefined,
      month_days: rule.frequency_config.month_days ? [...rule.frequency_config.month_days] : undefined,
      interval_days: rule.frequency_config.interval_days,
    },
    transaction_template: {
      description: rule.transaction_template.description || '',
      payee: rule.transaction_template.payee,
      tags: rule.transaction_template.tags ? [...rule.transaction_template.tags] : undefined,
      postings,
    },
    start_date: rule.start_date,
    end_date: rule.end_date || '',
    is_active: rule.is_active,
  }
  resetFrequencySelection(rule.frequency_config.weekdays || [1], rule.frequency_config.month_days || [1])
  editorError.value = ''
  showEditor.value = true
}
function addPosting() { draft.value.transaction_template.postings.push({ account: '', amount: '0', currency: 'CNY' }) }
function removePosting(index: number) { draft.value.transaction_template.postings.splice(index, 1) }
async function saveRule() {
  const postings = draft.value.transaction_template.postings
  if (postings.length < 2 || postings.some(posting => !posting.account || !/^-?\d+(?:\.\d+)?$/.test(posting.amount))) {
    editorError.value = '至少需要两条账户和金额有效的分录'; return
  }
  const frequencyConfig = draft.value.frequency === 'monthly'
    ? { month_days: sortUnique(selectedMonthDays.value) }
    : draft.value.frequency === 'weekly' || draft.value.frequency === 'biweekly'
      ? { weekdays: sortUnique(selectedWeekdays.value) } : {}
  if ((draft.value.frequency === 'monthly' && !frequencyConfig.month_days?.length)
    || ((draft.value.frequency === 'weekly' || draft.value.frequency === 'biweekly') && !frequencyConfig.weekdays?.length)) {
    editorError.value = '请选择频率对应的日期'
    return
  }
  const payload = {
    ...draft.value,
    frequency_config: frequencyConfig,
    end_date: draft.value.end_date || undefined,
  }
  saving.value = true; editorError.value = ''
  try {
    if (editingId.value != null) {
      await recurringApi.updateRule(editingId.value, payload)
      showSuccessToast('周期规则已更新')
    } else {
      await recurringApi.createRule(payload)
      showSuccessToast('周期规则已创建')
    }
    showEditor.value = false
    editingId.value = null
    await loadRules()
  } catch (reason) { editorError.value = (reason as ApiError).message }
  finally { saving.value = false }
}
async function toggleRule(rule: RecurringRule) {
  error.value = ''
  try { const updated = await recurringApi.updateRule(rule.id, { is_active: !rule.is_active }); rule.is_active = updated.is_active }
  catch (reason) { error.value = (reason as ApiError).message }
}
async function executeRule(rule: RecurringRule) {
  try { await recurringApi.executeRule(rule.id, new Date().toISOString().slice(0, 10)); showSuccessToast('执行成功') }
  catch (reason) { showFailToast((reason as ApiError).message) }
}
onMounted(() => { loadRules(); loadAccounts() })
</script>

<style scoped>
.rule-list{padding:4px 0}
.rule-card{
  display:flex;
  flex-direction:column;
  gap:12px;
  padding:14px 16px;
  border-bottom:1px solid var(--app-border, var(--van-border-color));
}
.rule-card:last-child{border-bottom:none}
.rule-card-main{min-width:0}
.rule-card-title-row{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  margin-bottom:6px;
}
.rule-card-name{
  min-width:0;
  flex:1;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  font-size:16px;
  font-weight:600;
  color:var(--van-text-color);
}
.rule-card-meta{
  margin:0;
  color:var(--bm-muted, var(--van-text-color-2));
  font-size:13px;
  line-height:1.45;
  word-break:break-word;
  overflow-wrap:anywhere;
}
.rule-actions{
  display:flex;
  flex-wrap:wrap;
  gap:8px;
}
.popup-page{height:100%;overflow:auto}
.posting-editor{padding:8px 0 12px;border-bottom:1px solid var(--app-border);margin-bottom:8px}
.posting-editor>.van-button{margin-left:16px}
.multi-picker{display:flex;flex-direction:column;max-height:70vh}
.multi-picker-scroll{height:100%}
.multi-picker-list{overflow:auto;padding-bottom:12px}
.multi-picker-grid{max-height:calc(70vh - 46px)}
</style>
