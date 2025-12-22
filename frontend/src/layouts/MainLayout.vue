<template>
  <f7-page :page-content="false">
    <f7-toolbar tabbar icons bottom>
      <f7-toolbar-pane>
        <f7-link
          tab-link="#tab-1"
          tab-link-active
          text="首页"
          icon-ios="f7:house_fill"
          icon-md="material:home"
        />
        <f7-link
          tab-link="#tab-2"
          text="流水"
          icon-ios="f7:list_bullet"
          icon-md="material:view_list"
        />
        <f7-link
          tab-link="#tab-3"
          text="报表"
          icon-ios="f7:chart_bar_fill"
          icon-md="material:bar_chart"
        />
        <f7-link
          tab-link="#tab-4"
          text="设置"
          icon-ios="f7:gear_alt_fill"
          icon-md="material:settings"
        />
      </f7-toolbar-pane>
    </f7-toolbar>

    <f7-tabs>
      <f7-tab id="tab-1" class="page-content" tab-active>
        <DashboardPage />
      </f7-tab>
      <f7-tab id="tab-2" class="page-content">
        <TransactionsPage />
      </f7-tab>
      <f7-tab id="tab-3" class="page-content">
        <ReportsPage />
      </f7-tab>
      <f7-tab id="tab-4" class="page-content">
        <SettingsPage />
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
import { ref } from 'vue';
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

const router = useRouter();
const showAIDialog = ref(false);

function handleAddClick() {
  router.push('/transactions/add');
}
</script>

<style scoped>
/* Removed old add-button-link styles as it's no longer used */
</style>
