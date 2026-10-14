import { expect, test } from '@playwright/test'

test('la app carga, conecta con el servidor y navega', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { level: 1, name: 'Inicio' })).toBeVisible()
  await expect(page.getByText(/Conectado · versión \d+\.\d+\.\d+/)).toBeVisible()

  await page.getByRole('link', { name: 'Más' }).click()
  await expect(page).toHaveURL(/\/mas$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Más' })).toBeVisible()
})

test('las direcciones de la app funcionan al abrirlas directamente', async ({ page }) => {
  await page.goto('/movimientos')

  await expect(page.getByRole('heading', { level: 1, name: 'Movimientos' })).toBeVisible()
})

test('se puede instalar en la pantalla de inicio', async ({ page, request }) => {
  await page.goto('/')
  const manifestHref = await page.locator('link[rel="manifest"]').getAttribute('href')
  expect(manifestHref).toBeTruthy()

  const manifest = await (await request.get(manifestHref!)).json()
  expect(manifest).toMatchObject({ name: 'MiAhorro', display: 'standalone', lang: 'es-ES' })

  for (const path of ['/apple-touch-icon-180x180.png', '/pwa-512x512.png', '/sw.js']) {
    expect((await request.get(path)).ok(), path).toBe(true)
  }
})

test('envía cabeceras de seguridad', async ({ request }) => {
  const response = await request.get('/')
  const headers = response.headers()

  expect(headers['content-security-policy']).toContain("default-src 'self'")
  expect(headers['x-content-type-options']).toBe('nosniff')
  expect(headers['x-frame-options']).toBe('DENY')
})

test('la API responde a través del proxy', async ({ request }) => {
  const health = await request.get('/api/health')
  expect(health.status()).toBe(200)
  expect(await health.json()).toMatchObject({ status: 'ok', database: 'ok' })
})
