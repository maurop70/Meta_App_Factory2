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
      '/api/inventory': {
        target: 'http://127.0.0.1:5005',
        changeOrigin: true,
        secure: false
      },
      '/api/review': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      '/api/apps': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      '/api/qa/stream': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      '/api/ingest': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      '/api': {
        target: 'http://127.0.0.1:5000',
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
