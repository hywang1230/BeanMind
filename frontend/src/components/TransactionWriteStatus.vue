<template>
  <div v-if="store.unconfirmed === operation" class="write-status" role="status">
    <van-notice-bar wrapable :text="UNCONFIRMED_TRANSACTION_MESSAGE" />
    <van-button plain :loading="checking" @click="check">只读核对结果</van-button>
    <van-button v-if="checked" plain @click="resume">我已核对，返回操作</van-button>
    <van-popup v-model:show="show" position="bottom" round :style="{ maxHeight: '75%', overflow: 'auto' }">
      <div class="verification-results">
        <h3>核对当前交易记录</h3>
        <p>以下为当前查询结果，不代表原请求已结束。请核对日期、金额和备注，勿重复记账。</p>
        <p v-if="queryError">{{ queryError }}</p>
        <p v-else-if="!rows.length">当前未查到记录，仍不能确认原请求不会稍后完成。</p>
        <van-cell-group v-for="row in rows" :key="row.id">
          <van-cell :title="row.date" :value="row.payee || row.description || '-'" :label="row.description" />
          <van-cell v-for="(posting, index) in row.postings" :key="index" :title="posting.account" :value="`${posting.currency} ${posting.amount}`" />
        </van-cell-group>
        <van-button block @click="show = false">返回（保留草稿）</van-button>
      </div>
    </van-popup>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { showConfirmDialog } from 'vant'
import type { ApiError } from '../api/client'
import { transactionsApi, UNCONFIRMED_TRANSACTION_MESSAGE, type Transaction } from '../api/transactions'
import { useTransactionDraftStore } from '../stores/transactionDraft'
const props = defineProps<{ operation: string; transactionId?: string }>()
const store = useTransactionDraftStore()
const emit = defineEmits<{ (event: 'resume'): void }>()
const checking = ref(false)
const checked = ref(false)
const show = ref(false)
const rows = ref<Transaction[]>([])
const queryError = ref('')
async function check() {
  if (checking.value) return
  checking.value = true
  queryError.value = ''
  rows.value = []
  try {
    rows.value = props.transactionId
      ? [await transactionsApi.getTransaction(props.transactionId)]
      : (await transactionsApi.getTransactions({ limit: 20 })).items
    checked.value = true
  } catch (reason) {
    const error = reason as ApiError
    queryError.value = error.status === 404
      ? '当前未查到该交易，仍不能确认原请求不会稍后完成。'
      : `${error.message || '查询失败'}；操作结果仍未确认。`
    checked.value = true
  } finally {
    checking.value = false
    show.value = true
  }
}
async function resume() {
  try {
    await showConfirmDialog({ title: '返回操作', message: '解除提示不代表原请求失败。请确认已核对账本，避免重复保存或删除。' })
  } catch { return }
  store.unconfirmed = null
  checked.value = false
  emit('resume')
}
</script>
<style scoped>
.write-status { margin: 12px 0; }
.write-status > .van-button { margin: 8px 8px 0 0; }
.verification-results { padding: 16px 16px calc(16px + env(safe-area-inset-bottom)); }
</style>
