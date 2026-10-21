/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  // loadEnv also reads real environment variables (docker compose sets VITE_API_PROXY).
  const env = loadEnv(mode, '.', '')
  const apiTarget = env.VITE_API_PROXY || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': apiTarget,
        '/health': apiTarget,
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/setupTests.ts'],
      globals: true,
      // The first test in a file is slow on a Raspberry Pi (cold start); keep generous headroom.
      testTimeout: 20000,
    },
  }
})
