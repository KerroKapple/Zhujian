import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 开发环境将 /api 代理到后端 FastAPI（默认 8000 端口）
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 拆分大依赖为独立 chunk，避免单包过大、提升首屏缓存命中。
    // vite 8 默认 rolldown bundler 不再接受 manualChunks 的对象写法，
    // 必须用函数形式（按模块 id 归组）。
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('echarts')) return 'echarts'
          if (id.includes('element-plus')) return 'element-plus'
          if (id.includes('vue') || id.includes('pinia')) return 'vue'
        },
      },
    },
  },
})
