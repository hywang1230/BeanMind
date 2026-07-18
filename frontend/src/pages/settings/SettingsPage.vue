<template>
  <section class="page settings-page">
    <header class="page-header"><h1>设置</h1></header>
    <div class="settings-brand">
      <strong>BeanMind</strong>
    </div>
    <h2 class="section-title">功能入口</h2>
    <van-cell-group inset class="page-section">
      <van-cell title="账户管理" label="查看 Assets / Liabilities 余额" is-link to="/accounts" />
      <van-cell title="周期记账" label="按规则生成记账模板" is-link to="/recurring" />
      <van-cell title="币种管理" label="维护可选币种目录" is-link to="/currencies" />
      <van-cell title="汇率" label="查看与管理美元汇率" is-link to="/exchange-rates" />
      <van-cell title="高级报表" label="查看资产与收支报表" is-link to="/reports" />
    </van-cell-group>
    <h2 class="section-title">应用与系统</h2>
    <van-cell-group inset class="page-section">
      <van-cell title="主题" :value="themeLabel" is-link @click="openThemePicker" />
      <van-cell title="LLM" :value="config?.llm_enabled ? config.llm_model || '已启用' : '未启用'" />
      <van-cell title="账本状态" :value="ledgerStatusText" />
      <van-cell title="版本" :value="appVersion" />
    </van-cell-group>
    <van-empty v-if="error" image="error" :description="error"><van-button size="small" @click="load">重试</van-button></van-empty>
    <van-popup v-model:show="showThemePicker" position="bottom" round>
      <van-picker
        v-model="themePickerValues"
        title="选择主题"
        :columns="themeOptions"
        @confirm="confirmTheme"
        @cancel="showThemePicker = false"
      />
    </van-popup>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import apiClient, { type ApiError } from '../../api/client'
import { configApi, type PublicConfig } from '../../api/config'
import { useUIStore, type ThemeMode } from '../../stores/ui'

/** 与 backend/main.py FastAPI version 保持一致 */
const appVersion = '3.0.0'

const ui = useUIStore()
const config = ref<PublicConfig | null>(null)
const ledgerStatus = ref('LOADING')
const error = ref('')
const showThemePicker = ref(false)
const themePickerValues = ref<Array<string | number>>([ui.themeMode])
const themeOptions = [
  { text: '亮色', value: 'light' },
  { text: '暗色', value: 'dark' },
  { text: '跟随系统', value: 'auto' },
]

const themeLabel = computed(
  () => themeOptions.find((option) => option.value === ui.themeMode)?.text || '',
)

const ledgerStatusText = computed(() => {
  const labels: Record<string, string> = {
    LOADING: '读取中',
    READY: '正常',
    DIRTY: '未就绪',
  }
  return labels[ledgerStatus.value] ?? ledgerStatus.value
})

async function load() {
  error.value = ''
  ledgerStatus.value = 'LOADING'
  try {
    config.value = await configApi.get()
    const projection = (await apiClient.get('/api/transactions/projection/status')) as { status: string }
    ledgerStatus.value = projection.status
  } catch (reason) {
    error.value = (reason as ApiError).message
  }
}

function openThemePicker() {
  themePickerValues.value = [ui.themeMode]
  showThemePicker.value = true
}

function confirmTheme({ selectedValues }: { selectedValues: Array<string | number> }) {
  ui.setThemeMode(String(selectedValues[0] ?? 'auto') as ThemeMode)
  showThemePicker.value = false
}

onMounted(load)
</script>

<style scoped>
.settings-brand {
  margin: 26px 4px 6px;
}
.settings-brand strong {
  font-size: 16px;
}
</style>
