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
        <f7-nav-title>选择交易方</f7-nav-title>
      </f7-navbar>
      
      <f7-searchbar
        placeholder="搜索或输入新交易方"
        v-model:value="searchQuery"
        :disable-button="false"
        @searchbar:clear="searchQuery = ''"
      ></f7-searchbar>

      <f7-list>
        <!-- 如果搜索内容不在列表中，显示使用当前输入 -->
        <f7-list-item
          v-if="searchQuery && !filteredPayees.includes(searchQuery)"
          :title="`使用 '${searchQuery}'`"
          link="#"
          @click="onPayeeSelect(searchQuery)"
        >
          <template #media>
            <f7-icon f7="plus_circle_fill" color="blue"></f7-icon>
          </template>
        </f7-list-item>

        <f7-list-item
          v-for="payee in filteredPayees"
          :key="payee"
          :title="payee"
          link="#"
          @click="onPayeeSelect(payee)"
        ></f7-list-item>

        <f7-list-item v-if="filteredPayees.length === 0 && !searchQuery" title="暂无历史交易方"></f7-list-item>
      </f7-list>

    </f7-page>
  </f7-popup>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { transactionsApi } from '../api/transactions'

const props = defineProps<{
  opened: boolean
}>()

const emit = defineEmits<{
  (e: 'update:opened', value: boolean): void
  (e: 'select', payee: string): void
}>()

const searchQuery = ref('')
const allPayees = ref<string[]>([])

const filteredPayees = computed(() => {
  if (!searchQuery.value) return allPayees.value
  const query = searchQuery.value.toLowerCase()
  return allPayees.value.filter(p => p.toLowerCase().includes(query))
})

async function loadPayees() {
  try {
    const res = await transactionsApi.getPayees()
    if (Array.isArray(res)) {
       allPayees.value = res
    }
  } catch (e) {
    console.error('Failed to load payees', e)
  }
}

function onPayeeSelect(payee: string) {
  emit('select', payee)
  emit('update:opened', false)
}

function onPopupClosed() {
  emit('update:opened', false)
  searchQuery.value = ''
}

// 每次打开时重新加载，或者只加载一次
watch(() => props.opened, (newVal) => {
  if (newVal) {
    // 可以在这里决定是否每次都刷新
    loadPayees()
  }
})

onMounted(() => {
  loadPayees()
})
</script>
