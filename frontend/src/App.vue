<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useUIStore } from './stores/ui'

onMounted(() => useUIStore().initTheme())
</script>
