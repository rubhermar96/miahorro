import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { account, categories, page, transaction } from '../test/financeData'
import { fullSession, healthOk, mockApi } from '../test/mockApi'
import { renderApp } from '../test/render'

let api: ReturnType<typeof mockApi>

const mapping = {
  date: 'Fecha',
  description: ['Concepto'],
  amount: 'Importe',
  debit: null,
  credit: null,
  balance: 'Saldo',
  date_order: 'dmy',
  decimal_comma: true,
  invert_sign: false,
}

const row = (fields: Record<string, unknown>) => ({
  number: 2,
  date: '2026-10-15',
  description: 'COMPRA MERCADONA',
  amount: '-45.20',
  balance: '954.80',
  status: 'new',
  category_id: 'groceries',
  match_id: null,
  ...fields,
})

const preview = (fields: Record<string, unknown> = {}) => ({
  columns: ['Fecha', 'Concepto', 'Importe', 'Saldo'],
  sample: [['15/10/2026', 'COMPRA MERCADONA', '-45,20', '954,80']],
  mapping,
  template_id: null,
  error: null,
  rows: [
    row({}),
    row({ number: 3, description: 'NÓMINA', amount: '2000.00', status: 'duplicate' }),
    row({ number: 4, description: 'BAR', amount: '-3.00', status: 'possible_duplicate' }),
  ],
  skipped: [{ number: 5, reason: 'Sin fecha.', text: 'Total · 1.951,80' }],
  bank_balance: '954.80',
  bank_balance_date: '2026-10-15',
  balance_then: '954.80',
  ...fields,
})

const batch = {
  id: 'imp-1',
  account_id: 'acc-1',
  filename: 'extracto.csv',
  template_name: null,
  imported: 1,
  skipped: 2,
  date_from: '2026-10-15',
  date_to: '2026-10-15',
  created_at: '2026-10-16T08:00:00Z',
}

