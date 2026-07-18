<template>
  <section class="page secondary-page account-detail-page">
    <van-nav-bar title="账户详情" left-arrow @click-left="router.back()" />
    <div v-if="loading" class="state-card"><van-loading /></div>
    <van-empty v-else-if="error" image="error" :description="error">
      <van-button @click="load">重试</van-button>
    </van-empty>
    <template v-else-if="detail">
      <van-cell-group inset class="detail-card">
        <van-cell title="账户" :value="detail.name" />
        <van-cell title="类型" :value="detail.account_type" />
        <van-cell title="状态" :value="detail.is_active ? '活跃' : '已关闭'" />
        <van-cell title="开户日" :value="formatDate(detail.open_date)" />
        <van-cell title="关闭日" :value="formatDate(detail.close_date)" />
        <van-cell title="币种" :value="(detail.currencies || []).join(', ') || '-'" />
      </van-cell-group>

      <h2 class="section-title">余额</h2>
      <van-cell-group inset>
        <van-empty v-if="!balances.length" description="无余额" />
        <van-cell
          v-for="item in balances"
          :key="item.currency"
          :title="item.currency"
          :value="item.amount"
        />
      </van-cell-group>

      <div class="actions">
        <van-button
          v-if="detail.is_active"
          block
          type="danger"
          plain
          :loading="acting"
          @click="openClose"
        >关闭账户</van-button>
        <van-button
          v-else
          block
          type="primary"
          :loading="acting"
          @click="reopen"
        >重新开启</van-button>
      </div>
      <van-notice-bar v-if="actionError" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ actionError }}</van-notice-bar>
    </template>

    <van-dialog
      v-model:show="showClose"
      title="关闭账户"
      show-cancel-button
      :before-close="onCloseDialog"
    >
      <div class="close-dialog">
        <p>仅当所有币种余额为零且无活跃子账户时可关闭。</p>
        <DatePickerField v-model="closeDate" label="关闭日期" />
      </div>
    </van-dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showToast } from 'vant'
import { useRoute, useRouter } from 'vue-router'
import { accountsApi, type AccountDetail, type Balance } from '../../api/accounts'
import type { ApiError } from '../../api/client'
import DatePickerField from '../../components/DatePickerField.vue'

const route = useRoute()
const router = useRouter()
const detail = ref<AccountDetail | null>(null)
const balances = ref<Balance[]>([])
const loading = ref(false)
const acting = ref(false)
const error = ref('')
const actionError = ref('')
const showClose = ref(false)
const closeDate = ref(new Date().toISOString().slice(0, 10))

function accountName() {
  return decodeURIComponent(String(route.params.accountName || ''))
}

function formatDate(value?: string | null) {
  return value ? value.slice(0, 10) : '-'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const name = accountName()
    ;[detail.value, balances.value] = await Promise.all([
      accountsApi.getAccountDetail(name),
      accountsApi.getBalance(name),
    ])
  } catch (reason) {
    error.value = (reason as ApiError).message
  } finally {
    loading.value = false
  }
}

function openClose() {
  actionError.value = ''
  closeDate.value = new Date().toISOString().slice(0, 10)
  showClose.value = true
}

async function onCloseDialog(action: string) {
  if (action !== 'confirm') return true
  acting.value = true
  actionError.value = ''
  try {
    await accountsApi.closeAccount(accountName(), { close_date: closeDate.value })
    showToast('账户已关闭')
    await load()
    return true
  } catch (reason) {
    actionError.value = (reason as ApiError).message || '关闭失败'
    showToast(actionError.value)
    return false
  } finally {
    acting.value = false
  }
}

async function reopen() {
  acting.value = true
  actionError.value = ''
  try {
    await accountsApi.reopenAccount(accountName())
    showToast('账户已重新开启')
    await load()
  } catch (reason) {
    actionError.value = (reason as ApiError).message || '重新开启失败'
  } finally {
    acting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.detail-card { margin-top: 8px; }
.section-title { margin: 16px 16px 8px; font-size: 15px; }
.actions { margin: 20px 16px; display: grid; gap: 12px; }
.close-dialog { padding: 12px 16px 4px; }
.close-dialog p { margin: 0 0 8px; color: var(--bm-muted, #666); font-size: 13px; }
</style>
