<template>
  <div class="settings-page">
    <div class="page-header">
      <h1>更多</h1>
    </div>
    
    <f7-list inset strong>
      <f7-list-item 
        link="/reports" 
        title="报表" 
        ignore-cache
      >
        <template #media>
          <f7-icon ios="f7:chart_bar_fill" md="material:bar_chart" color="blue"></f7-icon>
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
import { f7List, f7ListItem, f7Icon } from 'framework7-vue';
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
