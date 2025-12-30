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
      registerType: 'autoUpdate',
      includeAssets: ['beanmind.svg'],
      manifest: {
        name: 'BeanMind',
        short_name: 'BeanMind',
        description: 'BeanMind Application',
        theme_color: '#ffffff',
        icons: [
          {
            src: 'beanmind.svg',
            sizes: '192x192',
            type: 'image/svg+xml'
          },
          {
            src: 'beanmind.svg',
            sizes: '512x512',
            type: 'image/svg+xml'
          }
        ]
      }
    })
  ],
  test: {
    globals: true,
    environment: 'jsdom',
  },
})
