import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8765',
      '/health': 'http://127.0.0.1:8765',
      '/ws': { target: 'ws://127.0.0.1:8765', ws: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('echarts')) return 'charts'
          if (id.includes('element-plus')) return 'element-plus'
          if (id.includes('node_modules/vue') || id.includes('pinia') || id.includes('vue-router')) return 'vue-core'
        },
      },
    },
  },
  test: { environment: 'jsdom' },
})
