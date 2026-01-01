<template>
    <f7-page name="exchange-rates">
        <f7-navbar>
            <f7-nav-left>
                <f7-link @click="goBack">
                    <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
                </f7-link>
            </f7-nav-left>
            <f7-nav-title>汇率管理</f7-nav-title>
            <f7-nav-right>
                <f7-link @click="showCreateModal = true">
                    <f7-icon ios="f7:plus" md="material:add" />
                </f7-link>
            </f7-nav-right>
        </f7-navbar>

        <!-- 主货币提示 -->
        <f7-block class="quote-currency-info">
            <div class="info-icon">💱</div>
            <div class="info-text">
                <strong>主货币：{{ quoteCurrency }}</strong>
                <p>以下汇率均表示对主货币的比率<br>例如：1 USD = {{ getDisplayRate('USD') }} CNY</p>
            </div>
        </f7-block>

        <!-- 加载状态 -->
        <div v-if="loading && exchangeRates.length === 0" class="loading-container">
            <f7-preloader></f7-preloader>
        </div>

        <!-- 空状态 -->
        <div v-else-if="exchangeRates.length === 0" class="empty-state">
            <div class="empty-icon">💰</div>
            <div class="empty-text">暂无汇率记录</div>
            <p class="empty-hint">点击右上角的 + 按钮添加汇率</p>
            <f7-button fill round @click="showCreateModal = true">
                添加汇率
            </f7-button>
        </div>

        <!-- 汇率列表 -->
        <f7-list v-else strong-ios dividers-ios inset class="exchange-rate-list">
            <f7-list-item v-for="rate in exchangeRates" :key="rate.currency" :title="rate.currency"
                :subtitle="`生效日期: ${formatDate(rate.effective_date)}`" swipeout @click="showRateDetail(rate)">
                <template #media>
                    <div class="currency-icon">
                        {{ getCurrencySymbol(rate.currency) }}
                    </div>
                </template>
                <template #after>
                    <span class="rate-value">{{ rate.rate }}</span>
                </template>
                <f7-swipeout-actions right>
                    <f7-swipeout-button color="blue" @click.stop="editRate(rate)">
                        编辑
                    </f7-swipeout-button>
                    <f7-swipeout-button color="red" @click.stop="confirmDeleteRate(rate)">
                        删除
                    </f7-swipeout-button>
                </f7-swipeout-actions>
            </f7-list-item>
        </f7-list>

        <!-- 创建汇率弹窗 -->
        <f7-popup :opened="showCreateModal" @popup:closed="onCreateModalClosed">
            <f7-page>
                <f7-navbar>
                    <f7-nav-left>
                        <f7-link @click="handleCreateModalBack">
                            <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
                        </f7-link>
                    </f7-nav-left>
                    <f7-nav-title>{{ isEditing ? '编辑汇率' : '添加汇率' }}</f7-nav-title>
                    <f7-nav-right>
                        <f7-link @click="handleSaveRate" :disabled="!canSave || saving">
                            {{ saving ? '保存中' : '保存' }}
                        </f7-link>
                    </f7-nav-right>
                </f7-navbar>

                <f7-list strong-ios dividers-ios inset>
                    <!-- 编辑模式或从详情页新增：源货币只读 -->
                    <f7-list-input v-if="isEditing || editFromDetail" label="源货币" type="text"
                        :value="`${newRate.currency} - ${getCurrencyName(newRate.currency)}`" readonly />

                    <!-- 从列表新增：可选择货币 -->
                    <f7-list-input v-else label="源货币" type="select" :value="newRate.currency"
                        @input="newRate.currency = $event.target.value">
                        <option value="" disabled>请选择货币</option>
                        <option v-for="curr in availableCurrencies" :key="curr" :value="curr">
                            {{ curr }} - {{ getCurrencyName(curr) }}
                        </option>
                    </f7-list-input>

                    <f7-list-input label="汇率" type="number" step="0.0001" placeholder="请输入汇率" :value="newRate.rate"
                        @input="newRate.rate = $event.target.value" info="表示 1 单位源货币 = 多少主货币" required />

                    <f7-list-input label="生效日期" type="text" :value="formatDateForDisplay(newRate.effective_date)"
                        readonly @click="openCalendar" placeholder="点击选择日期" />

                    <f7-list-item title="目标货币（主货币）" :after="quoteCurrency" />
                </f7-list>

                <f7-block v-if="saveError" class="error-block">
                    <p>{{ saveError }}</p>
                </f7-block>

                <!-- Beancount 格式预览 -->
                <f7-block-title>Beancount 格式预览</f7-block-title>
                <f7-block class="beancount-preview">
                    <code>{{ beancountPreview }}</code>
                </f7-block>
            </f7-page>
        </f7-popup>

        <!-- 汇率详情弹窗 -->
        <f7-popup :opened="showDetailModal" @popup:closed="showDetailModal = false">
            <f7-page v-if="selectedRate">
                <f7-navbar>
                    <f7-nav-left>
                        <f7-link popup-close>
                            <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
                        </f7-link>
                    </f7-nav-left>
                    <f7-nav-title>{{ selectedRate.currency }}/{{ selectedRate.quote_currency }}</f7-nav-title>
                    <f7-nav-right>
                        <f7-link @click="addNewRateForCurrency">
                            <f7-icon ios="f7:plus" md="material:add" />
                        </f7-link>
                    </f7-nav-right>
                </f7-navbar>

                <f7-block class="rate-detail-header">
                    <div class="rate-detail-icon">{{ getCurrencySymbol(selectedRate.currency) }}</div>
                    <div class="rate-detail-value">{{ selectedRate.rate }}</div>
                    <div class="rate-detail-pair">{{ selectedRate.currency_pair }}</div>
                </f7-block>

                <f7-list strong-ios dividers-ios inset>
                    <f7-list-item title="源货币" :after="selectedRate.currency" />
                    <f7-list-item title="目标货币" :after="selectedRate.quote_currency" />
                    <f7-list-item title="汇率" :after="selectedRate.rate" />
                    <f7-list-item title="生效日期" :after="formatDate(selectedRate.effective_date)" />
                </f7-list>

                <!-- 历史汇率 -->
                <f7-block-title v-if="rateHistory.length > 0">历史汇率（点击编辑，左滑删除）</f7-block-title>
                <f7-list v-if="rateHistory.length > 0" strong-ios dividers-ios inset>
                    <f7-list-item v-for="(rate, index) in rateHistory" :key="index"
                        :title="formatDate(rate.effective_date)" :after="rate.rate"
                        :class="{ 'current-rate': rate.effective_date === selectedRate?.effective_date }" link="#"
                        swipeout @click="editHistoryRate(rate)">
                        <f7-swipeout-actions right>
                            <f7-swipeout-button color="red" @click.stop="confirmDeleteHistoryRate(rate)">
                                删除
                            </f7-swipeout-button>
                        </f7-swipeout-actions>
                    </f7-list-item>
                </f7-list>

                <f7-block>
                    <f7-button fill color="red" @click="confirmDeleteRate(selectedRate)">
                        删除此汇率
                    </f7-button>
                </f7-block>
            </f7-page>
        </f7-popup>
    </f7-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { exchangeRatesApi, type ExchangeRate } from '../../api/exchangeRates'
