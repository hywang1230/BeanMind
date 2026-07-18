<template>
  <aside v-if="needRefresh" class="pwa-update" role="status" aria-live="polite">
    <div class="pwa-update__content">
      <strong>发现新版本</strong>
      <span>{{ updateError || '更新已准备好，可立即刷新应用。' }}</span>
    </div>
    <div class="pwa-update__actions">
      <button type="button" class="pwa-update__later" :disabled="updating" @click="dismissUpdate">
        稍后
      </button>
      <button type="button" class="pwa-update__confirm" :disabled="updating" @click="applyUpdate">
        {{ updating ? '更新中…' : '立即更新' }}
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { registerSW } from 'virtual:pwa-register'

const needRefresh = ref(false)
const updating = ref(false)
const updateError = ref('')

const updateServiceWorker = registerSW({
  onNeedRefresh() {
    needRefresh.value = true
    updateError.value = ''
  },
})

function dismissUpdate() {
  needRefresh.value = false
  updateError.value = ''
}

async function applyUpdate() {
  updating.value = true
  updateError.value = ''
  try {
    await updateServiceWorker(true)
  } catch {
    updateError.value = '更新失败，请稍后重试。'
    updating.value = false
  }
}
</script>

<style scoped>
.pwa-update {
  position: fixed;
  right: 16px;
  bottom: calc(var(--bm-tabbar-height, 50px) + env(safe-area-inset-bottom) + 16px);
  left: 16px;
  z-index: 3000;
  display: flex;
  align-items: center;
  gap: 16px;
  max-width: 520px;
  margin: 0 auto;
  padding: 14px 16px;
  color: var(--bm-text);
  background: var(--bm-surface);
  border: 1px solid var(--bm-border);
  border-radius: var(--bm-card-radius, 12px);
  box-shadow: 0 8px 28px rgb(0 0 0 / 16%);
}

.pwa-update__content {
  display: grid;
  flex: 1;
  gap: 3px;
  min-width: 0;
  font-size: 13px;
  color: var(--bm-muted);
}

.pwa-update__content strong {
  font-size: 15px;
  color: var(--bm-text);
}

.pwa-update__actions {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
}

.pwa-update button {
  min-height: 36px;
  padding: 0 12px;
  font: inherit;
  border: 0;
  border-radius: var(--bm-button-radius, 8px);
  cursor: pointer;
}

.pwa-update button:disabled {
  cursor: default;
  opacity: 0.6;
}

.pwa-update__later {
  color: var(--bm-muted);
  background: transparent;
}

.pwa-update__confirm {
  color: #fff;
  background: var(--bm-primary);
}

@media (max-width: 420px) {
  .pwa-update {
    align-items: stretch;
    flex-direction: column;
    gap: 10px;
  }

  .pwa-update__actions {
    justify-content: flex-end;
  }
}
</style>
