<template>
  <div class="report-account-tree-item">
    <!-- 账户行 -->
    <div 
      class="account-row" 
      :class="{ 'has-children': item.children && item.children.length > 0, expanded }"
      :style="{ paddingLeft: `${16 + item.depth * 16}px` }"
      @click="handleClick"
    >
      <!-- 展开/折叠图标 -->
      <span 
        v-if="item.children && item.children.length > 0" 
        class="expand-icon"
        @click.stop="toggleExpand"
      >
        <svg 
          xmlns="http://www.w3.org/2000/svg" 
          viewBox="0 0 24 24" 
          fill="currentColor" 
          width="16" 
          height="16"
          :class="{ rotated: expanded }"
        >
          <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"/>
        </svg>
      </span>
      <span v-else class="expand-placeholder"></span>
      
      <!-- 账户名称 -->
      <div class="account-info">
        <span class="account-name">{{ shortName }}</span>
        <!-- 多币种标识 -->
        <span v-if="hasMutipleCurrencies" class="multi-currency-badge">
          {{ Object.keys(item.balances).length }}币种
        </span>
      </div>
      
      <!-- 金额 -->
      <div class="account-amount">
        <span class="amount-cny" :class="amountClass">
          {{ formatCurrency(item.total_cny) }}
        </span>
        <!-- 如果有非 CNY 货币，显示原币种金额 -->
        <div v-if="hasNonCnyBalance" class="amount-original">
          <span v-for="(amount, currency) in nonCnyBalances" :key="currency" class="original-item">
            {{ currency }} {{ formatAmount(amount) }}
          </span>
        </div>
      </div>
      
      <!-- 箭头（仅叶子节点显示） -->
      <span v-if="!item.children || item.children.length === 0" class="detail-arrow">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
          <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"/>
        </svg>
      </span>
    </div>
    
    <!-- 子账户（递归） -->
    <transition name="expand">
      <div v-if="expanded && item.children && item.children.length > 0" class="children">
        <ReportAccountTreeItem
          v-for="child in item.children"
          :key="child.account"
          :item="child"
          :type="type"
          :default-expanded="false"
          :expanded-accounts="expandedAccounts"
          @click-account="(acc) => emit('click-account', acc)"
          @toggle-expand="(account, exp) => emit('toggle-expand', account, exp)"
        />
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { AccountBalanceItem } from '../api/reports'

interface Props {
  item: AccountBalanceItem
  type?: 'asset' | 'liability' | 'equity' | 'income' | 'expense'
  defaultExpanded?: boolean // 是否默认展开
  expandedAccounts?: Set<string> // 外部控制的展开账户集合
}

const props = withDefaults(defineProps<Props>(), {
  type: 'asset',
  defaultExpanded: false, // 默认收起
  expandedAccounts: undefined
})

const emit = defineEmits<{
  (e: 'click-account', account: AccountBalanceItem): void
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

const hasMutipleCurrencies = computed(() => {
  return Object.keys(props.item.balances).length > 1
})

const hasNonCnyBalance = computed(() => {
  const currencies = Object.keys(props.item.balances)
  return currencies.some(c => c !== 'CNY')
})

const nonCnyBalances = computed(() => {
  const result: Record<string, number> = {}
  for (const [currency, amount] of Object.entries(props.item.balances)) {
    if (currency !== 'CNY') {
      result[currency] = amount
    }
  }
  return result
})

const amountClass = computed(() => {
  const amount = props.item.total_cny
  if (props.type === 'asset' || props.type === 'income') {
    return amount >= 0 ? 'positive' : 'negative'
  } else if (props.type === 'liability' || props.type === 'expense') {
    return 'warning'
  }
  return ''
})

function formatCurrency(amount: number): string {
  const prefix = amount < 0 ? '-' : ''
  return `${prefix}¥${Math.abs(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
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
.report-account-tree-item {
  border-bottom: 0.5px solid #e5e5ea;
}

.report-account-tree-item:last-child {
  border-bottom: none;
}

.account-row {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  padding-right: 12px;
  cursor: pointer;
  transition: background-color 0.15s;
  min-height: 48px;
}

.account-row:active {
  background-color: #f8f8f8;
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

.account-info {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.account-name {
  font-size: 15px;
  color: #000;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.multi-currency-badge {
  font-size: 10px;
  padding: 2px 6px;
  background: #007aff;
  color: #fff;
  border-radius: 4px;
  flex-shrink: 0;
}

.account-amount {
  text-align: right;
  margin-left: 12px;
  flex-shrink: 0;
}

.amount-cny {
  font-size: 15px;
  font-weight: 500;
  color: #000;
}

.amount-cny.positive {
  color: #34c759;
}

.amount-cny.negative {
  color: #ff3b30;
}

.amount-cny.warning {
  color: #ff9500;
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
}

/* 子账户展开动画 */
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
  background: #fafafa;
}

.children .account-row {
  background: transparent;
}

.children .account-row:active {
  background: #f0f0f0;
}

/* 嵌套层级的子账户 */
.children .children {
  background: #f5f5f5;
}

/* 暗黑模式 */
@media (prefers-color-scheme: dark) {
  .report-account-tree-item {
    border-bottom-color: #38383a;
  }
  
  .account-row:active {
    background-color: #2c2c2e;
  }
  
  .account-name {
    color: #fff;
  }
  
  .amount-cny {
    color: #fff;
  }
  
  .amount-cny.positive {
    color: #30d158;
  }
  
  .amount-cny.negative {
    color: #ff453a;
  }
  
  .amount-cny.warning {
    color: #ff9f0a;
  }
  
  .detail-arrow {
    color: #48484a;
  }
  
  .children {
    background: #1c1c1e;
  }
  
  .children .account-row:active {
    background: #2c2c2e;
  }
  
  .children .children {
    background: #2c2c2e;
  }
}
</style>

