import { expect, test as setup } from '@playwright/test'

import { totp } from './totp'

export const AUTH_FILE = 'e2e/.auth/user.json'

/**
 * Real onboarding of a new user, as on the phone: register, set up the authenticator app and
 * keep the recovery codes. The resulting session is reused by the other tests.
 */
setup('registro de un usuario y configuración del segundo factor', async ({ page }) => {
  const email = `e2e-${Date.now()}@miahorro.test`

  await page.goto('/')
  await expect(page).toHaveURL(/\/entrar/)
  await page.getByRole('link', { name: 'Crear una' }).click()
  await expect(page).toHaveURL(/\/registro/)

  await page.getByLabel('Nombre').fill('Prueba')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Contraseña').fill('contraseña-de-pruebas-extremo-a-extremo')
  await page.getByRole('button', { name: 'Crear cuenta' }).click()

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
