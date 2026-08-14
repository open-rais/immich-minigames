/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Binds 0.0.0.0 instead of just localhost, so the dev server is reachable from other devices
    // on the LAN (e.g. a phone).
    host: true,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    // Node by default (faster); the files that need a DOM opt in per-file with a
    // `// @vitest-environment jsdom` comment on their first line, so the ones that don't
    // never pay for jsdom's startup.
    environment: 'node',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    restoreMocks: true,
    clearMocks: true,
  },
})
