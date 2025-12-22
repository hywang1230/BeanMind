<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isVisible" class="dialog-overlay" @click="handleClose">
        <div class="dialog-container" @click.stop>
          <div class="dialog-header">
            <div class="dialog-title">AI 智能分析</div>
            <button class="close-btn" @click="handleClose">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
              </svg>
            </button>
          </div>
          
          <div class="dialog-content">
            <div class="ai-status">
              <div class="ai-icon">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="80" height="80">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-4h2v2h-2v-2zm1.61-9.96c-2.06-.3-3.88.97-4.43 2.79-.18.58.26 1.17.87 1.17h.2c.41 0 .74-.29.88-.67.32-.89 1.27-1.5 2.3-1.28.95.2 1.65 1.13 1.57 2.1-.1 1.34-1.62 1.63-2.45 2.88 0 .01-.01.01-.01.02-.01.02-.02.03-.03.05-.09.15-.18.32-.25.5-.01.03-.03.05-.04.08-.01.02-.01.04-.02.07-.12.34-.2.75-.2 1.25h2c0-.42.11-.77.28-1.07.02-.03.03-.06.05-.09.08-.14.18-.27.28-.39.01-.01.02-.03.03-.04.1-.12.21-.23.33-.34.96-.91 2.26-1.65 1.99-3.56-.24-1.74-1.61-3.21-3.35-3.47z"/>
                </svg>
              </div>
              <p class="ai-text">AI 分析功能开发中</p>
              <p class="ai-description">
                即将为您提供智能账单分析、消费建议、预算优化等功能
              </p>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
interface Props {
  isVisible: boolean
}

defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

function handleClose() {
  emit('close')
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 9999;
}

.dialog-container {
  background: #fff;
  width: 100%;
  max-height: 90vh;
  border-radius: 12px 12px 0 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.dialog-header {
  padding: 16px;
  border-bottom: 0.5px solid #c6c6c8;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
}

.dialog-title {
  font-size: 17px;
  font-weight: 600;
  color: #000;
}

.close-btn {
  position: absolute;
  right: 16px;
  width: 30px;
  height: 30px;
  border: none;
  background: #e5e5ea;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8e8e93;
}

.close-btn:active {
  background: #d1d1d6;
}

.dialog-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  min-height: 400px;
}

.ai-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  padding: 40px 0;
}

.ai-icon {
  color: #5856d6;
  margin-bottom: 20px;
}

.ai-text {
  font-size: 20px;
  font-weight: 600;
  color: #000;
  margin: 0 0 12px;
}

.ai-description {
  font-size: 14px;
  color: #8e8e93;
  max-width: 280px;
  line-height: 1.5;
  margin: 0;
}

/* 动画 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-active .dialog-container,
.modal-leave-active .dialog-container {
  transition: transform 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .dialog-container,
.modal-leave-to .dialog-container {
  transform: translateY(100%);
}

/* 暗黑模式 */
@media (prefers-color-scheme: dark) {
  .dialog-container {
    background: #1c1c1e;
  }
  
  .dialog-header {
    border-bottom-color: #38383a;
  }
  
  .dialog-title {
    color: #fff;
  }
  
  .close-btn {
    background: #3a3a3c;
    color: #ebebf5;
  }
  
  .close-btn:active {
    background: #48484a;
  }
  
  .ai-icon {
    color: #5e5ce6;
  }
  
  .ai-text {
    color: #fff;
  }
}
</style>
