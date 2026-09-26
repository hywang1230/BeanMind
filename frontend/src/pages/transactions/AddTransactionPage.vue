<template>
  <section class="page transaction-editor-page">
    <van-nav-bar title="记一笔" left-arrow @click-left="onBack" />
    <TransactionForm ref="formRef" mode="create" :loading="loading" :disabled="draftStore.pendingWrite || draftStore.unconfirmed === 'create'" @submit="save" />
    <TransactionWriteStatus operation="create" @resume="error = ''" />
    <van-notice-bar v-if="error" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ error }}</van-notice-bar>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast } from 'vant'
import type { ApiError } from '../../api/client'
import { transactionsApi, type CreateTransactionRequest } from '../../api/transactions'
import TransactionWriteStatus from '../../components/TransactionWriteStatus.vue'
import TransactionForm from '../../components/TransactionForm.vue'
import { useTransactionDraftStore } from '../../stores/transactionDraft'

const router = useRouter()
const draftStore = useTransactionDraftStore()
const loading = ref(false)
const error = ref('')
const formRef = ref<{
  trySubmitFromDraft: () => boolean
  resetForNextEntry: (options?: { lastPayee?: string }) => void
} | null>(null)

async function save(value: CreateTransactionRequest) {
  if (draftStore.pendingWrite || draftStore.unconfirmed === 'create') return
  draftStore.pendingWrite = true
  loading.value = true
  error.value = ''
  try {
    await transactionsApi.createTransaction(value)
    draftStore.clear()
    formRef.value?.resetForNextEntry({ lastPayee: value.payee })
    showSuccessToast('已保存，可继续记账')
  } catch (reason) {
    const failure = reason as ApiError
    if (failure.code === 'TRANSACTION_RESULT_UNCONFIRMED') draftStore.unconfirmed = 'create'
    error.value = failure.code === 'REQUEST_CANCELED' ? '已取消等待，请核对交易记录后再操作' : failure.message
  } finally {
    loading.value = false
    draftStore.pendingWrite = false
  }
}

function onBack() {
  if (!draftStore.pendingWrite && !draftStore.unconfirmed) draftStore.clear()
  router.back()
}

</script>
