<template>
  <van-form class="transaction-form" @submit.prevent>
    <van-cell-group inset class="transaction-form-card">
      <van-field name="type" label="类型">
        <template #input>
          <van-radio-group v-model="form.type" direction="horizontal" @change="onTypeChange">
            <van-radio name="expense">支出</van-radio>
            <van-radio name="income">收入</van-radio>
            <van-radio name="transfer">转账</van-radio>
          </van-radio-group>
        </template>
      </van-field>

      <DatePickerField v-model="form.date" label="日期" />

      <AccountPicker
        :model-value="''"
        :label="fromLabel"
        :accounts="pickerAccounts"
        :prefixes="fromPrefixes"
        :as-of-date="form.date"
        :active-only="true"
        :include-accounts="form.fromAccounts"
        :selected-accounts="form.fromAccounts"
        :transaction-type="form.type"
        @update:model-value="addAccount('from', $event)"
        @remove="removeAccount('from', $event)"
      />

      <AccountPicker
        :model-value="''"
        :label="toLabel"
        :accounts="pickerAccounts"
        :prefixes="toPrefixes"
        :as-of-date="form.date"
        :active-only="true"
        :include-accounts="form.toAccounts"
        :selected-accounts="form.toAccounts"
        :transaction-type="form.type"
        @update:model-value="addAccount('to', $event)"
        @remove="removeAccount('to', $event)"
      />

      <SelectPickerField
        v-model="form.currency"
        label="币种"
        :options="currencyOptions"
        :placeholder="currencyPlaceholder"
        :error="currencyError"
      />
      <MoneyInput v-model="form.amount" :currency="form.currency" :error="amountError" :allow-negative="true" />

      <van-field
        v-model="form.payee"
        label="交易方"
        placeholder="选择或输入"
        clearable
      >
        <template #right-icon>
          <button type="button" class="field-action" aria-label="选择交易方" @click.stop="openPayeePicker">
            <van-icon name="arrow" />
          </button>
        </template>
      </van-field>
      <van-field v-model="form.description" label="备注" placeholder="可选" clearable />

      <van-cell v-if="needsDistribute" title="分配状态" :value="distributeHint" />
    </van-cell-group>

    <div class="transaction-submit">
      <van-button block type="primary" native-type="button" :loading="loading" @click="onPrimary">
        {{ primaryLabel }}
      </van-button>
    </div>

    <van-popup v-model:show="showPayeePicker" position="bottom" round :style="{ maxHeight: '70%' }">
      <div class="payee-panel">
        <header class="payee-header">
          <strong>选择交易方</strong>
          <button type="button" class="field-action payee-close" @click="showPayeePicker = false">关闭</button>
        </header>
        <van-search v-model="payeeKeyword" placeholder="搜索历史交易方" shape="round" />
        <van-cell
          v-if="payeeKeyword.trim() && !filteredPayees.includes(payeeKeyword.trim())"
          :title="`使用「${payeeKeyword.trim()}」`"
          is-link
          @click="selectPayee(payeeKeyword.trim())"
        />
        <van-cell
          v-for="payee in filteredPayees"
          :key="payee"
          :title="payee"
          clickable
          @click="selectPayee(payee)"
        />
        <van-empty v-if="!filteredPayees.length && !payeeKeyword.trim()" description="暂无历史交易方，可直接输入" />
      </div>
    </van-popup>
  </van-form>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { accountsApi, type Account } from '../api/accounts'
import { transactionsApi, type CreateTransactionRequest, type Transaction } from '../api/transactions'
import {
  draftFromTransaction,
  draftNeedsDistribute,
  sideIsBalanced,
  toCreateRequest,
  useTransactionDraftStore,
  type TransactionDraft,
  type TransactionType,
} from '../stores/transactionDraft'
import { isValidAmount } from '../utils/decimal'
import AccountPicker from './AccountPicker.vue'
import DatePickerField from './DatePickerField.vue'
import MoneyInput from './MoneyInput.vue'
import SelectPickerField from './SelectPickerField.vue'

