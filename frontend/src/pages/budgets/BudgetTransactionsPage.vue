<template>
    <f7-page name="budget-transactions">
        <f7-navbar>
            <f7-nav-left>
                <f7-link @click="goBack">
                    <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
                </f7-link>
            </f7-nav-left>
            <f7-nav-title>{{ accountPattern ? accountPattern.split(':').pop() : '预算流水' }}</f7-nav-title>
        </f7-navbar>

        <!-- 加载状态 -->
        <div v-if="loading" class="loading-container">
            <f7-preloader></f7-preloader>
        </div>

        <!-- 空状态 -->
        <div v-else-if="transactions.length === 0" class="empty-state">
            <div class="empty-icon">📝</div>
            <div class="empty-text">该预算项目暂无关联流水</div>
        </div>

        <!-- 流水列表 (按日期分组) -->
        <div v-else class="transactions-content">
            <div v-for="group in groupedTransactions" :key="group.date" class="transaction-group">
                <!-- 日期分组头 -->
                <div class="date-group-header">
                    <span class="date-title">{{ formatGroupDate(group.date) }}</span>
                    <span class="day-summary" :class="getDaySummaryClass(group.total)">
                        {{ formatDayTotal(group.total) }}
                    </span>
                </div>

                <!-- 该日期的交易列表 - 独立的圆角卡片 -->
                <f7-list media-list dividers-ios strong inset class="transaction-list">
                    <f7-list-item v-for="transaction in group.items" :key="transaction.id" link="#"
                        @click="viewTransaction(transaction)" class="transaction-item"
                        :class="getTransactionClass(transaction)">
                        <template #media>
                            <div class="transaction-icon" :class="getIconClass(transaction)">
                                <f7-icon :ios="getIcon(transaction)" size="20"></f7-icon>
                            </div>
                        </template>
                        <template #title>
                            <span class="transaction-title">{{ getTransactionTitle(transaction) }}</span>
                        </template>
                        <template #subtitle>
                            <span class="transaction-desc">{{ getTransactionSubtitle(transaction) }}</span>
                        </template>
                        <template #after>
                            <span class="transaction-amount" :class="getAmountClass(transaction)">
                                {{ formatAmount(transaction) }}
                            </span>
                        </template>
                    </f7-list-item>
                </f7-list>
            </div>
        </div>
    </f7-page>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { budgetsApi } from '../../api/budgets'
import type { Transaction } from '../../api/accounts'
import { f7 } from 'framework7-vue'

const route = useRoute()
const router = useRouter()

// to avoid undefined
const budgetId = (route.params.budgetId as string) || ''
const itemId = (route.params.itemId as string) || ''
const accountPattern = (route.query.pattern as string) || ''

const loading = ref(false)
const transactions = ref<Transaction[]>([])

function goBack() {
    router.back()
}

function viewTransaction(transaction: Transaction) {
    router.push(`/transactions/${transaction.id}`)
}

// ----------------------------------------------------------------------
// Grouping & Display Logic (Adapted from TransactionsPage.vue)
// ----------------------------------------------------------------------

interface TransactionGroup {
    date: string
    items: Transaction[]
    total: number
}

// 辅助函数：标准化日期格式 yyyy-MM-dd
function formatDateValue(dateStr: string | undefined): string {
    if (!dateStr) return ''
    return dateStr.split('T')[0] || ''
}

// 按日期分组交易
const groupedTransactions = computed<TransactionGroup[]>(() => {
    const groups: Record<string, TransactionGroup> = {}

    for (const transaction of transactions.value) {
        const date = formatDateValue(transaction.date)
        if (!groups[date]) {
            groups[date] = { date, items: [], total: 0 }
        }
        groups[date].items.push(transaction)

        // 计算匹配部分的金额（用于日汇总）
        const amount = getDisplayAmountValue(transaction)
        groups[date].total += amount
    }

    // 按日期降序排列
    return Object.values(groups).sort((a, b) => b.date.localeCompare(a.date))
})

// 获取用于显示的金额值（正负号）
// 在预算视图中，我们只关心匹配 accountPattern 的 postings
// 为了和 TransactionPage 样式保持一致 (支出=Red, 收入=Green)，我们需要根据 posting 的正负来决定显示
// 通常：Expenses posting 是正数。为了显示为 Red (Expense style), 我们取反。
// Income posting 是负数。为了显示为 Green (Income style), 我们取反 (变成正数, >0 -> Green)。
// 所以统一逻辑： return -sum(matching_postings)
function getDisplayAmountValue(transaction: Transaction): number {
    if (!transaction.postings) return 0

    let totalMatch = 0
    const cleanPattern = accountPattern.replace(':*', '')

    for (const p of transaction.postings) {
        if (p.account.startsWith(cleanPattern) && p.amount) {
            totalMatch += parseFloat(p.amount)
        }
    }

    // 如果没有匹配的（fallback逻辑），使用第一笔
    // 注意：如果是 fallback，我们可能无法保证正负号的含义，但通常是“本方”金额
    if (totalMatch === 0 && transaction.postings.length > 0) {
        return 0
    }

    return -totalMatch
}

function formatGroupDate(dateStr: string): string {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)

    const month = date.getMonth() + 1
    const day = date.getDate()
    const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    const weekDay = weekDays[date.getDay()]

    const todayStr = today.toISOString().split('T')[0]
    const yesterdayStr = yesterday.toISOString().split('T')[0]

    if (dateStr === todayStr) {
        return `今天 ${month}月${day}日`
    } else if (dateStr === yesterdayStr) {
        return `昨天 ${month}月${day}日`
    }

    return `${month}月${day}日 ${weekDay}`
}

