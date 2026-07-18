<template>
  <section class="page secondary-page distribute-page">
    <van-nav-bar :title="pageTitle" left-arrow @click-left="goBack">
      <template #right>
        <van-button size="small" type="primary" plain :disabled="!isValid || saving" :loading="saving" @click="handleNext">
          {{ isLastStep ? '保存' : '下一步' }}
        </van-button>
      </template>
    </van-nav-bar>

    <van-empty v-if="!draft" description="没有可分配的草稿，请返回重新填写">
      <van-button type="primary" @click="router.replace('/transactions/new')">去记账</van-button>
    </van-empty>

    <template v-else>
      <van-cell-group inset class="summary-card">
        <van-cell title="总金额" :value="`${draft.currency} ${formatAmountDisplay(draft.amount)}`" />
        <van-cell title="剩余未分配">
          <template #value>
            <span :class="isZero(remaining) ? 'ok' : 'bad'">{{ formatAmountDisplay(remaining) }}</span>
          </template>
        </van-cell>
      </van-cell-group>

      <van-cell-group inset class="lines-card">
        <van-field
          v-for="account in accounts"
          :key="account"
          :label="shortName(account)"
          :model-value="amounts[account] || ''"
          type="text"
          inputmode="decimal"
          placeholder="0.00"
          :error-message="fieldError(account)"
          @update:model-value="onAmountInput(account, $event)"
        >
          <template #extra>
            <span class="account-path">{{ account }}</span>
          </template>
        </van-field>
      </van-cell-group>

      <van-notice-bar v-if="error" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ error }}</van-notice-bar>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { accountShortLabel } from '../../utils/accountTree'
import { showSuccessToast } from 'vant'
import { useRoute, useRouter } from 'vue-router'
import type { ApiError } from '../../api/client'
import { transactionsApi } from '../../api/transactions'
import {
  sideIsBalanced,
  sideRemaining,
  toCreateRequest,
  useTransactionDraftStore,
  type DistributeSide,
  type DraftLine,
} from '../../stores/transactionDraft'
import { formatAmountDisplay, isZero, normalizeAmountInput } from '../../utils/decimal'

const route = useRoute()
const router = useRouter()
const draftStore = useTransactionDraftStore()
const draft = computed(() => draftStore.draft)
const saving = ref(false)
const error = ref('')
const amounts = reactive<Record<string, string>>({})
const submitted = ref(false)

const side = computed<DistributeSide>(() => (route.query.side === 'from' ? 'from' : 'to'))

const accounts = computed(() => {
  if (!draft.value) return [] as string[]
  return side.value === 'from' ? draft.value.fromAccounts : draft.value.toAccounts
})

const pageTitle = computed(() => {
  if (!draft.value) return '分配金额'
  if (side.value === 'to') {
    return draft.value.type === 'transfer' ? '分配转入账户' : '分配分类金额'
  }
  return draft.value.type === 'transfer' ? '分配转出账户' : '分配资金账户'
})

const lines = computed<DraftLine[]>(() =>
  accounts.value.map((account) => ({ account, amount: amounts[account] || '0' })),
)

const remaining = computed(() => {
  if (!draft.value) return '0'
  return sideRemaining(draft.value.amount, lines.value)
})

const isValid = computed(() => {
  if (!draft.value) return false
  return sideIsBalanced(draft.value.amount, lines.value, accounts.value)
})

const isLastStep = computed(() => {
  if (!draft.value) return true
  if (side.value === 'to' && draft.value.fromAccounts.length > 1) return false
  if (side.value === 'from' && draft.value.toAccounts.length > 1 && route.query.from !== 'to') {
    // if we started from from-side and to still multi and not yet done — after from, need to
  }
  if (side.value === 'from') {
    // when finishing from side, check if to still needs distribute and wasn't done
    if (draft.value.toAccounts.length > 1) {
      const toOk = sideIsBalanced(draft.value.amount, draft.value.toLines, draft.value.toAccounts)
      return toOk
    }
  }
  if (side.value === 'to') {
    if (draft.value.fromAccounts.length > 1) {
      const fromOk = sideIsBalanced(draft.value.amount, draft.value.fromLines, draft.value.fromAccounts)
      return fromOk
    }
  }
  return true
})

function shortName(name: string) {
  return accountShortLabel(name, accounts.value)
}

