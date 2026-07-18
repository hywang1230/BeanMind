<template>
  <section class="page transaction-editor-page">
    <van-nav-bar title="记一笔" left-arrow @click-left="onBack" />
    <TransactionForm ref="formRef" mode="create" :loading="loading" @submit="save" />
    <van-notice-bar v-if="error" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ error }}</van-notice-bar>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast } from 'vant'
import type { ApiError } from '../../api/client'
import { transactionsApi, type CreateTransactionRequest } from '../../api/transactions'
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
  loading.value = true
  error.value = ''
  try {
    await transactionsApi.createTransaction(value)
    draftStore.clear()
    formRef.value?.resetForNextEntry({ lastPayee: value.payee })
    showSuccessToast('已保存，可继续记账')
  } catch (reason) {
    error.value = (reason as ApiError).message
  } finally {
    loading.value = false
  }
}

function onBack() {
  draftStore.clear()
  router.back()
}

onMounted(() => {
  // If returning with a fully balanced multi draft, allow re-submit from form state.
  formRef.value?.trySubmitFromDraft()
})
</script>
