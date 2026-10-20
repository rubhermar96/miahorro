import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { account, categories, page } from '../test/financeData'
import { fullSession, healthOk, mockApi } from '../test/mockApi'
import { renderApp } from '../test/render'

let api: ReturnType<typeof mockApi>

const loan = (fields: Record<string, unknown> = {}) => ({
  id: 'loan-1',
  name: 'Coche',
  kind: 'car',
  lender: 'Banco',
  principal: '12000.00',
  signed_on: '2026-01-10',
  first_payment: '2026-02-05',
  term_months: 48,
  system: 'french',
  grace_months: 0,
  rate_type: 'fixed',
  fixed_rate: '6.0000',
  fixed_months: 0,
  index: null,
  spread: null,
  review_months: 12,
  tae: null,
  opening_fee: null,
  early_repayment_fee: '1.0000',
  account_id: null,
  note: null,
  archived: false,
  direction: 'owe',
  outstanding: '9963.23',
  principal_paid: '2036.77',
  interest_paid: '499.61',
  interest_left: '1029.97',
  next_payment: { date: '2026-11-05', amount: '281.82' },
  end_date: '2030-01-05',
  payments_left: 39,
  current_rate: '6.0000',
  warnings: [],
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
    'GET /api/goals': { status: 200, body: [] },
    'GET /api/savings-rate': { status: 200, body: { target: null, periods: [] } },
    'GET /api/budget': { status: 404 },
    'GET /api/loans': { status: 200, body: [loan()] },
    'GET /api/loans/loan-1': { status: 200, body: loan() },
    'GET /api/loans/loan-1/prepayments': { status: 200, body: [] },
    'GET /api/loans/loan-1/schedule': {
      status: 200,
      body: [
        {
          number: 1,
          date: '2026-02-05',
          rate: '6.0000',
          payment: '281.82',
          interest: '60.00',
          principal: '221.82',
          outstanding: '11778.18',
          paid: true,
          review: false,
        },
      ],
    },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('loans', () => {
  it('lists loans on Planificar with what is left and the next instalment', async () => {
    renderApp('/planificar')

    const loans = await screen.findByRole('region', { name: 'Préstamos' })
    const card = await within(loans).findByRole('link', { name: /Coche/ })
    expect(card).toHaveAttribute('href', '/planificar/prestamos/loan-1')
    expect(card).toHaveTextContent('9.963,23 €')
    expect(card).toHaveTextContent('Próxima cuota: 281,82 € el 5 nov 2026')
    expect(screen.getByText('Debes 9.963,23 €')).toBeInTheDocument()
  })

  it('creates a variable mortgage', async () => {
    const user = userEvent.setup()
    api.on('POST /api/loans', { status: 201, body: loan({ id: 'loan-2' }) })
    api.on('GET /api/loans/loan-2', { status: 200, body: loan({ id: 'loan-2' }) })
    api.on('GET /api/loans/loan-2/prepayments', { status: 200, body: [] })
    renderApp('/planificar/prestamos/nuevo')

    await user.type(await screen.findByLabelText('Nombre'), 'Hipoteca')
    await user.selectOptions(screen.getByLabelText('Tipo'), 'mortgage')
    await user.type(screen.getByLabelText('Capital'), '150.000')
    await user.type(screen.getByLabelText(/Plazo \(meses\)/), '300')
    await user.type(screen.getByLabelText('Primera cuota'), '2026-02-05')
    await user.click(screen.getByRole('radio', { name: 'Variable' }))
    await user.type(screen.getByLabelText('Tipo inicial (%)'), '1,99')
    await user.type(screen.getByLabelText('Diferencial sobre el Euribor (%)'), '0,75')
    await user.click(screen.getByRole('button', { name: 'Crear préstamo' }))

    expect(api.callsTo('POST /api/loans')[0]?.body).toMatchObject({
      name: 'Hipoteca',
      kind: 'mortgage',
      principal: '150000.00',
      term_months: 300,
      first_payment: '2026-02-05',
      rate_type: 'variable',
      fixed_rate: '1.99',
      fixed_months: 12,
      index: 'euribor_12m',
      spread: '0.75',
      review_months: 12,
    })
  })

  it('shows the summary and the amortization table', async () => {
    const user = userEvent.setup()
    renderApp('/planificar/prestamos/loan-1')

    const summary = await screen.findByRole('region', { name: 'Situación del préstamo' })
    expect(within(summary).getByText('9.963,23 €')).toBeInTheDocument()
    expect(within(summary).getByText('enero de 2030 · quedan 39 cuotas')).toBeInTheDocument()

    await user.click(await screen.findByText('Cuadro de amortización (1 cuotas)'))
    const table = await screen.findByRole('region', { name: 'Cuadro de amortización' })
    expect(within(table).getByText('11.778,18 €')).toBeInTheDocument()
  })

  it('simulates and registers an early repayment', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.on('POST /api/loans/loan-1/simulate', {
      status: 200,
      body: {
        fee: '30.00',
        fee_percent: '1.0000',
        legal_cap: '1.0000',
        interest_saved: '412.50',
        payment_before: '281.82',
        payment_after: '281.82',
        end_before: '2030-01-05',
        end_after: '2028-11-05',
        payments_saved: 14,
      },
    })
    api.on('POST /api/loans/loan-1/prepayments', { status: 201, body: loan() })
    renderApp('/planificar/prestamos/loan-1')

    await user.type(await screen.findByLabelText('Importe'), '3.000')
    await user.click(screen.getByRole('button', { name: 'Simular' }))

    expect(await screen.findByText('412,50 €')).toBeInTheDocument()
    expect(screen.getByText('noviembre de 2028 · 14 cuotas menos')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Registrar esta amortización' }))
    expect(api.callsTo('POST /api/loans/loan-1/prepayments')[0]?.body).toEqual({
      date: '2026-10-16',
      amount: '3000.00',
      mode: 'reduce_term',
    })
    expect(await screen.findByText('Amortización registrada.')).toBeInTheDocument()
  })

  it('warns when a review has no Euribor', async () => {
    api.on('GET /api/loans/loan-1', {
      status: 200,
      body: loan({
        rate_type: 'mixed',
        warnings: [
          'Falta el Euribor para la revisión del 05/08/2026: se mantiene el tipo anterior.',
        ],
      }),
    })
    renderApp('/planificar/prestamos/loan-1')

    expect(await screen.findByText(/Falta el Euribor/)).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Euribor/ })[0]).toHaveAttribute(
      'href',
      '/planificar/euribor',
    )
  })

  it('adds a Euribor value', async () => {
    const user = userEvent.setup()
    api.on('GET /api/reference-rates', { status: 200, body: [] })
    api.on('PUT /api/reference-rates', { status: 200, body: {} })
    renderApp('/planificar/euribor')

    await user.type(await screen.findByLabelText('Valor (%)'), '2,17')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(api.callsTo('PUT /api/reference-rates')[0]?.body).toEqual({
      index: 'euribor_12m',
      month: '2026-10-01',
      value: '2.17',
    })
  })
})
