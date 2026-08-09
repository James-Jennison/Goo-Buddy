import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

const configuredWorkers = process.env.GOO_BUDDY_VITEST_MAX_WORKERS;
if (configuredWorkers !== undefined && configuredWorkers !== '' && !/^[1-9]\d*$/.test(configuredWorkers)) {
  throw new Error('GOO_BUDDY_VITEST_MAX_WORKERS must be a positive integer');
}
const maxWorkers = configuredWorkers
  ? Number(configuredWorkers)
  : process.env.CI
    ? undefined
    : 4;

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    environmentOptions: {
      jsdom: {
        url: 'http://localhost:3000',
      },
    },
    setupFiles: ['./src/__tests__/setup.ts'],
    testTimeout: 10000,
    include: ['src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    exclude: ['node_modules', 'dist'],
    ...(maxWorkers === undefined ? {} : { maxWorkers }),
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/**/*.spec.{ts,tsx}',
        'src/__tests__/**',
        'src/main.tsx',
        'src/vite-env.d.ts',
      ],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
