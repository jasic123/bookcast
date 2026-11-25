import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${loadEnv(mode, process.cwd(), 'BOOKCAST_').BOOKCAST_API_PORT || '8000'}`,
        changeOrigin: true,
      },
    },
  },
}))
