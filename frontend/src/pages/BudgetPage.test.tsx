import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { account, categories, page } from '../test/financeData'
import { fullSession, healthOk, mockApi } from '../test/mockApi'
import { renderApp } from '../test/render'

let api: ReturnType<typeof mockApi>

const budget = (fields: Record<string, unknown> = {}) => ({
  mode: 'limits',
  rollover: false,
  start: '2026-10-01',
  end: '2026-10-31',
  previous_start: '2026-09-01',
  next_start: '2026-11-01',
  lines: [
    {
      category_id: 'food',
      assigned: '400.00',
      activity: '-150.00',
      carried: '0.00',
      available: '250.00',
    },
    {
      category_id: 'transport',
      assigned: '100.00',
      activity: '-130.00',
      carried: '0.00',
      available: '-30.00',
    },
  ],
  unbudgeted: '-50.00',
  assigned: '500.00',
  activity: '-280.00',
  available: '220.00',
  cash: null,
  to_assign: null,
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
    'GET /api/budget': { status: 200, body: budget() },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('budget', () => {
  it('asks how to keep the budget the first time', async () => {
    const user = userEvent.setup()
    api.on('GET /api/budget', { status: 200, body: budget({ mode: null, lines: [] }) })
    api.on('PATCH /api/me/preferences', { status: 200, body: fullSession.body.user })
    renderApp('/planificar/presupuesto')

    await user.click(await screen.findByRole('button', { name: 'Usar base cero' }))

    expect(api.callsTo('PATCH /api/me/preferences')[0]?.body).toEqual({
      budget_mode: 'zero_based',
    })
  })

  it('shows each limit with what is spent and what is left', async () => {
    renderApp('/planificar/presupuesto')

    const food = await screen.findByRole('button', { name: /Alimentación/ })
    expect(food).toHaveTextContent('150,00 € de 400,00 €')
    expect(food).toHaveTextContent('250,00 €quedan')
    expect(screen.getByRole('button', { name: /Transporte/ })).toHaveTextContent(
      '-30,00 €te has pasado',
    )
    expect(screen.getByText('Sin presupuestar').closest('li')).toHaveTextContent('-50,00 €')
    expect(screen.getByText('1 oct – 31 oct')).toBeInTheDocument()
  })

  it('changes a limit', async () => {
    const user = userEvent.setup()
    api.on('PUT /api/budget/lines/food', { status: 200, body: budget() })
    renderApp('/planificar/presupuesto')

    const food = await screen.findByRole('button', { name: /Alimentación/ })
    await user.click(food)
    const editor = within(food.closest('li')!)
    const field = editor.getByLabelText('Límite al mes')
    await user.clear(field)
    await user.type(field, '450')
    await user.click(editor.getByRole('button', { name: 'Guardar' }))

    expect(api.callsTo('PUT /api/budget/lines/food')[0]?.body).toEqual({
      amount: '450.00',
      date: '2026-10-01',
    })
  })

  it('goes to the previous month', async () => {
    const user = userEvent.setup()
    const { router } = renderApp('/planificar/presupuesto')

    await user.click(await screen.findByRole('button', { name: 'Mes anterior' }))

    expect(router.state.location.search).toBe('?mes=2026-09-01')
    expect(api.callsTo('GET /api/budget').at(-1)?.query.get('date')).toBe('2026-09-01')
  })

  it('zero-based shows what is left to assign and moves money', async () => {
    const user = userEvent.setup()
    const zero = budget({
      mode: 'zero_based',
      rollover: true,
      cash: '3000.00',
      to_assign: '2780.00',
    })
    api.on('GET /api/budget', { status: 200, body: zero })
    api.on('POST /api/budget/move', { status: 200, body: zero })
    renderApp('/planificar/presupuesto')

    const toAssign = await screen.findByRole('region', { name: 'Por asignar' })
    expect(within(toAssign).getByText('2.780,00 €')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Alimentación/ }))
    await user.selectOptions(screen.getByLabelText('Mover dinero a'), 'fuel')
    await user.type(screen.getByLabelText('Importe a mover'), '50')
    await user.click(screen.getByRole('button', { name: 'Mover' }))

    expect(api.callsTo('POST /api/budget/move')[0]?.body).toEqual({
      from_category_id: 'food',
      to_category_id: 'fuel',
      amount: '50.00',
      date: '2026-10-01',
    })
  })

  it('warns when more is assigned than there is', async () => {
    api.on('GET /api/budget', {
      status: 200,
      body: budget({ mode: 'zero_based', cash: '100.00', to_assign: '-120.00' }),
    })
    renderApp('/planificar/presupuesto')

    expect(await screen.findByText(/Has asignado más de lo que tienes/)).toBeInTheDocument()
  })

  it('switches mode without losing anything', async () => {
    const user = userEvent.setup()
    api.on('PATCH /api/me/preferences', { status: 200, body: fullSession.body.user })
    renderApp('/planificar/presupuesto')

    await user.click(await screen.findByRole('button', { name: 'Cambiar a base cero' }))

    expect(api.callsTo('PATCH /api/me/preferences')[0]?.body).toEqual({
      budget_mode: 'zero_based',
    })
  })

  it('appears on Planificar', async () => {
    renderApp('/planificar')

    const card = await screen.findByRole('link', { name: /Presupuesto/ })
    expect(card).toHaveAttribute('href', '/planificar/presupuesto')
    expect(card).toHaveTextContent('280,00 € gastados de 500,00 € este mes')
  })
})
