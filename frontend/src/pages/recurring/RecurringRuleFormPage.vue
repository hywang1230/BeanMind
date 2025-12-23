<template>
  <f7-page name="recurring-rule-form">
    <f7-navbar>
      <f7-nav-left>
        <f7-link @click="goBack">
          <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
        </f7-link>
      </f7-nav-left>
      <f7-nav-title>{{ isEditMode ? '编辑规则' : '新建规则' }}</f7-nav-title>
      <f7-nav-right>
        <f7-link @click="handleSubmit" :class="{ disabled: loading }">
          {{ loading ? '保存中' : '保存' }}
        </f7-link>
      </f7-nav-right>
    </f7-navbar>

    <!-- 基本信息 -->
    <f7-block-title>基本信息</f7-block-title>
    <f7-list strong-ios dividers-ios inset-ios>
      <f7-list-input
        label="规则名称"
        type="text"
        v-model:value="formData.name"
        placeholder="例如：每月房租"
        required
      >
        <template #media>
          <f7-icon ios="f7:textformat" md="material:title" />
        </template>
      </f7-list-input>

      <f7-list-item
        title="频率类型"
        smart-select
        :smart-select-params="{ openIn: 'sheet', closeOnSelect: true }"
      >
        <template #media>
          <f7-icon ios="f7:clock" md="material:schedule" />
        </template>
        <select v-model="formData.frequency">
          <option value="daily">每日</option>
          <option value="weekly">每周</option>
          <option value="biweekly">双周</option>
          <option value="monthly">每月</option>
          <option value="yearly">每年</option>
        </select>
      </f7-list-item>
    </f7-list>

    <!-- 频率配置 - 每周 -->
    <template v-if="formData.frequency === 'weekly' || formData.frequency === 'biweekly'">
      <f7-block-title>选择星期几</f7-block-title>
      <f7-block>
        <div class="weekday-selector">
          <f7-chip
            v-for="day in weekdays"
            :key="day.value"
            :text="day.label"
            :outline="!formData.frequency_config.weekdays?.includes(day.value)"
            :color="formData.frequency_config.weekdays?.includes(day.value) ? 'primary' : undefined"
            @click="toggleWeekday(day.value)"
          />
        </div>
      </f7-block>
    </template>

    <!-- 频率配置 - 每月 -->
    <template v-if="formData.frequency === 'monthly'">
      <f7-block-title>选择日期</f7-block-title>
      <f7-block>
        <div class="monthday-selector">
          <f7-chip
            v-for="day in 31"
            :key="day"
            :text="String(day)"
            :outline="!formData.frequency_config.month_days?.includes(day)"
            :color="formData.frequency_config.month_days?.includes(day) ? 'primary' : undefined"
            @click="toggleMonthDay(day)"
          />
          <f7-chip
            text="月末"
            :outline="!formData.frequency_config.month_days?.includes(-1)"
            :color="formData.frequency_config.month_days?.includes(-1) ? 'primary' : undefined"
            @click="toggleMonthDay(-1)"
          />
        </div>
      </f7-block>
    </template>

    <!-- 日期范围 -->
    <f7-block-title>有效期</f7-block-title>
    <f7-list strong-ios dividers-ios inset-ios>
      <f7-list-item
        title="开始日期"
        :after="formData.start_date"
        link="#"
        @click="openStartDatePicker"
      >
        <template #media>
          <f7-icon ios="f7:calendar" md="material:event" />
        </template>
      </f7-list-item>
      <f7-list-item
        title="结束日期"
        :after="formData.end_date || '不限'"
        link="#"
        @click="openEndDatePicker"
      >
        <template #media>
          <f7-icon ios="f7:calendar_badge_minus" md="material:event_busy" />
        </template>
      </f7-list-item>
    </f7-list>

    <!-- 交易模板 -->
    <f7-block-title>交易模板</f7-block-title>
    <f7-list strong-ios dividers-ios inset-ios>
      <!-- 交易方（弹窗选择） -->
      <f7-list-item
        title="交易方"
        :after="formData.transaction_template.payee || '请选择'"
        link="#"
        @click="openPayeePicker"
      >
        <template #media>
          <f7-icon ios="f7:person_2_fill" md="material:people" />
        </template>
      </f7-list-item>

      <!-- 备注 -->
      <f7-list-input
        label="备注"
        type="textarea"
        v-model:value="formData.transaction_template.description"
        placeholder="添加备注"
        resizable
      >
        <template #media>
          <f7-icon ios="f7:pencil_circle" md="material:edit" />
        </template>
      </f7-list-input>

      <!-- 标签 -->
      <f7-list-input
        label="标签"
        type="text"
        v-model:value="formData.transaction_template.tagString"
        placeholder="标签用空格分隔"
        info="例如: 旅行 餐饮"
      >
        <template #media>
          <f7-icon ios="f7:tag_fill" md="material:label" />
        </template>
      </f7-list-input>
    </f7-list>

    <!-- 交易明细 -->
    <f7-block-title>交易明细</f7-block-title>
    <f7-list strong-ios dividers-ios inset-ios>
      <f7-list-item
        v-for="(posting, index) in formData.transaction_template.postings"
        :key="index"
        class="posting-item"
      >
        <template #inner>
          <div class="posting-row">
            <div class="posting-main" @click="openAccountPicker(index)">
              <div class="posting-account">
                {{ formatAccountName(posting.account) || '选择类别' }}
              </div>
            </div>
            <div class="posting-amount-group">
              <select v-model="posting.currency" class="posting-currency-select">
                <option value="CNY">CNY</option>
                <option value="USD">USD</option>
                <option value="HKD">HKD</option>
              </select>
              <div class="posting-amount-input" @click="openAmountInput(index)">
                {{ formatAmount(posting.amount) }}
              </div>
              <f7-link
                v-if="formData.transaction_template.postings.length > 2"
                @click.stop="removePosting(index)"
                class="remove-posting-btn"
              >
                <f7-icon ios="f7:minus_circle_fill" md="material:remove_circle" color="red" />
              </f7-link>
            </div>
          </div>
        </template>
      </f7-list-item>
    </f7-list>

    <f7-block>
      <f7-button outline @click="addPosting">
        <f7-icon ios="f7:plus" md="material:add" />
        添加明细
      </f7-button>
    </f7-block>

    <!-- 启用状态 -->
    <f7-list strong-ios dividers-ios inset-ios>
      <f7-list-item title="启用规则">
        <template #after>
          <f7-toggle :checked="formData.is_active" @toggle:change="formData.is_active = $event" />
        </template>
      </f7-list-item>
    </f7-list>

    <f7-block v-if="error" class="text-color-red text-align-center">
      {{ error }}
    </f7-block>

    <!-- 账户选择弹窗（支持所有账户，单选） -->
    <AccountSelectionPopup
      v-model:opened="showAccountPicker"
      title="选择类别"
      :root-types="allAccountTypes"
      :allow-multi-select="false"
      @select="onAccountSelect"
    />

    <!-- 交易方选择弹窗 -->
    <PayeeSelectionPopup
      v-model:opened="showPayeePicker"
      @select="onPayeeSelect"
    />

    <!-- 金额输入键盘 -->
    <f7-sheet
      class="amount-keypad-sheet"
      :opened="showAmountKeypad"
      @sheet:closed="onAmountKeypadClosed"
      style="height: auto;"
      backdrop
      close-by-backdrop-click
      swipe-to-close
    >
      <div class="keypad-header">
        <span class="keypad-currency">{{ currentEditingPosting?.currency || 'CNY' }}</span>
        <span class="keypad-value">{{ amountExpression || '0' }}</span>
      </div>
      <div class="keypad-grid">
        <button class="key-btn number-key" @click="appendAmount('1')">1</button>
        <button class="key-btn number-key" @click="appendAmount('2')">2</button>
        <button class="key-btn number-key" @click="appendAmount('3')">3</button>
        <button class="key-btn action-key" @click="handleAmountDelete">
          <i class="f7-icons">delete_left</i>
        </button>

        <button class="key-btn number-key" @click="appendAmount('4')">4</button>
        <button class="key-btn number-key" @click="appendAmount('5')">5</button>
        <button class="key-btn number-key" @click="appendAmount('6')">6</button>
        <button class="key-btn op-key" @click="appendAmount('+')">+</button>

        <button class="key-btn number-key" @click="appendAmount('7')">7</button>
        <button class="key-btn number-key" @click="appendAmount('8')">8</button>
        <button class="key-btn number-key" @click="appendAmount('9')">9</button>
        <button class="key-btn op-key" @click="appendAmount('-')">-</button>

        <button class="key-btn number-key" @click="appendAmount('.')">.</button>
        <button class="key-btn number-key" @click="appendAmount('0')">0</button>
        <button class="key-btn action-key highlight" style="grid-column: span 2" @click="confirmAmount">
          确定
        </button>
      </div>
    </f7-sheet>
  </f7-page>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { f7 } from 'framework7-vue'
