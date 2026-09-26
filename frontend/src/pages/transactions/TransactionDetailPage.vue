<template><section class="page transaction-detail-page"><van-nav-bar title="交易详情" left-arrow @click-left="router.back()"><template #right><van-icon name="edit" size="20" @click="router.push(`/transactions/${route.params.id}/edit`)" /></template></van-nav-bar><div v-if="loading" class="state-card"><van-loading /></div><van-empty v-else-if="error" image="error" :description="error"><van-button @click="load">重试</van-button></van-empty><template v-else-if="transaction"><van-cell-group inset class="transaction-detail-card"><van-cell title="日期" :value="transaction.date"/><van-cell title="交易方" :value="transaction.payee || '-'"/><van-cell title="备注" :value="transaction.description || '-'"/><van-cell v-for="posting in transaction.postings" :key="posting.account" :title="posting.account" :value="`${posting.currency} ${posting.amount}`"/></van-cell-group><div class="detail-actions"><van-button block plain type="danger" :loading="deleting" :disabled="draftStore.pendingWrite || draftStore.unconfirmed === operation" @click="remove">删除交易</van-button></div></template><TransactionWriteStatus :operation="operation" :transaction-id="String(route.params.id)" @resume="error = ''" /></section></template>
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { showConfirmDialog } from 'vant'
import { useRoute, useRouter } from 'vue-router'
import { transactionsApi, type Transaction } from '../../api/transactions'
import type { ApiError } from '../../api/client'
import TransactionWriteStatus from '../../components/TransactionWriteStatus.vue'
import { useTransactionDraftStore } from '../../stores/transactionDraft'
const route = useRoute()
const router = useRouter()
const draftStore = useTransactionDraftStore()
const operation = computed(() => `delete:${route.params.id}`)
const transaction = ref<Transaction | null>(null)
const loading = ref(false)
const deleting = ref(false)
const error = ref('')
async function load() {
  loading.value = true
  error.value = ''
  try { transaction.value = await transactionsApi.getTransaction(String(route.params.id)) }
  catch (reason) { error.value = (reason as ApiError).message }
  finally { loading.value = false }
}
async function remove() {
  if (draftStore.pendingWrite || draftStore.unconfirmed === operation.value) return
  draftStore.pendingWrite = true
  try {
    await showConfirmDialog({ title: '删除交易', message: '确认删除这笔交易？' })
    deleting.value = true
    await transactionsApi.deleteTransaction(String(route.params.id))
    draftStore.pendingWrite = false
    await router.replace('/transactions')
  } catch (reason) {
    if (reason && typeof reason === 'object') {
      const failure = reason as ApiError
      if (failure.code === 'TRANSACTION_RESULT_UNCONFIRMED') draftStore.unconfirmed = operation.value
      error.value = failure.code === 'REQUEST_CANCELED' ? '已取消等待，请核对交易记录后再操作' : failure.message
    }
  } finally {
    deleting.value = false
    draftStore.pendingWrite = false
  }
}
onMounted(load)
</script>
<style scoped>.transaction-detail-card{margin-top:8px}.detail-actions{display:block;box-sizing:border-box;margin:20px 0;width:100%}.detail-actions :deep(.van-button){display:block;box-sizing:border-box;width:100%}</style>
