<template>
  <van-config-provider :theme="vantTheme" :theme-vars="themeVars">
    <router-view />
  </van-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useUIStore } from './stores/ui'

const themeVars = { primaryColor: 'var(--bm-primary)' }
const ui = useUIStore()
const { isDark } = storeToRefs(ui)
const vantTheme = computed(() => isDark.value ? 'dark' : 'light')

onMounted(() => ui.initTheme())
</script>
