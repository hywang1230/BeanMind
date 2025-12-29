<template>
  <div class="income-expense-tree-item">
    <!-- 项目行 -->
    <div class="item-row" :class="{ 'has-children': item.children && item.children.length > 0, expanded }"
      :style="{ paddingLeft: `${16 + item.depth * 16}px` }" @click="handleClick">
      <!-- 展开/折叠图标 -->
      <span v-if="item.children && item.children.length > 0" class="expand-icon" @click.stop="toggleExpand">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="16" height="16"
          :class="{ rotated: expanded }">
          <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
        </svg>
      </span>
      <span v-else class="expand-placeholder"></span>

      <!-- 项目名称 -->
      <div class="item-info">
        <span class="item-name">{{ shortName }}</span>
        <!-- 占比标签 -->
        <span v-if="item.percentage > 0" class="percentage-badge" :class="type">
          {{ item.percentage.toFixed(1) }}%
        </span>
      </div>

      <!-- 金额 -->
      <div class="item-amount">
        <span class="amount-cny" :class="type">
          {{ type === 'income' ? '+' : '-' }}{{ formatCurrency(item.total_cny) }}
        </span>
        <!-- 如果有非 CNY 货币，显示原币种金额 -->
        <div v-if="hasNonCnyAmount" class="amount-original">
          <span v-for="(amount, currency) in nonCnyAmounts" :key="currency" class="original-item">
            {{ currency }} {{ formatAmount(amount) }}
          </span>
        </div>
      </div>

      <!-- 箭头占位（保持对齐） -->
      <span class="detail-arrow" :class="{ invisible: item.children && item.children.length > 0 }">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
          <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
        </svg>
      </span>
    </div>

    <!-- 子项目（递归） -->
    <transition name="expand">
      <div v-if="expanded && item.children && item.children.length > 0" class="children">
        <IncomeExpenseTreeItem v-for="child in item.children" :key="child.account" :item="child" :type="type"
          :default-expanded="false" :expanded-accounts="expandedAccounts"
          @click-account="(acc) => emit('click-account', acc)"
          @toggle-expand="(account, exp) => emit('toggle-expand', account, exp)" />
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { IncomeExpenseItem } from '../api/reports'

interface Props {
  item: IncomeExpenseItem
  type?: 'income' | 'expense'
  defaultExpanded?: boolean // 是否默认展开
  expandedAccounts?: Set<string> // 外部控制的展开账户集合
}

const props = withDefaults(defineProps<Props>(), {
  type: 'expense',
  defaultExpanded: false, // 默认收起
  expandedAccounts: undefined
})

const emit = defineEmits<{
  (e: 'click-account', account: IncomeExpenseItem): void
  (e: 'toggle-expand', account: string, expanded: boolean): void
}>()

// 计算是否展开：优先使用外部控制的状态
const expanded = ref(
  props.expandedAccounts
    ? props.expandedAccounts.has(props.item.account)
    : props.defaultExpanded
)

// 监听外部展开状态的变化
watch(() => props.expandedAccounts, (newSet) => {
  if (newSet) {
    expanded.value = newSet.has(props.item.account)
  }
}, { deep: true })

// 显示短名称（只显示当前层级的名称）
const shortName = computed(() => {
  const parts = props.item.display_name.split(':')
  return parts[parts.length - 1] || props.item.display_name
})

const hasNonCnyAmount = computed(() => {
  const currencies = Object.keys(props.item.amounts)
  return currencies.some(c => c !== 'CNY')
})

const nonCnyAmounts = computed(() => {
  const result: Record<string, number> = {}
  for (const [currency, amount] of Object.entries(props.item.amounts)) {
    if (currency !== 'CNY') {
      result[currency] = amount
    }
  }
  return result
})

function formatCurrency(amount: number): string {
  return `¥${Math.abs(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatAmount(amount: number): string {
  return amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function toggleExpand() {
  expanded.value = !expanded.value
  // 通知父组件展开状态变化
  emit('toggle-expand', props.item.account, expanded.value)
}

function handleClick() {
  // 非叶子节点只展开/折叠，不进入详情页
  if (props.item.children && props.item.children.length > 0) {
    toggleExpand()
    return
  }
  emit('click-account', props.item)
}
</script>

<style scoped>
.income-expense-tree-item {
  border-bottom: 0.5px solid var(--separator);
}

.income-expense-tree-item:last-child {
  border-bottom: none;
}

.item-row {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  padding-right: 12px;
  cursor: pointer;
  transition: background-color 0.15s;
  min-height: 48px;
  background-color: var(--bg-secondary);
}

.item-row:active {
  background-color: var(--bg-tertiary);
}

.expand-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  color: #8e8e93;
  flex-shrink: 0;
  margin-right: 4px;
}

.expand-icon svg {
  transition: transform 0.2s;
}

.expand-icon svg.rotated {
  transform: rotate(90deg);
}

.expand-placeholder {
  width: 24px;
  flex-shrink: 0;
  margin-right: 4px;
}

.item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.item-name {
  font-size: 15px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.percentage-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.percentage-badge.income {
  background: rgba(52, 199, 89, 0.15);
  color: var(--ios-green);
}

.percentage-badge.expense {
  background: rgba(255, 59, 48, 0.15);
  color: var(--ios-red);
}

.item-amount {
  text-align: right;
  margin-left: 12px;
  flex-shrink: 0;
  min-width: 110px;
}

.amount-cny {
  font-size: 15px;
  font-weight: 500;
}

.amount-cny.income {
  color: var(--ios-green);
}

.amount-cny.expense {
  color: var(--ios-red);
}

.amount-original {
  margin-top: 2px;
}

.original-item {
  font-size: 11px;
  color: #8e8e93;
  display: block;
}

.detail-arrow {
  color: #c6c6c8;
  margin-left: 8px;
  flex-shrink: 0;
  width: 16px;
}

.detail-arrow.invisible {
  visibility: hidden;
}

/* 子项目展开动画 */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 1000px;
}

.children {
  background: var(--bg-tertiary);
}

.children .item-row {
  background: transparent;
}

.children .item-row:active {
  background: var(--bg-primary);
}

/* 嵌套层级的子项目 */
.children .children {
  background: rgba(0, 0, 0, 0.05);
}

/* 适配暗黑模式的嵌套背景加深 */
:global(.theme-dark) .children .children {
  background: rgba(255, 255, 255, 0.05);
}
</style>
