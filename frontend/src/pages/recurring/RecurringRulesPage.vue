<template>
  <f7-page name="recurring-rules">
    <f7-navbar>
      <f7-nav-left>
        <f7-link @click="goBack">
          <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
        </f7-link>
      </f7-nav-left>
      <f7-nav-title>周期记账</f7-nav-title>
      <f7-nav-right>
        <f7-link @click="openAIContext">
          <f7-icon ios="f7:sparkles" md="material:auto_awesome" />
        </f7-link>
        <f7-link @click="goToAddRule">
          <f7-icon ios="f7:plus" md="material:add" />
        </f7-link>
      </f7-nav-right>
    </f7-navbar>

    <div class="filter-section">
      <f7-segmented strong tag="div">
        <f7-button :active="activeTab === 'rules'" @click="activeTab = 'rules'">规则列表</f7-button>
        <f7-button :active="activeTab === 'history'" @click="switchToHistory">执行日志</f7-button>
      </f7-segmented>
    </div>

    <!-- 规则列表视图 -->
    <div v-if="activeTab === 'rules'">
      <!-- 加载中 -->
      <f7-block v-if="loading && rules.length === 0" class="text-align-center">
        <f7-preloader />
        <p>加载中...</p>
      </f7-block>

      <!-- 空状态 -->
      <f7-block v-else-if="!loading && rules.length === 0" class="empty-state">
        <div class="empty-icon">🔄</div>
        <div class="empty-text">暂无周期记账规则</div>
        <f7-button fill round @click="goToAddRule" class="empty-action-btn">
          创建规则
        </f7-button>
      </f7-block>

      <!-- 规则列表 -->
      <f7-list v-else media-list inset strong dividers-ios>
        <f7-list-item v-for="rule in rules" :key="rule.id" link="#" swipeout @click="showRuleDetails(rule)">
          <template #media>
            <div class="rule-icon" :class="{ inactive: !rule.is_active }">
              <f7-icon ios="f7:arrow_2_circlepath" md="material:autorenew" />
            </div>
          </template>

          <template #title>
            <div class="rule-title">{{ rule.name }}</div>
          </template>

          <template #subtitle>
            <div class="rule-info">{{ formatFrequency(rule) }}</div>
          </template>

          <template #text>
            <div class="rule-desc">{{ formatTemplate(rule) }}</div>
          </template>

          <template #after>
            <f7-chip v-if="!rule.is_active" text="已停用" color="gray" />
          </template>

          <f7-swipeout-actions right>
            <f7-swipeout-button color="blue" @click.stop="toggleRule(rule)">
              {{ rule.is_active ? '停用' : '启用' }}
            </f7-swipeout-button>
            <f7-swipeout-button color="orange" @click.stop="editRule(rule)">
              编辑
            </f7-swipeout-button>
            <f7-swipeout-button color="red" @click.stop="deleteRule(rule)">
              删除
            </f7-swipeout-button>
          </f7-swipeout-actions>
        </f7-list-item>
      </f7-list>
    </div>

    <!-- 执行日志视图 -->
    <div v-if="activeTab === 'history'">
      <!-- 加载中 -->
      <f7-block v-if="loadingHistory && executions.length === 0" class="text-align-center">
        <f7-preloader />
        <p>加载日志中...</p>
      </f7-block>

      <!-- 空状态 -->
      <f7-block v-else-if="!loadingHistory && executions.length === 0" class="empty-state">
        <div class="empty-icon">📝</div>
        <div class="empty-text">暂无执行记录</div>
      </f7-block>

      <!-- 日志列表 -->
      <f7-list v-else media-list inset strong dividers-ios>
        <f7-list-item v-for="execution in executions" :key="execution.id">
          <template #title>
            <div class="rule-title">{{ getRuleName(execution.rule_id) }}</div>
          </template>
          <template #subtitle>
            <div class="rule-info">{{ execution.execution_date }}</div>
          </template>
          <template #footer>
            <div class="rule-desc">{{ execution.created_at ? new Date(execution.created_at).toLocaleString() : '' }}
            </div>
          </template>

          <template #media>
            <div class="execution-icon" :class="execution.status.toLowerCase()">
              <f7-icon v-if="execution.status === 'SUCCESS'" ios="f7:checkmark_circle_fill"
                md="material:check_circle" />
              <f7-icon v-else ios="f7:xmark_circle_fill" md="material:error" />
            </div>
          </template>
          <template #after>
            <f7-chip :text="execution.status === 'SUCCESS' ? '成功' : '失败'"
              :color="execution.status === 'SUCCESS' ? 'green' : 'red'" />
          </template>
        </f7-list-item>
      </f7-list>
    </div>

    <!-- 规则详情弹窗 -->
    <f7-sheet :opened="showDetailSheet" @sheet:closed="showDetailSheet = false" class="rule-detail-sheet" swipe-to-close
      backdrop>
      <f7-page-content v-if="selectedRule">
        <div class="sheet-handle" />
        <f7-block-title class="margin-top">{{ selectedRule.name }}</f7-block-title>

        <f7-list inset strong>
          <f7-list-item title="频率" :after="formatFrequency(selectedRule)" />
          <f7-list-item title="状态" :after="selectedRule.is_active ? '启用' : '停用'" />
          <f7-list-item title="开始日期" :after="formatDate(selectedRule.start_date)" />
          <f7-list-item v-if="selectedRule.end_date" title="结束日期" :after="formatDate(selectedRule.end_date)" />
        </f7-list>

        <f7-block-title>交易明细</f7-block-title>
        <f7-list inset strong>
          <f7-list-item v-for="(posting, index) in selectedRule.transaction_template.postings" :key="index"
            :title="formatAccountName(posting.account)" :after="formatAmount(posting.amount, posting.currency)" />
        </f7-list>

        <f7-block class="action-buttons">
          <div class="button-row">
            <div class="button-col">
              <f7-button fill @click="executeRuleNow">
                <f7-icon ios="f7:play_fill" md="material:play_arrow" />
                立即执行
              </f7-button>
            </div>
            <div class="button-col">
              <f7-button fill color="blue" @click="editSelectedRule">
                <f7-icon ios="f7:pencil" md="material:edit" />
                编辑规则
              </f7-button>
            </div>
          </div>
        </f7-block>
      </f7-page-content>
    </f7-sheet>
  </f7-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { f7 } from 'framework7-vue'
