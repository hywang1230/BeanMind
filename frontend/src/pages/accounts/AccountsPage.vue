<template>
  <f7-page name="accounts">
    <f7-navbar>
      <f7-nav-left>
        <f7-link @click="goBack">
          <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
        </f7-link>
      </f7-nav-left>
      <f7-nav-title>账户管理</f7-nav-title>
      <f7-nav-right>
        <f7-link @click="openAIContext">
          <f7-icon ios="f7:sparkles" md="material:auto_awesome" />
        </f7-link>
        <f7-link @click="showCreateModal = true">
          <f7-icon ios="f7:plus" md="material:add" />
        </f7-link>
      </f7-nav-right>
    </f7-navbar>

    <!-- 加载状态 -->
    <div v-if="loading && accountTree.length === 0" class="loading-container">
      <f7-preloader></f7-preloader>
    </div>

    <!-- 空状态 -->
    <div v-else-if="accountTree.length === 0" class="empty-state">
      <div class="empty-icon">💰</div>
      <div class="empty-text">暂无账户</div>
      <f7-button fill round @click="showCreateModal = true">
        创建账户
      </f7-button>
    </div>

    <!-- 账户树 -->
    <div v-else class="accounts-content">
      <template v-for="type in accountTypes" :key="type.value">
        <template v-if="getAccountsByType(type.value).length > 0">
          <f7-block-title>{{ type.label }}</f7-block-title>
          <f7-list strong-ios dividers-ios inset class="account-list">
            <template v-for="account in getAccountsByType(type.value)" :key="account.name">
              <account-tree-item :account="account" :expanded-accounts="expandedAccounts" :depth="0"
                @toggle="toggleExpand" @select="handleAccountSelect" />
            </template>
          </f7-list>
        </template>
      </template>
    </div>

    <!-- 创建账户模态框 -->
    <f7-popup :opened="showCreateModal" @popup:closed="showCreateModal = false">
      <f7-page>
        <f7-navbar>
          <f7-nav-left>
            <f7-link popup-close>
              <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
            </f7-link>
          </f7-nav-left>
          <f7-nav-title>创建账户</f7-nav-title>
          <f7-nav-right>
            <f7-link @click="handleCreateAccount" :style="{ opacity: (!newAccount.name || creatingAccount) ? 0.5 : 1 }">
              {{ creatingAccount ? '保存中' : '保存' }}
            </f7-link>
          </f7-nav-right>
        </f7-navbar>

        <f7-list strong-ios dividers-ios inset>
          <f7-list-input label="账户类型" type="select" :value="newAccount.type"
            @input="newAccount.type = $event.target.value">
            <option v-for="type in accountTypes" :key="type.value" :value="type.value">
              {{ type.label }}
            </option>
          </f7-list-input>

          <f7-list-input label="账户名称" type="text" :placeholder="getAccountPlaceholder()" :value="newAccount.name"
            @input="newAccount.name = $event.target.value" required>
            <template #info>
              <span class="account-prefix">{{ newAccount.type }}:</span>
            </template>
          </f7-list-input>

          <f7-list-input label="支持币种" type="text" placeholder="例如: CNY,USD（逗号分隔）" :value="newAccount.currencies"
            @input="newAccount.currencies = $event.target.value"></f7-list-input>
        </f7-list>

        <f7-block v-if="createError" class="error-block">
          <p>{{ createError }}</p>
        </f7-block>
      </f7-page>
    </f7-popup>
  </f7-page>
</template>

<script setup lang="ts">
import { ref, onMounted, defineComponent, h } from 'vue'
import { useRouter } from 'vue-router'
import { accountsApi, type Account } from '../../api/accounts'
import { f7, f7ListItem, f7Icon } from 'framework7-vue'

const router = useRouter()

const accountTypes = [
  { value: 'Assets', label: '资产' },
  { value: 'Liabilities', label: '负债' },
  { value: 'Income', label: '收入' },
  { value: 'Expenses', label: '支出' },
  { value: 'Equity', label: '权益' }
]

