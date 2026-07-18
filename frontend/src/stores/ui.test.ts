import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useUIStore } from './ui'

describe('ui theme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.className = ''
    document.head.innerHTML = '<meta name="theme-color" content="#f5f6f8">'
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn() }))
    setActivePinia(createPinia())
  })

  it('synchronizes the BeanMind and Vant dark themes', () => {
    const ui = useUIStore()
    ui.setThemeMode('dark')

    expect(ui.isDark).toBe(true)
    expect(document.documentElement.classList.contains('theme-dark')).toBe(true)
    expect(document.documentElement.classList.contains('van-theme-dark')).toBe(true)
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute('content')).toBe('#0e1113')

    ui.setThemeMode('light')
    expect(ui.isDark).toBe(false)
    expect(document.documentElement.classList.contains('van-theme-dark')).toBe(false)
  })
})
