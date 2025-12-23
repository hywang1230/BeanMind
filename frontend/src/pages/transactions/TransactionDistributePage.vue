<template>
  <f7-page name="transaction-distribute">
    <f7-navbar>
      <f7-nav-left>
        <f7-link @click="goBack">
          <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
        </f7-link>
      </f7-nav-left>
      <f7-nav-title>{{ pageTitle }}</f7-nav-title>
      <f7-nav-right>
        <f7-link @click="handleNext" :class="{ disabled: loading }" :style="{ opacity: (!isValid || loading) ? 0.5 : 1 }">
          {{ isLastStep ? (loading ? '保存中' : '保存') : '下一步' }}
        </f7-link>
      </f7-nav-right>
    </f7-navbar>

    <f7-block class="margin-vertical">
      <div class="display-flex justify-content-space-between align-items-center">
        <span class="text-color-gray">总金额</span>
        <span class="text-size-large font-weight-bold">{{ draft?.currency }} {{ formatNumber(totalAmount) }}</span>
      </div>
      <div class="display-flex justify-content-space-between align-items-center margin-top-half">
        <span class="text-color-gray">剩余未分配</span>
        <span :class="remaining === 0 ? 'text-color-green' : 'text-color-red'" class="font-weight-bold">
          {{ formatNumber(remaining) }}
        </span>
      </div>
    </f7-block>

    <f7-list strong-ios dividers-ios inset-ios form>
      <f7-list-item 
        v-for="item in items" 
        :key="item" 
        :title="formatName(item)"
        link="#"
        @click="startEditing(item)"
      >
        <template #after>
            <div class="item-input-wrap display-flex align-items-center justify-content-flex-end" style="min-width: 100px;">
                <span :class="{ 'text-color-primary': currentEditingItem === item }">
                    {{ formatItemValue(item) }}
                </span>
                <span v-if="currentEditingItem === item && isKeypadOpen" class="cursor">|</span>
            </div>
        </template>
      </f7-list-item>
    </f7-list>
    
    <f7-block-footer class="text-align-center">
        <!-- Error message if any -->
    </f7-block-footer>

    <!-- Keypad Sheet -->
    <f7-sheet
      class="amount-keypad-sheet"
      :opened="isKeypadOpen"
      @sheet:closed="onSheetClosed"
      style="height: auto;"
      backdrop
      close-by-backdrop-click
      swipe-to-close
    >
        <div class="keypad-grid">
            <button class="key-btn number-key" @click="append('1')">1</button>
            <button class="key-btn number-key" @click="append('2')">2</button>
            <button class="key-btn number-key" @click="append('3')">3</button>
            <button class="key-btn action-key" @click="handleDelete">
                 <i class="f7-icons">delete_left</i>
            </button>

            <button class="key-btn number-key" @click="append('4')">4</button>
            <button class="key-btn number-key" @click="append('5')">5</button>
            <button class="key-btn number-key" @click="append('6')">6</button>
            <button class="key-btn op-key" @click="append('+')">+</button>

            <button class="key-btn number-key" @click="append('7')">7</button>
            <button class="key-btn number-key" @click="append('8')">8</button>
            <button class="key-btn number-key" @click="append('9')">9</button>
            <button class="key-btn op-key" @click="append('-')">-</button>

            <button class="key-btn number-key" @click="append('.')">.</button>
            <button class="key-btn number-key" @click="append('0')">0</button>
            <button class="key-btn action-key highlight" style="grid-column: span 2" @click="handleOK">
                确定
            </button>
        </div>
    </f7-sheet>
  </f7-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useTransactionStore } from '../../stores/transaction'
import { useUIStore } from '../../stores/ui'
import type { CreateTransactionRequest, Posting } from '../../api/transactions'
import { f7 } from 'framework7-vue'

const router = useRouter()
const route = useRoute()
const transactionStore = useTransactionStore()
const uiStore = useUIStore()
const draft = transactionStore.transactionDraft