import { f7 } from 'framework7-vue'

const router = useRouter()

// 状态
const loading = ref(false)
const saving = ref(false)
const exchangeRates = ref<ExchangeRate[]>([])
const quoteCurrency = ref('CNY')
const commonCurrencies = ref<string[]>([])

// 弹窗状态
const showCreateModal = ref(false)
const showDetailModal = ref(false)
const isEditing = ref(false)
const selectedRate = ref<ExchangeRate | null>(null)
const rateHistory = ref<ExchangeRate[]>([])

// 表单数据
const newRate = ref({
    currency: '',
    rate: '',
    effective_date: new Date().toISOString().split('T')[0]
})
const saveError = ref('')

// 可选货币列表（排除已有汇率的货币和主货币）
const availableCurrencies = computed(() => {
    const existingCurrencies = new Set(exchangeRates.value.map(r => r.currency))
    existingCurrencies.add(quoteCurrency.value)
    return commonCurrencies.value.filter(c => !existingCurrencies.has(c))
})

// 是否可以保存
const canSave = computed(() => {
    return newRate.value.currency && newRate.value.rate && parseFloat(newRate.value.rate) > 0
})

// Beancount 格式预览
const beancountPreview = computed(() => {
    if (!newRate.value.currency || !newRate.value.rate) {
        return '请填写完整信息'
    }
    const date = newRate.value.effective_date || new Date().toISOString().split('T')[0]
    return `${date} price ${newRate.value.currency} ${newRate.value.rate} ${quoteCurrency.value}`
})