import { recurringApi, type CreateRecurringRuleRequest } from '../../api/recurring'
import AccountSelectionPopup from '../../components/AccountSelectionPopup.vue'
import PayeeSelectionPopup from '../../components/PayeeSelectionPopup.vue'

const router = useRouter()
const route = useRoute()

const allAccountTypes = ['Assets', 'Liabilities', 'Income', 'Expenses', 'Equity']

const ruleId = computed(() => route.params.id as string | undefined)
const isEditMode = computed(() => !!ruleId.value)

const loading = ref(false)
const error = ref('')
const showAccountPicker = ref(false)
const showPayeePicker = ref(false)
const showAmountKeypad = ref(false)
const currentPostingIndex = ref(-1)
const amountExpression = ref('')

interface PostingData {
  account: string
  amount: number
  currency: string
}

interface FormData {
  name: string
  frequency: 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'yearly'
  frequency_config: {
    weekdays: number[]
    month_days: number[]
  }
  transaction_template: {
    description: string
    payee: string
    tagString: string
    postings: PostingData[]
  }
  start_date: string
  end_date: string
  is_active: boolean
}

const formData = ref<FormData>({
  name: '',
  frequency: 'monthly',
  frequency_config: {
    weekdays: [],
    month_days: []
  },
  transaction_template: {
    description: '',
    payee: '',
    tagString: '',
    postings: [
      { account: '', amount: 0, currency: 'CNY' },
      { account: '', amount: 0, currency: 'CNY' }
    ]
  },
  start_date: new Date().toISOString().split('T')[0] as string,
  end_date: '',
  is_active: true
})