const loading = ref(false)
const accounts = ref<Account[]>([])
const accountTree = ref<AccountNode[]>([])
const expandedAccounts = ref<Set<string>>(new Set())

const showCreateModal = ref(false)
const newAccount = ref({
  name: '',
  type: 'Assets',
  currencies: 'CNY'
})
const creatingAccount = ref(false)
const createError = ref('')

// 账户节点类型（带子账户）
interface AccountNode extends Account {
  children: AccountNode[]
  isLeaf: boolean
}

// 构建账户树
function buildAccountTree(accounts: Account[]): AccountNode[] {
  const accountMap = new Map<string, AccountNode>()
  const rootNodes: AccountNode[] = []

  // 辅助函数:确保节点存在,如果不存在则创建虚拟节点
  function ensureNode(name: string, accountType: string): AccountNode {
    if (!accountMap.has(name)) {
      accountMap.set(name, {
        name,
        account_type: accountType as any,
        currencies: [],
        children: [],
        isLeaf: true
      })
    }
    return accountMap.get(name)!
  }

  // 首先创建所有实际账户节点
  accounts.forEach(acc => {
    const node = ensureNode(acc.name, acc.account_type)
    node.currencies = acc.currencies
  })

  // 为每个账户创建完整的祖先路径
  accounts.forEach(acc => {
    const parts = acc.name.split(':')
    let currentPath = ''

    for (let i = 0; i < parts.length - 1; i++) {
      currentPath = currentPath ? `${currentPath}:${parts[i]!}` : parts[i]!
      ensureNode(currentPath, acc.account_type)
    }
  })

  // 建立父子关系
  accountMap.forEach((node, name) => {
    const parts = name.split(':')
    if (parts.length > 1) {
      const parentName = parts.slice(0, -1).join(':')
      const parent = accountMap.get(parentName)
      if (parent) {
        // 检查是否已经添加过
        if (!parent.children.find(c => c.name === name)) {
          parent.children.push(node)
        }
        parent.isLeaf = false
      }
    }
  })

  // 找出根节点(只有一级的账户)
  accountMap.forEach((node, name) => {
    const parts = name.split(':')
    if (parts.length === 1) {
      rootNodes.push(node)
    }
  })

  // 对子账户排序
  function sortChildren(node: AccountNode) {
    node.children.sort((a, b) => a.name.localeCompare(b.name))
    node.children.forEach(sortChildren)
  }
  rootNodes.forEach(sortChildren)
  rootNodes.sort((a, b) => a.name.localeCompare(b.name))

  return rootNodes
}

function getAccountsByType(type: string): AccountNode[] {
  return accountTree.value.filter(acc => acc.account_type === type)
}

function toggleExpand(accountName: string) {
  if (expandedAccounts.value.has(accountName)) {
    expandedAccounts.value.delete(accountName)
  } else {
    expandedAccounts.value.add(accountName)
  }
  // 保存展开状态到 sessionStorage
  saveExpandedState()
}

function handleAccountSelect(account: AccountNode) {
  if (account.isLeaf) {
    // 保存滚动位置
    saveScrollPosition()
    router.push(`/accounts/${encodeURIComponent(account.name)}`)
  }
}

function saveExpandedState() {
  sessionStorage.setItem('accountsExpandedState', JSON.stringify([...expandedAccounts.value]))
}

function loadExpandedState() {
  const saved = sessionStorage.getItem('accountsExpandedState')
  if (saved) {
    try {
      expandedAccounts.value = new Set(JSON.parse(saved))
    } catch (e) {
      console.error('Failed to load expanded state:', e)
    }
  }
}

function saveScrollPosition() {
  const page = document.querySelector('.page-content')
  if (page) {
    sessionStorage.setItem('accountsScrollPosition', String(page.scrollTop))
  }
}

function restoreScrollPosition() {
  const saved = sessionStorage.getItem('accountsScrollPosition')
  if (saved) {
    setTimeout(() => {
      const page = document.querySelector('.page-content')
      if (page) {
        page.scrollTop = parseInt(saved)
      }
    }, 100)
  }
}

