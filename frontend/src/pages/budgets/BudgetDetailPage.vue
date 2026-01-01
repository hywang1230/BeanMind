<template>
    <f7-page name="budget-detail">
        <f7-navbar>
            <f7-nav-left>
                <f7-link @click="goBack">
                    <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
                </f7-link>
            </f7-nav-left>
            <f7-nav-title>{{ budget?.name || '预算详情' }}</f7-nav-title>
            <f7-nav-right>
                <f7-link @click="navigateToEdit">
                    <f7-icon ios="f7:pencil" md="material:edit" />
                </f7-link>
            </f7-nav-right>
        </f7-navbar>

        <!-- 加载状态 -->
        <div v-if="loading" class="loading-container">
            <f7-preloader></f7-preloader>
        </div>

        <!-- 预算内容 -->
        <template v-else-if="budget">
            <!-- 预算概览卡片 -->
            <f7-block class="overview-block">
                <div class="overview-card">
                    <div class="overview-header">
                        <div class="period-info">
                            <span class="period-type">{{ getPeriodTypeText(budget.period_type) }}</span>
                            <span class="period-dates">{{ formatDate(budget.start_date) }} - {{
                                formatDate(budget.end_date || '') }}</span>
                        </div>
                        <f7-chip :color="getStatusColor(budget.status)" outline>
                            {{ getStatusText(budget.status) }}
                        </f7-chip>
                    </div>

                    <div class="overview-main">
                        <div class="overview-amount">
                            <span class="amount-label">总预算</span>
                            <span class="amount-value">¥{{ formatNumber(budget.total_budget) }}</span>
                        </div>
                        <div class="overview-progress-ring">
                            <svg viewBox="0 0 100 100" class="progress-ring">
                                <circle cx="50" cy="50" r="45" fill="none" stroke="var(--progress-bg)"
                                    stroke-width="8" />
                                <circle cx="50" cy="50" r="45" fill="none" :stroke="getProgressColor(budget.status)"
                                    stroke-width="8" stroke-linecap="round" :stroke-dasharray="circumference"
                                    :stroke-dashoffset="progressOffset" transform="rotate(-90 50 50)" />
                            </svg>
                            <div class="progress-center">
                                <span class="progress-percentage">{{ budget.overall_usage_rate.toFixed(0) }}%</span>
                                <span class="progress-label">已使用</span>
                            </div>
                        </div>
                    </div>

                    <div class="overview-stats">
                        <div class="stat-item">
                            <span class="stat-icon spent">↗</span>
                            <div class="stat-content">
                                <span class="stat-value">¥{{ formatNumber(budget.total_spent) }}</span>
                                <span class="stat-label">已支出</span>
                            </div>
                        </div>
                        <div class="stat-item">
                            <span class="stat-icon" :class="budget.total_remaining >= 0 ? 'remaining' : 'exceeded'">
                                {{ budget.total_remaining >= 0 ? '↙' : '!' }}
                            </span>
                            <div class="stat-content">
                                <span class="stat-value">¥{{ formatNumber(Math.abs(budget.total_remaining)) }}</span>
                                <span class="stat-label">{{ budget.total_remaining >= 0 ? '剩余' : '超支' }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </f7-block>

            <!-- 预算项目列表 -->
            <f7-block-title>包含的账户</f7-block-title>
            <f7-list strong-ios dividers-ios inset v-if="budget.items.length > 0">
                <f7-list-item v-for="item in budget.items" :key="item.id" class="budget-item" link="#"
                    @click="navigateToBudgetTransactions(item)">
                    <template #title>
                        <div class="item-title-row">
                            <span class="item-pattern">{{ formatAccountPattern(item.account_pattern) }}</span>
                        </div>
                    </template>
                    <template #after>
                        <div class="item-after-row">
                            <f7-chip color="blue" outline class="item-chip">
                                {{ calculateContribution(item.spent) }}%
                            </f7-chip>
                            <span class="item-spent">¥{{ formatNumber(item.spent) }}</span>
                        </div>
                    </template>
                </f7-list-item>
            </f7-list>

            <div v-else class="empty-items">
                <p>暂无预算项目</p>
            </div>

            <!-- 操作区域 -->
            <f7-block class="actions-block">
                <!-- 循环预算：查看周期按钮 -->
                <f7-button v-if="budget.cycle_type !== 'NONE'" color="blue" fill round @click="navigateToCycles">
                    查看周期 ({{ getCycleTypeText(budget.cycle_type) }})
                </f7-button>

                <f7-button v-if="budget.is_active" color="orange" outline round @click="toggleBudgetStatus">
                    停用预算
                </f7-button>
                <f7-button v-else color="green" outline round @click="toggleBudgetStatus">
                    启用预算
                </f7-button>
                <f7-button color="red" outline round @click="confirmDeleteBudget">
                    删除预算
                </f7-button>
            </f7-block>
        </template>
    </f7-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { budgetsApi, type Budget } from '../../api/budgets'
import { f7 } from 'framework7-vue'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const budget = ref<Budget | null>(null)

// 圆环进度条计算
const circumference = 2 * Math.PI * 45 // r=45
const progressOffset = computed(() => {
    if (!budget.value) return circumference
    const progress = Math.min(budget.value.overall_usage_rate, 100) / 100
    return circumference * (1 - progress)
})

function formatNumber(num: number): string {
    return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(dateStr: string): string {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function getPeriodTypeText(type: string): string {
    const types: Record<string, string> = {
        MONTHLY: '月度预算',
        YEARLY: '年度预算',
        CUSTOM: '自定义周期'
    }
    return types[type] || type
}

function getStatusText(status: string): string {
    const texts: Record<string, string> = {
        normal: '正常',
        warning: '警告',
        exceeded: '超支'
    }
    return texts[status] || status
}

function getStatusColor(status: string): string {
    const colors: Record<string, string> = {
        normal: 'green',
        warning: 'orange',
        exceeded: 'red'
    }
    return colors[status] || 'gray'
}

function getProgressColor(status: string): string {
    const colors: Record<string, string> = {
        normal: 'var(--ios-green)',
        warning: 'var(--ios-orange)',
        exceeded: 'var(--ios-red)'
    }
    return colors[status] || 'var(--ios-blue)'
}

function getCycleTypeText(type: string): string {
    const types: Record<string, string> = {
        NONE: '不循环',
        MONTHLY: '按月',
        YEARLY: '按年'
    }
    return types[type] || type
}

function formatAccountPattern(pattern: string): string {
    // 提取最后一级显示
    const parts = pattern.replace(':*', '').split(':')
    if (parts.length > 2) {
        return parts.slice(1).join(' > ')
    }
    return pattern
}

function calculateContribution(spent: number): string {
    if (!budget.value || budget.value.total_budget === 0) return '0'
    const percentage = (spent / budget.value.total_budget) * 100
    return percentage.toFixed(1)
}

async function loadBudget() {
    const budgetId = route.params.id as string
    if (!budgetId) return

    loading.value = true
    try {
        budget.value = await budgetsApi.getBudget(budgetId)
    } catch (error) {
        console.error('Failed to load budget:', error)
        f7.toast.create({
            text: '加载预算失败',
            position: 'center',
            closeTimeout: 2000
        }).open()
    } finally {
        loading.value = false
    }
}

async function toggleBudgetStatus() {
    if (!budget.value) return

    try {
        budget.value = await budgetsApi.updateBudget(budget.value.id, {
            is_active: !budget.value.is_active
        })

        f7.toast.create({
            text: budget.value.is_active ? '预算已启用' : '预算已停用',
            position: 'center',
            closeTimeout: 2000
        }).open()
    } catch (error) {
        f7.toast.create({
            text: '操作失败',
            position: 'center',
            closeTimeout: 2000
        }).open()
    }
}

function confirmDeleteBudget() {
    f7.dialog.confirm('确定要删除这个预算吗？此操作不可恢复。', '删除确认', async () => {
        if (!budget.value) return
        try {
            await budgetsApi.deleteBudget(budget.value.id)
            f7.toast.create({
                text: '预算已删除',
                position: 'center',
                closeTimeout: 2000
            }).open()
            router.replace('/budgets')
        } catch (error) {
            f7.toast.create({
                text: '删除失败',
                position: 'center',
                closeTimeout: 2000
            }).open()
        }
    })
}

function navigateToEdit() {
    if (budget.value) {
        router.push(`/budgets/${budget.value.id}/edit`)
    }
}

function navigateToCycles() {
    if (budget.value) {
        router.push(`/budgets/${budget.value.id}/cycles`)
    }
}

function navigateToBudgetTransactions(item: any) {
    if (!budget.value) return
    router.push({
        name: 'BudgetTransactions',
        params: {
            budgetId: budget.value.id,
            itemId: item.id
        },
        query: {
            pattern: item.account_pattern
        }
    })
}

function goBack() {
    router.back()
}

onMounted(() => {
    loadBudget()
})
</script>

<style scoped>
/* 加载状态 */
.loading-container {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 60px 0;
}

/* 概览卡片 */
.overview-block {
    margin-top: 0;
    padding-top: 16px;
}

.overview-card {
    background: var(--bg-secondary);
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.overview-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
}

.period-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.period-type {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

.period-dates {
    font-size: 12px;
    color: var(--text-secondary);
}

.overview-main {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
}

.overview-amount {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.amount-label {
    font-size: 14px;
    color: var(--text-secondary);
}

.amount-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--text-primary);
}

.overview-progress-ring {
    position: relative;
    width: 100px;
    height: 100px;
}

.progress-ring {
    width: 100%;
    height: 100%;
    --progress-bg: rgba(120, 120, 128, 0.16);
}

.progress-center {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
}

.progress-percentage {
    display: block;
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
}

.progress-label {
    font-size: 10px;
    color: var(--text-secondary);
}

.overview-stats {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--separator);
}

.stat-item {
    display: flex;
    align-items: center;
    gap: 12px;
}

.stat-icon {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 600;
}

.stat-icon.spent {
    background: rgba(255, 149, 0, 0.12);
    color: var(--ios-orange);
}

.stat-icon.remaining {
    background: rgba(52, 199, 89, 0.12);
    color: var(--ios-green);
}

.stat-icon.exceeded {
    background: rgba(255, 59, 48, 0.12);
    color: var(--ios-red);
}

.stat-content {
    display: flex;
    flex-direction: column;
}

.stat-value {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
}

.stat-label {
    font-size: 12px;
    color: var(--text-secondary);
}

/* 预算项目列表 */
.budget-item {
    --f7-list-item-min-height: auto;
}

.item-title-row {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.item-after-row {
    display: flex;
    align-items: center;
    gap: 8px;
}

.item-pattern {
    font-size: 16px;
    font-weight: 500;
    color: var(--text-primary);
}

.item-chip {
    font-size: 12px;
    height: 20px;
}

.item-spent {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    min-width: 80px;
    text-align: right;
}

/* 空项目状态 */
.empty-items {
    text-align: center;
    padding: 40px 20px;
    color: var(--text-secondary);
}

/* 操作区域 */
.actions-block {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-bottom: 32px;
}

/* 变量 */
:root {
    --text-primary: #1c1c1e;
    --text-secondary: #8e8e93;
    --text-tertiary: #c7c7cc;
    --bg-secondary: #ffffff;
    --separator: rgba(60, 60, 67, 0.12);
    --ios-green: #34c759;
    --ios-orange: #ff9500;
    --ios-red: #ff3b30;
    --ios-blue: #007aff;
}

@media (prefers-color-scheme: dark) {
    :root {
        --text-primary: #ffffff;
        --text-secondary: #98989d;
        --text-tertiary: #48484a;
        --bg-secondary: #1c1c1e;
        --separator: rgba(84, 84, 88, 0.65);
    }
}
</style>
