<template>
  <div class="app-shell">
    <main class="app-main" :class="{ 'with-tabbar': showTabbar }">
      <router-view />
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
      <van-tabbar-item replace to="/budgets" name="budgets" icon="chart-trending-o">预算</van-tabbar-item>
      <van-tabbar-item replace to="/settings" name="settings" icon="setting-o">设置</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeTab = computed(() => String(route.meta.tab || ''))
const showTabbar = computed(() => Boolean(route.meta.tab))
</script>

<style scoped>
.main-tabbar { border-top: 1px solid var(--bm-border); background: var(--bm-surface); }
</style>
