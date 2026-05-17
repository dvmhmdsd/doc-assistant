import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwind from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwind()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': process.env.VITE_API_BASE_URL
        ? process.env.VITE_API_BASE_URL
        : 'http://app:8000'
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})
