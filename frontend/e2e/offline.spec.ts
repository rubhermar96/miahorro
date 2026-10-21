import { expect, test } from '@playwright/test'

// Signed in (see auth.setup.ts). "Modo avión": the network goes down with the app open.

test('apuntar un gasto sin conexión y que se envíe una sola vez al volver', async ({
  page,
  context,
}) => {
  const name = `Sin red ${Date.now()}`
  const created = await page.request.post('/api/accounts', {
    data: { name, kind: 'checking', opening_date: '2026-01-01', opening_balance: '100' },
    headers: { 'X-MiAhorro-CSRF': '1' },
  })
  expect(created.ok()).toBe(true)
  const account = ((await created.json()) as { id: string }).id

  await page.goto('/anadir')
  await page.getByLabel('Cuenta').selectOption({ label: name })
  await context.setOffline(true)

  await page.getByLabel('Importe').fill('7,30')
  await page.getByRole('button', { name: 'Más categorías' }).click()
  await page
    .getByRole('button', { name: /Supermercado/ })
    .first()
    .click()
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText(/Sin conexión: 7,30\s€ queda guardado/)).toBeVisible()
  await expect(page.getByText('1 movimiento pendiente de enviar.')).toBeVisible()

  await context.setOffline(false)
  // Back online: it goes by itself, or on opening the app again.
  await page.reload()
  await expect(page.getByText('1 movimiento pendiente de enviar.')).toHaveCount(0)

  const list = await page.request.get(`/api/transactions?account_id=${account}`)
  const body = (await list.json()) as { total: number; items: { amount: string }[] }
  expect(body.total).toBe(1)
  expect(body.items[0]?.amount).toBe('-7.30')
})
