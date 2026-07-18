<template>
  <section class="page secondary-page currencies-page">
    <van-nav-bar title="币种管理" left-arrow @click-left="router.back()">
      <template #right>
        <van-button size="small" type="primary" plain @click="openCreate">新增</van-button>
      </template>
    </van-nav-bar>

    <div v-if="loading && !items.length" class="state-card"><van-loading /></div>
    <van-empty v-else-if="error && !items.length" image="error" :description="error">
      <van-button size="small" type="primary" @click="load">重试</van-button>
    </van-empty>
    <van-empty v-else-if="!items.length" description="暂无币种">
      <van-button type="primary" size="small" @click="openCreate">新增币种</van-button>
    </van-empty>
    <van-cell-group v-else inset class="currency-list">
      <van-cell
        v-for="item in items"
        :key="item.code"
        :title="item.name"
        :label="currencyLabel(item)"
      >
        <template #value>
          <div class="row-actions">
            <van-tag v-if="item.is_operating" type="success" plain size="medium">主币种</van-tag>
            <van-tag v-if="item.in_use" type="primary" plain size="medium">使用中</van-tag>
            <van-switch
              :model-value="item.enabled"
              size="20px"
              :disabled="togglingCode === item.code || Boolean(item.enabled && item.in_use)"
              @update:model-value="(value: boolean) => toggleEnabled(item, value)"
            />
            <van-button
              v-if="!item.in_use"
              size="mini"
              type="danger"
              plain
              :loading="deletingCode === item.code"
              @click="confirmDelete(item)"
            >
              删除
            </van-button>
          </div>
        </template>
      </van-cell>
    </van-cell-group>

    <van-notice-bar
      v-if="actionError || (error && items.length)"
      color="var(--bm-expense)"
      background="var(--bm-danger-soft)"
    >{{ actionError || error }}</van-notice-bar>

    <van-popup v-model:show="showCreate" position="bottom" round :style="{ minHeight: '45%' }">
      <div class="panel">
        <header class="panel-header">
          <strong>新增币种</strong>
          <button type="button" class="header-action" @click="showCreate = false">关闭</button>
        </header>
        <van-form @submit="createCurrency">
          <van-cell-group inset>
            <van-field
              v-model="createForm.code"
              label="代码"
              maxlength="3"
              placeholder="如 EUR"
              required
              :error-message="createFieldError"
            />
            <van-field v-model="createForm.name" label="名称" placeholder="显示名" required />
            <van-field v-model="createForm.symbol" label="符号" placeholder="可选，如 €" />
          </van-cell-group>
          <div class="panel-submit">
            <van-button block type="primary" native-type="submit" :loading="creating">保存</van-button>
          </div>
          <van-notice-bar
            v-if="createError"
            color="var(--bm-expense)"
            background="var(--bm-danger-soft)"
          >{{ createError }}</van-notice-bar>
        </van-form>
      </div>
    </van-popup>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useRouter } from 'vue-router'
import { currenciesApi, type CurrencyItem } from '../../api/currencies'
import type { ApiError } from '../../api/client'

const router = useRouter()
const items = ref<CurrencyItem[]>([])
const loading = ref(false)
const error = ref('')
const actionError = ref('')
const togglingCode = ref('')
const deletingCode = ref('')

const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const createFieldError = ref('')
const createForm = reactive({
  code: '',
  name: '',
  symbol: '',
})

function currencyLabel(item: CurrencyItem) {
  const parts = [item.symbol ? `${item.code} · ${item.symbol}` : item.code]
  if (item.is_operating) parts.push('主币种')
  if (item.in_use) parts.push('已使用不可关闭/删除')
  return parts.join(' · ')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    items.value = await currenciesApi.list(false)
  } catch (reason) {
    error.value = (reason as ApiError).message || '币种目录加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createForm.code = ''
  createForm.name = ''
  createForm.symbol = ''
  createError.value = ''
  createFieldError.value = ''
  showCreate.value = true
}

async function createCurrency() {
  createError.value = ''
  createFieldError.value = ''
  const code = createForm.code.trim().toUpperCase()
  if (!/^[A-Z]{3}$/.test(code)) {
    createFieldError.value = '代码须为 3 个字母'
    return
  }
  if (!createForm.name.trim()) {
    createError.value = '请填写名称'
    return
  }
  creating.value = true
  try {
    await currenciesApi.create({
      code,
      name: createForm.name.trim(),
      symbol: createForm.symbol.trim() || null,
      enabled: true,
    })
    showToast('已新增')
    showCreate.value = false
    await load()
  } catch (reason) {
    createError.value = (reason as ApiError).message || '新增失败'
  } finally {
    creating.value = false
  }
}

async function toggleEnabled(item: CurrencyItem, enabled: boolean) {
  if (enabled === false && item.in_use) {
    actionError.value = `币种 ${item.code} 已在系统中使用，不能停用`
    return
  }
  actionError.value = ''
  togglingCode.value = item.code
  try {
    const updated = await currenciesApi.update(item.code, { enabled })
    const index = items.value.findIndex((row) => row.code === item.code)
    if (index >= 0) items.value[index] = updated
  } catch (reason) {
    actionError.value = (reason as ApiError).message || '更新失败'
  } finally {
    togglingCode.value = ''
  }
}

async function confirmDelete(item: CurrencyItem) {
  if (item.in_use) {
    actionError.value = `币种 ${item.code} 已在系统中使用，不能删除`
    return
  }
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: `确定删除币种 ${item.code}（${item.name}）吗？`,
    })
  } catch {
    return
  }
  actionError.value = ''
  deletingCode.value = item.code
  try {
    await currenciesApi.delete(item.code)
    showToast('已删除')
    await load()
  } catch (reason) {
    actionError.value = (reason as ApiError).message || '删除失败'
  } finally {
    deletingCode.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.currency-list {
  margin-top: 8px;
}

.row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.panel {
  padding: 12px 0 20px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 16px 12px;
}

.header-action {
  border: 0;
  background: transparent;
  color: var(--bm-primary);
  font-size: 14px;
}

.panel-submit {
  padding: 8px 16px 0;
}
</style>
