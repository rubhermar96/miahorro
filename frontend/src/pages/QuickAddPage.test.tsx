import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { account, categories, transaction } from '../test/financeData'
import { fullSession, healthOk, mockApi } from '../test/mockApi'
import { renderApp } from '../test/render'

let api: ReturnType<typeof mockApi>

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-16T08:00:00Z') })
  api = mockApi({
    'GET /api/auth/session': fullSession,
    'GET /api/health': healthOk,
    'GET /api/accounts': {
      status: 200,
      body: [account(), account({ id: 'acc-2', name: 'Ahorro', kind: 'savings' })],
    },
    'GET /api/categories': { status: 200, body: categories },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('quick add', () => {
  it('saves an expense with amount, category and one tap', async () => {
    const user = userEvent.setup()
    api.on('POST /api/transactions', { status: 201, body: transaction() })
    renderApp('/anadir')

    await user.type(await screen.findByLabelText('Importe'), '12,5')
    await user.click(screen.getByRole('button', { name: /Supermercado/ }))
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(api.callsTo('POST /api/transactions')[0]?.body).toEqual({
      account_id: 'acc-1',
      kind: 'expense',
      amount: '12.50',
      category_id: 'groceries',
      date: '2026-10-16',
      description: '',
      note: null,
      tags: [],
    })
    expect(await screen.findByText('Gasto de 12,50 € guardado.')).toBeInTheDocument()
    expect(screen.getByLabelText('Importe')).toHaveValue('')
  })

  it('shows the most used categories first', async () => {
    renderApp('/anadir')

    const picker = await screen.findByRole('group', { name: 'Categoría' })
    const chips = within(picker).getAllByRole('button', { pressed: false })

    expect(chips[0]).toHaveTextContent('Restaurantes')
    expect(chips[1]).toHaveTextContent('Supermercado')
    expect(within(picker).queryByText('Alimentación')).not.toBeInTheDocument() // has subcategories
  })

  it('explains an invalid amount', async () => {
    const user = userEvent.setup()
    renderApp('/anadir')

    await user.type(await screen.findByLabelText('Importe'), 'doce')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Escribe un importe, por ejemplo 12,50.')
    expect(api.callsTo('POST /api/transactions')).toEqual([])
  })

  it('records income with income categories', async () => {
    const user = userEvent.setup()
    api.on('POST /api/transactions', { status: 201, body: transaction({ kind: 'income' }) })
    renderApp('/anadir')

    await user.click(await screen.findByRole('radio', { name: 'Ingreso' }))
    await user.type(screen.getByLabelText('Importe'), '2000')
    await user.click(screen.getByRole('button', { name: /Nómina/ }))
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(api.callsTo('POST /api/transactions')[0]?.body).toMatchObject({
      kind: 'income',
      amount: '2000.00',
      category_id: 'salary',
    })
  })

  it('moves money between own accounts', async () => {
    const user = userEvent.setup()
    api.on('POST /api/transfers', { status: 201, body: [] })
    renderApp('/anadir')

    await user.click(await screen.findByRole('radio', { name: 'Transferencia' }))
    await user.type(screen.getByLabelText('Importe'), '300')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(api.callsTo('POST /api/transfers')[0]?.body).toMatchObject({
      from_account_id: 'acc-1',
      to_account_id: 'acc-2',
      amount: '300.00',
    })
    expect(await screen.findByText('Transferencia de 300,00 € guardada.')).toBeInTheDocument()
  })

  it('remembers the last account used', async () => {
    const user = userEvent.setup()
    api.on('POST /api/transactions', { status: 201, body: transaction() })
    const { unmount } = renderApp('/anadir')
    await user.selectOptions(await screen.findByLabelText('Cuenta'), 'acc-2')
    await user.type(screen.getByLabelText('Importe'), '5')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    await screen.findByText(/guardado/)
    unmount()

    renderApp('/anadir')

    expect(await screen.findByLabelText('Cuenta')).toHaveValue('acc-2')
  })

  it('asks for an account first when there is none', async () => {
    api.on('GET /api/accounts', { status: 200, body: [] })
    renderApp('/anadir')

    expect(
      await screen.findByText('Antes de apuntar movimientos, crea al menos una cuenta.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Añadir cuenta' })).toHaveAttribute(
      'href',
      '/cuentas/nueva',
    )
  })
})
