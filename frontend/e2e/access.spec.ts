import { expect, test } from '@playwright/test'

// A visitor without a session (ignores the signed-in state the other tests reuse).
test.use({ storageState: { cookies: [], origins: [] } })

test('sin sesión, la app pide entrar y recuerda adónde ibas', async ({ page }) => {
  await page.goto('/movimientos')

  await expect(page).toHaveURL(/\/entrar\?siguiente=%2Fmovimientos$/)
  await expect(page.getByRole('button', { name: 'Entrar', exact: true })).toBeVisible()
})

test('el panel de administración manda a entrar', async ({ page }) => {
  await page.goto('/admin/')

  await expect(page).toHaveURL(/\/entrar\?siguiente=\/admin$/)
})

test('una contraseña incorrecta muestra un aviso', async ({ page }) => {
  await page.goto('/entrar')
  await page.getByLabel('Email').fill('nadie@miahorro.test')
  await page.getByLabel('Contraseña').fill('no-es-la-contraseña')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()

  await expect(page.getByRole('alert')).toHaveText('Email o contraseña incorrectos.')
})

test('la API rechaza escrituras sin la cabecera anti-CSRF', async ({ request }) => {
  const response = await request.post('/api/auth/login', {
    data: { email: 'a@b.c', password: 'x' },
  })

  expect(response.status()).toBe(403)
})
