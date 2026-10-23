import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const LOCAL_BACKEND_TARGET = process.env.VITE_CHAT_BACKEND_TARGET || process.env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000'
const BACKEND_TARGET = process.env.VITE_PROXY_TARGET || LOCAL_BACKEND_TARGET

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/chat': {
        target: LOCAL_BACKEND_TARGET,
        changeOrigin: true,
        timeout: 60000,
      },
      '/api/products/new-performance': {
        target: LOCAL_BACKEND_TARGET,
        changeOrigin: true,
      },
      '/api/new-products/performance': {
        target: LOCAL_BACKEND_TARGET,
        changeOrigin: true,
      },
      '/api': {
        target: BACKEND_TARGET,
        changeOrigin: true,
      },
    },
  },
  preview: {
    proxy: {
      '/api/chat': {
        target: LOCAL_BACKEND_TARGET,
        changeOrigin: true,
        timeout: 60000,
      },
      '/api/products/new-performance': {
        target: LOCAL_BACKEND_TARGET,
        changeOrigin: true,
      },
      '/api/new-products/performance': {
        target: LOCAL_BACKEND_TARGET,
        changeOrigin: true,
      },
      '/api': {
        target: BACKEND_TARGET,
        changeOrigin: true,
      },
    },
  },
})