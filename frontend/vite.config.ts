import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwind from '@tailwindcss/vite'

const backend = process.env.VITE_API_BASE_URL ?? 'http://app:8000'

export default defineConfig({
  plugins: [react(), tailwind()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/upload': backend,
      '/ask': backend,
      '/history': backend,
      '/session': backend,
      '/healthz': backend,
      '/metrics': backend,
      '/api': backend
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})
