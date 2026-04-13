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
        target: 'http://localhost:5100',
        changeOrigin: true,
      },
      '/api/builder': {
        target: 'http://localhost:5100',
        changeOrigin: true,
      },
      '/api/qa': {
        target: 'http://localhost:5030',
        changeOrigin: true,
      },
      '/api/test': {
        target: 'http://localhost:5030',
        changeOrigin: true,
      },
      '/api/pulse': {
        target: 'http://localhost:5030',
        changeOrigin: true,
      },
      '/api/reports': {
        target: 'http://localhost:5030',
        changeOrigin: true,
      },
      '/api/dashboard': {
        target: 'http://localhost:5030',
        changeOrigin: true,
      },
      '/api/repairs': {
        target: 'http://localhost:5030',
        changeOrigin: true,
      },
      '/api/ghost-stream': {
        target: 'http://localhost:5030',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://localhost:5000',
        ws: true,
      }
    }
  },
})
