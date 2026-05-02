import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icons/*.png'],
      manifest: {
        name: 'LocalCommandCenter',
        short_name: 'LCC',
        description: '本地指挥中心 — 智能任务管理与调度',
        start_url: '/',
        display: 'standalone',
        background_color: '#1a1a2e',
        theme_color: '#3498db',
        orientation: 'portrait-primary',
        lang: 'zh-CN',
        categories: ['productivity', 'utilities'],
        icons: [
          { src: '/static/icons/icon-72x72.png', sizes: '72x72', type: 'image/png' },
          { src: '/static/icons/icon-96x96.png', sizes: '96x96', type: 'image/png' },
          { src: '/static/icons/icon-128x128.png', sizes: '128x128', type: 'image/png' },
          { src: '/static/icons/icon-144x144.png', sizes: '144x144', type: 'image/png' },
          { src: '/static/icons/icon-152x152.png', sizes: '152x152', type: 'image/png' },
          { src: '/static/icons/icon-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: '/static/icons/icon-384x384.png', sizes: '384x384', type: 'image/png' },
          { src: '/static/icons/icon-512x512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      workbox: {
        globPatterns: ['assets/*', 'registerSW.js', 'favicon.svg', 'manifest.webmanifest'],
        navigateFallback: '/static/index.html',
        navigateFallbackDenylist: [/^\/api/, /^\/health/, /^\/docs/],
        runtimeCaching: [
          {
            urlPattern: /^\/api\/(task|tasks|notes|habits|dashboard|advanced)/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'lcc-api-cache',
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 5 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
  base: '/static/',
  build: {
    outDir: '../static',
    emptyOutDir: false,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8900',
      '/health': 'http://localhost:8900',
    },
  },
})