const weekdays = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' }
]

const currentEditingPosting = computed(() => {
  if (currentPostingIndex.value >= 0 && currentPostingIndex.value < formData.value.transaction_template.postings.length) {
    return formData.value.transaction_template.postings[currentPostingIndex.value]
  }
  return null
})

function formatAccountName(account: string): string {
  if (!account) return ''
  const parts = account.split(':')
  return parts.length > 1 ? parts.slice(1).join(':') : account
}

function formatAmount(amount: number): string {
  return amount.toFixed(2)
}

function toggleWeekday(day: number) {
  if (!formData.value.frequency_config.weekdays) {
    formData.value.frequency_config.weekdays = []
  }
  const index = formData.value.frequency_config.weekdays.indexOf(day)
  if (index > -1) {
    formData.value.frequency_config.weekdays.splice(index, 1)
  } else {
    formData.value.frequency_config.weekdays.push(day)
    formData.value.frequency_config.weekdays.sort((a, b) => a - b)
  }
}

function toggleMonthDay(day: number) {
  if (!formData.value.frequency_config.month_days) {
    formData.value.frequency_config.month_days = []
  }
  const index = formData.value.frequency_config.month_days.indexOf(day)
  if (index > -1) {
    formData.value.frequency_config.month_days.splice(index, 1)
  } else {
    formData.value.frequency_config.month_days.push(day)
    formData.value.frequency_config.month_days.sort((a, b) => {
      if (a === -1) return 1
      if (b === -1) return -1
      return a - b
    })
  }
}

// 日期选择器
let startDateCalendar: any = null
let endDateCalendar: any = null

function openStartDatePicker() {
  const currentDate = formData.value.start_date 
    ? new Date(formData.value.start_date) 
    : new Date()
  
  if (!startDateCalendar) {
    startDateCalendar = f7.calendar.create({
      closeOnSelect: true,
      value: [currentDate],
      on: {
        change: function (_: any, values: unknown) {
          const dateValues = values as Date[]
          if (dateValues && dateValues[0]) {
            const d = dateValues[0]
            formData.value.start_date = formatDateString(d)
          }
        }
      }
    })
  } else {
    startDateCalendar.setValue([currentDate])
  }
  startDateCalendar.open()
}

function openEndDatePicker() {
  const currentDate = formData.value.end_date 
    ? new Date(formData.value.end_date) 
    : new Date()
  
  if (!endDateCalendar) {
    endDateCalendar = f7.calendar.create({
      closeOnSelect: true,
      value: formData.value.end_date ? [currentDate] : [],
      on: {
        change: function (_: any, values: unknown) {
          const dateValues = values as Date[]
          if (dateValues && dateValues[0]) {
            const d = dateValues[0]
            formData.value.end_date = formatDateString(d)
          }
        }
      }
    })
  } else {
    endDateCalendar.setValue(formData.value.end_date ? [currentDate] : [])
  }
  endDateCalendar.open()
}

