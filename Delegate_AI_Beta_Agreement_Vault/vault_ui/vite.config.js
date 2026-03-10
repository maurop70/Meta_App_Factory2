import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
    plugins: [react()],
    server: {
        host: true,
        port: 5008,
        proxy: {
            '/health': 'http://localhost:5007',
            '/vault': 'http://localhost:5007',
            '/alerts': 'http://localhost:5007',
            '/audit': 'http://localhost:5007',
        },
    },
})
