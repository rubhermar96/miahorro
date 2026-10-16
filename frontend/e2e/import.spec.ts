import { expect, type Page, test } from '@playwright/test'

// Signed in (see auth.setup.ts). Shared templates are never saved here: they would outlive
// the test users.

// As Spanish banks export it: preamble, ";" separator, comma decimals, Windows-1252.
const STATEMENT = Buffer.from(
  [
    'Movimientos de la cuenta;ES12 **** 1234',
    '',
    'Fecha operación;Fecha valor;Concepto;Importe;Saldo',
    '15/10/2026;15/10/2026;COMPRA TARJ. 1234 MERCADONA VALENCIA;-45,20;1.954,80',
    '14/10/2026;14/10/2026;NÓMINA OCTUBRE;2.000,00;2.000,00',
  ].join('\r\n'),
  'latin1',
)

async function newAccount(page: Page, name: string) {
  await page.goto('/cuentas/nueva')
  await page.getByLabel('Nombre').fill(name)
  await page.getByLabel('Saldo', { exact: true }).fill('0')
  await page.getByRole('button', { name: 'Crear cuenta' }).click()
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
}

async function chooseStatement(page: Page) {
  await page
    .getByLabel(/Fichero del banco/)
    .setInputFiles({ name: 'extracto.csv', mimeType: 'text/csv', buffer: STATEMENT })
  await page.getByRole('button', { name: 'Ver movimientos' }).click()
}

test('importar un extracto, reimportarlo sin duplicados y deshacerlo', async ({ page }) => {
  const name = `Importada ${Date.now()}`
  await newAccount(page, name)

  await page.getByRole('link', { name: 'Importar extracto' }).click()
  await chooseStatement(page)
  await expect(page.getByText('2 nuevos', { exact: true })).toBeVisible()
  await expect(page.getByText('Cuadra con el banco.')).toBeVisible()
  await page.getByRole('button', { name: 'Importar 2 movimientos' }).click()
  await expect(page.getByText(`2 movimientos importados en ${name}.`)).toBeVisible()

  await page.getByRole('button', { name: 'Importar otro fichero' }).click()
  await chooseStatement(page)
  await expect(page.getByText('0 nuevos · 2 ya importados')).toBeVisible()

  page.once('dialog', (dialog) => void dialog.accept())
  const history = page.getByRole('region', { name: 'Importaciones anteriores' })
  await history.getByRole('button', { name: 'Deshacer' }).click()
  await expect(page.getByText('Importación deshecha.')).toBeVisible()
})

test('una regla categoriza lo que se importa', async ({ page }) => {
  const name = `Con reglas ${Date.now()}`
  await newAccount(page, name)

  await page.goto('/mas/reglas')
  await page.getByLabel('El concepto contiene').fill('mercadona')
  await page.getByLabel('Categoría').selectOption({ label: '   Supermercado' })
  await page.getByRole('button', { name: 'Añadir regla' }).click()
  await expect(page.getByText('«mercadona»')).toBeVisible()

  await page.goto('/importar')
  await page.getByLabel('Cuenta').selectOption({ label: name })
  await chooseStatement(page)
  await expect(
    page.getByRole('checkbox', { name: /MERCADONA.*Alimentación › Supermercado/ }),
  ).toBeChecked()
  await page.getByRole('button', { name: 'Importar 2 movimientos' }).click()
  await page.getByRole('link', { name: 'Ver movimientos' }).click()

  await expect(
    page.getByRole('link', { name: /MERCADONA.*Alimentación › Supermercado/ }),
  ).toBeVisible()
})