const props = defineProps<{
  initial?: Transaction | null
  loading?: boolean
  mode?: 'create' | 'edit'
}>()

const emit = defineEmits<{
  (event: 'submit', value: CreateTransactionRequest): void
}>()

const router = useRouter()
const draftStore = useTransactionDraftStore()
const accounts = ref<Account[]>([])
const payees = ref<string[]>([])
const submitted = ref(false)
const showPayeePicker = ref(false)
const payeeKeyword = ref('')

const form = reactive({
  type: 'expense' as TransactionType,
  date: new Date().toISOString().slice(0, 10),
  payee: '',
  description: '',
  currency: 'CNY',
  amount: '',
  fromAccounts: [] as string[],
  toAccounts: [] as string[],
})

const amountError = computed(() => {
  if (!submitted.value && !form.amount) return ''
  if (!isValidAmount(form.amount, { allowZero: false, allowNegative: true })) return '请输入有效金额'
  return ''
})

const fromLabel = computed(() => (form.type === 'transfer' ? '转出账户' : '资金账户'))
const toLabel = computed(() => {
  if (form.type === 'transfer') return '转入账户'
  if (form.type === 'income') return '收入分类'
  return '支出分类'
})

const fromPrefixes = computed(() => {
  if (form.type === 'transfer') return ['Assets', 'Liabilities']
  return ['Assets', 'Liabilities']
})
const toPrefixes = computed(() => {
  if (form.type === 'expense') return ['Expenses']
  if (form.type === 'income') return ['Income']
  return ['Assets', 'Liabilities']
})

const needsDistribute = computed(() => form.fromAccounts.length > 1 || form.toAccounts.length > 1)
const primaryLabel = computed(() => (needsDistribute.value ? '下一步：分配金额' : '保存'))

const distributeHint = computed(() => {
  const parts: string[] = []
  if (form.fromAccounts.length > 1) parts.push(`${form.fromAccounts.length} 个资金账户`)
  if (form.toAccounts.length > 1) parts.push(`${form.toAccounts.length} 个分类/转入`)
  return parts.join(' · ') || '需分配'
})

const pickerAccounts = computed(() => accounts.value)

// 产品仅支持人民币、美元。
const SUPPORTED_CURRENCIES = ['CNY', 'USD'] as const

const accountCurrencyMap = computed(() => {
  const map = new Map<string, string[]>()
  const walk = (nodes: Account[]) => {
    for (const node of nodes) {
      map.set(node.name, (node.currencies || []).filter(Boolean))
      if (node.children?.length) walk(node.children)
    }
  }
  walk(accounts.value)
  return map
})

const fundingAccountNames = computed(() => {
  if (form.type === 'transfer') {
    return [...form.fromAccounts, ...form.toAccounts]
  }
  return [...form.fromAccounts]
})

const availableCurrencies = computed(() => {
  if (!fundingAccountNames.value.length) return [] as string[]

  const supported = new Set<string>(SUPPORTED_CURRENCIES)
  const declared = new Set<string>()
  let unrestricted = false
  for (const name of fundingAccountNames.value) {
    // Missing map entry or empty currencies means Open 未声明币种限制。
    if (!accountCurrencyMap.value.has(name)) {
      unrestricted = true
      continue
    }
    const currencies = accountCurrencyMap.value.get(name) || []
    if (!currencies.length) {
      unrestricted = true
      continue
    }
    for (const currency of currencies) {
      if (supported.has(currency)) declared.add(currency)
    }
  }

  if (unrestricted || !declared.size) {
    return [...SUPPORTED_CURRENCIES]
  }

  return Array.from(declared).sort()
})

const currencyOptions = computed(() =>
  availableCurrencies.value.map((currency) => ({ text: currency, value: currency })),
)

