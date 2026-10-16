import { expect, test } from '@playwright/test'

// Signed in (see auth.setup.ts).

test('un pago con Apple Pay llega al momento y queda pendiente', async ({ page, request }) => {
  const name = `Captura ${Date.now()}`
  await page.goto('/cuentas/nueva')
  await page.getByLabel('Nombre').fill(name)
  await page.getByLabel('Saldo', { exact: true }).fill('100')
  await page.getByRole('button', { name: 'Crear cuenta' }).click()
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()

  await page.goto('/mas/captura')
  await page.getByLabel('Nombre').fill(`iPhone ${name}`)
  await page.getByLabel('Cuenta por defecto').selectOption({ label: name })
  await page.getByRole('button', { name: 'Crear token y ver los pasos' }).click()
  const authorization = await page.getByLabel('Authorization').textContent()
  expect(authorization).toMatch(/^Bearer mia_/)

  // What the Shortcut sends: no session, just the token.
  const response = await request.post('/api/capture/payments', {
    headers: { Authorization: authorization! },
    data: { amount: '12,50 €', merchant: 'Cafetería Prueba', card: `Tarjeta ${name}` },
  })
  expect(response.ok()).toBeTruthy()
  expect((await response.json()).message).toBe(`Cafetería Prueba: 12,50 € en ${name}`)

  await page.goto('/')
  await page.getByRole('link', { name: new RegExp(name) }).click()
  await expect(page.getByText('87,50 €').first()).toBeVisible()
  await expect(page.getByRole('link', { name: /Cafetería Prueba.*Pendiente/ })).toBeVisible()
})
