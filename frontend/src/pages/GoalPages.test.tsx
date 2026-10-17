import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { account, categories, page } from '../test/financeData'
import { fullSession, healthOk, mockApi } from '../test/mockApi'
import { renderApp } from '../test/render'

let api: ReturnType<typeof mockApi>

const goal = (fields: Record<string, unknown> = {}) => ({
  id: 'goal-1',
  name: 'Entrada del piso',
  target_amount: '12000.00',
  target_date: '2027-09-30',
  priority: 1,
  icon: '🏠',
  note: null,
  account_ids: [],
  pots: [{ account_id: 'acc-1', amount: '3000.00' }],
  achieved: false,
  saved: '3000.00',
  remaining: '9000.00',
  percent: 25,
  required_monthly: '750.00',
  pace: '800.00',
  estimated_date: '2027-08-15',
  status: 'on_track',
  ...fields,
})

const rate = {
  target: 20,
  periods: [
    {
      start: '2026-08-25',
      end: '2026-09-24',
      income: '2000.00',
      expenses: '-1700.00',
      saved: '300.00',
      rate: '15.0',
    },
    {
      start: '2026-09-25',
      end: '2026-10-16',
      income: '2000.00',
      expenses: '-1500.00',
      saved: '500.00',
      rate: '25.0',
    },
  ],
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-16T08:00:00Z') })
  api = mockApi({
    'GET /api/auth/session': fullSession,
    'GET /api/health': healthOk,
    'GET /api/accounts': {
      status: 200,
      body: [account({ reserved: '3000.00', available: '-2000.00' })],
    },
    'GET /api/categories': { status: 200, body: categories },
    'GET /api/transactions': { status: 200, body: page([]) },
    'GET /api/goals': { status: 200, body: [goal()] },
    'GET /api/goals/goal-1': { status: 200, body: goal() },
    'GET /api/goals/goal-1/contributions': { status: 200, body: [] },
    'GET /api/savings-rate': { status: 200, body: rate },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('plan', () => {
  it('shows each goal with its progress and how it is going', async () => {
    renderApp('/planificar')

    const card = await screen.findByRole('link', { name: /Entrada del piso/ })
    expect(card).toHaveAttribute('href', '/planificar/objetivos/goal-1')
    expect(
      within(card).getByRole('progressbar', { name: 'Progreso de Entrada del piso' }),
    ).toHaveAttribute('aria-valuenow', '25')
    expect(
      within(card).getByText('Vas bien: a este ritmo lo consigues en agosto de 2027.'),
    ).toBeInTheDocument()
  })

  it('shows the savings rate per month against the target', async () => {
    renderApp('/planificar')

    const card = await screen.findByRole('region', { name: 'Tasa de ahorro' })
    expect(await within(card).findByText('25 %', { selector: '.total' })).toBeInTheDocument()
    const history = within(card).getByRole('list', { name: 'Tasa de ahorro de los últimos meses' })
    expect(
      within(history)
        .getAllByRole('listitem')
        .map((row) => row.textContent),
    ).toEqual(['25 ago15 %', '25 sept25 %'])
    expect(within(card).getByLabelText(/^Objetivo de ahorro/)).toHaveValue('20')
  })

  it('changes the savings target', async () => {
    const user = userEvent.setup()
    api.on('PATCH /api/me/preferences', { status: 200, body: fullSession.body.user })
    renderApp('/planificar')

    await user.selectOptions(await screen.findByLabelText(/^Objetivo de ahorro/), '30')

    expect(api.callsTo('PATCH /api/me/preferences')[0]?.body).toEqual({ savings_rate_target: 30 })
  })
})

describe('goals', () => {
  it('creates a goal', async () => {
    const user = userEvent.setup()
    api.on('GET /api/goals', { status: 200, body: [] })
    api.on('POST /api/goals', { status: 201, body: goal({ id: 'goal-2' }) })
    api.on('GET /api/goals/goal-2', { status: 200, body: goal({ id: 'goal-2' }) })
    api.on('GET /api/goals/goal-2/contributions', { status: 200, body: [] })
    const { router } = renderApp('/planificar/objetivos/nuevo')

    await user.type(await screen.findByLabelText('Nombre'), 'Coche')
    await user.click(screen.getByRole('button', { name: 'Imagen 🚗' }))
    await user.type(screen.getByLabelText('Importe'), '15.000')
    await user.type(screen.getByLabelText('Fecha límite (opcional)'), '2028-06-30')
    await user.click(screen.getByRole('radio', { name: 'Alta' }))
    await user.click(screen.getByRole('button', { name: 'Crear objetivo' }))

    expect(api.callsTo('POST /api/goals')[0]?.body).toEqual({
      name: 'Coche',
      icon: '🚗',
      target_amount: '15000.00',
      target_date: '2028-06-30',
      priority: 1,
      note: null,
      account_ids: [],
    })
    await screen.findByText('Hucha')
    expect(router.state.location.pathname).toBe('/planificar/objetivos/goal-2')
  })

  it('sets money aside and explains when there is not enough', async () => {
    const user = userEvent.setup()
    api.on('POST /api/goals/goal-1/contributions', {
      status: 409,
      body: { error: { message: 'En «Nómina» solo hay 1.000,00 € disponibles para apartar.' } },
    })
    renderApp('/planificar/objetivos/goal-1')

    expect(await screen.findByText('Necesitas apartar al mes')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Importe'), '2.000')
    await user.click(screen.getByRole('button', { name: 'Apartar' }))

    expect(api.callsTo('POST /api/goals/goal-1/contributions')[0]?.body).toEqual({
      account_id: 'acc-1',
      amount: '2000.00',
      action: 'add',
    })
    expect(await screen.findByRole('alert')).toHaveTextContent('solo hay 1.000,00 € disponibles')
  })

  it('marks a goal as achieved', async () => {
    const user = userEvent.setup()
    api.on('PATCH /api/goals/goal-1', { status: 200, body: goal({ achieved: true }) })
    renderApp('/planificar/objetivos/goal-1')

    await user.click(await screen.findByRole('button', { name: 'Marcar como conseguido' }))

    expect(api.callsTo('PATCH /api/goals/goal-1')[0]?.body).toEqual({ achieved: true })
  })
})

it('home shows what is available when goals hold part of an account', async () => {
  api.on('GET /api/accounts', {
    status: 200,
    body: [account({ balance: '5000.00', reserved: '3000.00', available: '2000.00' })],
  })
  api.on('GET /api/inbox', { status: 200, body: { unconfirmed: [], overdue: [] } })
  api.on('GET /api/recurring/upcoming', { status: 200, body: [] })
  renderApp('/')

  expect(await screen.findByText('Disponible 2.000,00 €')).toBeInTheDocument()
})
