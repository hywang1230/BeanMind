<template>
  <div class="app-shell">
    <main class="app-main" :class="{ 'with-tabbar': showTabbar }">
      <router-view v-slot="{ Component, route: currentRoute }">
        <keep-alive include="TransactionsPage">
          <component :is="Component" :key="currentRoute.path" />
        </keep-alive>
      </router-view>
    </main>
    <van-tabbar
      v-if="showTabbar"
      :model-value="activeTab"
      route
      safe-area-inset-bottom
      active-color="var(--bm-primary)"
      inactive-color="var(--bm-muted)"
      class="main-tabbar"
    >
      <van-tabbar-item replace to="/dashboard" name="dashboard" icon="home-o">首页</van-tabbar-item>
      <van-tabbar-item replace to="/transactions" name="transactions" icon="orders-o">流水</van-tabbar-item>
      <van-tabbar-item name="add" class="tabbar-add" aria-label="记一笔" @click="onAddTransaction">
        <template #icon>
          <span class="tabbar-add-btn">
            <van-icon name="plus" />
          </span>
        </template>
      </van-tabbar-item>
      <van-tabbar-item replace to="/budgets" name="budgets" icon="chart-trending-o">预算</van-tabbar-item>
      <van-tabbar-item replace to="/settings" name="settings" icon="setting-o">设置</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const activeTab = computed(() => String(route.meta.tab || ''))
const showTabbar = computed(() => Boolean(route.meta.tab))

function onAddTransaction() {
  if (route.path === '/transactions/new') return
  router.push('/transactions/new')
}
</script>

<style scoped>
.main-tabbar {
  border-top: 1px solid var(--bm-border);
  background: var(--bm-surface);
}
.tabbar-add {
  flex: 1 1 0;
}
/* 内嵌在底栏内，不上浮，避免顶部分割线外的凸起 */
.tabbar-add :deep(.van-tabbar-item__icon) {
  margin-bottom: 0;
}
.tabbar-add :deep(.van-tabbar-item__text) {
  display: none;
}
.tabbar-add-btn {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--bm-primary);
  color: #fff;
}
.tabbar-add-btn :deep(.van-icon) {
  font-size: 22px;
  font-weight: 700;
}
.tabbar-add:active .tabbar-add-btn {
  filter: brightness(0.94);
  transform: scale(0.97);
}
</style>