function formatDateString(d: Date): string {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

onBeforeUnmount(() => {
  if (startDateCalendar) {
    startDateCalendar.destroy()
  }
  if (endDateCalendar) {
    endDateCalendar.destroy()
  }
})

// 账户选择
function openAccountPicker(index: number) {
  currentPostingIndex.value = index
  showAccountPicker.value = true
}

function onAccountSelect(names: string[]) {
  const posting = formData.value.transaction_template.postings[currentPostingIndex.value]
  if (currentPostingIndex.value >= 0 && names.length > 0 && posting) {
    posting.account = names[0] as string
  }
}

// 交易方选择
function openPayeePicker() {
  showPayeePicker.value = true
}

function onPayeeSelect(payee: string) {
  formData.value.transaction_template.payee = payee
}

// 金额输入
function openAmountInput(index: number) {
  currentPostingIndex.value = index
  const posting = formData.value.transaction_template.postings[index]
  if (posting) {
    amountExpression.value = posting.amount ? posting.amount.toString() : ''
    showAmountKeypad.value = true
  }
}

function appendAmount(char: string) {
  // Prevent multiple dots
  if (char === '.') {
    const parts = amountExpression.value.split(/[+\-]/)
    const currentNum = parts[parts.length - 1]
    if (currentNum && currentNum.includes('.')) return
  }
  
  // Prevent multiple operators
  if (['+', '-'].includes(char)) {
    const lastChar = amountExpression.value.slice(-1)
    if (['+', '-'].includes(lastChar)) {
      amountExpression.value = amountExpression.value.slice(0, -1) + char
      return
    }
    if (amountExpression.value === '' && char === '+') return
  }

  amountExpression.value += char
}

function handleAmountDelete() {
  if (amountExpression.value.length > 0) {
    amountExpression.value = amountExpression.value.slice(0, -1)
  }
}

function confirmAmount() {
  try {
    if (!amountExpression.value) {
      updatePostingAmount(0)
      return
    }
    
    let sanitized = amountExpression.value.replace(/[^0-9+\-.]/g, '')
    if (['+', '-'].includes(sanitized.slice(-1))) {
      sanitized = sanitized.slice(0, -1)
    }
    
    let result = Function('"use strict";return (' + sanitized + ')')()
    result = Math.round(result * 100) / 100
    
    updatePostingAmount(result)
  } catch (e) {
    updatePostingAmount(0)
  }
  
  showAmountKeypad.value = false
}

function updatePostingAmount(amount: number) {
  const posting = formData.value.transaction_template.postings[currentPostingIndex.value]
  if (posting) {
    posting.amount = amount
  }
}

function onAmountKeypadClosed() {
  showAmountKeypad.value = false
}

// 交易明细操作
function addPosting() {
  formData.value.transaction_template.postings.push({
    account: '',
    amount: 0,
    currency: 'CNY'
  })
}

function removePosting(index: number) {
  formData.value.transaction_template.postings.splice(index, 1)
}

// 加载编辑数据
async function loadRule() {
  if (!ruleId.value) return
  
  loading.value = true
  try {
    const rule = await recurringApi.getRule(ruleId.value)
    
    formData.value = {
      name: rule.name,
      frequency: rule.frequency as any,
      frequency_config: {
        weekdays: rule.frequency_config?.weekdays || [],
        month_days: rule.frequency_config?.month_days || []
      },
      transaction_template: {
        description: rule.transaction_template?.description || '',
        payee: rule.transaction_template?.payee || '',
        tagString: rule.transaction_template?.tags?.join(' ') || '',
        postings: rule.transaction_template?.postings || [
          { account: '', amount: 0, currency: 'CNY' },
          { account: '', amount: 0, currency: 'CNY' }
        ]
      },
      start_date: rule.start_date,
      end_date: rule.end_date || '',
      is_active: rule.is_active
    }
  } catch (err: any) {
    error.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

// 表单验证
function validateForm(): boolean {
  if (!formData.value.name.trim()) {
    f7.toast.show({ text: '请输入规则名称', position: 'center', closeTimeout: 2000 })
    return false
  }
  
  if (formData.value.frequency === 'weekly' || formData.value.frequency === 'biweekly') {
    if (!formData.value.frequency_config.weekdays?.length) {
      f7.toast.show({ text: '请选择执行的星期', position: 'center', closeTimeout: 2000 })
      return false
    }
  }
  
  if (formData.value.frequency === 'monthly') {
    if (!formData.value.frequency_config.month_days?.length) {
      f7.toast.show({ text: '请选择执行的日期', position: 'center', closeTimeout: 2000 })
      return false
    }
  }
  
  const validPostings = formData.value.transaction_template.postings.filter(p => p.account)
  if (validPostings.length < 2) {
    f7.toast.show({ text: '至少需要配置两个有效的交易明细', position: 'center', closeTimeout: 2000 })
    return false
  }

  // 检查借贷平衡
  const sums: Record<string, number> = {}
  for (const p of validPostings) {
    const currency = p.currency || 'CNY'
    if (!sums[currency]) sums[currency] = 0
    sums[currency] += (Number(p.amount) || 0)
  }
  
  for (const currency in sums) {
    // 使用少量误差容忍浮点数运算
    if (Math.abs(sums[currency] || 0) > 0.001) {
      f7.toast.show({ 
        text: `借贷不平衡：${currency} 金额之和必须为 0 (当前: ${(sums[currency] || 0).toFixed(2)})`, 
        position: 'center', 
        closeTimeout: 3000 
      })
      return false
    }
  }
  
  return true
}

// 提交表单
async function handleSubmit() {
  if (!validateForm()) return
  
  loading.value = true
  error.value = ''
  
  try {
    const tags = formData.value.transaction_template.tagString
      .split(' ')
      .map(t => t.trim())
      .filter(t => t.length > 0)

    const request: CreateRecurringRuleRequest = {
      name: formData.value.name,
      frequency: formData.value.frequency,
      frequency_config: {
        weekdays: formData.value.frequency_config.weekdays,
        month_days: formData.value.frequency_config.month_days
      },
      transaction_template: {
        description: formData.value.transaction_template.description,
        payee: formData.value.transaction_template.payee || undefined,
        postings: formData.value.transaction_template.postings.filter(p => p.account),
        tags: tags.length > 0 ? tags : undefined
      },
      start_date: formData.value.start_date,
      end_date: formData.value.end_date || undefined,
      is_active: formData.value.is_active
    }
    
    if (isEditMode.value && ruleId.value) {
      await recurringApi.updateRule(ruleId.value, request)
      f7.toast.show({ text: '更新成功', position: 'center', closeTimeout: 1500 })
    } else {
      await recurringApi.createRule(request)
      f7.toast.show({ text: '创建成功', position: 'center', closeTimeout: 1500 })
    }
    
    router.back()
  } catch (err: any) {
    error.value = err.message || '保存失败'
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.back()
}

onMounted(() => {
  if (isEditMode.value) {
    loadRule()
  }
})
</script>

<style scoped>
.weekday-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.monthday-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.monthday-selector :deep(.chip) {
  min-width: 40px;
  justify-content: center;
}

.posting-item :deep(.item-inner) {
  padding-top: 8px;
  padding-bottom: 8px;
}

.posting-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.posting-main {
  background: var(--f7-list-item-bg-color, var(--f7-list-bg-color));
  border: 1px solid var(--f7-list-item-border-color);
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
}

.posting-account {
  color: var(--f7-list-item-title-text-color);
  font-size: 15px;
}

.posting-account:empty::before {
  content: '选择类别';
  color: var(--f7-input-placeholder-color);
}

.posting-amount-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.posting-currency-select {
  flex-shrink: 0;
  width: 80px;
  border: 1px solid var(--f7-list-item-border-color);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 15px;
  background: var(--f7-list-item-bg-color, var(--f7-list-bg-color));
  color: var(--f7-list-item-title-text-color);
}

.posting-amount-input {
  flex: 1;
  min-width: 100px;
  border: 1px solid var(--f7-list-item-border-color);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 15px;
  background: var(--f7-list-item-bg-color, var(--f7-list-bg-color));
  color: var(--f7-list-item-title-text-color);
  text-align: right;
  cursor: pointer;
}

.remove-posting-btn {
  padding: 4px;
}

/* 金额键盘样式 */
.keypad-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
}

.keypad-currency {
  font-size: 16px;
  color: #666;
}

.keypad-value {
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.keypad-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 8px;
  background: #f0f0f5;
  padding-bottom: calc(8px + var(--f7-safe-area-bottom));
}

.key-btn {
  appearance: none;
  border: none;
  background: white;
  border-radius: 5px;
  font-size: 20px;
  font-weight: 500;
  color: #000;
  padding: 15px 0;
  box-shadow: 0 1px 1px rgba(0,0,0,0.2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.key-btn:active {
  background: #e5e5e5;
}

.action-key {
  background: #e4e4e9;
}

.highlight {
  background: var(--f7-theme-color);
  color: white;
}

.highlight:active {
  opacity: 0.8;
}

.op-key {
  background: #f4d03f;
  color: black;
}
</style>
