/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // `src/sw.ts` is hand-written (push/notificationclick land in a later phase, and the
      // per-route caching strategies in workbox-routing calls need real code, not just a glob
      // list) - `generateSW` mode only supports the latter, so injectManifest is the only mode
      // that fits.
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      // We register from src/pwa/register.ts ourselves (gated on the feature-detects in
      // src/pwa/push.ts::getPushSupport), not the plugin's own virtual:pwa-register module.
      injectRegister: false,
      // public/manifest.webmanifest is hand-written (F0) with our own icon set; disabling this
      // stops the plugin from generating a second, competing manifest.
      manifest: false,
      injectManifest: {
        // Only the hashed bundle - logo.svg/icons/covers get their own StaleWhileRevalidate route
        // in sw.ts and index.html gets its own NetworkFirst route, so neither should also sit in
        // the precache list under a second identity.
        globPatterns: ['assets/**/*.{js,css,woff,woff2}'],
      },
      devOptions: {
        // Runs the real src/sw.ts (push/notificationclick included) against an empty precache
        // manifest in dev - needed so push/notifications are testable at all without a full
        // `npm run build`. `type: "module"` since sw.ts uses `import`, unlike the 'classic'
        // default worker type. The routing/caching logic doesn't touch anything HMR uses
        // (Vite's own /@vite/client, /@react-refresh, unbundled /src/*.tsx module fetches match
        // none of sw.ts's registered routes), so this doesn't fight the dev server.
        enabled: true,
        type: 'module',
      },
    }),
  ],
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