// Keypad State
const isKeypadOpen = ref(false)
const currentEditingItem = ref<string | null>(null)
const currentExpression = ref('')

const type = computed(() => route.query.type as 'category' | 'account') // 'category' or 'account'
const loading = ref(false)

// Init check
if (!draft) {
    router.replace('/transactions/add')
}

const totalAmount = computed(() => draft?.amount || 0)
const items = computed(() => {
    if (!draft) return []
    if (type.value === 'category') return draft.category || []
    
    // type === 'account'
    const side = route.query.side as 'from' | 'to' | undefined
    if (side === 'to') return draft.toAccount || []
    return draft.fromAccount || []
})

const distributions = ref<Record<string, number | string>>({})

function initDistributions() {
    distributions.value = {} // Clear previous
    if (!draft) return
    
    // Load existing if any, or init default
    let existing: Record<string, number> | undefined
    if (type.value === 'category') existing = draft.categoryDistributions
    else {
        existing = draft.accountDistributions
    }
    
    const targets: string[] = items.value
    if (existing && Object.keys(existing).length > 0) {
        targets.forEach((t: string) => {
            if (existing && existing[t] !== undefined) {
                distributions.value[t] = existing[t]
            }
        })
    }
    
    // Check coverage
    const hasAll = targets.every((t: string) => distributions.value[t] !== undefined)
    
    if (!hasAll) {
        // Auto split evenly
        const count = targets.length
        if (count > 0 && draft.amount) {
            const perItem = parseFloat((draft.amount / count).toFixed(2))
            let sum = 0
            targets.forEach((t: string, i: number) => {
                if (i === count - 1) {
                    distributions.value[t] = parseFloat((draft.amount! - sum).toFixed(2))
                } else {
                    distributions.value[t] = perItem
                    sum += perItem
                }
            })
        }
    }
}

watch(() => route.query, () => {
    initDistributions()
})

// Initialize distributions
onMounted(() => {
    initDistributions()
})

const currentSum = computed(() => {
    return Object.values(distributions.value).reduce<number>((sum, val) => sum + (Number(val) || 0), 0)
})

const remaining = computed(() => {
    return Number((totalAmount.value - (currentSum.value || 0)).toFixed(2))
})

const isValid = computed(() => Math.abs(remaining.value) < 0.01)

const pageTitle = computed(() => {
    if (type.value === 'category') return '分配分类金额'
    if (route.query.side === 'to') return '分配转入账户'
    return '分配账户金额'
})

// Navigation Logic
const isLastStep = computed(() => {
    if (!draft) return true
    // Logic: 
    // If current is Category: check if Account needs split.
    // If current is Account (From): check if Account (To) needs split? (For transfer).
    
    if (type.value === 'category') {
        // Check Next: Account Multi?
        if (draft.type === 'transfer') {
             if (draft.fromAccount.length > 1) return false
             if (draft.toAccount.length > 1) return false
        } else {
             // Expense/Income
             if (draft.fromAccount.length > 1) return false
        }
        return true
    }
    
    if (type.value === 'account') {
        const side = route.query.side
        if (draft.type === 'transfer' && side === 'from') {
             if (draft.toAccount.length > 1) return false
        }
        return true
    }
    
    return true
})

function formatName(name: string) {
    return name.split(':').pop()
}

