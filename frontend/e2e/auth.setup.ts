import { execFileSync } from 'node:child_process'

import { expect, test as setup } from '@playwright/test'

import { totp } from './totp'

export const AUTH_FILE = 'e2e/.auth/user.json'

/**
 * Real onboarding of a new user, as on the phone: the admin creates the account with the CLI,
 * then the user signs in, sets up the authenticator app and keeps the recovery codes.
 * The resulting session is reused by the other tests.
 */
setup('alta de un usuario y primer inicio de sesión', async ({ page }) => {
  const email = `e2e-${Date.now()}@miahorro.test`
  const password = 'contraseña-de-pruebas-extremo-a-extremo'
  execFileSync(
    'docker',
    [
      'compose',
      'exec',
      '-T',
      'api',
      'python',
      '-m',
      'app.cli',
      'create-user',
      '--email',
      email,
      '--name',
      'Prueba',
      '--password-stdin',
    ],
    { input: `${password}\n`, cwd: '..', stdio: ['pipe', 'inherit', 'inherit'] },
  )

  await page.goto('/')
  await expect(page).toHaveURL(/\/entrar/)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Contraseña').fill(password)
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()

  await expect(page.getByRole('heading', { name: 'Protege tu cuenta' })).toBeVisible()
  await page.getByText('Clave para añadirla a mano').click()
  const secret = (await page.locator('.totp__secret').textContent())?.replace(/\s/g, '')
  expect(secret).toBeTruthy()
  await page.getByLabel('Código').fill(totp(secret!))
  await page.getByRole('button', { name: 'Activar' }).click()

  await expect(page.getByRole('heading', { name: 'Códigos de recuperación' })).toBeVisible()
  await page.getByRole('button', { name: 'Ya los he guardado' }).click()
  await expect(page.getByText('Hola, Prueba')).toBeVisible()

  await page.context().storageState({ path: AUTH_FILE })
})
