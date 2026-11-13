import { randomBytes } from 'node:crypto';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, resolve } from 'node:path';
import { defineConfig, devices } from '@playwright/test';

/** Configure Chromium coverage for the platform's first-run browser journey. */
const repositoryRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const backendDirectory = resolve(repositoryRoot, 'backend');
const frontendDirectory = resolve(repositoryRoot, 'frontend');
const virtualEnvPython = process.env.VIRTUAL_ENV ? join(process.env.VIRTUAL_ENV, 'bin', 'python') : undefined;
const homeVenvPython = process.env.HOME ? join(process.env.HOME, 'venvs', 'app', 'bin', 'python') : undefined;
const backendPython = process.env.PYTHON_BIN
  ?? virtualEnvPython
  ?? (homeVenvPython && existsSync(homeVenvPython) ? homeVenvPython : 'python3');
const shellQuote = (value: string): string => `'${value.replace(/'/g, "'\\''")}'`;
const jwtSecret = randomBytes(48).toString('hex');
const testEnvironment = {
  MONGODB_URI: process.env.MONGODB_URI ?? 'mongodb://127.0.0.1:27017',
  MONGODB_DB: `ketsip_e2e_${randomBytes(8).toString('hex')}`,
  JWT_SECRET: jwtSecret,
  SEED_ADMIN_PASSWORD: 'TestAdminPassword123!',
  SEED_DEMO_PASSWORD: 'KetsipDemo2025!',
  VITE_PROXY_TARGET: 'http://127.0.0.1:18080',
};

export default defineConfig({
  testDir: '../e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:15173',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: `PYTHONPATH=. ${shellQuote(backendPython)} -m uvicorn app.main:app --host 127.0.0.1 --port 18080`,
      cwd: backendDirectory,
      url: 'http://127.0.0.1:18080/api/health',
      reuseExistingServer: false,
      timeout: 60000,
      env: { ...process.env, ...testEnvironment },
    },
    {
      command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 15173 --strictPort',
      cwd: frontendDirectory,
      url: 'http://127.0.0.1:15173',
      reuseExistingServer: false,
      timeout: 30000,
      env: { ...process.env, ...testEnvironment },
    },
  ],
});