// 货币符号映射
const currencySymbols: Record<string, string> = {
    CNY: '¥',
    USD: '$',
    EUR: '€',
    GBP: '£',
    JPY: '¥',
    HKD: '$',
    TWD: '$',
    SGD: '$',
    AUD: '$',
    CAD: '$',
    CHF: '₣',
    KRW: '₩'
}

// 货币名称映射
const currencyNames: Record<string, string> = {
    CNY: '人民币',
    USD: '美元',
    EUR: '欧元',
    GBP: '英镑',
    JPY: '日元',
    HKD: '港币',
    TWD: '新台币',
    SGD: '新加坡元',
    AUD: '澳元',
    CAD: '加元',
    CHF: '瑞士法郎',
    KRW: '韩元'
}

function getCurrencySymbol(currency: string): string {
    return currencySymbols[currency] || currency.charAt(0)
}

function getCurrencyName(currency: string): string {
    return currencyNames[currency] || currency
}

function formatDate(dateStr: string): string {
    const date = new Date(dateStr)
    return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    })
}

function getDisplayRate(currency: string): string {
    const rate = exchangeRates.value.find(r => r.currency === currency)
    return rate?.rate || '?'
}

async function loadExchangeRates() {
    loading.value = true
    try {
        exchangeRates.value = await exchangeRatesApi.getExchangeRates(quoteCurrency.value)
    } catch (error) {
        console.error('Failed to load exchange rates:', error)
        f7.toast.create({
            text: '加载汇率失败',
            position: 'center',
            closeTimeout: 2000
        }).open()
    } finally {
        loading.value = false
    }
}

async function loadCommonCurrencies() {
    try {
        commonCurrencies.value = await exchangeRatesApi.getCommonCurrencies()
    } catch (error) {
        console.error('Failed to load common currencies:', error)
        // 使用默认列表
        commonCurrencies.value = ['USD', 'EUR', 'GBP', 'JPY', 'HKD', 'TWD', 'SGD', 'AUD', 'CAD', 'CHF', 'KRW']
    }
}

function resetCreateForm() {
    showCreateModal.value = false
    isEditing.value = false
    editFromDetail.value = false
    editingCurrency.value = ''
    newRate.value = {
        currency: '',
        rate: '',
        effective_date: new Date().toISOString().split('T')[0]
    }
    saveError.value = ''
}

// 处理创建弹窗返回按钮点击
async function handleCreateModalBack() {
    const shouldReturnToDetail = editFromDetail.value
    const currencyToReturn = editingCurrency.value

    // 关闭创建弹窗
    showCreateModal.value = false

    // 如果是从详情页进入，返回详情页
    if (shouldReturnToDetail && currencyToReturn) {
        try {
            const rates = await exchangeRatesApi.getExchangeRateHistory(
                currencyToReturn,
                quoteCurrency.value
            )
            if (rates.length > 0) {
                selectedRate.value = rates[0]!
                rateHistory.value = rates
                showDetailModal.value = true
            }
        } catch (error) {
            console.error('Failed to load rate history:', error)
        }
    }

    // 重置表单状态
    isEditing.value = false
    editFromDetail.value = false
    editingCurrency.value = ''
    newRate.value = {
        currency: '',
        rate: '',
        effective_date: new Date().toISOString().split('T')[0]
    }
    saveError.value = ''
}

// 弹窗关闭时的回调（通过其他方式关闭时）
function onCreateModalClosed() {
    // 只重置表单状态，不处理返回逻辑（因为可能已经通过 handleCreateModalBack 处理过了）
    if (!showDetailModal.value) {
        isEditing.value = false
        editFromDetail.value = false
        editingCurrency.value = ''
        newRate.value = {
            currency: '',
            rate: '',
            effective_date: new Date().toISOString().split('T')[0]
        }
        saveError.value = ''
    }
}

async function handleSaveRate() {
    if (!canSave.value) return

    saving.value = true
    saveError.value = ''

    const currencyToReturn = editFromDetail.value ? editingCurrency.value : ''

    try {
        if (isEditing.value) {
            const effectiveDate = newRate.value.effective_date || new Date().toISOString().split('T')[0]!
            await exchangeRatesApi.updateExchangeRate(
                newRate.value.currency,
                effectiveDate,
                { rate: newRate.value.rate },
                quoteCurrency.value
            )
            f7.toast.create({
                text: '汇率更新成功',
                position: 'center',
                closeTimeout: 2000
            }).open()
        } else {
            await exchangeRatesApi.createExchangeRate({
                currency: newRate.value.currency,
                rate: newRate.value.rate,
                quote_currency: quoteCurrency.value,
                effective_date: newRate.value.effective_date
            })
            f7.toast.create({
                text: '汇率添加成功',
                position: 'center',
                closeTimeout: 2000
            }).open()
        }

        resetCreateForm()
        await loadExchangeRates()

        // 如果是从详情页编辑，返回到详情页
        if (currencyToReturn) {
            const latestRates = await exchangeRatesApi.getExchangeRateHistory(
                currencyToReturn,
                quoteCurrency.value
            )
            if (latestRates.length > 0) {
                selectedRate.value = latestRates[0]!
                rateHistory.value = latestRates
                showDetailModal.value = true
            }
        }
    } catch (err: any) {
        saveError.value = err.message || '保存失败，请重试'
    } finally {
        saving.value = false
    }
}