function fieldError(account: string) {
  if (!submitted.value) return ''
  if (!amounts[account]) return '请输入金额'
  return ''
}

function onAmountInput(account: string, value: string) {
  amounts[account] = normalizeAmountInput(value)
}

function initAmounts() {
  if (!draft.value) return
  const existing = side.value === 'from' ? draft.value.fromLines : draft.value.toLines
  const total = draft.value.amount
  const list = accounts.value
  for (const key of Object.keys(amounts)) delete amounts[key]

  const hasAll = list.length > 0 && list.every((a) => existing.some((l) => l.account === a && l.amount))
  if (hasAll) {
    for (const line of existing) amounts[line.account] = line.amount
    return
  }

  // Equal split with last residual via string math
  if (list.length === 1) {
    const only = list[0]
    if (only) amounts[only] = total
    return
  }
  // simple equal: divide by count using integer cents if possible, else leave empty for user
  // Use equal integer division on scaled digits when total looks like decimal with <= 2 places
  try {
    const n = list.length
    // fallback equal split via repeated sub for residual on last
    // approximate: use floor of (total * 100 / n) / 100 when 2dp
    const scaled = total.includes('.') ? total : `${total}.00`
    const [intPart, frac = ''] = scaled.replace(/^-/, '').split('.')
    const scale = Math.max(frac.length, 2)
    const digits = `${intPart}${frac.padEnd(scale, '0')}`
    const totalInt = BigInt(digits)
    const base = totalInt / BigInt(n)
    let used = 0n
    list.forEach((account, index) => {
      let share = base
      if (index === n - 1) share = totalInt - used
      used += share
      const neg = total.startsWith('-')
      const raw = fromScaled(share, scale)
      amounts[account] = neg ? `-${raw}` : raw
    })
  } catch {
    for (const account of list) amounts[account] = ''
  }
}

function fromScaled(value: bigint, scale: number): string {
  let digits = value.toString()
  if (scale === 0) return digits
  if (digits.length <= scale) digits = digits.padStart(scale + 1, '0')
  const cut = digits.length - scale
  const frac = digits.slice(cut).replace(/0+$/, '')
  return frac ? `${digits.slice(0, cut)}.${frac}` : digits.slice(0, cut)
}

function persistSide() {
  if (!draft.value) return
  draftStore.setSideLines(side.value, lines.value)
}

function goBack() {
  router.back()
}

async function handleNext() {
  submitted.value = true
  error.value = ''
  if (!draft.value || !isValid.value) return
  persistSide()

  if (!isLastStep.value) {
    const nextSide: DistributeSide = side.value === 'to' ? 'from' : 'to'
    await router.replace({ path: '/transactions/distribute', query: { side: nextSide, from: side.value } })
    return
  }

  // Ensure single sides get lines
  const d = draftStore.draft!
  if (d.fromAccounts.length === 1 && !d.fromLines.length) {
    const fromAccount = d.fromAccounts[0]
    if (fromAccount) draftStore.setSideLines('from', [{ account: fromAccount, amount: d.amount }])
  }
  if (d.toAccounts.length === 1 && !d.toLines.length) {
    const toAccount = d.toAccounts[0]
    if (toAccount) draftStore.setSideLines('to', [{ account: toAccount, amount: d.amount }])
  }

  const payload = toCreateRequest(draftStore.draft!)
  saving.value = true
  try {
    if (d.mode.startsWith('edit:')) {
      const id = d.mode.slice('edit:'.length)
      await transactionsApi.updateTransaction(id, payload)
      draftStore.clear()
      await router.replace(`/transactions/${id}`)
    } else {
      await transactionsApi.createTransaction(payload)
      draftStore.clear()
      showSuccessToast('已保存，可继续记账')
      await router.replace('/transactions/new')
    }
  } catch (reason) {
    // keep draft for retry
    error.value = (reason as ApiError).message || '保存失败'
  } finally {
    saving.value = false
  }
}

watch(
  () => [draft.value?.mode, side.value, accounts.value.join('|')],
  () => initAmounts(),
  { immediate: true },
)
</script>

<style scoped>
.summary-card, .lines-card { margin-top: 12px; }
.ok { color: var(--van-success-color, #07c160); font-weight: 700; }
.bad { color: var(--bm-expense, #ee0a24); font-weight: 700; }
.account-path { display: none; }
</style>
