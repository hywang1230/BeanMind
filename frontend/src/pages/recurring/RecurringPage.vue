<template>
  <section class="page recurring-page">
    <van-nav-bar title="周期记账" left-arrow @click-left="router.back()">
      <template #right><van-button size="small" type="primary" @click="openCreate">新建规则</van-button></template>
    </van-nav-bar>

    <div v-if="loading && !rules.length" class="state-card"><van-loading>加载中</van-loading></div>
    <van-empty v-else-if="error && !rules.length" image="error" :description="error">
      <van-button size="small" type="primary" @click="loadRules">重试</van-button>
    </van-empty>
    <van-empty v-else-if="!rules.length" description="暂无周期任务">
      <van-button size="small" type="primary" @click="openCreate">创建规则</van-button>
    </van-empty>
    <van-cell-group v-else inset class="page-section">
      <van-cell v-for="rule in rules" :key="rule.id" :title="rule.name" :label="ruleLabel(rule)">
        <template #value>
          <van-tag :type="rule.is_active ? 'success' : 'default'">{{ rule.is_active ? '启用' : '停用' }}</van-tag>
        </template>
        <template #extra>
          <div class="rule-actions">
            <van-button size="mini" @click="toggleRule(rule)">{{ rule.is_active ? '停用' : '启用' }}</van-button>
            <van-button size="mini" type="primary" @click="executeRule(rule)">立即执行</van-button>
          </div>
        </template>
      </van-cell>
    </van-cell-group>
    <van-notice-bar v-if="error && rules.length" color="#c92a2a" background="#fff1f0">{{ error }}</van-notice-bar>

    <van-popup v-model:show="showCreate" position="bottom" round :style="{ height: '88%' }">
      <div class="popup-page">
        <van-nav-bar title="创建周期规则" left-text="取消" @click-left="showCreate = false" />
        <van-form @submit="createRule">
          <van-cell-group inset>
            <van-field v-model="draft.name" label="规则名称" placeholder="例如：每月房租" :rules="[{ required: true, message: '请输入规则名称' }]" />
            <van-field label="频率">
              <template #input>
                <select v-model="draft.frequency" class="native-select">
                  <option value="daily">每日</option><option value="weekly">每周</option>
                  <option value="biweekly">双周</option><option value="monthly">每月</option><option value="yearly">每年</option>
                </select>
              </template>
            </van-field>
            <van-field v-if="draft.frequency === 'weekly' || draft.frequency === 'biweekly'" v-model="weekdaysText" label="星期" placeholder="1,3,5（周一至周日为 1-7）" />
            <van-field v-if="draft.frequency === 'monthly'" v-model="monthDaysText" label="每月日期" placeholder="1,15,-1（月末）" />
            <van-field v-model="draft.start_date" label="开始日期" type="date" :rules="[{ required: true, message: '请选择开始日期' }]" />
            <van-field v-model="draft.end_date" label="结束日期" type="date" />
            <van-field v-model="draft.transaction_template.description" label="交易描述" :rules="[{ required: true, message: '请输入交易描述' }]" />
          </van-cell-group>

          <van-cell-group inset class="page-section">
            <van-cell title="交易分录" :value="`${draft.transaction_template.postings.length} 条`" />
            <div v-for="(posting, index) in draft.transaction_template.postings" :key="index" class="posting-editor">
              <van-field v-model="posting.account" :label="`账户 ${index + 1}`" placeholder="Assets:Cash" />
              <van-field v-model="posting.amount" label="金额" inputmode="decimal" placeholder="正负金额" />
              <van-field v-model="posting.currency" label="币种" />
              <van-button v-if="draft.transaction_template.postings.length > 2" size="mini" type="danger" @click="removePosting(index)">删除分录</van-button>
            </div>
            <van-button block plain type="primary" @click="addPosting">添加分录</van-button>
          </van-cell-group>
          <van-notice-bar v-if="createError" color="#c92a2a" background="#fff1f0">{{ createError }}</van-notice-bar>
          <div style="margin:16px"><van-button block round type="primary" native-type="submit" :loading="creating">创建</van-button></div>
        </van-form>
      </div>
    </van-popup>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showFailToast, showSuccessToast } from 'vant'
