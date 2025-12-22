<template>
  <f7-page name="add-transaction">
    <f7-navbar>
      <f7-nav-left>
        <f7-link @click="goBack">
          <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
        </f7-link>
      </f7-nav-left>
      <f7-nav-title>记一笔</f7-nav-title>
      <f7-nav-right>
        <f7-link @click="handleSubmit" :class="{ disabled: !isFormValid || loading }">{{ loading ? '保存中' : '保存' }}</f7-link>
      </f7-nav-right>
    </f7-navbar>

    <f7-block class="no-padding-vertical margin-vertical">
      <f7-segmented strong tag="div">
        <f7-button :active="formData.type === 'expense'" @click="selectType('expense')">支出</f7-button>
        <f7-button :active="formData.type === 'income'" @click="selectType('income')">收入</f7-button>
        <f7-button :active="formData.type === 'transfer'" @click="selectType('transfer')">转账</f7-button>
      </f7-segmented>
    </f7-block>

    <f7-list strong-ios dividers-ios inset-ios form>
      <!-- 账户/转出账户 -->
      <f7-list-item
        link="#"
        :title="formData.type === 'transfer' ? '转出账户' : '账户'"
        :after="formData.fromAccount || '请选择'"
        @click="openFromAccountPicker"
      >
        <template #media>
          <i class="icon f7-icons">creditcard_fill</i>
        </template>
      </f7-list-item>

      <!-- 金额 -->
      <f7-list-item class="amount-item" title="金额" link="#">
        <template #media>
          <i class="icon f7-icons">money_yen_circle_fill</i>
        </template>
        <template #after>
            <AmountInput
            v-model="formData.amount"
            :allow-negative="formData.type !== 'transfer'"
            />
        </template>
      </f7-list-item>

      <!-- 分类 (非转账) -->
      <f7-list-item
        v-if="formData.type !== 'transfer'"
        link="#"
        title="分类"
        :after="formData.category || '请选择'"
        @click="openCategoryPicker"
      >
        <template #media>
          <i class="icon f7-icons">folder_fill</i>
        </template>
      </f7-list-item>

      <!-- 转入账户 -->
      <f7-list-item
        v-if="formData.type === 'transfer'"
        link="#"
        title="转入账户"
        :after="formData.toAccount || '请选择'"
        @click="openToAccountPicker"
      >
        <template #media>
          <i class="icon f7-icons">arrow_right_circle_fill</i>
        </template>
      </f7-list-item>

      <!-- 日期 -->
      <f7-list-input
        label="日期"
        type="date"
        :value="formData.date"
        @input="formData.date = $event.target.value"
        placeholder="选择日期"
      >
        <template #media>
          <i class="icon f7-icons">calendar_today</i>
        </template>
      </f7-list-input>

      <!-- 备注 -->
      <f7-list-input
        label="备注"
        type="textarea"
        :value="formData.description"
        @input="formData.description = $event.target.value"
        placeholder="添加备注（可选）"
        resizable
      >
        <template #media>
          <i class="icon f7-icons">pencil_circle</i>
        </template>
      </f7-list-input>

      <!-- 标签 -->
      <f7-list-input
        label="标签"
        type="text"
        :value="formData.tagString"
        @input="formData.tagString = $event.target.value"
        placeholder="标签用空格分隔"
        info="例如: 旅行 餐饮"
      >
        <template #media>
          <i class="icon f7-icons">tag_fill</i>
        </template>
      </f7-list-input>
    </f7-list>

    <f7-block v-if="error" class="text-color-red text-align-center">
      {{ error }}
    </f7-block>



    <!-- Pickers -->
    <AccountSelectionPopup
      v-model:opened="showCategoryPicker"
      title="选择分类"
      :root-types="categoryRoots"
      @select="onCategorySelect"
    />

    <AccountSelectionPopup
      v-model:opened="showFromAccountPicker"
      :title="formData.type === 'transfer' ? '选择转出账户' : '选择账户'"
      :root-types="accountRoots"
      @select="onFromAccountSelect"
    />

    <AccountSelectionPopup
      v-model:opened="showToAccountPicker"
      title="选择转入账户"
      :root-types="['Assets', 'Liabilities']"
      @select="onToAccountSelect"
    />

  </f7-page>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTransactionStore } from '../../stores/transaction'
