<template>
  <router-view />
</template>

<script setup lang="ts">
// Main App component
</script>

<style>
:root {
  --f7-theme-color: #667eea;
  --f7-theme-color-rgb: 102, 126, 234;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: #f5f5f5;
}

#app {
  min-height: 100vh;
}
</style>