async function showRateDetail(rate: ExchangeRate) {
    selectedRate.value = rate
    showDetailModal.value = true

    // 加载历史汇率
    try {
        rateHistory.value = await exchangeRatesApi.getExchangeRateHistory(
            rate.currency,
            quoteCurrency.value
        )
    } catch (error) {
        console.error('Failed to load rate history:', error)
        rateHistory.value = [rate]
    }
}

function editRate(rate: ExchangeRate) {
    isEditing.value = true
    newRate.value = {
        currency: rate.currency,
        rate: rate.rate,
        effective_date: rate.effective_date
    }
    showCreateModal.value = true
}

// 记录编辑来源，用于保存后返回正确页面
const editFromDetail = ref(false)
const editingCurrency = ref('')

// 从详情页添加该币种的新汇率
function addNewRateForCurrency() {
    if (selectedRate.value) {
        editFromDetail.value = true
        editingCurrency.value = selectedRate.value.currency
        isEditing.value = false
        newRate.value = {
            currency: selectedRate.value.currency,
            rate: '',
            effective_date: new Date().toISOString().split('T')[0]
        }
        showDetailModal.value = false
        showCreateModal.value = true
    }
}

// 格式化日期用于显示
function formatDateForDisplay(dateStr: string | undefined): string {
    if (!dateStr) return ''
    return formatDate(dateStr)
}

// 打开日历控件
function openCalendar() {
    const calendarInstance = f7.calendar.create({
        inputEl: undefined,
        value: newRate.value.effective_date ? [new Date(newRate.value.effective_date)] : [new Date()],
        dateFormat: 'yyyy-mm-dd',
        closeOnSelect: true,
        header: true,
        headerPlaceholder: '选择生效日期',
        toolbarCloseText: '确定',
        monthNames: ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'],
        monthNamesShort: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
        dayNames: ['周日', '周一', '周二', '周三', '周四', '周五', '周六'],
        dayNamesShort: ['日', '一', '二', '三', '四', '五', '六'],
        on: {
            change: (_cal, value) => {
                const dates = value as Date[]
                if (dates && dates.length > 0) {
                    const date = dates[0]!
                    const year = date.getFullYear()
                    const month = String(date.getMonth() + 1).padStart(2, '0')
                    const day = String(date.getDate()).padStart(2, '0')
                    newRate.value.effective_date = `${year}-${month}-${day}`
                }
            }
        }
    })
    calendarInstance.open()
}

// 编辑历史汇率
function editHistoryRate(rate: ExchangeRate) {
    editFromDetail.value = true
    editingCurrency.value = rate.currency
    showDetailModal.value = false
    editRate(rate)
}

// 删除历史汇率
function confirmDeleteHistoryRate(rate: ExchangeRate) {
    f7.dialog.create({
        title: '确认删除',
        text: `确定要删除 ${formatDate(rate.effective_date)} 的汇率记录吗？`,
        buttons: [
            {
                text: '取消',
                color: 'gray'
            },
            {
                text: '确定',
                onClick: async () => {
                    try {
                        await exchangeRatesApi.deleteExchangeRate(
                            rate.currency,
                            rate.effective_date,
                            quoteCurrency.value
                        )
                        f7.toast.create({
                            text: '汇率已删除',
                            position: 'center',
                            closeTimeout: 2000
                        }).open()

                        // 重新加载历史汇率
                        if (selectedRate.value) {
                            rateHistory.value = await exchangeRatesApi.getExchangeRateHistory(
                                selectedRate.value.currency,
                                quoteCurrency.value
                            )
                            // 如果历史汇率为空，关闭详情弹窗
                            if (rateHistory.value.length === 0) {
                                showDetailModal.value = false
                            } else {
                                // 更新 selectedRate 为最新的汇率
                                selectedRate.value = rateHistory.value[0]!
                            }
                        }
                        await loadExchangeRates()
                    } catch (error: any) {
                        f7.toast.create({
                            text: error.message || '删除失败',
                            position: 'center',
                            closeTimeout: 2000
                        }).open()
                    }
                }
            }
        ]
    }).open()
}

