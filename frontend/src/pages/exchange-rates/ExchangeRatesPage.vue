<template>
  <section class="page secondary-page exchange-rates-page">
    <van-nav-bar title="汇率" left-arrow @click-left="router.back()">
      <template #right>
        <van-button size="small" type="primary" plain @click="openCreate()">添加</van-button>
      </template>
    </van-nav-bar>

    <article class="quote-card">
      <div class="quote-card__title">主货币：{{ quoteCurrency }}</div>
      <p class="quote-card__desc">
        汇率来自币种目录中已启用的外币，表示 1 单位源货币可兑换的主货币数量。
        例如：1 {{ exampleCurrency }} = {{ exampleRate }} {{ quoteCurrency }}
      </p>
    </article>

    <div v-if="loading && !rates.length" class="state-card"><van-loading /></div>
    <van-empty v-else-if="error && !rates.length" image="error" :description="error">
      <van-button @click="load">重试</van-button>
    </van-empty>
    <van-empty v-else-if="!rates.length" description="账本中暂无汇率">
      <van-button type="primary" size="small" @click="openCreate()">添加汇率</van-button>
    </van-empty>

    <van-cell-group v-else inset class="rate-list">
      <van-cell
        v-for="rate in rates"
        :key="`${rate.currency}-${rate.effective_date}`"
        is-link
        :title="rate.currency_pair || `${rate.currency}/${rate.quote_currency}`"
        :value="rate.rate"
        :label="`生效日期：${rate.effective_date}`"
        @click="openDetail(rate)"
      />
    </van-cell-group>

    <van-notice-bar
      v-if="error && rates.length"
      color="var(--bm-expense)"
      background="var(--bm-danger-soft)"
    >
      {{ error }}
    </van-notice-bar>

    <!-- 详情 + 历史 -->
    <van-popup v-model:show="showDetail" position="bottom" round :style="{ minHeight: '55%' }">
      <div class="panel" v-if="selectedRate">
        <header class="panel-header">
          <strong>{{ selectedRate.currency }}/{{ quoteCurrency }} 详情</strong>
          <button type="button" class="header-action" @click="showDetail = false">关闭</button>
        </header>

        <van-cell-group inset>
          <van-cell title="最新汇率" :value="selectedRate.rate" />
          <van-cell title="生效日期" :value="selectedRate.effective_date" />
        </van-cell-group>

        <div class="panel-actions">
          <van-button size="small" type="primary" plain @click="openCreateForCurrency(selectedRate.currency)">
            添加汇率
          </van-button>
          <van-button size="small" type="primary" plain @click="openEdit(selectedRate)">编辑最新</van-button>
          <van-button size="small" type="danger" plain :loading="deleting" @click="confirmDelete(selectedRate)">
            删除最新
          </van-button>
        </div>

        <h3 class="panel-subtitle">历史汇率</h3>
        <div v-if="historyLoading" class="state-card"><van-loading size="24px" /></div>
        <van-empty v-else-if="!history.length" description="暂无历史记录" />
        <van-cell-group v-else inset>
          <van-cell
            v-for="item in history"
            :key="`${item.currency}-${item.effective_date}`"
            :title="item.effective_date"
            :value="item.rate"
          >
            <template #label>
              <div class="history-actions">
                <button type="button" class="link-btn" @click.stop="openEdit(item)">编辑</button>
                <button type="button" class="link-btn link-btn--danger" @click.stop="confirmDelete(item)">删除</button>
              </div>
            </template>
          </van-cell>
        </van-cell-group>
      </div>
    </van-popup>

    <!-- 新增 / 编辑 -->
    <van-popup v-model:show="showForm" position="bottom" round :style="{ minHeight: '50%' }">
      <div class="panel">
        <header class="panel-header">
          <strong>{{ isEditing ? '编辑汇率' : '添加汇率' }}</strong>
          <button type="button" class="header-action" @click="showForm = false">关闭</button>
        </header>

        <van-form @submit="saveRate">
          <van-cell-group inset>
            <SelectPickerField
              v-if="!isEditing"
              v-model="form.currency"
              label="源货币"
              :options="sourceCurrencyOptions"
              placeholder="请选择源货币"
              :rules="[{ required: true, message: '请选择源货币' }]"
              :error="currencyFieldError"
            />
            <van-cell v-else title="源货币" :value="sourceCurrencyLabel(form.currency)" />

            <van-field
              v-model="form.rate"
              label="汇率"
              type="text"
              inputmode="decimal"
              placeholder="如 7.1234"
              required
              :error-message="rateFieldError"
              @update:model-value="onRateInput"
            />

            <DatePickerField
              v-if="!isEditing"
              v-model="form.effective_date"
              label="生效日期"
              :rules="[{ required: true, message: '请选择生效日期' }]"
            />
            <van-cell v-else title="生效日期" :value="form.effective_date" />

            <van-cell title="目标货币" :value="quoteCurrency" />
          </van-cell-group>

          <div class="preview-card">
            <div class="preview-label">Beancount 预览</div>
            <code class="preview-code">{{ beancountPreview }}</code>
          </div>

          <div class="panel-submit">
            <van-button block type="primary" native-type="submit" :loading="saving" :disabled="saving">
              {{ saving ? '保存中' : '保存' }}
            </van-button>
          </div>
          <van-notice-bar
            v-if="saveError"
            color="var(--bm-expense)"
            background="var(--bm-danger-soft)"
          >
            {{ saveError }}
          </van-notice-bar>
        </van-form>
      </div>
    </van-popup>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useRouter } from 'vue-router'
