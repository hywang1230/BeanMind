<template>
  <section class="page transaction-editor-page">
    <van-nav-bar title="编辑交易" left-arrow @click-left="onBack" />
    <div v-if="loadingInitial" class="state-card"><van-loading /></div>
    <van-empty v-else-if="error && !transaction" image="error" :description="error">
      <van-button @click="load">重试</van-button>
    </van-empty>
    <TransactionForm
      v-else
      mode="edit"
      :initial="transaction"
      :loading="saving"
      :disabled="draftStore.pendingWrite || draftStore.unconfirmed === operation"
      @submit="save"
    />
    <TransactionWriteStatus :operation="operation" :transaction-id="String(route.params.id)" @resume="error = ''" />
    <van-notice-bar v-if="error && transaction" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ error }}</van-notice-bar>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ApiError } from '../../api/client'
import { transactionsApi, type CreateTransactionRequest, type Transaction } from '../../api/transactions'
import TransactionWriteStatus from '../../components/TransactionWriteStatus.vue'
import TransactionForm from '../../components/TransactionForm.vue'
import { useTransactionDraftStore } from '../../stores/transactionDraft'

const route = useRoute()
const router = useRouter()
const draftStore = useTransactionDraftStore()
const operation = computed(() => `edit:${route.params.id}`)
const transaction = ref<Transaction | null>(null)
const loadingInitial = ref(false)
const saving = ref(false)
const error = ref('')
async function load() {
  loadingInitial.value = true
  error.value = ''
  try {
    transaction.value = await transactionsApi.getTransaction(String(route.params.id))
  } catch (reason) {
    error.value = (reason as ApiError).message
  } finally {
    loadingInitial.value = false
  }
}

async function save(value: CreateTransactionRequest) {
  if (draftStore.pendingWrite || draftStore.unconfirmed === operation.value) return
  draftStore.pendingWrite = true
  saving.value = true
  error.value = ''
  try {
    await transactionsApi.updateTransaction(String(route.params.id), value)
    draftStore.clear()
    draftStore.pendingWrite = false
    await router.replace(`/transactions/${route.params.id}`)
  } catch (reason) {
    const failure = reason as ApiError
    if (failure.code === 'TRANSACTION_RESULT_UNCONFIRMED') draftStore.unconfirmed = operation.value
    error.value = failure.code === 'REQUEST_CANCELED' ? '已取消等待，请核对交易记录后再操作' : failure.message
  } finally {
    draftStore.pendingWrite = false
    saving.value = false
  }
}

function onBack() {
  if (!draftStore.pendingWrite && !draftStore.unconfirmed) draftStore.clear()
  router.back()
}

onMounted(load)
</script>
