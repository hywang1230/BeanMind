<template>
  <section class="page secondary-page accounts-page">
    <van-nav-bar title="账户" left-arrow @click-left="router.back()">
      <template #right>
        <van-button size="small" type="primary" plain @click="openCreate">新建</van-button>
      </template>
    </van-nav-bar>

    <div v-if="loading" class="state-card"><van-loading /></div>
    <van-empty v-else-if="error" image="error" :description="error"><van-button @click="load">重试</van-button></van-empty>
    <van-empty v-else-if="!treeNodes.length" description="暂无账户" />

    <div v-else class="account-groups">
      <article v-for="root in treeNodes" :key="root.name" class="account-group" :class="`type-${root.name}`">
        <button
          type="button"
          class="group-header"
          :aria-label="isExpanded(root.name) ? `收起${root.name}` : `展开${root.name}`"
          @click="toggle(root.name)"
        >
          <span class="group-mark">{{ accountTypeMeta(root.name).mark }}</span>
          <span class="group-title">
            <strong>{{ accountTypeMeta(root.name).title }}</strong>
            <small>{{ selectableCount(root) }} 个账户</small>
          </span>
          <van-icon class="group-arrow" :name="isExpanded(root.name) ? 'arrow-down' : 'arrow'" />
        </button>

        <div v-show="isExpanded(root.name)" class="group-body">
          <button
            v-if="root.selectable"
            type="button"
            class="account-row account-row--root"
            @click="openDetail(root.name)"
          >
            <span class="row-icon row-icon--leaf"><van-icon name="description-o" /></span>
            <span class="row-main">
              <span class="row-name">{{ root.label }}</span>
              <span class="row-path">{{ root.name }}</span>
            </span>
            <span class="row-tags">
              <van-tag v-if="root.account.is_active === false" plain type="warning">已关闭</van-tag>
              <van-tag v-for="currency in root.account.currencies" :key="currency" plain>{{ currency }}</van-tag>
            </span>
            <van-icon class="row-arrow" name="arrow" />
          </button>

          <button
            v-for="node in visibleChildren(root)"
            :key="node.name"
            type="button"
            class="account-row"
            :class="{ 'account-row--group': node.hasChildren || !node.selectable, 'account-row--leaf': node.selectable && !node.hasChildren }"
            :style="{ '--level': String(Math.max(node.level - 1, 0)) }"
            :aria-label="node.hasChildren ? (isExpanded(node.name) ? `收起${node.name}` : `展开${node.name}`) : node.name"
            :aria-disabled="!node.selectable && !node.hasChildren"
            @click="handleNodeClick(node)"
          >
            <span class="tree-line" aria-hidden="true" />
            <span class="row-icon" :class="node.hasChildren ? 'row-icon--group' : 'row-icon--leaf'">
              <van-icon v-if="node.hasChildren" :name="isExpanded(node.name) ? 'arrow-down' : 'arrow'" />
              <van-icon v-else name="description-o" />
            </span>
            <span class="row-main">
              <span class="row-name">{{ node.label }}</span>
              <span class="row-path">{{ node.name }}</span>
            </span>
            <span class="row-tags">
              <van-tag v-if="node.hasChildren" plain type="primary">分组</van-tag>
              <van-tag v-if="node.account.is_active === false" plain type="warning">已关闭</van-tag>
              <van-tag v-for="currency in node.account.currencies" :key="currency" plain>{{ currency }}</van-tag>
            </span>
            <van-icon v-if="node.selectable && !node.hasChildren" class="row-arrow" name="arrow" />
          </button>
        </div>
      </article>
    </div>

    <van-popup v-model:show="showCreate" position="bottom" round :style="{ minHeight: '50%' }">
      <div class="create-panel">
        <header class="create-header">
          <strong>新建账户</strong>
          <button type="button" class="header-action" @click="showCreate = false">关闭</button>
        </header>
        <van-form @submit="createAccount">
          <van-cell-group inset>
            <van-field name="type" label="类型">
              <template #input>
                <van-radio-group v-model="createForm.account_type" direction="horizontal">
                  <van-radio name="Assets">资产</van-radio>
                  <van-radio name="Liabilities">负债</van-radio>
                  <van-radio name="Equity">权益</van-radio>
                  <van-radio name="Income">收入</van-radio>
                  <van-radio name="Expenses">支出</van-radio>
                </van-radio-group>
              </template>
            </van-field>
            <van-field
              v-model="createForm.nameSuffix"
              label="账户名"
              :placeholder="`如 Bank:Checking`"
              required
            >
              <template #label>
                <span>账户名</span>
              </template>
              <template #input>
                <div class="name-input-row">
                  <span class="name-prefix">{{ namePrefix }}</span>
                  <input
                    v-model="createForm.nameSuffix"
                    class="name-suffix-input"
                    type="text"
                    :placeholder="nameSuffixPlaceholder"
                    required
                  >
                </div>
              </template>
            </van-field>
            <van-field name="currencies" label="币种" required>
              <template #input>
                <van-checkbox-group v-model="createForm.currencies" direction="horizontal" class="currency-checks">
                  <van-checkbox
                    v-for="currency in currencyOptions"
                    :key="currency"
                    :name="currency"
                    shape="square"
                  >{{ currency }}</van-checkbox>
                </van-checkbox-group>
              </template>
            </van-field>
            <DatePickerField v-model="createForm.open_date" label="开户日期" />
          </van-cell-group>
          <div class="create-actions">
            <van-button block type="primary" native-type="submit" :loading="creating">创建</van-button>
          </div>
          <van-notice-bar v-if="createError" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ createError }}</van-notice-bar>
        </van-form>
      </div>
    </van-popup>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { showToast } from 'vant'