function confirmDeleteRate(rate: ExchangeRate) {
    f7.dialog.create({
        title: '确认删除',
        text: `确定要删除 ${rate.currency}/${rate.quote_currency} (${formatDate(rate.effective_date)}) 的汇率记录吗？`,
        buttons: [
            {
                text: '取消',
                color: 'gray'
            },
            {
                text: '确定',
                onClick: async () => {
                    try {
                        await exchangeRatesApi.deleteExchangeRate(
                            rate.currency,
                            rate.effective_date,
                            quoteCurrency.value
                        )
                        f7.toast.create({
                            text: '汇率已删除',
                            position: 'center',
                            closeTimeout: 2000
                        }).open()

                        showDetailModal.value = false
                        await loadExchangeRates()
                    } catch (error: any) {
                        f7.toast.create({
                            text: error.message || '删除失败',
                            position: 'center',
                            closeTimeout: 2000
                        }).open()
                    }
                }
            }
        ]
    }).open()
}

function goBack() {
    router.back()
}

onMounted(() => {
    loadCommonCurrencies()
    loadExchangeRates()
})
</script>

<style scoped>
/* 主货币信息块 */
.quote-currency-info {
    display: flex;
    align-items: flex-start;
    background: linear-gradient(135deg, rgba(0, 122, 255, 0.08), rgba(88, 86, 214, 0.08));
    border-radius: 12px;
    padding: 16px;
    margin: 16px;
}

.info-icon {
    font-size: 32px;
    margin-right: 12px;
}

.info-text {
    flex: 1;
}

.info-text strong {
    font-size: 16px;
    color: var(--text-primary);
}

.info-text p {
    font-size: 13px;
    color: var(--text-secondary);
    margin: 4px 0 0 0;
    line-height: 1.4;
}

/* 加载状态 */
.loading-container {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 60px 0;
}

/* 空状态 */
.empty-state {
    text-align: center;
    padding: 60px 20px;
}

.empty-icon {
    font-size: 64px;
    margin-bottom: 16px;
}

.empty-text {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 8px;
}

.empty-hint {
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 24px;
}

/* 汇率列表 */
.exchange-rate-list {
    --f7-list-bg-color: var(--bg-secondary);
    --f7-list-item-title-text-color: var(--text-primary);
    --f7-list-item-after-text-color: var(--text-primary);
    --f7-list-item-border-color: var(--separator);
}

:deep(.list .item-content) {
    background-color: var(--bg-secondary);
}

:deep(.list strong) {
    background-color: var(--bg-secondary);
}

/* 货币图标 */
.currency-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: linear-gradient(135deg, var(--ios-blue), var(--ios-purple));
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 700;
}

/* 汇率值 */
.rate-value {
    font-size: 17px;
    font-weight: 600;
    color: var(--ios-blue);
}

/* 错误块 */
.error-block {
    background: rgba(255, 59, 48, 0.12);
    color: var(--ios-red);
    padding: 16px;
    border-radius: 8px;
    margin: 16px;
}

.error-block p {
    margin: 0;
    font-size: 14px;
    font-weight: 500;
}

/* Beancount 预览 */
.beancount-preview {
    background: var(--bg-secondary);
    border-radius: 8px;
    padding: 16px;
    margin: 0 16px;
}

.beancount-preview code {
    font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
    font-size: 14px;
    color: var(--ios-green);
    word-break: break-all;
}

/* 汇率详情头部 */
.rate-detail-header {
    text-align: center;
    padding: 24px 16px;
}

.rate-detail-icon {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: linear-gradient(135deg, var(--ios-blue), var(--ios-purple));
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    font-weight: 700;
    margin: 0 auto 16px;
}

.rate-detail-value {
    font-size: 36px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.rate-detail-pair {
    font-size: 16px;
    color: var(--text-secondary);
}

/* 当前汇率高亮 */
.current-rate {
    background: rgba(0, 122, 255, 0.08);
}

.current-rate :deep(.item-title) {
    font-weight: 600;
    color: var(--ios-blue);
}

/* 历史汇率列表样式 */
:deep(.item-title) {
    color: var(--text-primary);
}

:deep(.item-after) {
    color: var(--text-primary);
}
</style>
