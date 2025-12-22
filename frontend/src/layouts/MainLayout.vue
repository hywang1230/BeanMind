<template>
  <div class="main-layout">
    <!-- 页面内容区域 -->
    <div class="page-content-wrapper">
      <router-view />
    </div>
    
    <!-- 底部导航栏 - Framework7 Tabbar Icons 风格 -->
    <div class="tabbar-wrapper">
      <div class="tabbar tabbar-icons">
        <router-link 
          v-for="tab in tabs" 
          :key="tab.path"
          :to="tab.path"
          class="tab-link"
          :class="{ 'tab-link-active': isActiveTab(tab.path) }"
        >
          <div class="tab-icon">
            <!-- 首页图标 -->
            <svg v-if="tab.icon === 'house'" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              <polyline points="9 22 9 12 15 12 15 22"></polyline>
            </svg>
            <!-- 流水图标 -->
            <svg v-if="tab.icon === 'list'" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="16" y1="2" x2="16" y2="6"></line>
              <line x1="8" y1="2" x2="8" y2="6"></line>
              <line x1="3" y1="10" x2="21" y2="10"></line>
            </svg>
            <!-- 报表图标 -->
            <svg v-if="tab.icon === 'chart'" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="20" x2="18" y2="10"></line>
              <line x1="12" y1="20" x2="12" y2="4"></line>
              <line x1="6" y1="20" x2="6" y2="14"></line>
            </svg>
            <!-- 设置图标 -->
            <svg v-if="tab.icon === 'gear'" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
          </div>
          <span class="tab-label">{{ tab.label }}</span>
        </router-link>
      </div>
    </div>
    
    <!-- 悬浮按钮组 (FAB) -->
    <div class="fab-container">
      <button 
        class="fab fab-ai" 
        @click="handleAIClick"
        aria-label="AI 分析"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2a10 10 0 1 0 10 10H12V2z"></path>
          <path d="M12 2a10 10 0 0 1 10 10"></path>
          <circle cx="12" cy="12" r="3"></circle>
        </svg>
      </button>
      <button 
        class="fab fab-add" 
        @click="handleAddClick"
        aria-label="记账"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
      </button>
    </div>
    
    <!-- AI 对话框 -->
    <AIDialog :is-visible="showAIDialog" @close="showAIDialog = false" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import AIDialog from '../components/AIDialog.vue'

const router = useRouter()
const route = useRoute()

const showAIDialog = ref(false)

const tabs = [
  { path: '/dashboard', icon: 'house', label: '首页' },
  { path: '/transactions', icon: 'list', label: '流水' },
  { path: '/reports', icon: 'chart', label: '报表' },
  { path: '/settings', icon: 'gear', label: '设置' }
]

function isActiveTab(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}

function handleAddClick() {
  router.push('/transactions/add')
}

function handleAIClick() {
  showAIDialog.value = true
}
</script>

<style scoped>
.main-layout {
  min-height: 100vh;
  background: #f2f2f7;
  position: relative;
}

.page-content-wrapper {
  min-height: 100vh;
  padding-bottom: 100px;
}

/* Tabbar 容器 */
.tabbar-wrapper {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 8px 12px;
  padding-bottom: calc(8px + env(safe-area-inset-bottom, 0px));
  z-index: 1000;
}

/* Framework7 风格 Tabbar */
.tabbar {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-radius: 20px;
  box-shadow: 0 2px 20px rgba(0, 0, 0, 0.08);
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 6px 8px;
}

.tabbar-icons .tab-link {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 8px 12px;
  border-radius: 14px;
  text-decoration: none;
  color: #8e8e93;
  transition: all 0.2s ease;
  -webkit-tap-highlight-color: transparent;
}

.tabbar-icons .tab-link .tab-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 2px;
}

.tabbar-icons .tab-link .tab-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: -0.24px;
}

/* 活动状态 */
.tabbar-icons .tab-link-active {
  background: rgba(0, 122, 255, 0.12);
  color: #007aff;
}

/* FAB 悬浮按钮 */
.fab-container {
  position: fixed;
  bottom: 110px;
  right: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  z-index: 999;
}

.fab {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
  transition: transform 0.2s, box-shadow 0.2s;
  -webkit-tap-highlight-color: transparent;
}

.fab:active {
  transform: scale(0.95);
}

.fab svg {
  color: white;
}

.fab-add {
  background: #007aff;
}

.fab-ai {
  background: #5856d6;
  width: 44px;
  height: 44px;
}

/* 暗黑模式 */
@media (prefers-color-scheme: dark) {
  .main-layout {
    background: #000000;
  }
  
  .tabbar {
    background: rgba(28, 28, 30, 0.85);
    box-shadow: 0 2px 20px rgba(0, 0, 0, 0.3);
  }
  
  .tabbar-icons .tab-link {
    color: #636366;
  }
  
  .tabbar-icons .tab-link-active {
    background: rgba(10, 132, 255, 0.2);
    color: #0a84ff;
  }
}
</style>
