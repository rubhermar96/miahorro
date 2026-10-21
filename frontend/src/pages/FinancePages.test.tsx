import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { account, categories, page, transaction } from '../test/financeData'
import { fullSession, healthOk, mockApi } from '../test/mockApi'
import { renderApp } from '../test/render'

let api: ReturnType<typeof mockApi>

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-16T08:00:00Z') })
  api = mockApi({
    'GET /api/auth/session': fullSession,
    'GET /api/health': healthOk,
    'GET /api/accounts': { status: 200, body: [account()] },
    'GET /api/categories': { status: 200, body: categories },
    'GET /api/transactions': { status: 200, body: page([]) },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('home', () => {
  it('invites to add the first account', async () => {
    api.on('GET /api/accounts', { status: 200, body: [] })
    renderApp('/')

    expect(
      await screen.findByRole('heading', { name: 'Empieza por tus cuentas' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Añadir cuenta' })).toHaveAttribute(
      'href',
      '/cuentas/nueva',
    )
  })

  it('leads with net worth and lists the accounts by kind', async () => {
    const worth = (fields: Record<string, unknown>) => ({
      date: '2026-10-16',
      accounts: '10000.30',
      investments: '0.00',
      lent: '0.00',
      debts: '0.00',
      total: '10000.30',
      other_currencies: { USD: '50.00' },
      ...fields,
    })
    api.on('GET /api/dashboard', {
      status: 200,
      body: {
        today: '2026-10-16',
        net_worth: worth({}),
        previous: worth({ date: '2026-09-30', total: '9800.30' }),
        available: '0.30',
        reserved: '0.00',
        month: {
          start: '2026-10-01',
          end: '2026-10-16',
          income: '2000.00',
          expenses: '-450.00',
          saved: '1550.00',
          rate: '77.5',
        },
        savings_target: null,
      },
    })
    api.on('GET /api/accounts', {
      status: 200,
      body: [
        account({ balance: '0.10' }),
        account({ id: 'acc-2', name: 'Ahorro', kind: 'savings', balance: '0.20' }),
        account({
          id: 'acc-3',
          name: 'Revolut USD',
          kind: 'wallet',
          currency: 'USD',
          balance: '50',
        }),
        account({
          id: 'acc-4',
          name: 'Depósito',
          kind: 'deposit',
          balance: '10000',
          maturity_date: '2026-12-01',
        }),
      ],
    })
    renderApp('/')

    const total = await screen.findByRole('region', { name: 'Patrimonio neto' })
    expect(within(total).getAllByText('10.000,30 €')).toHaveLength(2) // the total and accounts
    expect(within(total).getByText('+200,00 €')).toBeInTheDocument()
    expect(within(total).getByText('desde el 30 sept 2026')).toBeInTheDocument()
    expect(within(total).getByText('Además: 50,00 USD')).toBeInTheDocument()
    const month = screen.getByRole('link', { name: /Ahorrado este mes/ })
    expect(month).toHaveTextContent('+1.550,00 €')
    expect(month).toHaveTextContent(
      'Ingresos 2.000,00 € · gastos 450,00 € · 77,5 % de tus ingresos',
    )
    expect(screen.getByRole('region', { name: 'Ahorro' })).toHaveTextContent('0,20 €')
    expect(screen.getByRole('link', { name: 'Depósito vence el 1 dic 2026' })).toHaveAttribute(
      'href',
      '/cuentas/acc-4',
    )
  })
})

describe('dashboard', () => {
  it('shows the first goals and the next loan instalment among what is coming', async () => {
    api.on('GET /api/goals', {
      status: 200,
      body: [
        {
          id: 'goal-1',
          name: 'Entrada del piso',
          target_amount: '12000.00',
          target_date: '2027-09-30',
          priority: 1,
          icon: '🏠',
          note: null,
          account_ids: [],
          pots: [],
          achieved: false,
          saved: '3000.00',
          remaining: '9000.00',
          percent: 25,
          required_monthly: '750.00',
          pace: '800.00',
          estimated_date: '2027-08-15',
          status: 'on_track',
        },
      ],
    })
    api.on('GET /api/recurring/upcoming', {
      status: 200,
      body: [
        { item_id: 'r1', name: 'Netflix', date: '2026-11-02', amount: '-12.99', overdue: false },
      ],
    })
    api.on('GET /api/loans', {
      status: 200,
      body: [
        {
          id: 'loan-1',
          name: 'Coche',
          direction: 'owe',
          next_payment: { date: '2026-11-05', amount: '281.82' },
        },
      ],
    })
    renderApp('/')

    const goals = await screen.findByRole('region', { name: 'Objetivos' })
    expect(within(goals).getByRole('progressbar', { name: /Entrada del piso/ })).toHaveAttribute(
      'aria-valuenow',
      '25',
    )
    const coming = await screen.findByRole('region', { name: 'Próximos 30 días' })
    const rows = within(within(coming).getByRole('list')).getAllByRole('link')
    expect(rows.map((row) => row.textContent?.replace(/\s/g, ' '))).toEqual([
      'Netflix2 nov 2026-12,99 €',
      'Coche5 nov 2026-281,82 €',
    ])
    expect(rows[1]).toHaveAttribute('href', '/planificar/prestamos/loan-1')
  })
})

describe('transactions', () => {
  it('lists transactions by day with totals', async () => {
    api.on('GET /api/transactions', {
      status: 200,
      body: page(
        [
          transaction(),
          transaction({ id: 'tx-3', amount: '-3.00', description: '' }),
          transaction({
            id: 'tx-2',
            date: '2026-10-14',
            kind: 'income',
            amount: '2000.00',
            description: '',
            category_id: 'salary',
          }),
        ],
        { income: '2000.00', expenses: '-45.20' },
      ),
    })
    renderApp('/movimientos')

    const today = await screen.findByRole('region', { name: 'jueves, 15 de octubre' })
    expect(within(today).getByRole('link', { name: /Mercadona/ })).toHaveAttribute(
      'href',
      '/movimientos/tx-1',
    )
    expect(within(today).getByText('Alimentación › Supermercado · Nómina')).toBeInTheDocument()
    expect(within(today).getByText('-45,20 €')).toBeInTheDocument()
    // Without a concept, the category is the title and is not repeated below.
    expect(
      within(today).getByRole('link', { name: /^Supermercado\s*Alimentación · Nómina/ }),
    ).toHaveAttribute('href', '/movimientos/tx-3')
    const before = screen.getByRole('region', { name: 'miércoles, 14 de octubre' })
    expect(within(before).getByText('+2.000,00 €')).toBeInTheDocument()
    expect(screen.getByText('3 movimientos')).toBeInTheDocument()
  })

  it('shows the balance after each movement for a single account', async () => {
    api.on('GET /api/accounts', {
      status: 200,
      body: [account(), account({ id: 'acc-2', name: 'Ahorro' })],
    })
    api.on('GET /api/transactions', {
      status: 200,
      body: page([transaction({ balance_after: '954.80' })]),
    })
    const { unmount } = renderApp('/movimientos')
    expect(await screen.findByText('Mercadona')).toBeInTheDocument()
    expect(screen.queryByText('Saldo 954,80 €')).not.toBeInTheDocument() // two accounts mixed
    unmount()

    renderApp('/movimientos?cuenta=acc-1')

    expect(await screen.findByText('Saldo 954,80 €')).toBeInTheDocument()
  })

  it('searches and filters through the URL', async () => {
    const user = userEvent.setup()
    const { router } = renderApp('/movimientos')

    await user.type(await screen.findByRole('searchbox', { name: 'Buscar' }), 'merca')
    await user.click(screen.getByRole('button', { name: 'Buscar' }))
    await user.click(screen.getByText('Filtros'))
    await user.selectOptions(screen.getByLabelText('Cuenta'), 'acc-1')

    expect(router.state.location.search).toBe('?texto=merca&cuenta=acc-1')
    const last = api.callsTo('GET /api/transactions').at(-1)
    expect(last?.query.get('q')).toBe('merca')
    expect(last?.query.get('account_id')).toBe('acc-1')
  })

  it('loads more on demand', async () => {
    const user = userEvent.setup()
    const items = Array.from({ length: 50 }, (_, i) => transaction({ id: `tx-${i}` }))
    api.on('GET /api/transactions', (request) => {
      const offset = new URL(request.url).searchParams.get('offset')
      return offset === '0'
        ? { status: 200, body: page(items, { total: 51 }) }
        : {
            status: 200,
            body: page([transaction({ id: 'tx-last', description: 'El último' })], { total: 51 }),
          }
    })
    renderApp('/movimientos')

    await user.click(await screen.findByRole('button', { name: 'Cargar más' }))

    expect(await screen.findByText('El último')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cargar más' })).not.toBeInTheDocument()
  })

  it('edits a transaction', async () => {
    const user = userEvent.setup()
    api.on('GET /api/transactions/tx-1', { status: 200, body: transaction() })
    api.on('PATCH /api/transactions/tx-1', { status: 200, body: transaction() })
    renderApp('/movimientos/tx-1')

    const amount = await screen.findByLabelText('Importe')
    expect(amount).toHaveValue('45,20')
    await user.clear(amount)
    await user.type(amount, '50')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(api.callsTo('PATCH /api/transactions/tx-1')[0]?.body).toMatchObject({
      amount: '50.00',
      kind: 'expense',
      account_id: 'acc-1',
      category_id: 'groceries',
    })
  })

  it('warns that deleting a transfer deletes both sides', async () => {
    const user = userEvent.setup()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    api.on('GET /api/transactions/tx-1', {
      status: 200,
      body: transaction({ kind: 'transfer', transfer_id: 't', category_id: null }),
    })
    renderApp('/movimientos/tx-1')

    await user.click(await screen.findByRole('button', { name: 'Eliminar' }))

    expect(confirm).toHaveBeenCalledWith(
      '¿Eliminar la transferencia? Se borrarán sus dos movimientos.',
    )
    expect(screen.queryByLabelText('Cuenta')).not.toBeInTheDocument()
  })
})

describe('account', () => {
  beforeEach(() => {
    api.on('GET /api/accounts/acc-1', {
      status: 200,
      body: account({
        kind: 'savings',
        current_rate: {
          id: 'r1',
          valid_from: '2026-09-01',
          tiers: [
            { up_to: '10000.00', rate: '2.0000' },
            { up_to: null, rate: '0.0000' },
          ],
          tae: '2.0200',
          liquidation: 'monthly',
          withholding: '19.0000',
        },
      }),
    })
    api.on('GET /api/accounts/acc-1/rates', { status: 200, body: [] })
  })

  it('shows balance and the remuneration in force', async () => {
    renderApp('/cuentas/acc-1')

    expect(await screen.findByText('1.000,00 €')).toBeInTheDocument()
    expect(
      screen.getByText('Vigente: 2 % hasta 10.000,00 €, 0 % el resto · TAE 2,02 % · Mensual'),
    ).toBeInTheDocument()
  })

  it('reconciles with the bank', async () => {
    const user = userEvent.setup()
    api.on('POST /api/accounts/acc-1/reconcile', {
      status: 200,
      body: { adjustment: transaction({ kind: 'adjustment', amount: '-4.50' }), balance: '995.50' },
    })
    renderApp('/cuentas/acc-1')

    await user.click(await screen.findByText('Cuadrar con el banco'))
    await user.type(screen.getByLabelText('Saldo real'), '995,50')
    await user.click(screen.getByRole('button', { name: 'Cuadrar' }))

    expect(api.callsTo('POST /api/accounts/acc-1/reconcile')[0]?.body).toEqual({
      balance: '995.50',
    })
    expect(await screen.findByText('Cuadrado: ajuste de -4,50 €.')).toBeInTheDocument()
  })

  it('creates an account', async () => {
    const user = userEvent.setup()
    api.on('POST /api/accounts', { status: 201, body: account({ id: 'acc-9' }) })
    api.on('GET /api/accounts/acc-9', { status: 200, body: account({ id: 'acc-9' }) })
    api.on('GET /api/accounts/acc-9/rates', { status: 200, body: [] })
    const { router } = renderApp('/cuentas/nueva')

    await user.type(await screen.findByLabelText('Nombre'), 'Nómina')
    await user.type(screen.getByLabelText('Saldo'), '1.500,25')
    await user.type(screen.getByLabelText('Entidad'), 'Bankinter')
    await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    expect(api.callsTo('POST /api/accounts')[0]?.body).toMatchObject({
      name: 'Nómina',
      kind: 'checking',
      opening_balance: '1500.25',
      opening_date: '2026-10-16',
      institution: 'Bankinter',
      currency: 'EUR',
    })
    await screen.findByText('Últimos movimientos')
    expect(router.state.location.pathname).toBe('/cuentas/acc-9')
  })
})

describe('categories', () => {
  it('adds a subcategory', async () => {
    const user = userEvent.setup()
    api.on('POST /api/categories', { status: 201, body: categories[1] })
    renderApp('/mas/categorias')

    await user.type(await screen.findByLabelText('Nombre'), 'Mercados')
    await user.selectOptions(screen.getByLabelText('Dentro de'), 'food')
    await user.click(screen.getByRole('button', { name: 'Añadir categoría' }))

    expect(api.callsTo('POST /api/categories')[0]?.body).toEqual({
      name: 'Mercados',
      kind: 'expense',
      parent_id: 'food',
      icon: null,
    })
  })
})
