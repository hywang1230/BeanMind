<template>
  <f7-popup :opened="opened" @popup:closed="onPopupClosed">
    <f7-page>
      <f7-navbar>
        <f7-nav-left>
          <f7-link popup-close>
            <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
            <span></span>
          </f7-link>
        </f7-nav-left>
        <f7-nav-title>{{ title }}</f7-nav-title>
        <f7-nav-right v-if="allowMultiSelect">
          <f7-link v-if="!isMultiSelect" @click="isMultiSelect = true">多选</f7-link>
          <f7-link v-else @click="confirmMultiSelect" bold :class="{ 'disabled': selectedNames.length === 0 }">确定</f7-link>
        </f7-nav-right>
      </f7-navbar>
      
      <f7-searchbar
        placeholder="搜索账户"
        v-model:value="searchQuery"
        :disable-button="false"
        @searchbar:clear="searchQuery = ''"
      ></f7-searchbar>

      <f7-list class="account-tree-list">
        <f7-treeview v-if="filteredAccounts.length > 0">
          <account-tree-item
            v-for="account in filteredAccounts"
            :key="account.name"
            :account="account"
            :is-multi-select="isMultiSelect"
            :selected-names="selectedNames"
            @select="onAccountSelect"
          />
        </f7-treeview>
        <f7-list-item v-else title="未找到账户"></f7-list-item>
      </f7-list>

    </f7-page>
  </f7-popup>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { accountsApi, type Account } from '../api/accounts'
import AccountTreeItem from './AccountTreeItem.vue'

// 定义树节点类型（与 Account 类型兼容）
type AccountType = 'Assets' | 'Liabilities' | 'Equity' | 'Income' | 'Expenses'

interface AccountTreeNode {
  name: string
  account_type: AccountType
  currencies: string[]
  children: AccountTreeNode[]
  opened?: boolean
}

const props = withDefaults(defineProps<{
  opened: boolean
  title: string
  rootTypes?: string[] // e.g. ['Expenses', 'Income']
  allowMultiSelect?: boolean
}>(), {
  allowMultiSelect: true
})

const emit = defineEmits<{
  (e: 'update:opened', value: boolean): void
  (e: 'select', accountNames: string[]): void
}>()

const searchQuery = ref('')
const isMultiSelect = ref(false)
const selectedNames = ref<string[]>([])
const accounts = ref<Account[]>([])

// 默认筛选 Assets 和 Liabilities
const defaultRootTypes = ['Assets', 'Liabilities']

/**
 * 更简洁的树构建方法
 */
function buildTree(flatAccounts: Account[]): AccountTreeNode[] {
  const nodeMap = new Map<string, AccountTreeNode>()
  
  for (const account of flatAccounts) {
    const parts = account.name.split(':')
    let currentPath = ''
    
    parts.forEach((part, i) => {
      currentPath = currentPath ? `${currentPath}:${part}` : part
      
      if (!nodeMap.has(currentPath)) {
        nodeMap.set(currentPath, {
          name: currentPath,
          account_type: account.account_type,
          currencies: i === parts.length - 1 ? (account.currencies || []) : [],
          children: []
        })
      }
    })
  }
  
  const roots: AccountTreeNode[] = []
  
  for (const [path, node] of nodeMap) {
    const parts = path.split(':')
    if (parts.length === 1) {
      roots.push(node)
    } else {
      const parentPath = parts.slice(0, -1).join(':')
      const parent = nodeMap.get(parentPath)
      if (parent) {
        if (!parent.children.some(c => c.name === node.name)) {
          parent.children.push(node)
        }
      }
    }
  }
  
  return roots
}

const filteredAccounts = computed(() => {
  const types = (props.rootTypes && props.rootTypes.length > 0) 
    ? props.rootTypes 
    : defaultRootTypes
  
  const filtered = accounts.value.filter(acc => types.includes(acc.account_type))
  const tree = buildTree(filtered)
  
  const secondLevelNodes: AccountTreeNode[] = []
  for (const root of tree) {
    if (root.children && root.children.length > 0) {
      secondLevelNodes.push(...root.children)
    }
  }
  
  if (!searchQuery.value) {
    return secondLevelNodes
  }
  
  const query = searchQuery.value.toLowerCase()
  
  function filterTree(nodes: AccountTreeNode[]): AccountTreeNode[] {
    const result: AccountTreeNode[] = []
    
    for (const node of nodes) {
      const parts = node.name.split(':')
      const nodeName = parts[parts.length - 1] || ''
      const matchesSelf = nodeName.toLowerCase().includes(query)
      
      const filteredChildren = filterTree(node.children)
      const hasMatchingChildren = filteredChildren.length > 0
      
      if (matchesSelf || hasMatchingChildren) {
        result.push({
          ...node,
          children: hasMatchingChildren ? filteredChildren : node.children,
          opened: hasMatchingChildren
        })
      }
    }
    
    return result
  }
  
  return filterTree(secondLevelNodes)
})

async function loadAccounts() {
  try {
    const res: any = await accountsApi.getAccounts()
    if (Array.isArray(res)) {
      accounts.value = res
    } else if (res && Array.isArray(res.accounts)) {
      accounts.value = res.accounts
    } else if (res && Array.isArray(res.data)) {
      accounts.value = res.data
    } else {
      accounts.value = []
    }
  } catch (e) {
    console.error('Failed to load accounts', e)
    accounts.value = []
  }
}

function onAccountSelect(name: string) {
  if (!isMultiSelect.value) {
    emit('select', [name])
    emit('update:opened', false)
  } else {
    const index = selectedNames.value.indexOf(name)
    if (index > -1) {
      selectedNames.value.splice(index, 1)
    } else {
      selectedNames.value.push(name)
    }
  }
}

function confirmMultiSelect() {
  if (selectedNames.value.length > 0) {
    emit('select', [...selectedNames.value])
    emit('update:opened', false)
  }
}

function onPopupClosed() {
  emit('update:opened', false)
  isMultiSelect.value = false
  selectedNames.value = []
  searchQuery.value = ''
}

onMounted(() => {
  loadAccounts()
})
</script>

