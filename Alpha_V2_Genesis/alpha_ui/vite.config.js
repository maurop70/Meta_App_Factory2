import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    // Keep Vite on the C:\AlphaV2 junction path instead of following
    // the symlink to Google Drive (spaces/parens break file loading)
    preserveSymlinks: true,
  },
})
