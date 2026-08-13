/// <reference types="vitest/config" />

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const API_TARGET = 'http://127.0.0.1:8090'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': API_TARGET,
      '/health': API_TARGET,
    },
  },
  test: {
    include: ['tests/**/*.spec.ts'],
  },
})
