<template>
  <f7-app v-bind="f7params">
    <f7-view main class="safe-areas">
      <router-view />
    </f7-view>
  </f7-app>
</template>

<script setup lang="ts">
import { f7App, f7View } from 'framework7-vue';

const f7params = {
  name: 'BeanMind',
  theme: 'auto',
  darkMode: 'auto',
};
</script>

<style>
:root {
  /* iOS 系统颜色 */
  --ios-blue: #007aff;
  --ios-green: #34c759;
  --ios-red: #ff3b30;
  --ios-orange: #ff9500;
  --ios-purple: #5856d6;
  
  /* 浅色模式 */
  --bg-primary: #f2f2f7;
  --bg-secondary: #ffffff;
  --bg-tertiary: #f2f2f7;
  --text-primary: #000000;
  --text-secondary: #8e8e93;
  --separator: #c6c6c8;
}

@media (prefers-color-scheme: dark) {
  :root {
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
</style>