function formatNumber(num: number) {
    return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function goBack() {
    router.back()
}

function formatItemValue(item: string) {
    if (currentEditingItem.value === item && isKeypadOpen.value) {
        return currentExpression.value
    }
    const val = distributions.value[item]
    if (val === undefined || val === '') return '0.00'
    return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// Keypad Logic
function startEditing(item: string) {
    currentEditingItem.value = item
    const val = distributions.value[item]
    currentExpression.value = (val !== undefined && val !== '') ? val.toString() : ''
    isKeypadOpen.value = true
}

function closeKeypad() {
    calculate()
    isKeypadOpen.value = false
    currentEditingItem.value = null
}

function onSheetClosed() {
    calculate()
    isKeypadOpen.value = false
    currentEditingItem.value = null
}

function handleOK() {
    closeKeypad()
}

function append(char: string) {
    // Prevent multiple dots
    if (char === '.') {
        // Find last number segment
        const parts = currentExpression.value.split(/[\+\-]/)
        const currentNum = parts[parts.length - 1]
        if (currentNum && currentNum.includes('.')) return
    }
    
    // Prevent multiple operators
    if (['+', '-'].includes(char)) {
        const lastChar = currentExpression.value.slice(-1)
        if (['+', '-'].includes(lastChar)) {
            currentExpression.value = currentExpression.value.slice(0, -1) + char
            return
        }
        if (currentExpression.value === '' && char === '+') return // Don't start with +
    }

    currentExpression.value += char
}

function handleDelete() {
    if (currentExpression.value.length > 0) {
        currentExpression.value = currentExpression.value.slice(0, -1)
    }
}

function calculate() {
    if (!currentEditingItem.value) return
    try {
        let result = 0
        if (currentExpression.value) {
            let sanitized = currentExpression.value.replace(/[^0-9\+\-\.]/g, '')
            if (['+', '-'].includes(sanitized.slice(-1))) {
                sanitized = sanitized.slice(0, -1)
            }
            if (sanitized) {
                result = Function('"use strict";return (' + sanitized + ')')()
                result = Math.round(result * 100) / 100
            }
        }
        
        // Update current
        distributions.value[currentEditingItem.value] = result
        currentExpression.value = result.toString()

        // Distribute remaining to subsequent items
        redistribute(currentEditingItem.value)
    } catch (e) {
        // ignore
    }
}

function redistribute(changedItem: string) {
    const list: string[] = items.value
    const idx = list.indexOf(changedItem)
    if (idx === -1 || idx === list.length - 1) return

    // Calculate sum of items up to including changedItem (locked)
    let lockedSum = 0
    for (let i = 0; i <= idx; i++) {
        const item = list[i]
        if (item) {
            lockedSum += Number(distributions.value[item] || 0)
        }
    }

    const remaining = totalAmount.value - lockedSum
    const subsequentCount = list.length - 1 - idx
    
    // Distribute remaining evenly
    const perItem = Math.floor((remaining / subsequentCount) * 100) / 100
    let distributedSum = 0

    for (let i = idx + 1; i < list.length; i++) {
        const item = list[i]
        if (!item) continue
        
        if (i === list.length - 1) {
            // Last item takes dust
            // Total remaining exactly
             distributions.value[item] = Number((remaining - distributedSum).toFixed(2))
        } else {
            distributions.value[item] = perItem
            distributedSum += perItem
        }
    }
}

async function handleNext() {
    if (!isValid.value) {
        f7.toast.show({ text: '请分配所有金额', position: 'center', closeTimeout: 2000 })
        return
    }
    
    // Save to draft
    if (!draft) return
    
    // Convert strings to numbers
    const finalDist: Record<string, number> = {}
    for (const [k, v] of Object.entries(distributions.value)) {
        finalDist[k] = Number(v)
    }
    
    if (type.value === 'category') {
        draft.categoryDistributions = { ...draft.categoryDistributions, ...finalDist }
    } else {
        draft.accountDistributions = { ...draft.accountDistributions, ...finalDist }
    }
    
    transactionStore.setTransactionDraft(draft)
    
    if (isLastStep.value) {
        await submitTransaction()
    } else {
        // Navigate to next
        if (type.value === 'category') {
             // Next is Account. Which side?
             if (draft.type === 'transfer') {
                  if (draft.fromAccount.length > 1) {
                      router.push({ path: '/transactions/distribute', query: { type: 'account', side: 'from' } })
                  } else {
                      router.push({ path: '/transactions/distribute', query: { type: 'account', side: 'to' } })
                  }
             } else {
                  router.push({ path: '/transactions/distribute', query: { type: 'account', side: 'from' } }) // Expense/Income uses fromAccount
             }
        } else if (type.value === 'account') {
             if (route.query.side === 'from' && draft.type === 'transfer' && draft.toAccount.length > 1) {
                  router.push({ path: '/transactions/distribute', query: { type: 'account', side: 'to' } })
             }
        }
    }
}

function buildFinalPostings(): Posting[] {
    if (!draft) return []
    const posts: Posting[] = []
    const currency = draft.currency
    const totalAmount = draft.amount || 0
    
    // Helper to get amount for an item
    // 如果分配记录存在，使用分配的金额
    // 如果只有单个项目且没有分配记录，使用总金额
    const getAmt = (item: string, distMap: Record<string, number> | undefined, itemList: string[], sign: number = 1) => {
        if (distMap && distMap[item] !== undefined) {
            return distMap[item] * sign
        }
        // 单项目情况：使用总金额
        if (itemList.length === 1) {
            return totalAmount * sign
        }
        // Fallback: 不应该发生
        return 0
    }

    if (draft.type === 'expense') {
        // Expense: +Category, -Account
        draft.category.forEach(cat => {
            posts.push({ account: cat, amount: getAmt(cat, draft.categoryDistributions, draft.category, 1).toFixed(2), currency })
        })
        draft.fromAccount.forEach(acc => {
            posts.push({ account: acc, amount: getAmt(acc, draft.accountDistributions, draft.fromAccount, -1).toFixed(2), currency })
        })
    } else if (draft.type === 'income') {
        // Income: +Account, -Category
        draft.fromAccount.forEach(acc => {
             posts.push({ account: acc, amount: getAmt(acc, draft.accountDistributions, draft.fromAccount, 1).toFixed(2), currency })
        })
        draft.category.forEach(cat => {
             posts.push({ account: cat, amount: getAmt(cat, draft.categoryDistributions, draft.category, -1).toFixed(2), currency })
        })
    } else if (draft.type === 'transfer') {
        // Transfer: -From, +To
         draft.fromAccount.forEach(acc => {
             posts.push({ account: acc, amount: getAmt(acc, draft.accountDistributions, draft.fromAccount, -1).toFixed(2), currency })
        })
        draft.toAccount.forEach(acc => {
             posts.push({ account: acc, amount: getAmt(acc, draft.accountDistributions, draft.toAccount, 1).toFixed(2), currency })
        })
    }
    
    return posts
}

async function submitTransaction() {
    loading.value = true
    try {
        if (!draft) throw new Error("No draft")
        
        const tags = draft.tagString
            .split(' ')
            .map(t => t.trim())
            .filter(t => t.length > 0)

        const request: CreateTransactionRequest = {
            date: draft.date,
            description: draft.description || undefined,
            payee: draft.payee || undefined,
            postings: buildFinalPostings(),
            tags: tags.length > 0 ? tags : undefined
        }

        await transactionStore.createTransaction(request)
        transactionStore.clearTransactionDraft()
        // 标记交易列表需要刷新
        uiStore.markTransactionsNeedsRefresh()
        // Go back to where? Ideally dash or transaction list.
        // AddTransactionPage was pushed from List or Dash.
        // Distribute Page is pushed from Add.
        // History: [..., List, Add, Distribute]
        // We want to go back to List.
        router.push('/transactions') // Safer
    } catch (err: any) {
        console.error(err)
        f7.toast.show({ text: err.message || '保存失败', position: 'center', closeTimeout: 2000 })
    } finally {
        loading.value = false
    }
}
</script>

<style scoped>
.margin-vertical {
    margin-top: 16px;
    margin-bottom: 16px;
}
.text-size-large {
    font-size: 24px;
}
.disabled {
    opacity: 0.5;
    pointer-events: none;
}

/* Keypad Styles */
.cursor {
    margin-left: 2px;
    animation: blink 1s infinite;
    font-weight: 300;
    color: var(--f7-theme-color);
}
@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
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
