import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'auto'
const STORAGE_KEY = 'beanmind-theme-mode'
const MEDIA_QUERY = '(prefers-color-scheme: dark)'

export const useUIStore = defineStore('ui', () => {
  const themeMode = ref<ThemeMode>((localStorage.getItem(STORAGE_KEY) as ThemeMode) || 'auto')
  const isDark = ref(resolveDark(themeMode.value))
  let initialized = false

  function resolveDark(mode: ThemeMode) {
    return mode === 'dark' || (mode === 'auto' && Boolean(window.matchMedia?.(MEDIA_QUERY).matches))
  }

  function applyTheme(mode: ThemeMode) {
    const root = document.documentElement
    const dark = resolveDark(mode)
    isDark.value = dark
    root.classList.remove('theme-dark', 'theme-light', 'van-theme-dark')
    root.classList.add(dark ? 'theme-dark' : 'theme-light')
    root.classList.toggle('van-theme-dark', dark)
    document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute('content', dark ? '#0e1113' : '#f5f6f8')
  }
  function setThemeMode(mode: ThemeMode) {
    themeMode.value = mode
    localStorage.setItem(STORAGE_KEY, mode)
    applyTheme(mode)
  }
  function initTheme() {
    applyTheme(themeMode.value)
    if (initialized) return
    initialized = true
    window.matchMedia?.(MEDIA_QUERY).addEventListener('change', () => {
      if (themeMode.value === 'auto') applyTheme('auto')
    })
  }
  return { themeMode, isDark, setThemeMode, initTheme }
})
