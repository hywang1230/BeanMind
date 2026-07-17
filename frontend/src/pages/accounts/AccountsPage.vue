<template>
  <section class="page secondary-page accounts-page">
    <van-nav-bar title="账户" left-arrow @click-left="router.back()" />

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
            <span class="row-tags"><van-tag v-for="currency in root.account.currencies" :key="currency" plain>{{ currency }}</van-tag></span>
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
              <van-tag v-for="currency in node.account.currencies" :key="currency" plain>{{ currency }}</van-tag>
            </span>
            <van-icon v-if="node.selectable && !node.hasChildren" class="row-arrow" name="arrow" />
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { accountsApi, type Account } from '../../api/accounts'
import type { ApiError } from '../../api/client'
import {
  buildAccountTree,
  flattenAccountTree,
  visibleAccountNodes,
  type AccountTreeNode,
  type VisibleAccountNode,
} from '../../utils/accountTree'

const router = useRouter()
const accounts = ref<Account[]>([])
const loading = ref(false)
const error = ref('')
const expandedNames = ref<Set<string>>(new Set())
const treeNodes = computed(() => sortNodes(buildAccountTree(accounts.value)))

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

function isExpanded(name: string): boolean { return expandedNames.value.has(name) }

function selectableCount(node: AccountTreeNode): number {
  return flattenAccountTree([node]).filter((item) => item.selectable).length
}

function sortNodes(nodes: AccountTreeNode[]): AccountTreeNode[] {
  return [...nodes]
    .sort(compareNodes)
    .map((node) => ({ ...node, children: sortNodes(node.children) }))
}

function compareNodes(a: AccountTreeNode, b: AccountTreeNode): number {
  const typeDiff = accountTypeRank(a.name) - accountTypeRank(b.name)
  if (typeDiff !== 0) return typeDiff
  return a.label.localeCompare(b.label, 'zh-Hans-CN')
}

function accountTypeRank(name: string): number {
  const order = ['Assets', 'Liabilities', 'Expenses', 'Income', 'Equity']
  const index = order.indexOf(name)
  return index === -1 ? order.length : index
}

function accountTypeMeta(name: string): { title: string; mark: string } {
  const meta: Record<string, { title: string; mark: string }> = {
    Assets: { title: '资产账户', mark: '资' },
    Liabilities: { title: '负债账户', mark: '负' },
    Expenses: { title: '支出账户', mark: '支' },
    Income: { title: '收入账户', mark: '收' },
    Equity: { title: '权益账户', mark: '权' },
  }
  return meta[name] || { title: `${name} 账户`, mark: name.slice(0, 1).toUpperCase() }
}

onMounted(load)
</script>

<style scoped>
.accounts-page { padding-bottom: 32px; }
.account-groups { display: grid; gap: 12px; }
.account-group { overflow: hidden; border: 1px solid var(--bm-border); border-radius: 18px; background: var(--bm-surface); box-shadow: var(--bm-card-shadow); }
.group-header { display: flex; width: 100%; align-items: center; gap: 12px; border: 0; background: color-mix(in srgb, var(--bm-primary-soft) 45%, var(--bm-surface)); padding: 13px 14px; color: var(--bm-text); text-align: left; }
.group-mark { display: inline-grid; width: 36px; height: 36px; flex: 0 0 36px; place-items: center; border-radius: 13px; background: var(--bm-primary); color: #fff; font-weight: 800; }
.group-title { display: grid; flex: 1; gap: 3px; min-width: 0; }
.group-title strong { font-size: 16px; }
.group-title small { color: var(--bm-muted); font-size: 12px; }
.group-arrow { color: var(--bm-muted); }
.group-body { padding: 7px 0; }
.account-row { position: relative; display: flex; width: 100%; min-height: 54px; align-items: center; gap: 10px; border: 0; background: var(--bm-surface); padding: 7px 12px 7px calc(14px + var(--level, 0) * 20px); color: var(--bm-text); text-align: left; }
.account-row + .account-row { border-top: 1px solid color-mix(in srgb, var(--bm-border) 78%, transparent); }
.account-row--group { background: color-mix(in srgb, var(--bm-bg) 42%, var(--bm-surface)); }
.account-row--leaf:active, .account-row--group:active { background: var(--bm-primary-soft); }
.account-row--root { --level: 0; border-bottom: 1px solid var(--bm-border); }
.tree-line { position: absolute; left: calc(28px + var(--level, 0) * 20px); top: 0; bottom: 0; width: 1px; background: color-mix(in srgb, var(--bm-border) 70%, transparent); }
.row-icon { z-index: 1; display: inline-grid; width: 26px; height: 26px; flex: 0 0 26px; place-items: center; border-radius: 10px; background: var(--bm-bg); color: var(--bm-muted); }
.row-icon--group { background: var(--bm-primary-soft); color: var(--bm-primary); }
.row-icon--leaf { background: var(--bm-bg); color: var(--bm-muted); }
.row-main { display: grid; flex: 1; gap: 3px; min-width: 0; }
.row-name { overflow: hidden; font-size: 15px; font-weight: 700; line-height: 20px; text-overflow: ellipsis; white-space: nowrap; }
.row-path { overflow: hidden; color: var(--bm-muted); font-size: 12px; line-height: 16px; text-overflow: ellipsis; white-space: nowrap; }
.row-tags { display: inline-flex; max-width: 92px; flex-wrap: wrap; justify-content: flex-end; gap: 4px; }
.row-arrow { flex: 0 0 auto; color: var(--bm-faint); }
.type-Liabilities .group-mark { background: #b7791f; }
.type-Expenses .group-mark { background: var(--bm-expense); }
.type-Income .group-mark { background: var(--bm-income); }
.type-Equity .group-mark { background: #6b7280; }
@media (max-width: 420px) {
  .row-tags { max-width: 74px; }
}
</style>
