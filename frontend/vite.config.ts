import { defineConfig } from 'vite';

const backendPort = ((globalThis as unknown as { process?: { env?: Record<string, string> } }).process?.env?.VITE_BACKEND_PORT) || '8000';

export default defineConfig({
  server: {
    proxy: {
      '/api': `http://127.0.0.1:${backendPort}`,
    },
  },
  preview: {
    port: 5173,
    proxy: {
      '/api': `http://127.0.0.1:${backendPort}`,
    },
  },
});