import { recurringApi, type RecurringRule, type RecurringExecution } from '../../api/recurring'

const router = useRouter()
const activeTab = ref('rules')
const loading = ref(false)
const loadingHistory = ref(false)
const rules = ref<RecurringRule[]>([])
const executions = ref<RecurringExecution[]>([])
const showDetailSheet = ref(false)
const selectedRule = ref<RecurringRule | null>(null)

const weekdays = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' }
]

function openAIContext() {
  router.push({
    path: '/ai',
    query: {
      prompt: selectedRule.value
        ? `解释一下周期规则「${selectedRule.value.name}」并检查是否需要调整`
        : '解释一下当前周期规则设置，并给出优化建议',
      source_page: '/recurring',
      selected_entity_id: selectedRule.value?.id,
    }
  })
}

function formatFrequency(rule: RecurringRule): string {
  const frequencies: Record<string, string> = {
    daily: '每日',
    weekly: '每周',
    biweekly: '双周',
    monthly: '每月',
    yearly: '每年'
  }

  let base = frequencies[rule.frequency] || rule.frequency

  if (rule.frequency === 'weekly' || rule.frequency === 'biweekly') {
    if (rule.frequency_config?.weekdays?.length) {
      const days = rule.frequency_config.weekdays.map(d => {
        const day = weekdays.find(w => w.value === d)
        return day ? day.label : d
      })
      base += ` (${days.join(', ')})`
    }
  } else if (rule.frequency === 'monthly') {
    if (rule.frequency_config?.month_days?.length) {
      const days = rule.frequency_config.month_days.map(d => d === -1 ? '月末' : `${d}日`)
      base += ` (${days.join(', ')})`
    }
  }

  return base
}

function formatTemplate(rule: RecurringRule): string {
  if (!rule.transaction_template) return ''
  return rule.transaction_template.description || ''
}

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function formatAccountName(account: string): string {
  if (!account) return ''
  const parts = account.split(':')
  return parts.length > 1 ? parts.slice(1).join(':') : account
}

function formatAmount(amount: number, currency: string): string {
  const sign = amount >= 0 ? '+' : ''
  return `${sign}${amount.toFixed(2)} ${currency}`
}

function getRuleName(ruleId: string | number): string {
  const rule = rules.value.find(r => r.id === ruleId)
  return rule ? rule.name : `规则 ID: ${ruleId}`
}

function goBack() {
  router.back()
}

function goToAddRule() {
  router.push('/recurring/add')
}

function switchToHistory() {
  activeTab.value = 'history'
  loadExecutions()
}

async function loadRules() {
  loading.value = true
  try {
    rules.value = await recurringApi.getRules()
  } catch (error: any) {
    f7.toast.show({ text: error.message || '加载规则失败', position: 'center', closeTimeout: 2000 })
  } finally {
    loading.value = false
  }
}

async function loadExecutions() {
  loadingHistory.value = true
  try {
    executions.value = await recurringApi.getExecutions()
    // 确保规则也加载了，以便显示名称
    if (rules.value.length === 0) {
      await loadRules()
    }
  } catch (error: any) {
    f7.toast.show({ text: error.message || '加载日志失败', position: 'center', closeTimeout: 2000 })
  } finally {
    loadingHistory.value = false
  }
}

