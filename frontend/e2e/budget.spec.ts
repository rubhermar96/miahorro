import { expect, test } from '@playwright/test'

// Signed in (see auth.setup.ts). The only test that changes the budget mode of the shared user.

test('presupuesto por límites y cambio a base cero sin perder nada', async ({ page }) => {
  const account = `Gastos ${Date.now()}`
  await page.goto('/cuentas/nueva')
  await page.getByLabel('Nombre').fill(account)
  await page.getByLabel('Saldo', { exact: true }).fill('1.000')
  await page.getByRole('button', { name: 'Crear cuenta' }).click()
  await expect(page.getByRole('heading', { level: 1, name: account })).toBeVisible()

  await page.goto('/planificar/presupuesto')
  await page.getByRole('button', { name: 'Usar límites por categoría' }).click()
  await page.getByLabel('Categoría').selectOption({ label: '🎉 Ocio' })
  await page.getByLabel('Límite al mes').fill('100')
  await page.getByRole('button', { name: 'Añadir', exact: true }).click()
  await expect(page.getByRole('button', { name: /Ocio/ })).toContainText('0,00 € de 100,00 €')

  await page.goto('/anadir')
  await page.getByLabel('Cuenta').selectOption({ label: account })
  await page.getByLabel('Importe').fill('30')
  await page.getByRole('button', { name: 'Más categorías' }).click()
  // A subcategory: it counts in its main category's line.
  await page
    .getByRole('button', { name: /Deporte/ })
    .first()
    .click()
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('Gasto de 30,00 € guardado.')).toBeVisible()

  await page.goto('/planificar/presupuesto')
  await expect(page.getByRole('button', { name: /Ocio/ })).toContainText('30,00 € de 100,00 €')

  await page.getByRole('button', { name: 'Cambiar a base cero' }).click()
  await expect(page.getByRole('region', { name: 'Por asignar' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Ocio/ })).toContainText('Asignado 100,00 €')
})