function getDaySummaryClass(total: number): string {
    if (total > 0) return 'positive'
    if (total < 0) return 'negative'
    return ''
}

function formatDayTotal(total: number): string {
    if (total === 0) return ''
    return `¥${Math.abs(total).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function getTransactionClass(transaction: Transaction): string {
    // 简单根据金额判断：负数为支出样式，正数为收入样式
    const amount = getDisplayAmountValue(transaction)
    if (amount > 0) return 'income-item' // Greenish bg? Or just class
    if (amount < 0) return 'expense-item'
    return ''
}

function getIcon(transaction: Transaction): string {
    // 这里的 type 可能是 inferred from pattern or transaction content
    // 基于金额正负判断方向：>0 Income, <0 Expense
    const amount = getDisplayAmountValue(transaction)
    if (amount > 0) return 'f7:arrow_down_circle' // Income logic
    if (amount < 0) return 'f7:arrow_up_circle'   // Expense logic
    return 'f7:doc_text'
}

function getIconClass(transaction: Transaction): string {
    const amount = getDisplayAmountValue(transaction)
    if (amount > 0) return 'income-icon'
    if (amount < 0) return 'expense-icon'
    return ''
}

// 获取分类名称（作为主标题）
function getTransactionTitle(transaction: Transaction): string {
    if (transaction.postings.length === 0) return '未分类'

    // 提取所有非资产/负债账户（即分类账户）的名称
    const categories: string[] = []

    for (const posting of transaction.postings) {
        const account = posting.account
        // 只显示支出和收入分类，跳过资产和负债账户
        if (account.startsWith('Expenses:') || account.startsWith('Income:')) {
            const parts = account.split(':')
            // 如果只有一级（如 Expenses），显示 Expenses
            // 如果有多级（Expenses:Food:Lunch），只显示最后一级 Lunch
            if (parts.length >= 2) {
                categories.push(parts[parts.length - 1]!)
            } else {
                categories.push(parts[0]!)
            }
        }
    }

    if (categories.length === 0) {
        // 如果没有找到分类账户，使用第一个账户
        const account = transaction.postings[0]!.account
        const parts = account.split(':')
        return parts.length >= 2 ? parts[parts.length - 1]! : parts[0]!
    }

    // 去重
    const uniqueCategories = [...new Set(categories)]
    return uniqueCategories.join(', ')
}

// 获取描述信息（Payee - Description）（作为副标题）
function getTransactionSubtitle(transaction: Transaction): string {
    const parts: string[] = []
    if (transaction.payee) parts.push(transaction.payee)
    if (transaction.description) parts.push(transaction.description)
    return parts.join(' - ') || ''
}

function getAmountClass(transaction: Transaction): string {
    const amount = getDisplayAmountValue(transaction)
    if (amount > 0) return 'positive'
    if (amount < 0) return 'negative'
    return 'neutral'
}

function formatAmount(transaction: Transaction): string {
    const amount = getDisplayAmountValue(transaction)
    // 假设都是 CNY，或者不做多币种符号处理，统一用 ¥
    return `¥${Math.abs(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

async function loadTransactions() {
    if (!budgetId || !itemId) return

    loading.value = true
    try {
        const res = await budgetsApi.getBudgetItemTransactions(budgetId, itemId)
        if (res && res.transactions) {
            transactions.value = res.transactions // date sorting happens in computed
        } else {
            transactions.value = []
        }
    } catch (error) {
        console.error('Failed to load transactions:', error)
        f7.toast.create({
            text: '加载流水失败',
            position: 'center',
            closeTimeout: 2000
        }).open()
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    loadTransactions()
})
</script>

<style scoped>
/* 复用 TransactionsPage.vue 的样式 */
.loading-container {
    display: flex;
    justify-content: center;
    padding: 60px 0;
}

.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #8e8e93;
}

.empty-icon {
    font-size: 64px;
    margin-bottom: 16px;
}

.empty-text {
    font-size: 16px;
    margin-bottom: 24px;
}

.transactions-content {
    padding: 0 16px 80px;
}

.transaction-list {
    margin: 0;
    --f7-list-inset-side-margin: 0;
    --f7-list-inset-border-radius: 12px;
    border-radius: 12px;
    overflow: hidden;
}

.transaction-group {
    margin-bottom: 16px;
}

.date-group-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 4px;
}

.date-title {
    font-size: 13px;
    color: #8e8e93;
    font-weight: 600;
}

.day-summary {
    font-size: 13px;
    font-weight: 600;
}

.day-summary.positive {
    color: var(--ios-green);
}

.day-summary.negative {
    color: var(--ios-red);
}

.transaction-item {
    --f7-list-item-padding-horizontal: 16px;
    background: var(--bg-secondary);
}

.transaction-icon {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.transaction-icon.expense-icon {
    background: rgba(255, 59, 48, 0.12);
    color: var(--ios-red);
}

.transaction-icon.income-icon {
    background: rgba(52, 199, 89, 0.12);
    color: var(--ios-green);
}

.transaction-title {
    font-size: 16px;
    font-weight: 500;
    color: var(--text-primary);
}

.transaction-desc {
    font-size: 13px;
    color: #8e8e93;
}

.transaction-amount {
    font-size: 17px;
    font-weight: 600;
}

.transaction-amount.positive {
    color: var(--ios-green);
}

.transaction-amount.negative {
    color: var(--ios-red);
}

.transaction-amount.neutral {
    color: var(--ios-blue);
}
</style>
