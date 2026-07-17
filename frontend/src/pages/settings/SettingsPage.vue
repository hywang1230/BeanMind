<template>
  <section class="page settings-page">
    <header class="page-header"><h1>设置</h1></header>
    <van-cell-group inset class="page-section">
      <van-cell title="账户管理" is-link to="/accounts" />
      <van-cell title="周期记账" is-link to="/recurring" />
      <van-cell title="汇率" is-link to="/exchange-rates" />
      <van-cell title="高级报表" is-link to="/reports" />
    </van-cell-group>
    <van-cell-group inset class="page-section">
      <van-cell title="主题">
        <template #value><select :value="ui.themeMode" class="native-select" @change="changeTheme"><option value="light">亮色</option><option value="dark">暗色</option><option value="auto">跟随系统</option></select></template>
      </van-cell>
      <van-cell title="部署模式" value="单机 · 单账本 · 单写者" />
      <van-cell title="备份" value="由 NAS / 部署环境负责" />
      <van-cell title="LLM" :value="config?.llm_enabled ? config.llm_model || '已启用' : '未启用'" />
      <van-cell title="投影状态" :value="projectionStatus" />
    </van-cell-group>
    <van-empty v-if="error" image="error" :description="error"><van-button size="small" @click="load">重试</van-button></van-empty>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'; import apiClient, { type ApiError } from '../../api/client'; import { configApi, type PublicConfig } from '../../api/config'; import { useUIStore, type ThemeMode } from '../../stores/ui'
const ui=useUIStore();const config=ref<PublicConfig|null>(null);const projectionStatus=ref('读取中');const error=ref('')
async function load(){error.value='';try{config.value=await configApi.get();const projection=await apiClient.get('/api/transactions/projection/status') as {status:string};projectionStatus.value=projection.status}catch(reason){error.value=(reason as ApiError).message}}
function changeTheme(event:Event){ui.setThemeMode((event.target as HTMLSelectElement).value as ThemeMode)}
onMounted(load)
</script>