import { useRouter } from 'vue-router'
import { recurringApi, type CreateRecurringRuleRequest, type RecurringRule } from '../../api/recurring'
import type { ApiError } from '../../api/client'

const router = useRouter()
const rules = ref<RecurringRule[]>([])
const loading = ref(false)
const error = ref('')
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const weekdaysText = ref('1')
const monthDaysText = ref('1')

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

function parseIntegerList(value: string, minimum: number, maximum: number, allowLast = false): number[] {
  const values = value.split(',').map(item => Number.parseInt(item.trim(), 10)).filter(Number.isInteger)
  return [...new Set(values.filter(item => (allowLast && item === -1) || (item >= minimum && item <= maximum)))]
}
function frequencyText(rule: RecurringRule): string {
  const names = { daily: '每日', weekly: '每周', biweekly: '双周', monthly: '每月', yearly: '每年' }
  if (rule.frequency === 'weekly' || rule.frequency === 'biweekly') return `${names[rule.frequency]}：${rule.frequency_config.weekdays?.join(',') || '未配置'}`
  if (rule.frequency === 'monthly') return `每月：${rule.frequency_config.month_days?.map(day => day === -1 ? '月末' : `${day}日`).join('、') || '未配置'}`
  return names[rule.frequency]
}
function ruleLabel(rule: RecurringRule): string {
  return `${frequencyText(rule)} · ${rule.transaction_template.description} · ${rule.start_date}${rule.end_date ? ` 至 ${rule.end_date}` : ''}`
}
async function loadRules() {
  loading.value = true; error.value = ''
  try { rules.value = await recurringApi.getRules() }
  catch (reason) { error.value = (reason as ApiError).message }
  finally { loading.value = false }
}
function openCreate() { draft.value = initialDraft(); weekdaysText.value = '1'; monthDaysText.value = '1'; createError.value = ''; showCreate.value = true }
function addPosting() { draft.value.transaction_template.postings.push({ account: '', amount: '0', currency: 'CNY' }) }
function removePosting(index: number) { draft.value.transaction_template.postings.splice(index, 1) }
async function createRule() {
  const postings = draft.value.transaction_template.postings
  if (postings.length < 2 || postings.some(posting => !posting.account || !/^-?\d+(?:\.\d+)?$/.test(posting.amount))) {
    createError.value = '至少需要两条账户和金额有效的分录'; return
  }
  const frequencyConfig = draft.value.frequency === 'monthly'
    ? { month_days: parseIntegerList(monthDaysText.value, 1, 31, true) }
    : draft.value.frequency === 'weekly' || draft.value.frequency === 'biweekly'
      ? { weekdays: parseIntegerList(weekdaysText.value, 1, 7) } : {}
  if ((draft.value.frequency === 'monthly' && !frequencyConfig.month_days?.length)
    || ((draft.value.frequency === 'weekly' || draft.value.frequency === 'biweekly') && !frequencyConfig.weekdays?.length)) {
    createError.value = '频率日期配置无效'; return
  }
  creating.value = true; createError.value = ''
  try {
    await recurringApi.createRule({ ...draft.value, frequency_config: frequencyConfig, end_date: draft.value.end_date || undefined })
    showCreate.value = false; await loadRules(); showSuccessToast('周期规则已创建')
  } catch (reason) { createError.value = (reason as ApiError).message }
  finally { creating.value = false }
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
onMounted(loadRules)
</script>

<style scoped>
.rule-actions{display:flex;gap:8px;margin-left:12px}.popup-page{height:100%;overflow:auto}.posting-editor{padding:8px 0 12px;border-bottom:1px solid var(--app-border);margin-bottom:8px}.posting-editor>.van-button{margin-left:16px}
</style>