import { useRouter } from 'vue-router'
import { accountsApi, type Account } from '../../api/accounts'
import type { ApiError } from '../../api/client'
import DatePickerField from '../../components/DatePickerField.vue'
import {
  buildAccountTree,
  visibleAccountNodes,
  type AccountTreeNode,
  type VisibleAccountNode,
} from '../../utils/accountTree'

const BASE_CURRENCIES = ['CNY', 'USD'] as const

const router = useRouter()
const accounts = ref<Account[]>([])
const loading = ref(false)
const error = ref('')
const expandedNames = ref<Set<string>>(new Set())
const treeNodes = computed(() => sortNodes(buildAccountTree(accounts.value)))
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = reactive({
  nameSuffix: '',
  account_type: 'Assets',
  currencies: ['CNY'] as string[],
  open_date: new Date().toISOString().slice(0, 10),
})

const namePrefix = computed(() => `${createForm.account_type}:`)
const nameSuffixPlaceholder = computed(() => {
  if (createForm.account_type === 'Assets') return 'Bank:Checking'
  if (createForm.account_type === 'Liabilities') return 'CreditCard:CMB'
  if (createForm.account_type === 'Equity') return 'OpeningBalances'
  if (createForm.account_type === 'Income') return 'Salary'
  return 'Food:Lunch'
})

const currencyOptions = computed(() => [...BASE_CURRENCIES])