async function loadAccounts() {
  loading.value = true
  try {
    accounts.value = await accountsApi.getAccounts()
    accountTree.value = buildAccountTree(accounts.value)
  } catch (error) {
    console.error('Failed to load accounts:', error)
    f7.toast.create({
      text: '加载账户失败',
      position: 'center',
      closeTimeout: 2000
    }).open()
  } finally {
    loading.value = false
  }
}

function getAccountPlaceholder(): string {
  const placeholders: Record<string, string> = {
    'Assets': '例如: Bank:ICBC 或 现金:钱包',
    'Liabilities': '例如: 信用卡:工行 或 借款:朋友',
    'Income': '例如: 工资 或 兼职:咨询',
    'Expenses': '例如: 餐饮 或 出行:公交',
    'Equity': '例如: 期初余额'
  }
  return placeholders[newAccount.value.type] || '例如: 子账户:详细分类'
}

async function handleCreateAccount() {
  if (!newAccount.value.name || !newAccount.value.type) {
    createError.value = '请填写所有必填字段'
    return
  }

  creatingAccount.value = true
  createError.value = ''

  try {
    const currencies = newAccount.value.currencies
      .split(',')
      .map(c => c.trim())
      .filter(c => c)

    // 将账户类型拼接到用户输入的账户名之前
    const fullAccountName = `${newAccount.value.type}:${newAccount.value.name}`

    await accountsApi.createAccount({
      name: fullAccountName,
      account_type: newAccount.value.type,
      currencies: currencies.length > 0 ? currencies : undefined
    })

    await loadAccounts()

    f7.toast.create({
      text: '账户创建成功',
      position: 'center',
      closeTimeout: 2000
    }).open()

    showCreateModal.value = false
    newAccount.value = {
      name: '',
      type: 'Assets',
      currencies: 'CNY'
    }
  } catch (err: any) {
    createError.value = err.message || '创建失败，请重试'
  } finally {
    creatingAccount.value = false
  }
}

function goBack() {
  router.back()
}

function openAIContext() {
  router.push({
    path: '/ai',
    query: {
      prompt: '解释一下当前账户结构，并给出账户分类或整理建议',
      source_page: '/accounts',
    }
  })
}

// 账户树项组件
const AccountTreeItem = defineComponent({
  name: 'AccountTreeItem',
  props: {
    account: { type: Object as () => AccountNode, required: true },
    expandedAccounts: { type: Object as () => Set<string>, required: true },
    depth: { type: Number, default: 0 }
  },
  emits: ['toggle', 'select'],
  setup(props, { emit }) {
    const isExpanded = () => props.expandedAccounts.has(props.account.name)
    const hasChildren = () => props.account.children && props.account.children.length > 0

    const getShortName = (fullName: string) => {
      const parts = fullName.split(':')
      return parts[parts.length - 1]
    }

    const getIconClass = () => {
      const type = props.account.account_type
      if (type === 'Assets') return 'assets-icon'
      if (type === 'Liabilities') return 'liabilities-icon'
      if (type === 'Income') return 'income-icon'
      if (type === 'Expenses') return 'expenses-icon'
      if (type === 'Equity') return 'equity-icon'
      return ''
    }

    const getAccountIcon = () => {
      if (hasChildren()) {
        return isExpanded() ? 'f7:folder_open' : 'f7:folder_fill'
      }
      const type = props.account.account_type
      if (type === 'Assets') return 'f7:creditcard_fill'
      if (type === 'Liabilities') return 'f7:doc_text_fill'
      if (type === 'Income') return 'f7:arrow_down_circle_fill'
      if (type === 'Expenses') return 'f7:arrow_up_circle_fill'
      if (type === 'Equity') return 'f7:chart_pie_fill'
      return 'f7:doc_fill'
    }

    const handleClick = (e: Event) => {
      e.stopPropagation()
      if (hasChildren()) {
        emit('toggle', props.account.name)
      } else {
        emit('select', props.account)
      }
    }

    return () => {
      const children: any[] = []

      // 主项
      children.push(
        h(f7ListItem, {
          title: getShortName(props.account.name),
          subtitle: hasChildren() ? `${props.account.children.length} 个子账户` : props.account.currencies.join(', '),
          link: props.account.isLeaf ? '#' : undefined,
          class: `tree-item depth-${props.depth}`,
          style: { paddingLeft: `${props.depth * 16}px` },
          onClick: handleClick
        }, {
          media: () => h('div', { class: ['account-icon', getIconClass()] }, [
            h(f7Icon, { ios: getAccountIcon(), size: 18 })
          ]),
          after: () => hasChildren() ? h(f7Icon, {
            ios: isExpanded() ? 'f7:chevron_down' : 'f7:chevron_right',
            size: 14,
            class: 'expand-icon'
          }) : null
        })
      )

      // 子项（如果展开）
      if (hasChildren() && isExpanded()) {
        props.account.children.forEach(child => {
          children.push(
            h(AccountTreeItem, {
              account: child,
              expandedAccounts: props.expandedAccounts,
              depth: props.depth + 1,
              onToggle: (name: string) => emit('toggle', name),
              onSelect: (acc: AccountNode) => emit('select', acc)
            })
          )
        })
      }

      return children
    }
  }
})