const statement = () => new File(['Fecha;Concepto;Importe\n'], 'extracto.csv', { type: 'text/csv' })

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-16T08:00:00Z') })
  api = mockApi({
    'GET /api/auth/session': fullSession,
    'GET /api/health': healthOk,
    'GET /api/accounts': { status: 200, body: [account()] },
    'GET /api/categories': { status: 200, body: categories },
    'GET /api/import-templates': { status: 200, body: [] },
    'GET /api/imports': { status: 200, body: [] },
    'GET /api/rules': { status: 200, body: [] },
    'GET /api/transactions': { status: 200, body: page([]) },
    'POST /api/imports/preview': { status: 200, body: preview() },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function choose(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(await screen.findByLabelText(/Fichero del banco/), statement())
  await user.click(screen.getByRole('button', { name: 'Ver movimientos' }))
}

describe('import', () => {
  it('previews a file and imports only the new rows by default', async () => {
    const user = userEvent.setup()
    api.on('POST /api/imports', { status: 201, body: batch })
    renderApp('/importar')

    await choose(user)

    expect(api.callsTo('POST /api/imports/preview')[0]?.body).toEqual({
      file: expect.any(String) as unknown,
      account_id: 'acc-1',
    })
    expect(await screen.findByText('1 nuevo · 1 ya importado · 1 quizá ya apuntado')).toBeVisible()
    expect(screen.getByRole('checkbox', { name: /COMPRA MERCADONA/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /NÓMINA/ })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: /BAR.*¿Ya apuntado\?/ })).not.toBeChecked()
    expect(screen.getByText('Cuadra con el banco.')).toBeInTheDocument()
    expect(screen.getByText('1 fila del fichero no es un movimiento')).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: /BAR/ }))
    await user.click(screen.getByRole('button', { name: 'Importar 2 movimientos' }))

    expect(api.callsTo('POST /api/imports')[0]?.body).toMatchObject({
      account_id: 'acc-1',
      mapping: JSON.stringify(mapping),
      rows: '[2,4]',
    })
    expect(await screen.findByText('1 movimiento importado en Nómina.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver movimientos' })).toHaveAttribute(
      'href',
      '/movimientos?cuenta=acc-1',
    )
  })

  it('asks for the columns when the file is not recognised', async () => {
    const user = userEvent.setup()
    api.on('POST /api/imports/preview', {
      status: 200,
      body: preview({
        columns: ['Dia', 'Que', 'Cuanto'],
        mapping: null,
        rows: [],
        skipped: [],
        bank_balance: null,
        bank_balance_date: null,
        balance_then: null,
        error: 'Indica qué columna es la fecha, el concepto y el importe.',
      }),
    })
    renderApp('/importar')
    await choose(user)

    expect(
      await screen.findByText('Indica qué columna es la fecha, el concepto y el importe.'),
    ).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Fecha'), 'Dia')
    await user.selectOptions(screen.getByLabelText('Concepto'), 'Que')
    await user.selectOptions(screen.getByLabelText('Importe'), 'Cuanto')

    const last = api.callsTo('POST /api/imports/preview').at(-1)?.body as Record<string, string>
    expect(JSON.parse(last.mapping ?? '{}')).toEqual({
      date: 'Dia',
      description: ['Que'],
      amount: 'Cuanto',
      balance: null,
      invert_sign: false,
      date_order: null,
      decimal_comma: null,
    })
  })

  it('saves the columns as a shared template when asked', async () => {
    const user = userEvent.setup()
    api.on('POST /api/imports', { status: 201, body: batch })
    renderApp('/importar')
    await choose(user)

    await user.click(await screen.findByLabelText('Guardar estas columnas como plantilla'))
    await user.type(screen.getByLabelText(/Nombre del banco/), 'Bankinter')
    await user.click(screen.getByRole('button', { name: 'Importar 1 movimiento' }))

    expect(api.callsTo('POST /api/imports')[0]?.body).toMatchObject({
      save_template_as: 'Bankinter',
    })
  })

  it('shows server errors such as a PDF', async () => {
    const user = userEvent.setup()
    api.on('POST /api/imports/preview', {
      status: 422,
      body: { error: { code: 'validation_error', message: 'Los PDF no se pueden importar.' } },
    })
    renderApp('/importar')
    await choose(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('Los PDF no se pueden importar.')
  })

  it('undoes an earlier import', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.on('GET /api/imports', { status: 200, body: [batch] })
    api.on('DELETE /api/imports/imp-1', { status: 204 })
    renderApp('/importar?cuenta=acc-1')

    const history = await screen.findByRole('region', { name: 'Importaciones anteriores' })
    await user.click(within(history).getByRole('button', { name: 'Deshacer' }))

    expect(window.confirm).toHaveBeenCalledWith(
      '¿Deshacer la importación? Se borrarán sus 1 movimientos, también si los has editado.',
    )
    expect(api.callsTo('DELETE /api/imports/imp-1')).toHaveLength(1)
    expect(await screen.findByText('Importación deshecha.')).toBeInTheDocument()
  })
})

describe('rules', () => {
  const rule = {
    id: 'rule-1',
    match_text: 'MERCADONA',
    category_id: 'groceries',
    account_id: null,
    amount_min: null,
    amount_max: '100.00',
    position: 0,
  }

  it('creates a rule and applies it to existing movements', async () => {
    const user = userEvent.setup()
    api.on('POST /api/rules', { status: 201, body: { rule, applied: 3 } })
    renderApp('/mas/reglas')

    await user.type(await screen.findByLabelText('El concepto contiene'), 'MERCADONA')
    await user.selectOptions(screen.getByLabelText('Categoría'), 'groceries')
    await user.click(screen.getByRole('button', { name: 'Añadir regla' }))

    expect(api.callsTo('POST /api/rules')[0]?.body).toEqual({
      match_text: 'MERCADONA',
      category_id: 'groceries',
      account_id: null,
      amount_min: null,
      amount_max: null,
      apply_to_existing: true,
    })
    expect(
      await screen.findByText('Regla creada. 3 movimientos recategorizados.'),
    ).toBeInTheDocument()
  })

  it('lists rules in order and moves them', async () => {
    const user = userEvent.setup()
    api.on('GET /api/rules', {
      status: 200,
      body: [rule, { ...rule, id: 'rule-2', match_text: 'AMAZON', amount_max: null, position: 1 }],
    })
    api.on('PATCH /api/rules/rule-2', { status: 200, body: rule })
    renderApp('/mas/reglas')

    expect(await screen.findByText('«MERCADONA»')).toBeInTheDocument()
    expect(screen.getByText('Alimentación › Supermercado · hasta 100,00 €')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Subir «MERCADONA»' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Subir «AMAZON»' }))

    expect(api.callsTo('PATCH /api/rules/rule-2')[0]?.body).toEqual({ position: 0 })
  })
})

