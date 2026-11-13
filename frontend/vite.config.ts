import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

/** Configure Vite, Vitest, and the same-origin development API proxy. */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    clearMocks: true,
  },
});
