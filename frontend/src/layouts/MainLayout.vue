<template>
  <f7-page :page-content="false">
    <f7-toolbar tabbar icons bottom>
      <f7-toolbar-pane>
        <f7-link
          tab-link="#tab-1"
          :tab-link-active="activeTabId === 'tab-1'"
          text="首页"
          icon-ios="f7:house_fill"
          icon-md="material:home"
          @click="onTabClick('tab-1')"
        />
        <f7-link
          tab-link="#tab-2"
          :tab-link-active="activeTabId === 'tab-2'"
          text="流水"
          icon-ios="f7:list_bullet"
          icon-md="material:view_list"
          @click="onTabClick('tab-2')"
        />
        <f7-link
          tab-link="#tab-3"
          :tab-link-active="activeTabId === 'tab-3'"
          text="报表"
          icon-ios="f7:chart_bar_fill"
          icon-md="material:bar_chart"
          @click="onTabClick('tab-3')"
        />
        <f7-link
          tab-link="#tab-4"
          :tab-link-active="activeTabId === 'tab-4'"
          text="设置"
          icon-ios="f7:gear_alt_fill"
          icon-md="material:settings"
          @click="onTabClick('tab-4')"
        />
      </f7-toolbar-pane>
    </f7-toolbar>

    <f7-tabs>
      <!-- 使用 v-if 实现懒加载：只有访问过的 Tab 才渲染内容 -->
      <f7-tab id="tab-1" class="page-content" :tab-active="activeTabId === 'tab-1'">
        <DashboardPage v-if="visitedTabs.has('tab-1')" />
      </f7-tab>
      <f7-tab id="tab-2" class="page-content" :tab-active="activeTabId === 'tab-2'">
        <TransactionsPage v-if="visitedTabs.has('tab-2')" />
      </f7-tab>
      <f7-tab id="tab-3" class="page-content" :tab-active="activeTabId === 'tab-3'">
        <ReportsPage v-if="visitedTabs.has('tab-3')" />
      </f7-tab>
      <f7-tab id="tab-4" class="page-content" :tab-active="activeTabId === 'tab-4'">
        <SettingsPage v-if="visitedTabs.has('tab-4')" />
      </f7-tab>
    </f7-tabs>

    <!-- Global Floating Action Button -->
    <f7-fab position="right-bottom" color="blue" @click="handleAddClick">
      <f7-icon ios="f7:plus" md="material:add"></f7-icon>
    </f7-fab>

    <!-- AI Dialog -->
    <AIDialog :is-visible="showAIDialog" @close="showAIDialog = false" />

  </f7-page>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { useRouter } from 'vue-router';
import {
  f7Page,
  f7Link,
  f7Toolbar,
  f7ToolbarPane,
  f7Tabs,
  f7Tab,
  f7Fab,
  f7Icon,
} from 'framework7-vue';

import DashboardPage from '../pages/dashboard/DashboardPage.vue';
import TransactionsPage from '../pages/transactions/TransactionsPage.vue';
import ReportsPage from '../pages/reports/ReportsPage.vue';
import SettingsPage from '../pages/settings/SettingsPage.vue';
import AIDialog from '../components/AIDialog.vue';
import { useUIStore } from '../stores/ui';

const router = useRouter();
const uiStore = useUIStore();
const showAIDialog = ref(false);

// 在组件初始化时立即确定正确的 Tab ID
// 如果需要恢复 Tab 状态，直接使用保存的 Tab ID，避免先渲染默认 Tab
function getInitialTabId(): string {
  if (uiStore.shouldRestoreTab) {
    // 清除恢复标记
    uiStore.clearTabRestoreFlag();
    // 使用保存的 Tab ID
    return uiStore.activeTabId;
  }
  // 正常访问：使用 tab-1
  return 'tab-1';
}

const activeTabId = ref(getInitialTabId());

// 追踪已访问过的 Tab，用于懒加载
// 使用 reactive 的 Set 来追踪
const visitedTabs = reactive(new Set<string>([activeTabId.value]));

function onTabClick(tabId: string) {
  activeTabId.value = tabId;
  uiStore.setActiveTab(tabId);
  // 标记此 Tab 已被访问
  visitedTabs.add(tabId);
}

function handleAddClick() {
  router.push('/transactions/add');
}
</script>

<style scoped>
/* Removed old add-button-link styles as it's no longer used */
</style>