const currencyPlaceholder = computed(() =>
  fundingAccountNames.value.length ? '请选择币种' : '请先选择资金账户',
)

const currencyError = computed(() => {
  if (!submitted.value) return ''
  if (!fundingAccountNames.value.length) return '请先选择资金账户'
  if (!form.currency) return '请选择币种'
  if (availableCurrencies.value.length && !availableCurrencies.value.includes(form.currency)) {
    return '币种不在可选范围内'
  }
  return ''
})

const filteredPayees = computed(() => {
  const keyword = payeeKeyword.value.trim().toLowerCase()
  if (!keyword) return payees.value
  return payees.value.filter((payee) => payee.toLowerCase().includes(keyword))
})

function syncCurrencyFromAccounts() {
  const options = availableCurrencies.value
  if (!options.length) return
  if (!options.includes(form.currency)) {
    form.currency = options.includes('CNY') ? 'CNY' : options[0]!
  }
}

function currentDraftSnapshot(): TransactionDraft {
  const mode =
    props.mode === 'edit' && props.initial?.id
      ? (`edit:${props.initial.id}` as const)
      : draftStore.draft?.mode || 'create'
  const existing = draftStore.draft
  return {
    mode,
    type: form.type,
    date: form.date,
    payee: form.payee,
    description: form.description,
    currency: form.currency || 'CNY',
    amount: form.amount,
    fromAccounts: [...form.fromAccounts],
    toAccounts: [...form.toAccounts],
    fromLines: existing?.mode === mode ? existing.fromLines : [],
    toLines: existing?.mode === mode ? existing.toLines : [],
  }
}

function applyDraft(draft: TransactionDraft) {
  form.type = draft.type
  form.date = draft.date
  form.payee = draft.payee
  form.description = draft.description
  form.currency = draft.currency
  form.amount = draft.amount
  form.fromAccounts = [...draft.fromAccounts]
  form.toAccounts = [...draft.toAccounts]
}

function loadInitial(transaction: Transaction | null | undefined) {
  if (!transaction) return
  const draft = draftFromTransaction(transaction)
  draftStore.setDraft(draft)
  applyDraft(draft)
}

function onTypeChange() {
  form.fromAccounts = []
  form.toAccounts = []
  if (draftStore.draft) {
    draftStore.updateDraft({
      type: form.type,
      fromAccounts: [],
      toAccounts: [],
      fromLines: [],
      toLines: [],
    })
  }
}

function addAccount(side: 'from' | 'to', name: string) {
  if (!name) return
  const list = side === 'from' ? form.fromAccounts : form.toAccounts
  if (list.includes(name)) return
  list.push(name)
  syncCurrencyFromAccounts()
}

function removeAccount(side: 'from' | 'to', name: string) {
  if (side === 'from') form.fromAccounts = form.fromAccounts.filter((item) => item !== name)
  else form.toAccounts = form.toAccounts.filter((item) => item !== name)
  if (draftStore.draft) {
    if (side === 'from') {
      draftStore.updateDraft({
        fromAccounts: form.fromAccounts,
        fromLines: draftStore.draft.fromLines.filter((l) => l.account !== name),
      })
    } else {
      draftStore.updateDraft({
        toAccounts: form.toAccounts,
        toLines: draftStore.draft.toLines.filter((l) => l.account !== name),
      })
    }
  }
  syncCurrencyFromAccounts()
}

function openPayeePicker() {
  payeeKeyword.value = form.payee
  showPayeePicker.value = true
}

function selectPayee(payee: string) {
  form.payee = payee
  showPayeePicker.value = false
  payeeKeyword.value = ''
}

function validateBase(): boolean {
  submitted.value = true
  if (amountError.value) return false
  if (currencyError.value) return false
  if (!form.fromAccounts.length || !form.toAccounts.length) return false
  return true
}

