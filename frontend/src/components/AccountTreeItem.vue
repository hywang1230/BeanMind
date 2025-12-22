<template>
  <f7-treeview-item
    :label="displayName"
    :toggle="hasChildren"
    :opened="account.opened"
    @click="onItemClick"
  >
    <template v-if="hasChildren">
      <AccountTreeItem
        v-for="child in account.children"
        :key="child.name"
        :account="child"
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
}>()

const emit = defineEmits<{
  (e: 'select', name: string): void
}>()

const hasChildren = computed(() => props.account.children && props.account.children.length > 0)

const displayName = computed(() => {
  const parts = props.account.name.split(':')
  return parts[parts.length - 1]
})

function onItemClick(e: MouseEvent) {
  // 如果点击的是展开/折叠按钮，不做任何处理（让 Framework7 处理展开/折叠）
  if (e.target && (e.target as HTMLElement).closest('.treeview-toggle')) {
    return
  }
  
  // 只有叶子节点（没有子节点）才能被选中
  if (!hasChildren.value) {
    emit('select', props.account.name)
  }
  // 如果有子节点，点击不触发选择，用户需要点击箭头来展开
}
</script>

