import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-fullstack',
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: 'list',
  timeout: 90_000,
  expect: { timeout: 30_000 },
  use: {
    baseURL: 'http://127.0.0.1:4174',
    channel: 'chrome',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    viewport: { width: 1600, height: 1000 },
  },
  webServer: {
    command: 'npm run dev -- --port 4174',
    url: 'http://127.0.0.1:4174/health/live',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
