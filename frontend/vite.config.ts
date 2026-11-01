import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // Same-origin in dev: the API needs no CORS configuration.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
