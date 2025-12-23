<template>
  <div class="settings-page">
    <div class="page-header">
      <h1>更多</h1>
    </div>
    
    <f7-list inset strong>
      <f7-list-item 
        link="#"
        title="报表" 
        @click="navigateTo('/reports')"
      >
        <template #media>
          <f7-icon ios="f7:chart_bar_fill" md="material:bar_chart" color="blue"></f7-icon>
        </template>
      </f7-list-item>
      
      <f7-list-item 
        link="#"
        title="周期记账" 
        @click="navigateTo('/recurring/rules')"
      >
        <template #media>
          <f7-icon ios="f7:arrow_2_circlepath" md="material:autorenew" color="purple"></f7-icon>
        </template>
      </f7-list-item>
    </f7-list>

    <f7-block-title class="section-title">系统设置</f7-block-title>
    <f7-list inset strong>
      <f7-list-item 
        link="#"
        title="账户管理" 
        @click="navigateTo('/accounts')"
      >
        <template #media>
          <f7-icon ios="f7:creditcard_fill" md="material:account_balance_wallet" color="green"></f7-icon>
        </template>
      </f7-list-item>
    </f7-list>

    <div class="coming-soon">
      <div class="icon">⚙️</div>
      <div class="text">更多功能开发中...</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { f7List, f7ListItem, f7Icon, f7BlockTitle } from 'framework7-vue';
import { useUIStore } from '../../stores/ui';

const router = useRouter();
const uiStore = useUIStore();

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
  color: var(--f7-text-color);
  margin: 0 0 10px 0;
}

.section-title {
  margin-top: 24px;
}

.coming-soon {
  text-align: center;
  padding: 40px 20px;
}

.icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.text {
  font-size: 16px;
  color: #999;
}
</style>