import type { CreateTransactionRequest, Posting } from '../../api/transactions'
import AccountSelectionPopup from '../../components/AccountSelectionPopup.vue'
import AmountInput from '../../components/AmountInput.vue'

const router = useRouter()
const transactionStore = useTransactionStore()

// State
const loading = ref(false)
const error = ref('')
const showCategoryPicker = ref(false)
const showFromAccountPicker = ref(false)
const showToAccountPicker = ref(false)

const formData = ref({
  type: 'expense' as 'expense' | 'income' | 'transfer',
  amount: undefined as number | undefined,
  currency: 'CNY',
  category: '',
  fromAccount: '',
  toAccount: '',
  date: new Date().toISOString().split('T')[0],
  description: '',
  tagString: ''
})

// Computed Props for Picker Roots
const categoryRoots = computed(() => {
  return formData.value.type === 'expense' ? ['Expenses'] : ['Income']
})

const accountRoots = computed(() => {
  // Generally select Assets or Liabilities
  return ['Assets', 'Liabilities', 'Equity']
})

const isFormValid = computed(() => {
  if (formData.value.amount === undefined || formData.value.amount === 0) return false
  if (formData.value.type === 'transfer' && formData.value.amount < 0) return false
  if (!formData.value.date) return false
  if (!formData.value.fromAccount) return false
  
  if (formData.value.type === 'transfer') {
    return !!formData.value.toAccount
  } else {
    return !!formData.value.category
  }
})

// Navigation
function goBack() {
  router.back()
}

// Types
function selectType(type: 'expense' | 'income' | 'transfer') {
  formData.value.type = type
  // Reset conflicting fields if needed
  if (type === 'transfer') {
      formData.value.category = ''
  } else if (type === 'expense' && formData.value.category.startsWith('Income')) {
      formData.value.category = ''
  } else if (type === 'income' && formData.value.category.startsWith('Expenses')) {
      formData.value.category = ''
  }
}

// Picker Handlers
function openCategoryPicker() { showCategoryPicker.value = true }
function openFromAccountPicker() { showFromAccountPicker.value = true }
function openToAccountPicker() { showToAccountPicker.value = true }

function onCategorySelect(val: string) { formData.value.category = val }
function onFromAccountSelect(val: string) { formData.value.fromAccount = val }
function onToAccountSelect(val: string) { formData.value.toAccount = val }

// Submission Logic
function buildPostings(): Posting[] {
  const posts: Posting[] = []
  const amt = formData.value.amount || 0
  const currency = formData.value.currency

  if (formData.value.type === 'expense') {
    // Expense: +Expense, -Asset
    // If amt is negative (e.g. refund), logic holds: -Expense, +Asset.
    posts.push({ account: formData.value.category, amount: amt, currency })
    posts.push({ account: formData.value.fromAccount, amount: -amt, currency })
  } else if (formData.value.type === 'income') {
    // Income: +Asset, -Income
    // If amt is negative (correction), logic holds: -Asset, +Income.
    posts.push({ account: formData.value.fromAccount, amount: amt, currency })
    posts.push({ account: formData.value.category, amount: -amt, currency })
  } else if (formData.value.type === 'transfer') {
    // Transfer: -From, +To
    posts.push({ account: formData.value.fromAccount, amount: -amt, currency })
    posts.push({ account: formData.value.toAccount, amount: amt, currency })
  }
  return posts
}

async function handleSubmit() {
  if (!isFormValid.value) {
      error.value = '请填写所有必填项'
      return 
  }

  loading.value = true
  error.value = ''

  try {
      const tags = formData.value.tagString
        .split(' ')
        .map(t => t.trim())
        .filter(t => t.length > 0)

      const request: CreateTransactionRequest = {
          date: formData.value.date,
          description: formData.value.description || `${formData.value.type === 'expense' ? '支出' : formData.value.type === 'income' ? '收入' : '转账'}`,
          postings: buildPostings(),
          tags: tags.length > 0 ? tags : undefined
      }

      await transactionStore.createTransaction(request)
      router.back()
  } catch (err: any) {
      console.error(err)
      error.value = err.message || '保存失败'
  } finally {
      loading.value = false
  }
}
</script>

<style scoped>
.amount-input {
  font-size: 1.2em;
}
.margin-vertical {
    margin-top: 16px;
    margin-bottom: 16px;
}
</style>
