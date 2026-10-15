import { defineConfig } from 'vite';
export default defineConfig({
  server: { proxy: { '/api': 'http://127.0.0.1:8741' } },
  build: { outDir: '../../src/cadharness/studio/web', emptyOutDir: true },
});
