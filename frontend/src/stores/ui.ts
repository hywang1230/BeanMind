import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'auto'
const STORAGE_KEY = 'beanmind-theme-mode'

export const useUIStore = defineStore('ui', () => {
  const themeMode = ref<ThemeMode>((localStorage.getItem(STORAGE_KEY) as ThemeMode) || 'auto')
  function applyTheme(mode: ThemeMode) {
    const root = document.documentElement
    root.classList.remove('theme-dark', 'theme-light')
    const dark = mode === 'dark' || (mode === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    root.classList.add(dark ? 'theme-dark' : 'theme-light')
  }
  function setThemeMode(mode: ThemeMode) {
    themeMode.value = mode
    localStorage.setItem(STORAGE_KEY, mode)
    applyTheme(mode)
  }
  function initTheme() {
    applyTheme(themeMode.value)
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (themeMode.value === 'auto') applyTheme('auto')
    })
  }
  return { themeMode, setThemeMode, initTheme }
})
