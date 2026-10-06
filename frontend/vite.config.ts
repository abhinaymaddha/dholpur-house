import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// In dev, /api is proxied to the FastAPI backend (VITE_API_PROXY, default localhost:8000).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY || 'http://localhost:8000'
  return {
    plugins: [react(), tailwindcss()],
    server: { proxy: { '/api': target, '/health': target } },
  }
})