import {
  exchangeRatesApi,
  type ExchangeRate,
} from '../../api/exchangeRates'
import { currenciesApi, type CurrencyItem } from '../../api/currencies'
import type { ApiError } from '../../api/client'
import DatePickerField from '../../components/DatePickerField.vue'
import SelectPickerField from '../../components/SelectPickerField.vue'
import { isValidAmount, normalizeAmountInput } from '../../utils/decimal'

const router = useRouter()
const quoteCurrency = ref('CNY')
const catalogCurrencies = ref<CurrencyItem[]>([])
const rates = ref<ExchangeRate[]>([])
const loading = ref(false)
const error = ref('')

const showDetail = ref(false)
const selectedRate = ref<ExchangeRate | null>(null)
const history = ref<ExchangeRate[]>([])
const historyLoading = ref(false)
const deleting = ref(false)

const showForm = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const saveError = ref('')
const rateFieldError = ref('')
const currencyFieldError = ref('')
const returnToDetailCurrency = ref('')

const form = reactive({
  currency: '',
  rate: '',
  effective_date: todayIso(),
})

const enabledSourceCodes = computed(() => {
  const quote = quoteCurrency.value.toUpperCase()
  return catalogCurrencies.value
    .filter((item) => item.enabled && item.code.toUpperCase() !== quote)
    .map((item) => item.code.toUpperCase())
})

const sourceCurrencyOptions = computed(() =>
  catalogCurrencies.value
    .filter((item) => item.enabled && item.code.toUpperCase() !== quoteCurrency.value.toUpperCase())
    .map((item) => ({
      text: `${item.code} - ${item.name}`,
      value: item.code.toUpperCase(),
    })),
)

const exampleRateItem = computed(() => {
  const preferred = rates.value.find((item) => item.currency.toUpperCase() === 'USD')
  return preferred || rates.value[0] || null
})

const exampleCurrency = computed(() => exampleRateItem.value?.currency || 'USD')
const exampleRate = computed(() => exampleRateItem.value?.rate || '—')

const beancountPreview = computed(() => {
  const datePart = form.effective_date || 'YYYY-MM-DD'
  const currency = form.currency || 'CURRENCY'
  const rate = form.rate || 'RATE'
  return `${datePart} price ${currency} ${rate} ${quoteCurrency.value}`
})

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function sourceCurrencyLabel(code: string) {
  const upper = code.toUpperCase()
  const item = catalogCurrencies.value.find((entry) => entry.code.toUpperCase() === upper)
  if (!item) return upper
  return `${item.code} - ${item.name}`
}

function defaultSourceCurrency() {
  const options = sourceCurrencyOptions.value
  const usd = options.find((option) => option.value === 'USD')
  return usd?.value || options[0]?.value || ''
}

function onRateInput(value: string) {
  form.rate = normalizeAmountInput(value)
  rateFieldError.value = ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [catalog, list] = await Promise.all([
      currenciesApi.list(true),
      exchangeRatesApi.getExchangeRates(quoteCurrency.value),
    ])
    catalogCurrencies.value = catalog
    const quote = quoteCurrency.value.toUpperCase()
    const enabledCodes = new Set(
      catalog
        .filter((item) => item.enabled && item.code.toUpperCase() !== quote)
        .map((item) => item.code.toUpperCase()),
    )
    rates.value = list.filter((item) => enabledCodes.has(item.currency.toUpperCase()))
  } catch (reason) {
    error.value = (reason as ApiError).message || '汇率加载失败'
  } finally {
    loading.value = false
  }
}

async function openDetail(rate: ExchangeRate) {
  selectedRate.value = rate
  showDetail.value = true
  historyLoading.value = true
  try {
    history.value = await exchangeRatesApi.getExchangeRateHistory(
      rate.currency,
      quoteCurrency.value,
    )
    if (history.value.length) {
      selectedRate.value = history.value[0]!
    }
  } catch (reason) {
    history.value = [rate]
    showToast((reason as ApiError).message || '历史加载失败')
  } finally {
    historyLoading.value = false
  }
}

