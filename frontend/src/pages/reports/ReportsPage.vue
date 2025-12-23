<template>
  <f7-page name="reports">
    <f7-navbar title="报表" back-link="更多"></f7-navbar>
    
    <div class="reports-content">
      <div class="empty-state">
        <div class="empty-icon">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="64" height="64">
            <path d="M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zm5.6 8H19v6h-2.8v-6z"/>
          </svg>
        </div>
        <p class="empty-text">报表功能正在开发中</p>
        <p class="empty-hint">即将为您提供详细的财务分析报表</p>
      </div>
    </div>
  </f7-page>
</template>

<script setup lang="ts">
import { f7Page, f7Navbar } from 'framework7-vue';
</script>

<style scoped>
.reports-content {
  height: 100%;
  background: #f2f2f7;
  display: flex;
  flex-direction: column;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  text-align: center;
  flex: 1;
}

.empty-icon {
  color: #c6c6c8;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 17px;
  font-weight: 600;
  color: #000;
  margin: 0 0 8px;
}

.empty-hint {
  font-size: 14px;
  color: #8e8e93;
  margin: 0;
}

@media (prefers-color-scheme: dark) {
  .reports-content {
    background: #000;
  }
  
  .empty-icon {
    color: #48484a;
  }
  
  .empty-text {
    color: #fff;
  }
}
</style>
