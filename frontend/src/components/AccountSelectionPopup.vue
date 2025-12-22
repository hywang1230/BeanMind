<template>
  <f7-popup :opened="opened" @popup:closed="$emit('update:opened', false)">
    <f7-page>
      <f7-navbar :title="title">
        <f7-nav-right>
          <f7-link popup-close>关闭</f7-link>
        </f7-nav-right>
      </f7-navbar>
      
      <f7-searchbar
        search-container=".account-tree-list"
        search-in=".item-title"
        placeholder="搜索账户"
        :disable-button="false"
      ></f7-searchbar>

      <f7-list class="account-tree-list searchbar-found">
        <f7-treeview>
          <account-tree-item
            v-for="account in filteredAccounts"
            :key="account.name"
            :account="account"
            @select="selectAccount"
          />
        </f7-treeview>
      </f7-list>
      
      <f7-list class="searchbar-not-found">
        <f7-list-item title="未找到账户"></f7-list-item>
      </f7-list>

    </f7-page>
  </f7-popup>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { accountsApi, type Account } from '../api/accounts'
import AccountTreeItem from './AccountTreeItem.vue' // We will create this recursive component

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

const filteredAccounts = computed(() => {
  if (!props.rootTypes || props.rootTypes.length === 0) return accounts.value
  return accounts.value.filter(acc => props.rootTypes?.includes(acc.type))
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
