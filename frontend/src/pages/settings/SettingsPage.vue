<template>
  <section class="page settings-page">
    <header class="page-header"><h1>设置</h1></header>
    <div class="settings-brand">
      <strong>BeanMind</strong>
      <span>单机个人财务 · Beancount 真账本</span>
    </div>
    <h2 class="section-title">功能入口</h2>
    <van-cell-group inset class="page-section">
      <van-cell title="账户管理" label="查看 Assets / Liabilities 余额" is-link to="/accounts" />
      <van-cell title="周期记账" label="按规则生成记账模板" is-link to="/recurring" />
      <van-cell title="汇率" label="展示与换算参考" is-link to="/exchange-rates" />
      <van-cell title="高级报表" label="查看资产与收支报表" is-link to="/reports" />
    </van-cell-group>
    <h2 class="section-title">应用与系统</h2>
    <van-cell-group inset class="page-section">
      <SelectPickerField :model-value="ui.themeMode" label="主题" :options="themeOptions" @change="changeTheme" />
      <van-cell title="部署模式" value="单机 · 单账本 · 单写者" />
      <van-cell title="备份" value="由 NAS / 部署环境负责" />
      <van-cell title="LLM" :value="config?.llm_enabled ? config.llm_model || '已启用' : '未启用'" />
      <van-cell title="投影状态" :value="projectionStatus" />
    </van-cell-group>
    <aside class="finance-note">
      <strong>设计约束</strong>
      不提供身份、云端与应用内快照功能。Beancount 是交易真值，SQLite 投影可重建；投影 DIRTY 时不返回预算与统计。
    </aside>
    <van-empty v-if="error" image="error" :description="error"><van-button size="small" @click="load">重试</van-button></van-empty>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'; import apiClient, { type ApiError } from '../../api/client'; import { configApi, type PublicConfig } from '../../api/config'; import { useUIStore, type ThemeMode } from '../../stores/ui'; import SelectPickerField from '../../components/SelectPickerField.vue'
const ui=useUIStore();const config=ref<PublicConfig|null>(null);const projectionStatus=ref('读取中');const error=ref('')
const themeOptions=[{text:'亮色',value:'light'},{text:'暗色',value:'dark'},{text:'跟随系统',value:'auto'}]
async function load(){error.value='';try{config.value=await configApi.get();const projection=await apiClient.get('/api/transactions/projection/status') as {status:string};projectionStatus.value=projection.status}catch(reason){error.value=(reason as ApiError).message}}
function changeTheme(value:string){ui.setThemeMode(value as ThemeMode)}
onMounted(load)
</script>

<style scoped>
.settings-brand { display: grid; gap: 4px; margin: 26px 4px 6px; }
.settings-brand strong { font-size: 16px; }
.settings-brand span { color: var(--bm-muted); font-size: 13px; }
</style>
