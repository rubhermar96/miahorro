import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { account, categories, page, transaction } from '../test/financeData'
import { fullSession, healthOk, mockApi } from '../test/mockApi'
import { renderApp } from '../test/render'

let api: ReturnType<typeof mockApi>

const investment = (fields: Record<string, unknown> = {}) => ({
  id: 'inv-1',
  name: 'Fondo indexado',
  kind: 'fund',
  isin: 'IE00B4L5Y983',
  ticker: null,
  account_id: 'acc-1',
  note: null,
  archived: false,
  units: '10.5',
  cost: '1052.50',
  average_cost: '100.238095',
  price: '112.5',
  price_date: '2026-10-14',
  price_source: 'manual',
  value: '1181.25',
  gain: '128.75',
  gain_percent: '12.23',
  realized_total: '0.00',
  realized_year: '0.00',
  dividends_year: '0.00',
  withholding_year: '0.00',
  ...fields,
})

const portfolio = {
  value: '1181.25',
  cost: '1052.50',
  gain: '128.75',
  gain_percent: '12.23',
  unpriced: 0,
  realized_year: '346.50',
  dividends_year: '0.00',
  withholding_year: '0.00',
  year: 2026,
  by_kind: [{ kind: 'fund', value: '1181.25' }],
}

const operation = (fields: Record<string, unknown> = {}) => ({
  id: 'op-1',
  investment_id: 'inv-1',
  date: '2026-01-10',
  kind: 'buy',
  direction: 'out',
  units: '10.5',
  amount: '1050.00',
  fee: '2.50',
  withholding: '0.00',
  split_from: null,
  split_to: null,
  target_investment_id: null,
  target_units: null,
  price: '100',
  cash_account_id: 'acc-1',
  transaction_id: 'tx-9',
  gain: null,
  note: null,
  ...fields,
})

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-16T08:00:00Z') })
  const detail = {
    ...investment(),
    lots: [{ acquired: '2026-01-10', units: '10.5', cost: '1052.50' }],
  }
  api = mockApi({
    'GET /api/auth/session': fullSession,
    'GET /api/health': healthOk,
    'GET /api/accounts': { status: 200, body: [account({ balance: '2000.00' })] },
    'GET /api/categories': { status: 200, body: categories },
    'GET /api/transactions': { status: 200, body: page([]) },
    'GET /api/inbox': { status: 200, body: { unconfirmed: [], overdue: [] } },
    'GET /api/recurring/upcoming': { status: 200, body: [] },
    'GET /api/investments': { status: 200, body: [investment()] },
    'GET /api/investments/inv-1': { status: 200, body: detail },
    'GET /api/investments/inv-1/operations': { status: 200, body: [operation()] },
    'GET /api/investments/inv-1/prices': { status: 200, body: [] },
    'GET /api/portfolio': { status: 200, body: portfolio },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('investments', () => {
  it('are listed on the home screen', async () => {
    renderApp('/')

    const list = await screen.findByRole('region', { name: 'Inversiones' })
    expect(await within(list).findByText('+12,23 %')).toBeInTheDocument()
    expect(within(list).getByRole('link', { name: /Fondo indexado/ })).toHaveAttribute(
      'href',
      '/inversiones/inv-1',
    )
  })

  it('show the portfolio and each investment', async () => {
    renderApp('/inversiones')

    const summary = await screen.findByRole('region', { name: 'Resumen de la cartera' })
    expect(within(summary).getByText('1.181,25 €')).toBeInTheDocument()
    expect(within(summary).getByText('(+12,23 %)')).toBeInTheDocument()
    expect(within(summary).getByText('+346,50 €')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Informe fiscal de 2026/ })).toHaveAttribute(
      'href',
      '/inversiones/informe-fiscal',
    )
    expect(screen.getByRole('link', { name: /Fondo indexado/ })).toHaveTextContent('+12,23 %')
  })

  it('creates an investment with its ISIN', async () => {
    const user = userEvent.setup()
    api.on('POST /api/investments', { status: 201, body: investment({ id: 'inv-2' }) })
    api.on('GET /api/investments/inv-2', {
      status: 200,
      body: { ...investment({ id: 'inv-2' }), lots: [] },
    })
    api.on('GET /api/investments/inv-2/operations', { status: 200, body: [] })
    api.on('GET /api/investments/inv-2/prices', { status: 200, body: [] })
    renderApp('/inversiones/nueva')

    await user.type(await screen.findByLabelText('Nombre'), 'iShares Core MSCI World')
    await user.selectOptions(screen.getByLabelText('Tipo'), 'etf')
    await user.type(screen.getByLabelText('ISIN'), 'ie00b4l5y983')
    await user.selectOptions(screen.getByLabelText(/^Cuenta donde está/), 'acc-1')
    await user.click(screen.getByRole('button', { name: 'Añadir inversión' }))

    expect(api.callsTo('POST /api/investments')[0]?.body).toEqual({
      name: 'iShares Core MSCI World',
      kind: 'etf',
      isin: 'ie00b4l5y983',
      ticker: null,
      account_id: 'acc-1',
      note: null,
    })
  })

  it('shows what it holds and updates the price', async () => {
    const user = userEvent.setup()
    api.on('PUT /api/investments/inv-1/prices', {
      status: 200,
      body: { id: 'p1', date: '2026-10-16', price: '113.2' },
    })
    renderApp('/inversiones/inv-1')

    const summary = await screen.findByRole('region', { name: 'Situación de la inversión' })
    expect(within(summary).getByText('1.181,25 €')).toBeInTheDocument()
    expect(within(summary).getByText('10,5')).toBeInTheDocument()
    expect(within(summary).getByText('100,238095 €')).toBeInTheDocument()
    const ops = await screen.findByRole('region', { name: 'Operaciones' })
    expect(within(ops).getByRole('link', { name: /Compra/ })).toHaveTextContent('10,5 a 100 €')

    await user.type(screen.getByLabelText('Precio por participación (€)'), '113,2')
    await user.click(screen.getByRole('button', { name: 'Guardar precio' }))
    expect(api.callsTo('PUT /api/investments/inv-1/prices')[0]?.body).toEqual({
      date: '2026-10-16',
      price: '113.2',
    })
  })

  it('records a purchase charged to its account', async () => {
    const user = userEvent.setup()
    api.on('POST /api/investments/inv-1/operations', { status: 201, body: operation() })
    renderApp('/inversiones/inv-1/operaciones/nueva')

    await user.type(await screen.findByLabelText('Participaciones'), '10,5')
    await user.type(screen.getByLabelText(/^Importe pagado \(€\)/), '1.050')
    expect(screen.getByText(/Precio: 100 €/)).toBeInTheDocument()
    await user.type(screen.getByLabelText('Comisión (€)'), '2,5')
    expect(screen.getByLabelText(/^Cuenta de cargo o abono/)).toHaveValue('acc-1')
    await user.click(screen.getByRole('button', { name: 'Guardar operación' }))

    expect(api.callsTo('POST /api/investments/inv-1/operations')[0]?.body).toEqual({
      date: '2026-10-16',
      kind: 'buy',
      units: '10.5',
      amount: '1050.00',
      fee: '2.50',
      withholding: '0.00',
      note: null,
      cash_account_id: 'acc-1',
    })
  })

  it('transfers to another fund keeping the cost', async () => {
    const user = userEvent.setup()
    api.on('GET /api/investments', {
      status: 200,
      body: [investment(), investment({ id: 'inv-2', name: 'Fondo B', isin: null })],
    })
    api.on('POST /api/investments/inv-1/operations', { status: 201, body: operation() })
    renderApp('/inversiones/inv-1/operaciones/nueva')

    await user.selectOptions(await screen.findByLabelText('Operación'), 'transfer')
    await user.click(screen.getByRole('button', { name: 'Todas' }))
    await user.type(screen.getByLabelText('Participaciones recibidas'), '20')
    await user.click(screen.getByRole('button', { name: 'Guardar operación' }))

    expect(api.callsTo('POST /api/investments/inv-1/operations')[0]?.body).toMatchObject({
      kind: 'transfer',
      units: '10.5',
      target_investment_id: 'inv-2',
      target_units: '20',
      cash_account_id: null,
    })
  })

  it('calls pension plan operations by their names', async () => {
    api.on('GET /api/investments/inv-1', {
      status: 200,
      body: { ...investment({ kind: 'pension_plan' }), lots: [] },
    })
    renderApp('/inversiones/inv-1/operaciones/nueva')

    const kinds = await screen.findByLabelText('Operación')
    expect(
      within(kinds)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Aportación', 'Rescate', 'Traspaso'])
  })

  it('lists the year sales by FIFO for the tax return', async () => {
    const user = userEvent.setup()
    api.on('GET /api/portfolio/tax-report', {
      status: 200,
      body: {
        year: 2026,
        sales: [
          {
            operation_id: 's1',
            investment_id: 'inv-3',
            name: 'Acciones',
            kind: 'stock',
            date: '2026-03-10',
            units: '10',
            proceeds: '800.00',
            cost: '1000.00',
            gain: '-200.00',
            withholding: '0.00',
            taxable: true,
            repurchase_warning: true,
            parts: [
              {
                acquired: '2025-03-10',
                units: '10',
                cost: '1000.00',
                proceeds: '800.00',
                gain: '-200.00',
              },
            ],
          },
        ],
        gains: '0.00',
        losses: '-200.00',
        net: '-200.00',
        sale_withholding: '0.00',
        dividends: [],
        dividends_gross: '0.00',
        dividends_withholding: '0.00',
        pension_rescues: '0.00',
      },
    })
    renderApp('/inversiones/informe-fiscal')

    const summary = await screen.findByRole('region', { name: 'Resumen para la declaración' })
    expect(within(summary).getByText('Resultado neto').parentElement).toHaveTextContent('-200,00 €')
    await user.click(screen.getByText('Acciones'))
    expect(screen.getByRole('region', { name: 'Lotes vendidos de Acciones' })).toHaveTextContent(
      '10 mar 2025',
    )
    expect(screen.getByText(/dos meses anteriores o posteriores/)).toBeVisible()
    expect(api.callsTo('GET /api/portfolio/tax-report')[0]?.query.get('year')).toBe('2026')
  })

  it('keep investment movements editable only from the investment', async () => {
    api.on('GET /api/transactions/tx-9', {
      status: 200,
      body: transaction({ id: 'tx-9', kind: 'investment', amount: '-1052.50', category_id: null }),
    })
    renderApp('/movimientos/tx-9')

    expect(await screen.findByText(/Viene de una operación de inversión/)).toBeInTheDocument()
    expect(screen.getByLabelText('Importe')).toBeDisabled()
  })
})
