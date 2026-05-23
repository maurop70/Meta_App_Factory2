import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: {
      '/api/operator': {
        target: 'http://127.0.0.1:5100',
        changeOrigin: true,
      },
      '/api/builder': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/api/qa': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/api/test': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/api/pulse': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/api/reports': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/api/dashboard': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/api/repairs': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/api/ghost-stream': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/api/v1/architect': {
        target: 'http://127.0.0.1:5060',
        changeOrigin: true,
      },
      // 1. Route Chat/Inference traffic to Master Architect
      '/api/review': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      // 2. Route Binary Ingestion to Master Architect Vault
      '/api/ingest': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      // 3. Route Enterprise/Inventory traffic to SQLite Engine
      '/api': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      '/ws': {
        target: 'ws://127.0.0.1:5000',
        ws: true,
      }
    }
  },
})
