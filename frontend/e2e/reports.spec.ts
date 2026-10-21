import { readFile } from 'node:fs/promises'

import { expect, test } from '@playwright/test'

// Signed in (see auth.setup.ts). Other tests add data at the same time, so this one checks
// that each piece is there and adds up, not exact totals.

test('el panel lleva del patrimonio neto a los informes', async ({ page }) => {
  const stamp = Date.now()
  const response = await page.request.post('/api/accounts', {
    data: {
      name: `Panel ${stamp}`,
      kind: 'checking',
      opening_date: '2026-01-01',
      opening_balance: '1000',
    },
    headers: { 'X-MiAhorro-CSRF': '1' },
  })
  expect(response.ok()).toBe(true)

  await page.goto('/')
  const worth = page.getByRole('region', { name: 'Patrimonio neto' })
  await expect(worth).toBeVisible()
  await expect(worth).toContainText('Cuentas')
  await expect(page.getByRole('link', { name: /Ahorrado este mes/ })).toBeVisible()

  await worth.getByRole('link', { name: 'Ver evolución e informes' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Informes' })).toBeVisible()
  await expect(page.getByRole('img', { name: /Evolución del patrimonio neto/ })).toBeVisible()
  await page.getByText('Ver como tabla').click()
  await expect(
    page.getByRole('region', { name: 'Patrimonio neto a fin de cada mes' }),
  ).toContainText('31 ene 2026')

  await page.getByRole('radio', { name: 'Ingresos y gastos' }).click()
  await expect(page.getByLabel('Totales del periodo')).toBeVisible()
  await expect(page.getByText('Ingresos frente a gastos')).toBeVisible()

  await page.getByRole('radio', { name: 'Gastos', exact: true }).click()
  await expect(page.getByText(/^Gastado del/)).toBeVisible()
})

test('exportar todos los datos en JSON y volver a leerlos', async ({ page }) => {
  await page.goto('/mas')
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'Descargar JSON' }).click(),
  ])

  expect(download.suggestedFilename()).toMatch(/^miahorro-\d{4}-\d{2}-\d{2}\.json$/)
  const data = JSON.parse(await readFile(await download.path(), 'utf-8')) as {
    format: string
    tables: Record<string, unknown[]>
  }
  expect(data.format).toBe('miahorro-export')
  expect(data.tables.accounts?.length).toBeGreaterThan(0)
  expect(Object.keys(data.tables)).toContain('transactions')
})
