<template>
  <f7-page name="ai">
    <f7-navbar title="AI 智能分析"></f7-navbar>
    
    <div class="ai-content">
      <div class="ai-status">
        <div class="icon-wrapper">
          <f7-icon f7="sparkles" size="80" class="ai-icon" />
        </div>
        <p class="ai-text">AI 分析功能开发中</p>
        <p class="ai-description">
          即将为您提供智能账单分析、消费建议、预算优化等功能
        </p>
      </div>
    </div>
  </f7-page>
</template>

<script setup lang="ts">
import { f7Page, f7Navbar, f7Icon } from 'framework7-vue';
</script>

<style scoped>
.ai-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.ai-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.icon-wrapper {
  margin-bottom: 24px;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e0f2fe 0%, #dbeafe 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.ai-icon {
  color: #3b82f6;
}

.ai-text {
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 12px;
}

.ai-description {
  font-size: 16px;
  color: #6b7280;
  max-width: 280px;
  line-height: 1.6;
  margin: 0;
}

/* 暗黑模式适配 */
:global(.theme-dark) .icon-wrapper {
  background: linear-gradient(135deg, #1e3a8a 0%, #172554 100%);
}

:global(.theme-dark) .ai-text {
  color: #f3f4f6;
}

:global(.theme-dark) .ai-description {
  color: #9ca3af;
}
</style>