function resetForm() {
  form.currency = defaultSourceCurrency()
  form.rate = ''
  form.effective_date = todayIso()
  isEditing.value = false
  saveError.value = ''
  rateFieldError.value = ''
  currencyFieldError.value = ''
}

function openCreate() {
  if (!sourceCurrencyOptions.value.length) {
    showToast('暂无可用外币，请先在币种管理中启用或新增')
    return
  }
  resetForm()
  showForm.value = true
}

function openCreateForCurrency(currency: string) {
  const code = currency.toUpperCase()
  if (!enabledSourceCodes.value.includes(code)) {
    showToast('该币种未在币种目录中启用')
    return
  }
  returnToDetailCurrency.value = code
  showDetail.value = false
  resetForm()
  form.currency = code
  showForm.value = true
}

function openEdit(rate: ExchangeRate) {
  const code = rate.currency.toUpperCase()
  resetForm()
  isEditing.value = true
  form.currency = code
  form.rate = rate.rate
  form.effective_date = rate.effective_date
  returnToDetailCurrency.value = code
  showDetail.value = false
  showForm.value = true
}

function validateForm(): boolean {
  rateFieldError.value = ''
  currencyFieldError.value = ''
  saveError.value = ''

  form.currency = (form.currency || '').toUpperCase()
  if (!form.currency) {
    currencyFieldError.value = '请选择源货币'
    return false
  }
  if (!enabledSourceCodes.value.includes(form.currency)) {
    currencyFieldError.value = '请选择币种目录中已启用的外币'
    return false
  }
  if (!form.rate || !isValidAmount(form.rate, { allowNegative: false, allowZero: false })) {
    rateFieldError.value = '请输入大于 0 的汇率'
    return false
  }
  if (!isEditing.value && !form.effective_date) {
    saveError.value = '请选择生效日期'
    return false
  }
  return true
}

async function saveRate() {
  if (saving.value) return
  if (!validateForm()) return

  saving.value = true
  saveError.value = ''
  const currencyToReturn = returnToDetailCurrency.value || form.currency
  try {
    if (isEditing.value) {
      await exchangeRatesApi.updateExchangeRate(
        form.currency,
        form.effective_date,
        { rate: form.rate },
        quoteCurrency.value,
      )
      showToast('汇率已更新')
    } else {
      await exchangeRatesApi.createExchangeRate({
        currency: form.currency,
        rate: form.rate,
        quote_currency: quoteCurrency.value,
        effective_date: form.effective_date,
      })
      showToast('汇率已添加')
    }

    showForm.value = false
    resetForm()
    await load()

    if (currencyToReturn) {
      const latest = rates.value.find((item) => item.currency === currencyToReturn)
      if (latest) {
        await openDetail(latest)
      }
      returnToDetailCurrency.value = ''
    }
  } catch (reason) {
    saveError.value = (reason as ApiError).message || '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

async function confirmDelete(rate: ExchangeRate) {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: `确定删除 ${rate.currency}/${rate.quote_currency}（${rate.effective_date}）的汇率吗？`,
    })
  } catch {
    return
  }

  deleting.value = true
  try {
    await exchangeRatesApi.deleteExchangeRate(
      rate.currency,
      rate.effective_date,
      quoteCurrency.value,
    )
    showToast('汇率已删除')
    await load()

    if (showDetail.value && selectedRate.value) {
      const currency = selectedRate.value.currency
      const remaining = await exchangeRatesApi.getExchangeRateHistory(
        currency,
        quoteCurrency.value,
      )
      history.value = remaining
      if (!remaining.length) {
        showDetail.value = false
        selectedRate.value = null
      } else {
        selectedRate.value = remaining[0]!
      }
    }
  } catch (reason) {
    showToast((reason as ApiError).message || '删除失败')
  } finally {
    deleting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.exchange-rates-page {
  padding-bottom: 24px;
}

.quote-card {
  margin: 0 0 12px;
  padding: 14px 16px;
  border: 1px solid var(--bm-primary-border);
  border-radius: var(--bm-radius);
  background: var(--bm-primary-soft);
  color: var(--bm-text);
}

.quote-card__title {
  font-size: 15px;
  font-weight: 600;
}

.quote-card__desc {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--bm-muted);
}

.rate-list {
  margin-top: 8px;
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

.panel-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px 4px;
}

.panel-subtitle {
  margin: 16px 16px 8px;
  font-size: 14px;
  font-weight: 600;
}

.history-actions {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}

.link-btn {
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--bm-primary);
  font-size: 13px;
}

.link-btn--danger {
  color: var(--bm-expense);
}

.preview-card {
  margin: 12px 16px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--bm-bg);
}

.preview-label {
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--bm-muted);
}

.preview-code {
  display: block;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  word-break: break-all;
  color: var(--bm-text);
}

.panel-submit {
  padding: 8px 16px 0;
}
</style>
