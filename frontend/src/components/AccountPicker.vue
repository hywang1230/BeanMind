<template>
  <van-field
    :model-value="fieldDisplayValue"
    :label="label"
    :placeholder="placeholderText"
    :error-message="error"
    readonly
    @click="open"
  >
    <template v-if="isMultiDisplay" #input>
      <div class="account-chips">
        <van-tag
          v-for="name in selectedAccounts"
          :key="name"
          closeable
          type="primary"
          @click.stop
          @close.stop="removeSelected(name)"
        >{{ shortName(name) }}</van-tag>
        <span v-if="!(selectedAccounts?.length)" class="chip-placeholder">{{ placeholderText }}</span>
      </div>
    </template>
    <template #right-icon>
      <button v-if="clearable && modelValue && !isMultiDisplay" type="button" class="field-action" :aria-label="`清空${label}`" @click.stop="clear">
        <van-icon name="cross" />
      </button>
      <van-icon v-else name="arrow" />
    </template>
  </van-field>

  <van-popup v-model:show="show" position="bottom" round class="account-picker-popup">
    <div class="account-picker-panel">
      <header class="account-picker-header">
        <button type="button" class="header-action" @click="show = false">取消</button>
        <strong>选择{{ label }}</strong>
        <button type="button" class="header-action" @click="clearSearch">清空搜索</button>
      </header>
      <van-search v-model="search" placeholder="搜索完整账户名、叶子名称或父级路径" />
      <div v-if="frequentAccounts.length && !search.trim()" class="frequent-section">
        <div class="frequent-title">最近常用</div>
        <button
          v-for="item in frequentAccounts"
          :key="item.name"
          type="button"
          class="frequent-item"
          @click="select(item.name)"
        >
          <van-icon name="star" class="frequent-icon" />
          <span class="frequent-main">
            <span class="frequent-label">{{ shortName(item.name) }}</span>
            <span class="frequent-path">{{ item.name }}</span>
          </span>
        </button>
      </div>
      <van-empty v-if="!treeNodes.length" description="暂无账户" />
      <van-empty v-else-if="!visibleNodes.length" description="没有匹配的账户" />
      <div v-else class="account-tree" role="tree">
        <button
          v-for="node in visibleNodes"
          :key="node.name"
          type="button"
          class="account-tree-row"
          :class="{ selected: isRowSelected(node.name), disabled: !node.selectable }"
          :style="{ paddingLeft: `${12 + node.level * 18}px` }"
          role="treeitem"
          :aria-selected="isRowSelected(node.name)"
          :aria-disabled="!node.selectable"
          @click="handleRowClick(node)"
        >
          <span
            v-if="node.hasChildren && !search.trim()"
            class="account-tree-toggle"
            :aria-label="isExpanded(node.name) ? `收起${node.name}` : `展开${node.name}`"
            @click.stop="toggle(node.name)"
          >
            <van-icon :name="isExpanded(node.name) ? 'arrow-down' : 'arrow'" />
          </span>
          <span v-else class="account-tree-spacer" />
          <span class="account-tree-main">
            <span class="account-tree-label">{{ node.label }}</span>
            <span class="account-tree-path">{{ node.name }}</span>
          </span>
          <van-icon v-if="node.selectable && isRowSelected(node.name)" name="success" class="account-tree-selected" />
        </button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Account } from '../api/accounts'
import { statisticsApi, type FrequentItem } from '../api/statistics'
import { accountShortLabel, filterAccountNodes, flattenAccountTree, visibleAccountNodes, type VisibleAccountNode } from '../utils/accountTree'

const props = withDefaults(defineProps<{
  modelValue: string
  accounts: Account[]
  label?: string
  prefixes?: string[]
  error?: string
  clearable?: boolean
  /** Prefer active accounts; included closed accounts always kept for edit restore. */
  activeOnly?: boolean
  currency?: string
  asOfDate?: string
  includeAccounts?: string[]
  /** When provided, field shows selected chips and supports multi-add UX. */
  selectedAccounts?: string[]
  placeholder?: string
  /** 记账交易类型；用于加载「最近常用」账户/分类 */
  transactionType?: 'expense' | 'income' | 'transfer'
}>(), {
  label: '账户',
  prefixes: () => [],
  error: '',
  clearable: false,
  activeOnly: false,
  currency: '',
  asOfDate: '',
  includeAccounts: () => [],
  selectedAccounts: undefined,
  placeholder: '请选择账户',
  transactionType: undefined,
})

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'change', value: string): void
  (event: 'remove', value: string): void
}>()

const show = ref(false)
const search = ref('')
const expandedNames = ref<Set<string>>(new Set())
const frequentAccounts = ref<FrequentItem[]>([])

const isMultiDisplay = computed(() => props.selectedAccounts !== undefined)
const placeholderText = computed(() => props.placeholder || '请选择账户')
const fieldDisplayValue = computed(() => {
  if (isMultiDisplay.value) return ''
  if (!props.modelValue) return ''
  // 与多选 chips / 记账页一致：展示短名，值仍为完整账户路径
  return shortName(props.modelValue)
})

const selectableAccountNames = computed(() => flatNodes.value.filter((node) => node.selectable).map((node) => node.name))

function shortName(name: string) {
  return accountShortLabel(name, selectableAccountNames.value)
}

function isRowSelected(name: string) {
  if (isMultiDisplay.value) return (props.selectedAccounts || []).includes(name)
  return name === props.modelValue
}

function dateOnly(value?: string | null): string {
  if (!value) return ''
  return value.slice(0, 10)
}

