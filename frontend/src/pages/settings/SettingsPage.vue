<template>
  <div class="settings-page">
    <div class="page-header">
      <h1>更多</h1>
    </div>

    <f7-list inset strong>
      <f7-list-item link="#" title="报表" @click="navigateTo('/reports')">
        <template #media>
          <f7-icon ios="f7:chart_bar_fill" md="material:bar_chart" color="blue"></f7-icon>
        </template>
      </f7-list-item>

      <f7-list-item link="#" title="周期记账" @click="navigateTo('/recurring/rules')">
        <template #media>
          <f7-icon ios="f7:arrow_2_circlepath" md="material:autorenew" color="purple"></f7-icon>
        </template>
      </f7-list-item>
    </f7-list>

    <f7-block-title class="section-title">系统设置</f7-block-title>
    <f7-list inset strong>
      <f7-list-item link="#" title="账户管理" @click="navigateTo('/accounts')">
        <template #media>
          <f7-icon ios="f7:creditcard_fill" md="material:account_balance_wallet" color="green"></f7-icon>
        </template>
      </f7-list-item>

      <f7-list-item link="#" title="汇率管理" @click="navigateTo('/exchange-rates')">
        <template #media>
          <f7-icon ios="f7:arrow_right_arrow_left_circle_fill" md="material:currency_exchange" color="teal"></f7-icon>
        </template>
      </f7-list-item>
    </f7-list>

    <f7-block-title class="section-title">外观</f7-block-title>
    <f7-list inset strong>
      <f7-list-item title="主题模式" smart-select :smart-select-params="{ openIn: 'sheet', closeOnSelect: true }">
        <template #media>
          <f7-icon ios="f7:paintbrush_fill" md="material:palette" color="orange"></f7-icon>
        </template>
        <select v-model="currentTheme" @change="onThemeChange">
          <option value="light">亮色</option>
          <option value="dark">暗黑</option>
          <option value="auto">跟随系统</option>
        </select>
      </f7-list-item>
    </f7-list>

    <f7-block-title class="section-title">其他</f7-block-title>
    <f7-list inset strong>
      <f7-list-item link="#" title="关于" @click="showVersionInfo">
        <template #media>
          <f7-icon ios="f7:info_circle_fill" md="material:info" color="gray"></f7-icon>
        </template>
        <template #after>
          <span class="version-badge">{{ appVersion }}</span>
        </template>
      </f7-list-item>
    </f7-list>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { f7List, f7ListItem, f7Icon, f7BlockTitle, f7 } from 'framework7-vue';
import { useUIStore, type ThemeMode } from '../../stores/ui';
import { ref, onMounted, watch } from 'vue';

const router = useRouter();
const uiStore = useUIStore();

// 应用版本
const appVersion = ref('1.0.0');

// 当前主题
const currentTheme = ref<ThemeMode>(uiStore.themeMode);

// 同步主题状态
onMounted(() => {
  currentTheme.value = uiStore.themeMode;
});

// 监听主题变化
watch(() => uiStore.themeMode, (newVal) => {
  currentTheme.value = newVal;
});

function onThemeChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  const mode = target.value as ThemeMode;
  uiStore.setThemeMode(mode);
}

function showVersionInfo() {
  const content = `
    <div style="text-align: center; margin-bottom: 10px;">
      <p><b>BeanMind 智能记账</b></p>
      <p style="color: var(--f7-text-color-secondary); font-size: 14px;">
        您的个人财务智能助手，让记账更简单、更专业。
      </p>
    </div>
    <div style="text-align: center; font-size: 13px; color: var(--f7-label-color);">
      版本: v${appVersion.value}<br>
    </div>
  `;
  f7.dialog.alert(content, '');
}

function navigateTo(path: string) {
  // 标记需要恢复 Tab 状态，以便从目标页面返回时能回到正确的 Tab
  uiStore.markForTabRestore();
  router.push(path);
}
</script>

<style scoped>
.settings-page {
  padding-bottom: 20px;
}

.page-header {
  padding: 20px 20px 0;
}


.page-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 10px 0;
}

.section-title {
  margin-top: 24px;
  color: #8e8e93;
  /* 保持 Framework7 默认的灰色，或者用 var(--text-secondary) */
}

/* 覆盖 Framework7 列表样式以适配暗黑模式 */
:deep(.list) {
  --f7-list-bg-color: var(--bg-secondary);
  --f7-list-item-title-text-color: var(--text-primary);
  --f7-list-item-after-text-color: #8e8e93;
  --f7-list-item-border-color: var(--separator);
}

:deep(.list .item-content) {
  background-color: var(--bg-secondary);
}

:deep(.list.inset) {
  background-color: transparent;
}

:deep(.list strong) {
  background-color: var(--bg-secondary);
}

.version-badge {
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-secondary);
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
}

@media (prefers-color-scheme: dark) {
  .version-badge {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
  }
}
</style>