describe('correcting a category', () => {
  it('offers a rule after a category is changed by hand', async () => {
    const user = userEvent.setup()
    api.on('GET /api/transactions/tx-1', {
      status: 200,
      body: transaction({ category_id: null, description: 'COMPRA TARJ. MERCADONA' }),
    })
    api.on('PATCH /api/transactions/tx-1', { status: 200, body: transaction() })
    api.on('GET /api/rules/suggestion', {
      status: 200,
      body: { match_text: 'MERCADONA', matches: 4 },
    })
    api.on('POST /api/rules', { status: 201, body: { rule: {}, applied: 4 } })
    renderApp('/movimientos/tx-1')

    await user.selectOptions(await screen.findByLabelText('Categoría'), 'groceries')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(await screen.findByRole('heading', { name: '¿Hacerlo siempre así?' })).toBeVisible()
    expect(screen.getByLabelText(/irán a Alimentación › Supermercado/)).toHaveValue('MERCADONA')
    expect(
      screen.getByLabelText('Cambiar también 4 movimientos parecidos que ya tienes'),
    ).toBeChecked()
    await user.click(screen.getByRole('button', { name: 'Crear regla' }))

    expect(api.callsTo('POST /api/rules')[0]?.body).toEqual({
      match_text: 'MERCADONA',
      category_id: 'groceries',
      apply_to_existing: true,
    })
  })

  it('does not ask when the category did not change', async () => {
    api.on('GET /api/transactions/tx-1', { status: 200, body: transaction() })
    api.on('PATCH /api/transactions/tx-1', { status: 200, body: transaction() })
    const user = userEvent.setup()
    renderApp('/movimientos/tx-1')

    await user.click(await screen.findByRole('button', { name: 'Guardar' }))

    expect(api.callsTo('GET /api/rules/suggestion')).toEqual([])
  })
})

describe('bulk edit', () => {
  it('recategorises the picked movements', async () => {
    const user = userEvent.setup()
    api.on('GET /api/transactions', {
      status: 200,
      body: page([
        transaction(),
        transaction({ id: 'tx-2', description: 'Lidl' }),
        transaction({ id: 'tx-3', description: 'Cine' }),
      ]),
    })
    api.on('POST /api/transactions/bulk', { status: 200, body: { affected: 2 } })
    renderApp('/movimientos')

    await user.click(await screen.findByRole('button', { name: 'Seleccionar' }))
    await user.click(screen.getByRole('checkbox', { name: /Mercadona/ }))
    await user.click(screen.getByRole('checkbox', { name: /Lidl/ }))
    const bar = screen.getByRole('region', { name: '2 seleccionados' })
    await user.selectOptions(within(bar).getByLabelText('Poner categoría'), 'restaurants')
    await user.click(within(bar).getByRole('button', { name: 'Aplicar' }))

    expect(api.callsTo('POST /api/transactions/bulk')[0]?.body).toEqual({
      ids: ['tx-1', 'tx-2'],
      action: 'categorise',
      category_id: 'restaurants',
    })
    expect(await screen.findByText('2 movimientos actualizados.')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: /Mercadona/ })).not.toBeInTheDocument()
  })

  it('deletes the picked movements after confirming', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.on('GET /api/transactions', { status: 200, body: page([transaction()]) })
    api.on('POST /api/transactions/bulk', { status: 200, body: { affected: 1 } })
    renderApp('/movimientos')

    await user.click(await screen.findByRole('button', { name: 'Seleccionar' }))
    await user.click(screen.getByRole('button', { name: 'Seleccionar los 1 cargados' }))
    await user.click(screen.getByRole('button', { name: 'Borrar' }))

    expect(api.callsTo('POST /api/transactions/bulk')[0]?.body).toEqual({
      ids: ['tx-1'],
      action: 'delete',
    })
    expect(await screen.findByText('1 movimiento borrado.')).toBeInTheDocument()
  })
})
