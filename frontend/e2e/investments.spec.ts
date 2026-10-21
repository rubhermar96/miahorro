import { expect, type Page, test } from '@playwright/test'

// Signed in (see auth.setup.ts). Data is set up through the API the app itself uses.

async function post(page: Page, path: string, data: unknown) {
  const response = await page.request.post(path, {
    data,
    headers: { 'X-MiAhorro-CSRF': '1' },
  })
  expect(response.ok(), await response.text()).toBe(true)
  return (await response.json()) as { id: string }
}

test('comprar un fondo con cargo en cuenta y actualizar su precio', async ({ page }) => {
  const stamp = Date.now()
  const bank = await post(page, '/api/accounts', {
    name: `Broker ${stamp}`,
    kind: 'brokerage',
    opening_date: '2026-01-01',
    opening_balance: '5000',
  })

  await page.goto('/inversiones/nueva')
  await page.getByLabel('Nombre').fill(`Fondo ${stamp}`)
  await page.getByLabel(/^Cuenta donde está/).selectOption(bank.id)
  await page.getByRole('button', { name: 'Añadir inversión' }).click()
  await expect(page.getByRole('heading', { level: 1, name: `Fondo ${stamp}` })).toBeVisible()

  await page.getByRole('link', { name: 'Añadir operación' }).click()
  await page.getByLabel('Fecha', { exact: true }).fill('2026-01-10')
  await page.getByLabel('Participaciones', { exact: true }).fill('10')
  await page.getByLabel(/^Importe pagado \(€\)/).fill('1.000')
  await page.getByRole('button', { name: 'Guardar operación' }).click()

  const summary = page.getByRole('region', { name: 'Situación de la inversión' })
  await expect(summary).toContainText('1.000,00 €')
  await page.getByLabel('Precio por participación (€)').fill('112,5')
  await page.getByRole('button', { name: 'Guardar precio' }).click()
  await expect(summary).toContainText('1.125,00 €')
  await expect(summary).toContainText('+12,5 %')

  // The purchase left the broker account, as an investment movement, not an expense.
  await page.goto(`/cuentas/${bank.id}`)
  await expect(page.getByText('4.000,00 €').first()).toBeVisible()
  await expect(page.getByText(`Compra de Fondo ${stamp}`)).toBeVisible()
})

test('un traspaso entre fondos conserva la fecha y el coste en el informe fiscal', async ({
  page,
}) => {
  const stamp = Date.now()
  const source = await post(page, '/api/investments', { name: `Origen ${stamp}`, kind: 'fund' })
  const target = await post(page, '/api/investments', { name: `Destino ${stamp}`, kind: 'fund' })
  await post(page, `/api/investments/${source.id}/operations`, {
    date: '2024-05-10',
    kind: 'buy',
    units: '10',
    amount: '1000',
  })

  await page.goto(`/inversiones/${source.id}/operaciones/nueva`)
  await page.getByLabel('Operación').selectOption('transfer')
  await page.getByLabel('Fecha', { exact: true }).fill('2025-06-01')
  await page.getByRole('button', { name: 'Todas' }).click()
  await page.getByLabel('Fondo de destino').selectOption(target.id)
  await page.getByLabel('Participaciones recibidas').fill('20')
  await page.getByRole('button', { name: 'Guardar operación' }).click()
  await expect(page.getByRole('heading', { level: 1, name: `Origen ${stamp}` })).toBeVisible()

  await page.goto(`/inversiones/${target.id}`)
  await page.getByText('Lotes por FIFO (1)').click()
  const lots = page.getByRole('region', { name: 'Lotes por FIFO' })
  await expect(lots).toContainText('10 may 2024')
  await expect(lots).toContainText('1.000,00 €')

  await page.getByRole('link', { name: 'Añadir operación' }).click()
  await page.getByLabel('Operación').selectOption('sell')
  await page.getByLabel('Fecha', { exact: true }).fill('2026-10-01')
  await page.getByLabel('Participaciones', { exact: true }).fill('5')
  await page.getByLabel(/^Importe de la venta \(€\)/).fill('300')
  await page.getByRole('button', { name: 'Guardar operación' }).click()
  await expect(page.getByRole('heading', { level: 1, name: `Destino ${stamp}` })).toBeVisible()

  await page.goto('/inversiones/informe-fiscal?anio=2026')
  await page.getByText(`Destino ${stamp}`).click()
  // 5 of the 20 units received: a quarter of the 1.000 € cost, bought on 10/05/2024
  const sold = page.getByRole('region', { name: `Lotes vendidos de Destino ${stamp}` })
  await expect(sold).toContainText('10 may 2024')
  await expect(sold).toContainText('250,00 €')
  await expect(sold).toContainText('50,00 €')
})
