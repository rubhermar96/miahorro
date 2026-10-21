import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { account, categories, page } from '../test/financeData'
import { fullSession, healthOk, mockApi } from '../test/mockApi'
import { renderApp } from '../test/render'

let api: ReturnType<typeof mockApi>

const point = (date: string, total: string) => ({
  date,
  accounts: total,
  investments: '0.00',
  lent: '0.00',
  debts: '0.00',
  total,
  other_currencies: {},
})

const period = (start: string, end: string, income: string, expenses: string, rate: string) => ({
  start,
  end,
  income,
  expenses,
  saved: String(Number(income) + Number(expenses)) + '.00',
  rate,
})

const line = (fields: Record<string, unknown>) => ({
  icon: null,
  previous: '0.00',
  last_year: '0.00',
  children: [],
  ...fields,
})

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-16T08:00:00Z') })
  api = mockApi({
    'GET /api/auth/session': fullSession,
    'GET /api/health': healthOk,
    'GET /api/accounts': { status: 200, body: [account()] },
    'GET /api/categories': { status: 200, body: categories },
    'GET /api/transactions': { status: 200, body: page([]) },
    'GET /api/reports/net-worth': {
      status: 200,
      body: {
        start: '2026-01-01',
        points: [
          point('2026-08-31', '9000.00'),
          point('2026-09-30', '9500.00'),
          point('2026-10-16', '10000.30'),
        ],
      },
    },
    'GET /api/reports/cash-flow': {
      status: 200,
      body: {
        periods: [
          period('2026-09-01', '2026-09-30', '2000.00', '-1500.00', '25.0'),
          period('2026-10-01', '2026-10-16', '2000.00', '-450.00', '77.5'),
        ],
        total: period('2026-09-01', '2026-10-16', '4000.00', '-1950.00', '51.3'),
        savings_target: 20,
      },
    },
    'GET /api/reports/spending': {
      status: 200,
      body: {
        by: 'category',
        current: { start: '2026-10-01', end: '2026-10-16' },
        previous: { start: '2026-09-01', end: '2026-09-16' },
        last_year: { start: '2025-10-01', end: '2025-10-16' },
        total: '80.00',
        total_previous: '40.00',
        total_last_year: '20.00',
        lines: [
          line({
            key: 'food',
            label: 'Alimentación',
            icon: '🛒',
            amount: '80.00',
            previous: '40.00',
            children: [
              line({ key: 'groceries', label: 'Supermercado', amount: '50.00', previous: '40.00' }),
              line({ key: 'restaurants', label: 'Restaurantes', amount: '30.00' }),
            ],
          }),
        ],
      },
    },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('reports', () => {
  it('show how net worth has changed, with a table to read it', async () => {
    const user = userEvent.setup()
    renderApp('/informes')

    const chart = await screen.findByRole('img', { name: /Evolución del patrimonio neto/ })
    expect(screen.getByText('+1.000,30 €')).toBeInTheDocument()
    expect(screen.getByText('desde el 31 ago 2026')).toBeInTheDocument()

    fireEvent.focus(chart)
    expect(screen.getByRole('status')).toHaveTextContent('10.000,30 €')
    fireEvent.keyDown(chart, { key: 'ArrowLeft' })
    expect(screen.getByRole('status')).toHaveTextContent('9.500,00 €30 sept 2026')

    await user.click(screen.getByText('Ver como tabla'))
    const table = screen.getByRole('region', { name: 'Patrimonio neto a fin de cada mes' })
    expect(within(table).getAllByRole('row')).toHaveLength(4)

    await user.click(screen.getByRole('radio', { name: 'Este año' }))
    expect(api.callsTo('GET /api/reports/net-worth').at(-1)?.query.get('start')).toBe('2026-01-01')
  })

  it('compare income and expenses and the share saved', async () => {
    const user = userEvent.setup()
    renderApp('/informes?vista=flujo')

    const totals = await screen.findByLabelText('Totales del periodo')
    expect(totals).toHaveTextContent('4.000,00 €')
    expect(totals).toHaveTextContent('1.950,00 €')
    expect(totals).toHaveTextContent('51,3 % de tus ingresos')
    expect(
      screen.getByRole('img', {
        name: /^septiembre de 2026: Ingresos 2\.000,00\s€, Gastos 1\.500,00\s€$/,
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('progressbar', { name: 'Tasa de ahorro de octubre de 2026' }),
    ).toHaveAttribute('aria-valuenow', '78')

    await user.click(screen.getByRole('radio', { name: 'Por años' }))
    const call = api.callsTo('GET /api/reports/cash-flow').at(-1)
    expect([call?.query.get('group'), call?.query.get('start')]).toEqual(['year', '2022-01-01'])
  })

  it('show where the money goes against earlier periods', async () => {
    const user = userEvent.setup()
    renderApp('/informes?vista=gastos')

    const lines = await screen.findByRole('list', { name: 'Gasto por grupo' })
    expect(within(lines).getByText('🛒 Alimentación')).toBeInTheDocument()
    expect(lines).toHaveTextContent('Antes: 40,00 € (+100 %) · Hace un año: 0,00 €')
    await user.click(within(lines).getByText('2 subcategorías'))
    expect(within(lines).getByText('Restaurantes')).toBeVisible()
    expect(api.callsTo('GET /api/reports/spending')[0]?.query.get('start')).toBe('2026-10-01')

    await user.click(screen.getByRole('radio', { name: 'Comercio' }))
    expect(api.callsTo('GET /api/reports/spending').at(-1)?.query.get('by')).toBe('merchant')
    await user.click(screen.getByRole('radio', { name: 'Mes anterior' }))
    const last = api.callsTo('GET /api/reports/spending').at(-1)
    expect([last?.query.get('start'), last?.query.get('end')]).toEqual(['2026-09-01', '2026-09-30'])
  })

  it('let you download everything from Más', async () => {
    renderApp('/mas')

    expect(await screen.findByRole('link', { name: 'Descargar JSON' })).toHaveAttribute(
      'href',
      '/api/export.json',
    )
    expect(screen.getByRole('link', { name: 'Descargar CSV (ZIP)' })).toHaveAttribute(
      'href',
      '/api/export.zip',
    )
    expect(screen.getByRole('link', { name: /Informes/ })).toHaveAttribute('href', '/informes')
  })
})
