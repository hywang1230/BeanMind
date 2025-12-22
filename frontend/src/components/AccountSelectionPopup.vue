<template>
  <f7-popup :opened="opened" @popup:closed="$emit('update:opened', false)">
    <f7-page>
      <f7-navbar :title="title">
        <f7-nav-right>
          <f7-link popup-close>关闭</f7-link>
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
            @select="selectAccount"
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

const searchQuery = ref('')

const props = defineProps<{
  opened: boolean
  title: string
  rootTypes?: string[] // e.g. ['Expenses', 'Income']
}>()

const emit = defineEmits<{
  (e: 'update:opened', value: boolean): void
  (e: 'select', accountName: string): void
}>()

const accounts = ref<Account[]>([])

// 默认筛选 Assets 和 Liabilities
const defaultRootTypes = ['Assets', 'Liabilities']

/**
 * 更简洁的树构建方法
 */
function buildTree(flatAccounts: Account[]): AccountTreeNode[] {
  // 创建所有节点的 Map
  const nodeMap = new Map<string, AccountTreeNode>()
  
  // 首先，为每个账户创建节点，同时创建所有中间节点
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
  
  // 建立父子关系
  const roots: AccountTreeNode[] = []
  
  for (const [path, node] of nodeMap) {
    const parts = path.split(':')
    if (parts.length === 1) {
      // 这是根节点
      roots.push(node)
    } else {
      // 找到父节点并添加
      const parentPath = parts.slice(0, -1).join(':')
      const parent = nodeMap.get(parentPath)
      if (parent) {
        // 检查是否已添加
        if (!parent.children.some(c => c.name === node.name)) {
          parent.children.push(node)
        }
      }
    }
  }
  
  return roots
}

const filteredAccounts = computed(() => {
  // 使用传入的 rootTypes，如果没有则默认只显示 Assets 和 Liabilities
  const types = (props.rootTypes && props.rootTypes.length > 0) 
    ? props.rootTypes 
    : defaultRootTypes
  
  // 先筛选符合类型的账户
  const filtered = accounts.value.filter(acc => types.includes(acc.account_type))
  
  // 构建树形结构
  const tree = buildTree(filtered)
  
  // 从第二层开始展示：将所有根节点的 children 合并返回
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
          opened: hasMatchingChildren // 如果子节点有匹配，则展开父节点
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
    console.log('Loaded accounts response:', res)
    if (Array.isArray(res)) {
      accounts.value = res
    } else if (res && Array.isArray(res.accounts)) {
      // Backend returns { accounts: [...], total: ... }
      accounts.value = res.accounts
    } else if (res && Array.isArray(res.data)) {
      accounts.value = res.data
    } else {
      console.warn('Accounts API returned non-array:', res)
      accounts.value = []
    }
  } catch (e) {
    console.error('Failed to load accounts', e)
    accounts.value = []
  }
}

function selectAccount(name: string) {
  emit('select', name)
  emit('update:opened', false)
}

onMounted(() => {
  loadAccounts()
})
</script>
