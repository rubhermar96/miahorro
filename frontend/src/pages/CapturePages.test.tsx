import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { account, categories, page, transaction } from '../test/financeData'
import { fullSession, healthOk, mockApi } from '../test/mockApi'
import { renderApp } from '../test/render'

let api: ReturnType<typeof mockApi>

const token = {
  id: 'tok-1',
  name: 'iPhone',
  hint: 'mia_AbCd',
  default_account_id: 'acc-1',
  created_at: '2026-10-16T08:00:00Z',
  last_used_at: null,
}

const item = {
  id: 'rec-1',
  name: 'Préstamo',
  account_id: 'acc-1',
  kind: 'expense',
  amount: '352.59',
  tolerance: '10.00',
  category_id: null,
  match_text: 'CUOTA PTMO',
  frequency: 'monthly',
  next_date: '2026-10-27',
  last_transaction_id: null,
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-16T08:00:00Z') })
  api = mockApi({
    'GET /api/auth/session': fullSession,
    'GET /api/health': healthOk,
    'GET /api/accounts': { status: 200, body: [account()] },
    'GET /api/categories': { status: 200, body: categories },
    'GET /api/transactions': { status: 200, body: page([]) },
    'GET /api/capture/tokens': { status: 200, body: [] },
    'GET /api/capture/cards': { status: 200, body: [] },
    'GET /api/recurring': { status: 200, body: [] },
    'GET /api/recurring/upcoming': { status: 200, body: [] },
    'GET /api/inbox': { status: 200, body: { unconfirmed: [], overdue: [] } },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('capture', () => {
  it('creates a token and shows the Shortcut steps with it, once', async () => {
    const user = userEvent.setup()
    api.on('POST /api/capture/tokens', {
      status: 201,
      body: { token, secret: 'mia_AbCdSECRET', url: '/api/capture/payments' },
    })
    renderApp('/mas/captura')

    await user.clear(await screen.findByLabelText('Nombre'))
    await user.type(screen.getByLabelText('Nombre'), 'iPhone')
    await user.click(screen.getByRole('button', { name: 'Crear token y ver los pasos' }))

    expect(api.callsTo('POST /api/capture/tokens')[0]?.body).toEqual({
      name: 'iPhone',
      default_account_id: 'acc-1',
    })
    const guide = await screen.findByRole('region', { name: 'Crea el Atajo en el iPhone' })
    expect(within(guide).getByLabelText('Dirección')).toHaveTextContent(
      'http://localhost:3000/api/capture/payments',
    )
    expect(within(guide).getByLabelText('Authorization')).toHaveTextContent('Bearer mia_AbCdSECRET')
    await user.click(within(guide).getByRole('button', { name: 'Hecho' }))
    expect(screen.queryByText(/mia_AbCdSECRET/)).not.toBeInTheDocument()
  })

  it('revokes a token and maps a card to an account', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.on('GET /api/accounts', {
      status: 200,
      body: [account(), account({ id: 'acc-2', name: 'Visa', kind: 'credit_card' })],
    })
    api.on('GET /api/capture/tokens', { status: 200, body: [token] })
    api.on('GET /api/capture/cards', {
      status: 200,
      body: [{ id: 'card-1', name: 'Visa Bankinter', account_id: 'acc-1', last_seen_at: '' }],
    })
    api.on('DELETE /api/capture/tokens/tok-1', { status: 204 })
    api.on('PATCH /api/capture/cards/card-1', { status: 200, body: {} })
    renderApp('/mas/captura')

    await user.selectOptions(await screen.findByLabelText('Visa Bankinter'), 'acc-2')
    await user.click(screen.getByRole('button', { name: 'Desconectar' }))

    expect(api.callsTo('PATCH /api/capture/cards/card-1')[0]?.body).toEqual({
      account_id: 'acc-2',
    })
    expect(api.callsTo('DELETE /api/capture/tokens/tok-1')).toHaveLength(1)
  })
})

describe('review and recurring', () => {
  it('home shows what to review and what is coming', async () => {
    api.on('GET /api/inbox', {
      status: 200,
      body: { unconfirmed: [transaction({ pending: true })], overdue: [] },
    })
    api.on('GET /api/recurring/upcoming', {
      status: 200,
      body: [
        {
          item_id: 'rec-1',
          name: 'Préstamo',
          account_id: 'acc-1',
          date: '2026-10-27',
          amount: '-352.59',
          overdue: false,
        },
      ],
    })
    renderApp('/')

    expect(await screen.findByRole('link', { name: '1 cosa para revisar ›' })).toHaveAttribute(
      'href',
      '/revisar',
    )
    const upcoming = screen.getByRole('region', { name: 'Próximos 30 días' })
    expect(within(upcoming).getByText('Préstamo')).toBeInTheDocument()
    expect(within(upcoming).getByText('-352,59 €')).toBeInTheDocument()
  })

  it('keeps or discards a payment the bank never confirmed', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.on('GET /api/inbox', {
      status: 200,
      body: {
        unconfirmed: [
          transaction({ id: 'tx-1', description: 'Cine', pending: true }),
          transaction({ id: 'tx-2', description: 'Denegado', pending: true }),
        ],
        overdue: [],
      },
    })
    api.on('POST /api/transactions/tx-1/confirm', { status: 200, body: transaction() })
    api.on('DELETE /api/transactions/tx-2', { status: 204 })
    renderApp('/revisar')

    const rows = await screen.findAllByRole('listitem')
    await user.click(within(rows[0]!).getByRole('button', { name: 'Mantener' }))
    await user.click(within(rows[1]!).getByRole('button', { name: 'Descartar' }))

    expect(api.callsTo('POST /api/transactions/tx-1/confirm')).toHaveLength(1)
    expect(api.callsTo('DELETE /api/transactions/tx-2')).toHaveLength(1)
  })

  it('creates a recurring item', async () => {
    const user = userEvent.setup()
    api.on('POST /api/recurring', { status: 201, body: item })
    renderApp('/mas/recurrentes')

    await user.type(await screen.findByLabelText('Nombre'), 'Préstamo')
    await user.type(screen.getByLabelText('Importe esperado'), '352,59')
    await user.clear(screen.getByLabelText('Próxima fecha'))
    await user.type(screen.getByLabelText('Próxima fecha'), '2026-10-27')
    await user.type(screen.getByLabelText(/El concepto del banco contiene/), 'CUOTA PTMO')
    await user.click(screen.getByRole('button', { name: 'Crear recurrente' }))

    expect(api.callsTo('POST /api/recurring')[0]?.body).toEqual({
      name: 'Préstamo',
      account_id: 'acc-1',
      kind: 'expense',
      amount: '352.59',
      tolerance: '10',
      category_id: null,
      match_text: 'CUOTA PTMO',
      frequency: 'monthly',
      next_date: '2026-10-27',
    })
    expect(await screen.findByText('«Préstamo» guardado.')).toBeInTheDocument()
  })

  it('marks captured payments as pending in the lists', async () => {
    api.on('GET /api/transactions', {
      status: 200,
      body: page([transaction({ pending: true, source: 'capture' })]),
    })
    renderApp('/movimientos')

    expect(await screen.findByText('Pendiente')).toBeInTheDocument()
  })
})
