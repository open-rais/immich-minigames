import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Binds 0.0.0.0 instead of just localhost, so the dev server is reachable from other devices
    // on the LAN (e.g. a phone) - see docs/TODO/DEV_NOTES.md for the tradeoff/revert note.
    host: true,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
