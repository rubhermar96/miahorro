import { expect, test } from '@playwright/test'

// Signed in (see auth.setup.ts).

test('dar de alta un préstamo, ver su cuadro y simular una amortización', async ({ page }) => {
  const name = `Coche ${Date.now()}`
  await page.goto('/planificar/prestamos/nuevo')
  await page.getByLabel('Nombre').fill(name)
  await page.getByRole('combobox', { name: /^Tipo/ }).selectOption({ label: 'Préstamo del coche' })
  await page.getByRole('textbox', { name: 'Capital' }).fill('12.000')
  await page.getByLabel(/Plazo \(meses\)/).fill('48')
  await page.getByLabel('Fecha de firma').fill('2026-01-10')
  await page.getByLabel('Primera cuota').fill('2026-02-05')
  await page.getByLabel('TIN (%)').fill('6')
  await page.getByLabel('Comisión por amortizar antes (%)').fill('1')
  await page.getByRole('button', { name: 'Crear préstamo' }).click()

  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
  const summary = page.getByRole('region', { name: 'Situación del préstamo' })
  await expect(summary).toContainText('de 12.000,00 €')
  await expect(summary).toContainText('281,82 €') // =PAGO(6%/12; 48; -12000)

  await page.getByText(/Cuadro de amortización \(48 cuotas\)/).click()
  await expect(page.getByRole('region', { name: 'Cuadro de amortización' })).toContainText(
    '60,00 €',
  )

  await page.getByLabel('Importe').fill('3.000')
  await page.getByRole('button', { name: 'Simular' }).click()
  await expect(page.getByText('Te ahorras en intereses')).toBeVisible()
  await expect(page.getByText(/cuotas menos/)).toBeVisible()
})
