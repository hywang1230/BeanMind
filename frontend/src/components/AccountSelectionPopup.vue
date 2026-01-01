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
          <f7-link v-else @click="confirmMultiSelect" bold
            :class="{ 'disabled': selectedNames.length === 0 }">确定</f7-link>
        </f7-nav-right>
      </f7-navbar>

      <f7-searchbar placeholder="搜索账户" v-model:value="searchQuery" :disable-button="false"
        @searchbar:clear="searchQuery = ''"></f7-searchbar>

      <!-- 常用账户区域 -->
      <f7-block v-if="frequentAccounts.length > 0 && !searchQuery" class="frequent-section">
        <div class="frequent-title">最近常用</div>
        <f7-list>
          <f7-list-item
            v-for="account in frequentAccounts"
            :key="account.name"
            link="#"
            @click="onAccountSelect(account.name)"
          >
            <template #title>
              <span class="frequent-account-name">{{ formatFrequentAccountName(account.name) }}</span>
            </template>
            <template #media>
              <f7-icon f7="star_fill" class="frequent-icon"></f7-icon>
            </template>
          </f7-list-item>
        </f7-list>
      </f7-block>

      <f7-list class="account-tree-list">
        <f7-treeview v-if="filteredAccounts.length > 0">
          <account-tree-item v-for="account in filteredAccounts" :key="account.name" :account="account"
            :is-multi-select="isMultiSelect" :selected-names="selectedNames" @select="onAccountSelect" />
        </f7-treeview>
        <f7-list-item v-else title="未找到账户"></f7-list-item>
      </f7-list>

    </f7-page>
  </f7-popup>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { accountsApi, type Account } from '../api/accounts'
import { statisticsApi, type FrequentItem } from '../api/statistics'
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
  transactionType?: 'expense' | 'income' | 'transfer' // 交易类型，用于获取常用账户
}>(), {
  allowMultiSelect: true,
  transactionType: undefined
})

const emit = defineEmits<{
  (e: 'update:opened', value: boolean): void
  (e: 'select', accountNames: string[]): void
}>()

const searchQuery = ref('')
const isMultiSelect = ref(false)
const selectedNames = ref<string[]>([])
const accounts = ref<Account[]>([])
const frequentAccounts = ref<FrequentItem[]>([])

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

async function loadFrequentAccounts() {
  // 如果没有指定交易类型，不加载常用账户
  if (!props.transactionType) {
    frequentAccounts.value = []
    return
  }

  try {
    let type: 'expense' | 'income' | 'transfer' | 'account' = 'account'

    // 根据交易类型和账户类型确定要获取的常用账户类型
    if (props.transactionType === 'expense') {
      // 支出：如果选择分类，显示Expenses的常用项
      type = props.rootTypes?.includes('Expenses') ? 'expense' : 'account'
    } else if (props.transactionType === 'income') {
      // 收入：如果选择分类，显示Income的常用项
      type = props.rootTypes?.includes('Income') ? 'income' : 'account'
    } else if (props.transactionType === 'transfer') {
      // 转账：显示账户的常用项
      type = 'account'
    }

    const result = await statisticsApi.getFrequentItems({
      type,
      days: 30,
      limit: 3
    })

    // 过滤出符合当前rootTypes的常用账户
    const types = (props.rootTypes && props.rootTypes.length > 0)
      ? props.rootTypes
      : defaultRootTypes

    frequentAccounts.value = result.filter(item => {
      return types.some(rootType => item.name.startsWith(rootType))
    })
  } catch (e) {
    console.error('Failed to load frequent accounts', e)
    frequentAccounts.value = []
  }
}

function formatAccountName(name: string): string {
  const parts = name.split(':')
  return parts[parts.length - 1] || name
}

// 格式化常用账户名称：显示完整路径，但突出显示末级
function formatFrequentAccountName(name: string): string {
  const parts = name.split(':')
  if (parts.length <= 2) {
    // 如果只有两级，直接返回完整路径
    return name
  }
  // 三级及以上，显示完整路径，让用户能看到上下文
  // 例如：Expenses:Food:Restaurant
  return name
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

// 监听popup打开状态，加载常用账户
watch(() => props.opened, async (newVal) => {
  if (newVal) {
    await loadFrequentAccounts()
  }
})

onMounted(() => {
  loadAccounts()
})
</script>

<style scoped>
/* 确保 Popup 内部元素使用正确的背景色和文字颜色 */
:deep(.page) {
  background-color: var(--bg-primary);
}

:deep(.navbar-inner),
:deep(.navbar-bg) {
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

:deep(.subnavbar) {
  background-color: var(--bg-primary);
}

:deep(.searchbar) {
  background-color: var(--bg-primary);
}

:deep(.searchbar input) {
  background-color: var(--bg-secondary);
  color: var(--text-primary);
}

:deep(.list) {
  background-color: var(--bg-primary);
}

:deep(.item-content) {
  background-color: transparent;
  color: var(--text-primary);
}

/* 针对树形控件的样式覆盖 */
:deep(.treeview-item-content) {
  color: var(--text-primary);
  /* 移除背景色，避免嵌套导致的多重底纹 */
  background-color: transparent;
}

:deep(.treeview-item-label) {
  color: var(--text-primary);
}

:deep(.treeview-toggle) {
  color: var(--text-secondary);
}

/* 选中状态（如果需要高亮）可以在这里处理，但目前 AccountTreeItem 已经处理了 selected-item 类 */

/* 常用账户区域样式 */
.frequent-section {
  padding: 0;
  margin: 0;
}

.frequent-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 8px 16px;
  background: var(--bg-primary);
}

.frequent-icon {
  color: #ff9500;
  font-size: 20px;
}

.frequent-account-name {
  font-size: 15px;
  color: var(--text-primary);
  word-break: break-all;
}

.frequent-section :deep(.list) {
  margin: 0;
  background: var(--bg-primary);
}

.frequent-section :deep(.item-content) {
  background: transparent;
}

.frequent-section :deep(.item-title) {
  font-size: 15px;
}
</style>
