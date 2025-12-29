<template>
  <f7-app v-bind="f7params">
    <f7-view main class="safe-areas">
      <router-view />
    </f7-view>
  </f7-app>
</template>

<script setup lang="ts">
import { f7App, f7View } from 'framework7-vue';
import { onMounted } from 'vue';
import { useUIStore } from './stores/ui';

const f7params = {
  name: 'BeanMind',
  theme: 'auto',
  darkMode: 'auto',
};

// 初始化主题
onMounted(() => {
  const uiStore = useUIStore();
  uiStore.initTheme();
});
</script>

<style>
:root {
  /* iOS 系统颜色 */
  --ios-blue: #007aff;
  --ios-green: #34c759;
  --ios-red: #ff3b30;
  --ios-orange: #ff9500;
  --ios-purple: #5856d6;

  /* 浅色模式（默认） */
  --bg-primary: #f2f2f7;
  --bg-secondary: #ffffff;
  --bg-tertiary: #f2f2f7;
  --text-primary: #000000;
  --text-secondary: #8e8e93;
  --separator: #c6c6c8;
}

/* 暗黑模式 - 通过类名控制 */
html.theme-dark {
  --ios-blue: #0a84ff;
  --ios-green: #30d158;
  --ios-red: #ff453a;
  --ios-orange: #ff9f0a;
  --ios-purple: #5e5ce6;

  --bg-primary: #000000;
  --bg-secondary: #1c1c1e;
  --bg-tertiary: #2c2c2e;
  --text-primary: #ffffff;
  --text-secondary: #8e8e93;
  --separator: #38383a;
}

/* 亮色模式 - 通过类名控制 */
html.theme-light {
  --ios-blue: #007aff;
  --ios-green: #34c759;
  --ios-red: #ff3b30;
  --ios-orange: #ff9500;
  --ios-purple: #5856d6;

  --bg-primary: #f2f2f7;
  --bg-secondary: #ffffff;
  --bg-tertiary: #f2f2f7;
  --text-primary: #000000;
  --text-secondary: #8e8e93;
  --separator: #c6c6c8;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  -webkit-tap-highlight-color: transparent;
}

html {
  -webkit-text-size-adjust: 100%;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display',
    'Helvetica Neue', Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.022em;
}

#app {
  min-height: 100vh;
}

/* iOS 安全区域 */
@supports (padding: env(safe-area-inset-bottom)) {
  body {
    padding-bottom: env(safe-area-inset-bottom);
  }
}

/* 全局覆盖 Framework7 Smart Select Sheet 样式 (暗黑模式适配) */
.smart-select-sheet .sheet-modal-inner {
  background-color: var(--bg-secondary) !important;
}

.smart-select-sheet .toolbar {
  background-color: var(--bg-tertiary) !important;
}

.smart-select-sheet .toolbar .title {
  color: var(--text-primary) !important;
}

.smart-select-sheet .list {
  background-color: transparent !important;
}

.smart-select-sheet .item-content {
  background-color: transparent !important;
}

.smart-select-sheet .item-title {
  color: var(--text-primary) !important;
}

.smart-select-sheet .checkbox i,
.smart-select-sheet .icon-radio {
  border-color: var(--separator) !important;
}
</style>