onMounted(() => {
  loadExpandedState()
  loadAccounts().then(() => {
    restoreScrollPosition()
  })
})
</script>

<style scoped>
/* 加载状态 */
.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 16px;
  color: var(--text-primary);
  opacity: 0.6;
  margin-bottom: 24px;
}

/* 账户内容 */
.accounts-content {
  padding-bottom: 80px;
}

/* 账户列表样式覆盖 */
.account-list {
  margin-top: 0;
  --f7-list-bg-color: var(--bg-secondary);
  --f7-list-item-title-text-color: var(--text-primary);
  --f7-list-item-after-text-color: #8e8e93;
  --f7-list-item-border-color: var(--separator);
}

:deep(.list .item-content) {
  background-color: var(--bg-secondary);
}

:deep(.list strong) {
  background-color: var(--bg-secondary);
}

:deep(.item-title) {
  color: var(--text-primary);
}

:deep(.item-subtitle) {
  color: #8e8e93;
}

/* 树项缩进 */
:deep(.tree-item) {
  transition: background-color 0.2s;
}

:deep(.depth-0) {
  --f7-list-item-padding-horizontal: 16px;
}

:deep(.depth-1) {
  --f7-list-item-padding-horizontal: 32px;
}

:deep(.depth-2) {
  --f7-list-item-padding-horizontal: 48px;
}

:deep(.depth-3) {
  --f7-list-item-padding-horizontal: 64px;
}

:deep(.depth-4) {
  --f7-list-item-padding-horizontal: 80px;
}

/* 账户图标 */
.account-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.account-icon.assets-icon {
  background: rgba(0, 122, 255, 0.12);
  color: var(--ios-blue);
}

.account-icon.liabilities-icon {
  background: rgba(175, 82, 222, 0.12);
  color: var(--ios-purple);
}

.account-icon.income-icon {
  background: rgba(52, 199, 89, 0.12);
  color: var(--ios-green);
}

.account-icon.expenses-icon {
  background: rgba(255, 59, 48, 0.12);
  color: var(--ios-red);
}

.account-icon.equity-icon {
  background: rgba(255, 149, 0, 0.12);
  color: var(--ios-orange);
}

/* 展开图标 */
:deep(.expand-icon) {
  color: #999;
  transition: transform 0.2s;
}

/* 错误块 */
.error-block {
  background: rgba(255, 59, 48, 0.12);
  color: var(--ios-red);
  padding: 16px;
  border-radius: 8px;
  margin: 16px;
}

.error-block p {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

/* 账户前缀 */
.account-prefix {
  color: var(--f7-theme-color);
  font-weight: 600;
  font-size: 12px;
}
</style>
