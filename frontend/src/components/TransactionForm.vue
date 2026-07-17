<template>
  <van-form @submit="submit">
    <van-cell-group inset>
      <van-field label="类型">
        <template #input>
          <select v-model="form.type" class="native-select" @change="resetAccounts">
            <option value="expense">支出</option>
            <option value="income">收入</option>
            <option value="transfer">转账</option>
          </select>
        </template>
      </van-field>
      <van-field v-model="form.date" label="日期" type="date" :rules="[{ required: true, message: '请选择日期' }]" />
      <van-field v-model="form.payee" label="交易方" placeholder="可选" />
      <van-field v-model="form.description" label="备注" placeholder="这笔交易是什么" />
      <MoneyInput v-model="form.amount" :currency="form.currency" :error="amountError" />
      <van-field v-model="form.currency" label="币种" maxlength="16" />
      <AccountPicker
        v-model="form.fromAccount"
        :accounts="accounts"
        :label="form.type === 'income' ? '收款账户' : '付款账户'"
        :prefixes="['Assets', 'Liabilities']"
        :error="submitted && !form.fromAccount ? '请选择账户' : ''"
      />
      <AccountPicker
        v-model="form.toAccount"
        :accounts="accounts"
        :label="form.type === 'expense' ? '支出分类' : form.type === 'income' ? '收入分类' : '转入账户'"
        :prefixes="targetPrefixes"
        :error="submitted && !form.toAccount ? '请选择账户' : ''"
      />
    </van-cell-group>
    <div style="margin: 16px">
      <van-button block round type="primary" native-type="submit" :loading="loading">保存</van-button>
    </div>
  </van-form>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { accountsApi, type Account } from '../api/accounts'
import type { CreateTransactionRequest, Transaction } from '../api/transactions'
import AccountPicker from './AccountPicker.vue'
import MoneyInput from './MoneyInput.vue'

const props = withDefaults(defineProps<{ initial?: Transaction | null; loading?: boolean }>(), { initial: null, loading: false })
const emit = defineEmits<{ (event: 'submit', value: CreateTransactionRequest): void }>()
const accounts = ref<Account[]>([])
const submitted = ref(false)
const today = new Date().toISOString().slice(0, 10)
const form = reactive({ type: 'expense', date: today, payee: '', description: '', amount: '', currency: 'CNY', fromAccount: '', toAccount: '' })

const targetPrefixes = computed(() => form.type === 'expense' ? ['Expenses'] : form.type === 'income' ? ['Income'] : ['Assets', 'Liabilities'])
const amountError = computed(() => submitted.value && (!/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(form.amount) || /^0(?:\.0*)?$/.test(form.amount)) ? '请输入大于零的金额' : '')
const negate = (value: string) => value.startsWith('-') ? value.slice(1) : `-${value}`

function loadInitial(transaction: Transaction | null | undefined) {
  if (!transaction) return
  const category = transaction.postings.find(item => item.account.startsWith('Expenses:') || item.account.startsWith('Income:'))
  const funding = transaction.postings.find(item => item !== category)
  form.type = transaction.transaction_type === 'income' ? 'income' : transaction.transaction_type === 'transfer' ? 'transfer' : 'expense'
  form.date = transaction.date
  form.payee = transaction.payee || ''
  form.description = transaction.description || ''
  form.currency = category?.currency || funding?.currency || 'CNY'
  form.amount = String(category?.amount || funding?.amount || '').replace(/^-/, '')
  if (form.type === 'income') {
    form.fromAccount = funding?.account || ''
    form.toAccount = category?.account || ''
  } else if (form.type === 'expense') {
    form.fromAccount = funding?.account || ''
    form.toAccount = category?.account || ''
  } else {
    const source = transaction.postings.find(item => item.amount.startsWith('-'))
    const target = transaction.postings.find(item => item !== source)
    form.fromAccount = source?.account || ''
    form.toAccount = target?.account || ''
    form.amount = String(source?.amount || '').replace(/^-/, '')
  }
}

watch(() => props.initial, loadInitial, { immediate: true })
onMounted(async () => { accounts.value = await accountsApi.getAccounts() })
function resetAccounts() { form.fromAccount = ''; form.toAccount = '' }
function submit() {
  submitted.value = true
  if (amountError.value || !form.fromAccount || !form.toAccount) return
  const positive = form.amount
  const postings = form.type === 'expense'
    ? [{ account: form.toAccount, amount: positive, currency: form.currency }, { account: form.fromAccount, amount: negate(positive), currency: form.currency }]
    : form.type === 'income'
      ? [{ account: form.fromAccount, amount: positive, currency: form.currency }, { account: form.toAccount, amount: negate(positive), currency: form.currency }]
      : [{ account: form.fromAccount, amount: negate(positive), currency: form.currency }, { account: form.toAccount, amount: positive, currency: form.currency }]
  emit('submit', { date: form.date, payee: form.payee || undefined, description: form.description || undefined, postings })
}
</script>
