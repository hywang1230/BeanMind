<template>
    <f7-page name="budget-cycles">
        <f7-navbar>
            <f7-nav-left>
                <f7-link icon-ios="f7:chevron_left" icon-md="material:arrow_back" @click="goBack"></f7-link>
            </f7-nav-left>
            <f7-nav-title>预算周期</f7-nav-title>
            <f7-nav-right>
                <f7-link icon-ios="f7:arrow_clockwise" icon-md="material:refresh" @click="refreshCycles" />
            </f7-nav-right>
        </f7-navbar>

        <f7-page-content>
            <div class="ptr-content" @ptr:refresh="onPtrRefresh">
                <div class="ptr-preloader">
                    <f7-preloader />
                </div>

                <f7-block v-if="loading && !cycles.length" class="text-align-center padding-vertical">
                    <f7-preloader />
                    <p>加载中...</p>
                </f7-block>

                <template v-if="!loading && summary?.is_cyclic && summary.current_cycle">
                    <f7-block class="stats-summary-block">
                        <div class="stats-summary-grid">
                            <div class="stat-summary-item">
                                <div class="stat-summary-value">{{ summary.total_cycles }}</div>
                                <div class="stat-summary-label">总周期</div>
                            </div>
                            <div class="stat-summary-item">
                                <div class="stat-summary-value">{{ summary.completed_cycles }}</div>
                                <div class="stat-summary-label">已完成</div>
                            </div>
                            <div class="stat-summary-item">
                                <div class="stat-summary-value">¥{{ formatMoney(summary.total_amount) }}</div>
                                <div class="stat-summary-label">总预算</div>
                            </div>
                            <div class="stat-summary-item">
                                <div class="stat-summary-value">¥{{ formatMoney(summary.total_spent) }}</div>
                                <div class="stat-summary-label">已花费</div>
                            </div>
                        </div>
                    </f7-block>

                    <f7-block-title class="block-title-custom">所有周期 ({{ cycles.length }})</f7-block-title>
                    <f7-list media-list class="cycles-list">
                        <f7-list-item v-for="cycle in cycles" :key="cycle.id" :title="`第 ${cycle.period_number} 期`"
                            :subtitle="`${formatDate(cycle.period_start)} - ${formatDate(cycle.period_end)}`"
                            :class="{ 'list-item-current': isCurrentCycle(cycle), 'list-item-completed': isCycleCompleted(cycle) }"
                            class="cycle-list-item">
                            <template #after>
                                <f7-chip :text="getStatusText(cycle.status)" :color="getStatusColor(cycle.status)" />
                            </template>
                            <div slot="footer" class="cycle-footer">
                                <div class="display-flex justify-content-space-between margin-bottom-half">
                                    <span class="footer-label">预算:</span>
                                    <span class="footer-value">¥{{ formatMoney(cycle.total_amount) }}</span>
                                </div>
                                <div class="display-flex justify-content-space-between margin-bottom-half">
                                    <span class="footer-label">已用:</span>
                                    <span class="footer-value text-color-pink">¥{{ formatMoney(cycle.spent_amount, true)
                                    }}</span>
                                </div>
                                <div class="display-flex justify-content-space-between margin-bottom-half">
                                    <span class="footer-label">剩余:</span>
                                    <span class="footer-value"
                                        :class="{ 'text-color-red': cycle.remaining_amount < 0 }">
                                        ¥{{ formatMoney(cycle.remaining_amount) }}
                                    </span>
                                </div>
                                <f7-progressbar :progress="Math.min(Math.max(cycle.usage_rate, 0), 100)"
                                    :color="getProgressColor(cycle.usage_rate)" />
                            </div>
                        </f7-list-item>
                    </f7-list>
                </template>

                <f7-block v-else-if="!loading && summary && !summary.is_cyclic" class="text-align-center">
                    <f7-icon ios="f7:calendar_badge_plus" md="material:event_busy" size="64" color="gray" />
                    <p>该预算不是循环预算</p>
                    <p v-if="summary.message" class="text-muted">{{ summary.message }}</p>
                </f7-block>

                <f7-block v-else-if="!loading && !summary" class="text-align-center">
                    <f7-icon ios="f7:exclamationmark_triangle" md="material:error_outline" size="64" color="red" />
                    <p>预算不存在或已被删除</p>
                </f7-block>
            </div>
        </f7-page-content>
    </f7-page>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { budgetsApi, type BudgetCycle, type BudgetCycleSummary, type BudgetStatus } from '../../api/budgets'
