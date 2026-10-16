import { expect, test } from '@playwright/test'

// Signed in (see auth.setup.ts). Each test uses its own account names: tests run in parallel
// with the same user.

test('crear una cuenta, apuntar un gasto en tres toques y verlo reflejado', async ({ page }) => {
  const name = `Nómina ${Date.now()}`

  await page.goto('/cuentas/nueva')
  await page.getByLabel('Nombre').fill(name)
  await page.getByLabel('Saldo', { exact: true }).fill('1.000')
  await page.getByRole('button', { name: 'Crear cuenta' }).click()
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
  await expect(page.getByText('1.000,00 €').first()).toBeVisible()

  await page.getByRole('link', { name: 'Añadir', exact: true }).click()
  await page.getByLabel('Cuenta').selectOption({ label: name })
  await page.getByLabel('Importe').fill('12,50')
  await page.getByRole('button', { name: 'Más categorías' }).click()
  // Other tests share the user: if it is already among the most used it appears twice.
  await page
    .getByRole('button', { name: /Supermercado/ })
    .first()
    .click()
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('Gasto de 12,50 € guardado.')).toBeVisible()

  await page.getByRole('link', { name: 'Inicio', exact: true }).click()
  await page.getByRole('link', { name: new RegExp(name) }).click()
  await expect(page.getByText('987,50 €').first()).toBeVisible()
  await expect(page.getByRole('link', { name: /^Supermercado\s*Alimentación/ })).toBeVisible()
})

test('una transferencia mueve el dinero entre dos cuentas', async ({ page }) => {
  const stamp = Date.now()
  for (const [name, balance] of [
    [`Origen ${stamp}`, '500'],
    [`Destino ${stamp}`, '0'],
  ]) {
    await page.goto('/cuentas/nueva')
    await page.getByLabel('Nombre').fill(name!)
    await page.getByLabel('Saldo', { exact: true }).fill(balance!)
    await page.getByRole('button', { name: 'Crear cuenta' }).click()
    await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
  }

  await page.goto('/anadir')
  await page.getByRole('radio', { name: 'Transferencia' }).click()
  await page.getByLabel('Desde').selectOption({ label: `Origen ${stamp}` })
  await page.getByLabel('Hacia').selectOption({ label: `Destino ${stamp}` })
  await page.getByLabel('Importe').fill('200')
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('Transferencia de 200,00 € guardada.')).toBeVisible()

  await page.goto('/')
  await expect(
    page.getByRole('link', { name: new RegExp(`Origen ${stamp}.*300,00`) }),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: new RegExp(`Destino ${stamp}.*200,00`) }),
  ).toBeVisible()
})
