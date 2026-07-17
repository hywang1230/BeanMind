<template>
  <van-field
    :model-value="displayValue"
    :label="label"
    placeholder="请选择账户"
    :error-message="error"
    readonly
    @click="open"
  >
    <template #right-icon>
      <button v-if="clearable && modelValue" type="button" class="field-action" :aria-label="`清空${label}`" @click.stop="clear">
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
      <van-empty v-if="!treeNodes.length" description="暂无账户" />
      <van-empty v-else-if="!visibleNodes.length" description="没有匹配的账户" />
      <div v-else class="account-tree" role="tree">
        <button
          v-for="node in visibleNodes"
          :key="node.name"
          type="button"
          class="account-tree-row"
          :class="{ selected: node.name === modelValue, disabled: !node.selectable }"
          :style="{ paddingLeft: `${12 + node.level * 18}px` }"
          role="treeitem"
          :aria-selected="node.name === modelValue"
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
          <van-icon v-if="node.selectable && node.name === modelValue" name="success" class="account-tree-selected" />
        </button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Account } from '../api/accounts'
import { filterAccountNodes, flattenAccountTree, visibleAccountNodes, type VisibleAccountNode } from '../utils/accountTree'

const props = withDefaults(defineProps<{
  modelValue: string
  accounts: Account[]
  label?: string
  prefixes?: string[]
  error?: string
  clearable?: boolean
}>(), { label: '账户', prefixes: () => [], error: '', clearable: false })
const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'change', value: string): void
}>()

const show = ref(false)
const search = ref('')
const expandedNames = ref<Set<string>>(new Set())

const treeNodes = computed(() => filterAccountNodes(props.accounts, props.prefixes))
const flatNodes = computed(() => flattenAccountTree(treeNodes.value))
const visibleNodes = computed(() => visibleAccountNodes(treeNodes.value, expandedNames.value, search.value))
const displayValue = computed(() => flatNodes.value.find((node) => node.name === props.modelValue)?.name || props.modelValue)

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

function isExpanded(name: string): boolean {
  return expandedNames.value.has(name)
}

function expandSelectedPath() {
  const selected = props.modelValue
  if (!selected) return
  const next = new Set(expandedNames.value)
  const parts = selected.split(':')
  for (let index = 1; index < parts.length; index += 1) {
    next.add(parts.slice(0, index).join(':'))
  }
  expandedNames.value = next
}

watch(() => props.prefixes, () => {
  expandedNames.value = new Set()
  search.value = ''
})
</script>

<style scoped>
.field-action { display: inline-grid; padding: 4px; place-items: center; border: 0; background: transparent; color: var(--bm-muted); font-size: 16px; }
.account-picker-popup { max-height: 82vh; }
.account-picker-panel { max-height: 82vh; display: flex; flex-direction: column; overflow: hidden; background: var(--bm-surface, var(--van-background-2, #fff)); color: var(--bm-text, #1f2937); }
.account-picker-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--bm-border, #e8e9eb); background: var(--bm-surface, var(--van-background-2, #fff)); }
.header-action { border: 0; background: transparent; color: var(--bm-primary, #0f766e); font-size: 14px; }
.account-tree { flex: 1; overflow-y: auto; padding: 4px 0 16px; background: var(--bm-surface, var(--van-background-2, #fff)); }
.account-tree-row { display: flex; width: 100%; min-height: 48px; align-items: center; gap: 8px; border: 0; border-bottom: 1px solid var(--bm-border, #e8e9eb); background: var(--bm-surface, var(--van-background-2, #fff)); padding-top: 6px; padding-right: 12px; padding-bottom: 6px; color: var(--bm-text, #1f2937); text-align: left; }
.account-tree-row.selected { background: var(--bm-primary-soft, rgba(15, 118, 110, 0.08)); }
.account-tree-row:active { background: var(--bm-primary-soft, rgba(15, 118, 110, 0.08)); }
.account-tree-toggle, .account-tree-spacer { width: 20px; flex: 0 0 20px; color: var(--bm-muted, #6b7280); }
.account-tree-main { min-width: 0; flex: 1; display: grid; gap: 2px; }
.account-tree-label { color: var(--bm-text, #1f2937); font-weight: 600; line-height: 20px; }
.account-tree-path { overflow: hidden; color: var(--bm-muted, #6b7280); font-size: 12px; line-height: 18px; text-overflow: ellipsis; white-space: nowrap; }
.account-tree-selected { color: var(--bm-primary, #0f766e); }
</style>
