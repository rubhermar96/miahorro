import { expect, test } from '@playwright/test'

// Signed in (see auth.setup.ts).

test('crear un objetivo, apartar dinero y ver lo disponible en la cuenta', async ({ page }) => {
  const account = `Ahorro ${Date.now()}`
  const goal = `Viaje ${Date.now()}`
  await page.goto('/cuentas/nueva')
  await page.getByLabel('Nombre').fill(account)
  await page.getByLabel('Saldo', { exact: true }).fill('5.000')
  await page.getByRole('button', { name: 'Crear cuenta' }).click()
  await expect(page.getByRole('heading', { level: 1, name: account })).toBeVisible()

  await page.getByRole('link', { name: 'Planificar', exact: true }).click()
  await page.getByRole('link', { name: 'Nuevo objetivo' }).click()
  await page.getByLabel('Nombre').fill(goal)
  await page.getByRole('button', { name: 'Imagen ✈️' }).click()
  await page.getByLabel('Importe').fill('2.000')
  await page.getByRole('button', { name: 'Crear objetivo' }).click()

  await expect(page.getByRole('heading', { level: 1, name: `✈️ ${goal}` })).toBeVisible()
  await page.getByLabel('Cuenta').selectOption({ label: account })
  await page.getByLabel('Importe').fill('500')
  await page.getByRole('button', { name: 'Apartar', exact: true }).click()
  await expect(page.getByText('Apartado.', { exact: true })).toBeVisible()
  await expect(page.getByRole('progressbar', { name: `Progreso de ${goal}` })).toHaveAttribute(
    'aria-valuenow',
    '25',
  )

  await page.goto('/')
  await expect(
    page.getByRole('link', { name: new RegExp(`${account}.*Disponible 4.500,00`) }),
  ).toBeVisible()
})
