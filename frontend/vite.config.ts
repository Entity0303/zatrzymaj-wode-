import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

// Proxy /api -> backend (lokalnie localhost:8000, w Dockerze serwis "backend")
const apiTarget = process.env.VITE_API_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    host: true,
    port: 5173,
    // w Dockerze na Windows/macOS zdarzenia zmian plików nie przechodzą przez bind mount
    watch: process.env.VITE_POLLING ? { usePolling: true, interval: 300 } : undefined,
    proxy: { '/api': { target: apiTarget, changeOrigin: true } },
  },
})