import { f7 } from 'framework7-vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const cycles = ref<BudgetCycle[]>([])
const summary = ref<BudgetCycleSummary | null>(null)

const budgetId = computed(() => route.params.id as string)

watch(budgetId, (newId) => {
    if (newId) loadCycles()
}, { immediate: true })

function goBack() {
    router.back()
}

async function loadCycles() {
    if (!budgetId.value) return

    loading.value = true
    try {
        const [cyclesRes, summaryRes] = await Promise.all([
            budgetsApi.getBudgetCycles(budgetId.value),
            budgetsApi.getBudgetCycleSummary(budgetId.value)
        ])

        cycles.value = cyclesRes.cycles
        summary.value = summaryRes
    } catch (err: any) {
        console.error('加载预算周期失败:', err)
        summary.value = {
            budget_id: budgetId.value,
            is_cyclic: false,
            message: '加载失败: ' + (err.message || '未知错误')
        }
        f7.toast.create({
            text: err.message || '加载周期失败',
            position: 'center',
            closeTimeout: 2000
        }).open()
    } finally {
        loading.value = false
    }
}

async function refreshCycles() {
    await loadCycles()
}

async function onPtrRefresh(done: () => void) {
    await loadCycles()
    done()
}

const statusTextMap: Record<BudgetStatus, string> = {
    normal: '正常',
    warning: '警告',
    exceeded: '超支'
}

const statusColorMap: Record<BudgetStatus, string> = {
    normal: 'green',
    warning: 'orange',
    exceeded: 'red'
}

function getStatusText(status: BudgetStatus): string {
    return statusTextMap[status] || '未知'
}

function getStatusColor(status: BudgetStatus): string {
    return statusColorMap[status] || 'gray'
}

function getProgressColor(usageRate: number): string {
    if (usageRate >= 100) return 'red'
    if (usageRate >= 80) return 'orange'
    return 'green'
}

function formatMoney(amount: number | undefined, absolute = false): string {
    if (amount === undefined) return '0.00'
    const value = absolute ? Math.abs(amount) : amount
    return value.toLocaleString('zh-CN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    })
}

function formatDate(dateStr: string): string {
    const date = new Date(dateStr)
    const month = date.getMonth() + 1
    const day = date.getDate()
    return `${month}月${day}日`
}

function isCurrentCycle(cycle: BudgetCycle): boolean {
    if (!summary.value?.current_cycle) return false
    return cycle.period_number === summary.value.current_cycle.period_number
}

function isCycleCompleted(cycle: BudgetCycle): boolean {
    const today = new Date()
    const endDate = new Date(cycle.period_end)
    return endDate < today
}
</script>

<style scoped>
/* 统计汇总 */
.stats-summary-block {
    margin: 0 8px 16px;
}

.stats-summary-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    background: var(--bg-secondary);
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.stat-summary-item {
    text-align: center;
}

.stat-summary-value {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.stat-summary-label {
    font-size: 11px;
    color: var(--text-secondary);
}

/* 周期列表 */
.cycles-list {
    margin: 0;
}

.cycle-list-item :deep(.item-title) {
    color: var(--text-primary);
}

.cycle-list-item :deep(.item-subtitle) {
    color: var(--text-secondary);
}

.list-item-current {
    background: rgba(0, 122, 255, 0.05);
}

.list-item-completed {
    opacity: 0.6;
}

.cycle-footer {
    padding: 6px 0 4px;
}

.footer-label {
    color: var(--text-secondary);
}

.footer-value {
    color: var(--text-primary);
}

.block-title-custom {
    color: var(--text-primary);
}

@media (prefers-color-scheme: dark) {
    .list-item-current {
        background: rgba(0, 122, 255, 0.1);
    }

    .cycle-list-item :deep(.item-title) {
        color: var(--text-primary) !important;
    }

    .cycle-list-item :deep(.item-subtitle) {
        color: var(--text-secondary) !important;
    }

    .cycle-list-item :deep(.item-inner) {
        background-color: transparent;
    }

    .footer-label {
        color: var(--text-secondary) !important;
    }

    .footer-value {
        color: var(--text-primary) !important;
    }

    .block-title-custom {
        color: var(--text-primary) !important;
    }
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