function onPrimary() {
  if (!validateBase()) return
  const draft = currentDraftSnapshot()
  draftStore.setDraft(draft)

  if (draftNeedsDistribute(draft)) {
    // Prefer category/to side first when multi, else from.
    const firstSide = draft.toAccounts.length > 1 ? 'to' : 'from'
    router.push({ path: '/transactions/distribute', query: { side: firstSide } })
    return
  }

  // Single accounts: lines from amount
  const fromAccount = draft.fromAccounts[0]
  const toAccount = draft.toAccounts[0]
  if (!fromAccount || !toAccount) return
  const ready: TransactionDraft = {
    ...draft,
    fromLines: [{ account: fromAccount, amount: draft.amount }],
    toLines: [{ account: toAccount, amount: draft.amount }],
  }
  draftStore.setDraft(ready)
  emit('submit', toCreateRequest(ready))
}

// When returning from distribute with balanced multi draft, parent may call submit via prop watch — expose method.
function trySubmitFromDraft() {
  const draft = draftStore.draft
  if (!draft) return false
  applyDraft(draft)
  if (!draftNeedsDistribute(draft)) {
    const fromAccount = draft.fromAccounts[0]
    const toAccount = draft.toAccounts[0]
    if (!fromAccount || !toAccount) return false
    emit('submit', toCreateRequest({
      ...draft,
      fromLines: draft.fromLines.length ? draft.fromLines : [{ account: fromAccount, amount: draft.amount }],
      toLines: draft.toLines.length ? draft.toLines : [{ account: toAccount, amount: draft.amount }],
    }))
    return true
  }
  const fromOk = draft.fromAccounts.length <= 1 || sideIsBalanced(draft.amount, draft.fromLines, draft.fromAccounts)
  const toOk = draft.toAccounts.length <= 1 || sideIsBalanced(draft.amount, draft.toLines, draft.toAccounts)
  if (fromOk && toOk) {
    emit('submit', toCreateRequest(draft))
    return true
  }
  return false
}

/** After successful create: keep type/date/funding account for continuous entry. */
function resetForNextEntry(options?: { lastPayee?: string }) {
  submitted.value = false
  form.amount = ''
  form.payee = ''
  form.description = ''
  form.toAccounts = []
  const lastPayee = options?.lastPayee?.trim()
  if (lastPayee && !payees.value.includes(lastPayee)) {
    payees.value = [lastPayee, ...payees.value]
  }
}

defineExpose({ trySubmitFromDraft, resetForNextEntry })

watch(() => props.initial, loadInitial, { immediate: true })
watch(availableCurrencies, () => {
  syncCurrencyFromAccounts()
})

onMounted(async () => {
  const [loadedAccounts, loadedPayees] = await Promise.all([
    accountsApi.getAccounts(),
    transactionsApi.getPayees().catch(() => [] as string[]),
  ])
  accounts.value = loadedAccounts
  payees.value = loadedPayees
  // Restore in-progress draft for create mode when returning from distribute without submit.
  if (!props.initial && draftStore.draft?.mode === 'create') {
    applyDraft(draftStore.draft)
  }
  syncCurrencyFromAccounts()
})
</script>

<style scoped>
.transaction-form-card { margin-top: 8px; }
.transaction-form :deep(.van-cell) { min-height: 54px; align-items: center; }
.transaction-form :deep(.van-field__label) { color: var(--bm-muted); }
.transaction-submit { display: block; box-sizing: border-box; margin: 20px 0 16px; width: 100%; }
.transaction-submit :deep(.van-button) { display: block; box-sizing: border-box; width: 100%; height: 48px; font-size: 16px; font-weight: 700; }
.field-action {
  display: inline-grid;
  padding: 4px;
  place-items: center;
  border: 0;
  background: transparent;
  color: var(--bm-muted);
  font-size: 16px;
}
.payee-panel { padding-bottom: 16px; }
.payee-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 8px;
  color: var(--bm-text);
}
.payee-close { color: var(--bm-primary); font-size: 14px; }
</style>
