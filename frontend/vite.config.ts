/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'prompt',
      injectRegister: 'auto',
      includeAssets: ['beanmind.svg', 'pwa-192x192.png', 'pwa-512x512.png'],
      manifest: {
        id: '/',
        name: 'BeanMind',
        short_name: 'BeanMind',
        description: '基于 Beancount 的单机个人财务应用',
        lang: 'zh-CN',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        background_color: '#f5f6f8',
        theme_color: '#f5f6f8',
        categories: ['finance'],
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable'
          }
        ]
      },
      workbox: {
        navigateFallbackDenylist: [/^\/api(?:\/|$)/, /^\/health$/],
      }
    })
  ],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