async function load() {
  loading.value = true
  error.value = ''
  try {
    const loaded = await accountsApi.getAccounts()
    accounts.value = loaded
    expandedNames.value = new Set(buildAccountTree(loaded).map((node) => node.name))
  } catch (reason) {
    error.value = (reason as ApiError).message
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createError.value = ''
  createForm.nameSuffix = ''
  createForm.account_type = 'Assets'
  createForm.currencies = ['CNY']
  createForm.open_date = new Date().toISOString().slice(0, 10)
  showCreate.value = true
}

async function createAccount() {
  creating.value = true
  createError.value = ''
  try {
    const suffix = createForm.nameSuffix.trim().replace(/^:+/, '').replace(/:+$/, '')
    if (!suffix) {
      createError.value = '请填写账户名'
      return
    }
    const currencies = createForm.currencies.filter(Boolean)
    if (!currencies.length) {
      createError.value = '请至少选择一个币种'
      return
    }
    await accountsApi.createAccount({
      name: `${createForm.account_type}:${suffix}`,
      account_type: createForm.account_type,
      currencies,
      open_date: createForm.open_date,
    })
    showToast('账户已创建')
    showCreate.value = false
    createForm.nameSuffix = ''
    await load()
  } catch (reason) {
    createError.value = (reason as ApiError).message || '创建失败'
  } finally {
    creating.value = false
  }
}

function visibleChildren(root: AccountTreeNode): VisibleAccountNode[] {
  return visibleAccountNodes(root.children, expandedNames.value)
}

function handleNodeClick(node: VisibleAccountNode) {
  if (node.hasChildren) {
    toggle(node.name)
    return
  }
  if (node.selectable) openDetail(node.name)
}

function openDetail(name: string) {
  router.push(`/accounts/${encodeURIComponent(name)}`)
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

function selectableCount(node: AccountTreeNode): number {
  let count = node.selectable ? 1 : 0
  for (const child of node.children) count += selectableCount(child)
  return count
}

function sortNodes(nodes: AccountTreeNode[]): AccountTreeNode[] {
  const order = ['Assets', 'Liabilities', 'Equity', 'Income', 'Expenses']
  return [...nodes].sort((a, b) => order.indexOf(a.name) - order.indexOf(b.name))
}

function accountTypeMeta(name: string) {
  const map: Record<string, { title: string; mark: string }> = {
    Assets: { title: '资产账户', mark: '资' },
    Liabilities: { title: '负债账户', mark: '债' },
    Equity: { title: '权益账户', mark: '益' },
    Income: { title: '收入账户', mark: '收' },
    Expenses: { title: '支出账户', mark: '支' },
  }
  return map[name] || { title: name, mark: name.slice(0, 1) }
}

onMounted(load)
</script>

<style scoped>
.account-groups { display: grid; gap: 12px; padding-bottom: 8px; }
.account-group {
  background: var(--bm-surface);
  border: 1px solid var(--bm-border);
  border-radius: var(--bm-radius);
  overflow: hidden;
  box-shadow: var(--bm-card-shadow);
  color: var(--bm-text);
}
.group-header {
  width: 100%; display: flex; align-items: center; gap: 10px;
  padding: 14px 14px; border: 0; background: transparent; text-align: left; color: inherit;
}
.group-mark {
  width: 28px; height: 28px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center;
  background: var(--bm-primary-soft); color: var(--bm-primary); font-size: 13px; font-weight: 700;
}
.group-title { flex: 1; display: flex; flex-direction: column; }
.group-title strong { color: var(--bm-text); font-size: 15px; }
.group-title small { color: var(--bm-muted); }
.group-arrow { color: var(--bm-muted); }
.account-row {
  width: 100%; display: flex; align-items: center; gap: 8px;
  padding: 12px 14px; border: 0; border-top: 1px solid var(--bm-border); background: transparent; text-align: left;
  padding-left: calc(14px + var(--level, 0) * 16px);
  color: inherit;
}
.row-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.row-name { color: var(--bm-text); font-weight: 600; }
.row-path { color: var(--bm-muted); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-tags { display: flex; gap: 4px; flex-wrap: wrap; justify-content: flex-end; max-width: 120px; }
.row-icon { width: 20px; display: inline-flex; justify-content: center; color: var(--bm-muted); }
.row-arrow { color: var(--bm-faint); }
.create-panel { padding-bottom: 24px; color: var(--bm-text); }
.create-header { display: flex; justify-content: space-between; align-items: center; padding: 16px; color: var(--bm-text); }
.header-action { border: 0; background: transparent; color: var(--bm-primary); }
.create-actions { margin: 16px; }
.name-input-row {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  min-width: 0;
}
.name-prefix {
  flex: 0 0 auto;
  color: var(--bm-primary);
  font-weight: 600;
  white-space: nowrap;
}
.name-suffix-input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--bm-text);
  font: inherit;
}
.currency-checks {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
}
.currency-checks :deep(.van-checkbox) {
  margin-right: 0;
}
</style>
