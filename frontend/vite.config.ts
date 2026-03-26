import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/flows': 'http://localhost:8000',
      '/browser': 'http://localhost:8000',
      '/logs': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
