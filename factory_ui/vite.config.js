import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/ - Unified Proxy Boundary
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
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false
      },
      '/api/cio/': {
        target: 'http://127.0.0.1:5090/',
        changeOrigin: true,
        secure: false
      },
      '/api/review': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      '/api/orchestrate': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      '/api/agent': {
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
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('proxyRes', (proxyRes, req, res) => {
            res.setHeader('Cache-Control', 'no-cache, no-transform');
            res.setHeader('Connection', 'keep-alive');
            res.setHeader('X-Accel-Buffering', 'no');
            proxyRes.headers['cache-control'] = 'no-cache, no-transform';
            proxyRes.headers['connection'] = 'keep-alive';
            proxyRes.headers['x-accel-buffering'] = 'no';
          });
        }
      },
      '/api/ingest': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      '/api/challenge/override': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
      },
      '/api/challenge': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false,
      },
      '/api/genesis': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      '/api/bridge/stream': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('proxyRes', (proxyRes, req, res) => {
            res.setHeader('Cache-Control', 'no-cache, no-transform');
            res.setHeader('Connection', 'keep-alive');
            res.setHeader('X-Accel-Buffering', 'no');
            proxyRes.headers['cache-control'] = 'no-cache, no-transform';
            proxyRes.headers['connection'] = 'keep-alive';
            proxyRes.headers['x-accel-buffering'] = 'no';
          });
        }
      },
      '/api/bridge': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      '/api/telemetry/stream': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('proxyRes', (proxyRes, req, res) => {
            res.setHeader('Cache-Control', 'no-cache, no-transform');
            res.setHeader('Connection', 'keep-alive');
            res.setHeader('X-Accel-Buffering', 'no');
            proxyRes.headers['cache-control'] = 'no-cache, no-transform';
            proxyRes.headers['connection'] = 'keep-alive';
            proxyRes.headers['x-accel-buffering'] = 'no';
          });
        }
      },
      '/api/test/adversarial': {
        target: 'http://127.0.0.1:5030',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('proxyRes', (proxyRes, req, res) => {
            res.setHeader('Cache-Control', 'no-cache, no-transform');
            res.setHeader('Connection', 'keep-alive');
            res.setHeader('X-Accel-Buffering', 'no');
            proxyRes.headers['cache-control'] = 'no-cache, no-transform';
            proxyRes.headers['connection'] = 'keep-alive';
            proxyRes.headers['x-accel-buffering'] = 'no';
          });
        }
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
