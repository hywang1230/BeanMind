<template>
  <div class="reports-page">
    <div class="page-header">
      <h1>报表</h1>
    </div>
    
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
</template>

<script setup lang="ts">
// Reports page - 待开发
</script>

<style scoped>
.reports-page {
  min-height: 100vh;
  background: #f2f2f7;
  padding: 0 16px;
}

.page-header {
  padding: 12px 0 8px;
}

.page-header h1 {
  font-size: 34px;
  font-weight: 700;
  color: #000;
  margin: 0;
  letter-spacing: -0.4px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  text-align: center;
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
  .reports-page {
    background: #000;
  }
  
  .page-header h1 {
    color: #fff;
  }
  
  .empty-icon {
    color: #48484a;
  }
  
  .empty-text {
    color: #fff;
  }
}
</style>