function isAccountAllowed(account: Account): boolean {
  const included = props.includeAccounts.includes(account.name)
  if (props.activeOnly && account.is_active === false && !included) return false

  if (props.currency && account.currencies?.length) {
    if (!account.currencies.includes(props.currency) && !included) return false
  }

  if (props.asOfDate) {
    const open = dateOnly(account.open_date)
    const close = dateOnly(account.close_date)
    if (open && open > props.asOfDate && !included) return false
    if (close && close <= props.asOfDate && !included) return false
  }
  return true
}

const filteredAccounts = computed(() => {
  const walk = (items: Account[]): Account[] =>
    items
      .map((item) => ({
        ...item,
        children: item.children ? walk(item.children) : undefined,
      }))
      .filter((item) => {
        const childOk = (item.children || []).length > 0
        return isAccountAllowed(item) || childOk
      })
  return walk(props.accounts)
})

const treeNodes = computed(() => filterAccountNodes(filteredAccounts.value, props.prefixes))
const flatNodes = computed(() => flattenAccountTree(treeNodes.value))
const visibleNodes = computed(() => visibleAccountNodes(treeNodes.value, expandedNames.value, search.value))

function open() {
  expandSelectedPath()
  show.value = true
}

function handleRowClick(node: VisibleAccountNode) {
  if (node.selectable) {
    select(node.name)
    return
  }
  if (node.hasChildren && !search.value.trim()) toggle(node.name)
}

function select(value: string) {
  emit('update:modelValue', value)
  emit('change', value)
  show.value = false
}

function removeSelected(name: string) {
  emit('remove', name)
}

function clear() {
  emit('update:modelValue', '')
  emit('change', '')
  show.value = false
}

function clearSearch() {
  search.value = ''
}

function toggle(name: string) {
  const next = new Set(expandedNames.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  expandedNames.value = next
}

function isExpanded(name: string) {
  return expandedNames.value.has(name)
}

function expandSelectedPath() {
  const target = props.modelValue || (props.selectedAccounts || [])[0] || ''
  if (!target) return
  const next = new Set(expandedNames.value)
  const parts = target.split(':')
  for (let i = 1; i < parts.length; i += 1) {
    next.add(parts.slice(0, i).join(':'))
  }
  expandedNames.value = next
}

watch(
  () => props.accounts,
  () => {
    if (!expandedNames.value.size && treeNodes.value.length) {
      expandedNames.value = new Set(treeNodes.value.map((n) => n.name))
    }
  },
  { immediate: true },
)

function matchesPrefixes(name: string): boolean {
  const prefixes = props.prefixes || []
  if (!prefixes.length) return true
  return prefixes.some((prefix) => name === prefix || name.startsWith(`${prefix}:`) || name.startsWith(prefix))
}

function resolveFrequentType(): 'expense' | 'income' | 'transfer' | 'account' {
  if (props.transactionType === 'expense') {
    return props.prefixes.some((prefix) => prefix === 'Expenses' || prefix.startsWith('Expenses'))
      ? 'expense'
      : 'account'
  }
  if (props.transactionType === 'income') {
    return props.prefixes.some((prefix) => prefix === 'Income' || prefix.startsWith('Income'))
      ? 'income'
      : 'account'
  }
  return 'account'
}

async function loadFrequentAccounts() {
  if (!props.transactionType) {
    frequentAccounts.value = []
    return
  }

  try {
    const result = await statisticsApi.getFrequentItems({
      type: resolveFrequentType(),
      days: 30,
      limit: 3,
    })
    const selectable = new Set(selectableAccountNames.value)
    frequentAccounts.value = result.filter((item) => {
      if (!matchesPrefixes(item.name)) return false
      // 仅展示当前可选账户范围内的末级账户
      if (selectable.size > 0 && !selectable.has(item.name)) return false
      return true
    })
  } catch {
    frequentAccounts.value = []
  }
}

watch(show, async (opened) => {
  if (opened) await loadFrequentAccounts()
})
</script>

<style scoped>
.account-picker-popup { height: 70vh; }
.account-picker-panel { display: flex; flex-direction: column; height: 100%; }
.account-picker-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--van-border-color);
}
.header-action { border: 0; background: transparent; color: var(--van-primary-color); font-size: 14px; }
.account-tree { overflow: auto; flex: 1; padding-bottom: 16px; }
.account-tree-row {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 10px 16px 10px 12px; border: 0; background: transparent; text-align: left;
}
.account-tree-row.selected { background: var(--van-primary-color-light, rgba(25, 137, 250, 0.08)); }
.account-tree-row.disabled { opacity: 0.55; }
.account-tree-toggle, .account-tree-spacer { width: 22px; display: inline-flex; justify-content: center; }
.account-tree-main { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.account-tree-label { font-weight: 600; }
.account-tree-path { color: var(--bm-muted, #888); font-size: 12px; overflow: hidden; text-overflow: ellipsis; }
.account-tree-selected { color: var(--van-primary-color); }
.field-action { border: 0; background: transparent; padding: 0; display: inline-flex; }
.account-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  width: 100%;
  justify-content: flex-end;
}
.chip-placeholder {
  color: var(--bm-muted, #888);
  font-size: 13px;
  line-height: 1.4;
}
.frequent-section {
  padding: 4px 12px 8px;
  border-bottom: 1px solid var(--van-border-color, #ebedf0);
}
.frequent-title {
  padding: 6px 4px 8px;
  font-size: 12px;
  color: var(--bm-muted, #888);
}
.frequent-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 8px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  text-align: left;
  color: inherit;
}
.frequent-item:active {
  background: var(--van-active-color, rgba(0, 0, 0, 0.05));
}
.frequent-icon {
  color: var(--van-warning-color, #ff976a);
  flex-shrink: 0;
}
.frequent-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.frequent-label {
  font-weight: 600;
}
.frequent-path {
  color: var(--bm-muted, #888);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
