import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end tests against the full stack (docker compose up -d --build --wait).
 * WebKit with an iPhone profile: the closest to Safari on the user's phone.
 * The "setup" project signs a new user in once; the other tests reuse that session.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    locale: 'es-ES',
    timezoneId: 'Europe/Madrid',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/, use: { ...devices['iPhone 15'] } },
    {
      name: 'iphone',
      dependencies: ['setup'],
      use: { ...devices['iPhone 15'], storageState: 'e2e/.auth/user.json' },
    },
  ],
})
