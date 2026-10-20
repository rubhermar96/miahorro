import { expect, test } from '@playwright/test'

// Signed in (see auth.setup.ts). The reference tables are loaded when the API starts.

test('simular la compra de una vivienda en Madrid con sus impuestos y fuentes', async ({
  page,
}) => {
  await page.goto('/planificar')
  await page
    .getByRole('region', { name: 'Calculadoras' })
    .getByRole('link', { name: 'Vivienda' })
    .click()
  await expect(page.getByRole('heading', { level: 1, name: 'Comprar vivienda' })).toBeVisible()

  await page.getByLabel('Precio de la vivienda (€)').fill('200.000')
  await page.getByLabel('Comunidad autónoma').selectOption({ label: 'Comunidad de Madrid' })
  await page.getByLabel('TIN (%)').fill('3')
  await page.getByLabel('Ingresos netos del hogar al mes (€)').fill('3.000')
  await page.getByLabel('Ahorro disponible (€)').fill('60.000')
  await page.getByRole('button', { name: 'Calcular' }).click()

  const result = page.getByRole('region', { name: 'Resultado' })
  // ITP 6 % (12.000 €) + table estimates for notary, registry, gestoría and appraisal
  await expect(result).toContainText('12.000,00 €')
  await expect(result).toContainText('53.750,00 €')
  await expect(result).toContainText('674,57 €') // =PAGO(3%/12; 360; -160000)
  await result.getByText('Valores de referencia usados').click()
  await expect(result).toContainText('guiafiscal.es')
  await expect(result).toContainText('Vigente desde el')
})

test('guardar dos escenarios de interés compuesto y compararlos', async ({ page }) => {
  const stamp = Date.now()
  await page.goto('/planificar/calculadoras/interes-compuesto')

  const save = async (name: string, rate: string) => {
    await page.getByLabel('Capital inicial (€)').fill('10.000')
    await page.getByLabel('Aportación al mes (€)').fill('0')
    await page.getByLabel('Rentabilidad anual (%)').fill(rate)
    await page.getByLabel('Inflación anual (%)').fill('0')
    await page.getByRole('radio', { name: 'Sin impuestos' }).click()
    await page.getByRole('button', { name: 'Calcular' }).click()
    await expect(page.getByRole('region', { name: 'Resultado' })).toBeVisible()
    await page.getByLabel('Nombre del escenario').fill(name)
    await page.getByRole('button', { name: 'Guardar escenario' }).click()
    await expect(page.getByText(`Escenario «${name}» guardado.`)).toBeVisible()
  }
  await save(`Prudente ${stamp}`, '3')
  await save(`Optimista ${stamp}`, '5')

  await page.getByRole('checkbox', { name: `Comparar «Prudente ${stamp}»` }).check()
  await page.getByRole('checkbox', { name: `Comparar «Optimista ${stamp}»` }).check()
  await page.getByRole('button', { name: 'Comparar 2 escenarios' }).click()

  const table = page.getByRole('region', { name: 'Comparación de escenarios' })
  // 10.000 × 1,03^10 and 10.000 × 1,05^10
  await expect(table).toContainText('13.439,16 €')
  await expect(table).toContainText('16.288,95 €')

  for (const name of [`Prudente ${stamp}`, `Optimista ${stamp}`]) {
    page.once('dialog', (dialog) => void dialog.accept())
    await page.getByRole('button', { name: `Eliminar «${name}»` }).click()
    await expect(page.getByText(name, { exact: true })).toHaveCount(0)
  }
})

test('la TAE real de un préstamo con comisión', async ({ page }) => {
  await page.goto('/planificar/calculadoras/prestamo-personal')

  await page.getByLabel('Importe (€) · Oferta 1').fill('10.000')
  await page.getByLabel('TIN (%) · Oferta 1').fill('7')
  await page.getByLabel('Importe (€) · Oferta 2').fill('10.000')
  await page.getByLabel('TIN (%) · Oferta 2').fill('6')
  await page.getByLabel('Comisión de apertura (%) · Oferta 2').fill('3')
  await page.getByRole('button', { name: 'Calcular' }).click()

  const table = page.getByRole('region', { name: 'Comparación de préstamos' })
  await expect(table).toContainText('198,01 €') // =PAGO(7%/12; 60; -10000)
  await expect(table.getByRole('row', { name: /TAE real/ })).toContainText('7,23 %')
})
