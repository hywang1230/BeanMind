<template>
  <f7-treeview-item
    :label="displayName"
    :toggle="hasChildren"
    :opened="account.opened"
    @click="onItemClick"
    :class="{ 'selected-item': isSelected }"
  >
    <template #content-start v-if="isMultiSelect && !hasChildren">
      <f7-checkbox
        :checked="isSelected"
        @change="onItemClick"
      />
    </template>
    
    <template v-if="hasChildren">
      <AccountTreeItem
        v-for="child in account.children"
        :key="child.name"
        :account="child"
        :is-multi-select="isMultiSelect"
        :selected-names="selectedNames"
        @select="(name: string) => $emit('select', name)"
      />
    </template>
  </f7-treeview-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'

// 定义树节点类型
interface AccountTreeNode {
  name: string
  account_type: 'Assets' | 'Liabilities' | 'Equity' | 'Income' | 'Expenses'
  currencies: string[]
  children: AccountTreeNode[]
  opened?: boolean
}

const props = defineProps<{
  account: AccountTreeNode
  isMultiSelect?: boolean
  selectedNames?: string[]
}>()

const emit = defineEmits<{
  (e: 'select', name: string): void
}>()

const hasChildren = computed(() => props.account.children && props.account.children.length > 0)

const isSelected = computed(() => {
  return props.selectedNames?.includes(props.account.name) || false
})

const displayName = computed(() => {
  const parts = props.account.name.split(':')
  return parts[parts.length - 1]
})

function onItemClick(e?: Event) {
  // 如果是 Framework7 的 toggle 点击，不触发选择
  if (e && e.target && (e.target as HTMLElement).closest('.treeview-toggle')) {
    return
  }
  
  // 只有叶子节点才能被选中
  if (!hasChildren.value) {
    emit('select', props.account.name)
  }
}
</script>

<style scoped>
.selected-item {
  background-color: var(--f7-theme-color-prev-light, rgba(0, 122, 255, 0.1));
}
</style>