function showRuleDetails(rule: RecurringRule) {
  selectedRule.value = rule
  showDetailSheet.value = true
}

async function toggleRule(rule: RecurringRule) {
  try {
    await recurringApi.updateRule(rule.id, {
      is_active: !rule.is_active
    })
    rule.is_active = !rule.is_active
    f7.toast.show({
      text: rule.is_active ? '已启用' : '已停用',
      position: 'center',
      closeTimeout: 1500
    })
  } catch (error: any) {
    f7.toast.show({ text: error.message || '操作失败', position: 'center', closeTimeout: 2000 })
  }
}

function editRule(rule: RecurringRule) {
  router.push(`/recurring/${rule.id}/edit`)
}

function editSelectedRule() {
  if (selectedRule.value) {
    showDetailSheet.value = false
    router.push(`/recurring/${selectedRule.value.id}/edit`)
  }
}

async function deleteRule(rule: RecurringRule) {
  f7.dialog.create({
    title: '删除确认',
    text: '确定要删除该规则吗？',
    buttons: [
      {
        text: '取消',
        color: 'gray'
      },
      {
        text: '确定',
        onClick: async () => {
          try {
            await recurringApi.deleteRule(rule.id)
            rules.value = rules.value.filter(r => r.id !== rule.id)
            f7.toast.show({ text: '删除成功', position: 'center', closeTimeout: 1500 })
          } catch (error: any) {
            f7.toast.show({ text: error.message || '删除失败', position: 'center', closeTimeout: 2000 })
          }
        }
      }
    ]
  }).open()
}

async function executeRuleNow() {
  if (!selectedRule.value) return

  const today = new Date().toISOString().split('T')[0] as string

  try {
    await recurringApi.executeRule(selectedRule.value.id, today)
    f7.toast.show({
      text: `规则 "${selectedRule.value.name}" 已执行`,
      position: 'center',
      closeTimeout: 2000
    })
    showDetailSheet.value = false
    // If in history tab, reload
    if (activeTab.value === 'history') {
      loadExecutions()
    }
  } catch (error: any) {
    f7.toast.show({ text: error.message || '执行失败', position: 'center', closeTimeout: 2000 })
  }
}

onMounted(() => {
  loadRules()
})
</script>

<style scoped>
.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 16px;
  color: var(--f7-list-item-after-text-color);
  margin-bottom: 24px;
}

.empty-action-btn {
  max-width: 200px;
  margin: 0 auto;
}

.rule-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.rule-icon.inactive {
  background: var(--f7-list-item-after-text-color);
}

.execution-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.execution-icon.success {
  color: var(--f7-color-green);
}

.execution-icon.failed {
  color: var(--f7-color-red);
}

.rule-detail-sheet {
  height: auto;
  max-height: 70vh;
}

.sheet-handle {
  width: 36px;
  height: 5px;
  background: var(--f7-list-item-after-text-color);
  border-radius: 3px;
  margin: 8px auto 0;
}

.action-buttons {
  padding-bottom: 20px;
}

.button-row {
  display: flex;
  gap: 12px;
}

.button-col {
  flex: 1;
}

.action-buttons .button {
  justify-content: center;
  gap: 8px;
}

.filter-section {
  padding: 16px;
  background: var(--f7-page-bg-color);
  position: sticky;
  top: 0;
  z-index: 100;
}

/* Custom styles for list content */
.rule-title {
  font-weight: 600;
  color: var(--f7-text-color);
}

.rule-info {
  font-size: 14px;
  color: var(--f7-list-item-footer-text-color);
}

.rule-desc {
  font-size: 14px;
  color: var(--f7-list-item-text-text-color);
}

/* Dark mode overrides */
@media (prefers-color-scheme: dark) {
  .rule-title {
    color: #fff;
  }

  .rule-info {
    color: rgba(255, 255, 255, 0.7);
  }

  .rule-desc {
    color: rgba(255, 255, 255, 0.55);
  }
}

:global(.theme-dark) .rule-title,
:global(.dark) .rule-title {
  color: #fff;
}

:global(.theme-dark) .rule-info,
:global(.dark) .rule-info {
  color: rgba(255, 255, 255, 0.7);
}

:global(.theme-dark) .rule-desc,
:global(.dark) .rule-desc {
  color: rgba(255, 255, 255, 0.55);
}
</style>

/* Fix for Rule Details Sheet in Dark Mode */
:global(.theme-dark) .rule-detail-sheet .item-title,
:global(.dark) .rule-detail-sheet .item-title,
:global(.theme-dark) .rule-detail-sheet .block-title,
:global(.dark) .rule-detail-sheet .block-title {
color: #fff !important;
}

:global(.theme-dark) .rule-detail-sheet .item-after,
:global(.dark) .rule-detail-sheet .item-after {
color: rgba(255, 255, 255, 0.7) !important;
}
