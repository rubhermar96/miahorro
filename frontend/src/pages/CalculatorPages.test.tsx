import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { account, categories, page } from '../test/financeData'
import { fullSession, healthOk, mockApi } from '../test/mockApi'
import { renderApp } from '../test/render'

let api: ReturnType<typeof mockApi>

const context = {
  months: 3,
  start: '2026-07-01',
  end: '2026-09-30',
  income: '2000.00',
  expenses: '360.00',
  saved: '1640.00',
  liquidity: '8921.00',
  loan_payments: '281.82',
  categories: [
    { category_id: 'c1', name: 'Alimentación', icon: '🛒', monthly: '300.00' },
    { category_id: 'c2', name: 'Ocio', icon: '🎉', monthly: '50.00' },
    { category_id: null, name: 'Sin categoría', icon: null, monthly: '10.00' },
  ],
  euribor: { month: '2026-09-01', value: '2.1700' },
}

const compoundResult = (final: string) => ({
  years: [
    {
      year: 1,
      contributed: '19680.00',
      gains: '420.00',
      tax: '0.00',
      balance: '20100.00',
      real_balance: '19705.88',
    },
  ],
  contributed: '19680.00',
  gains: '420.00',
  tax: '80.00',
  final,
  final_real: '19627.45',
  references: [
    {
      table: 'savings_tax',
      table_label: 'Escala del ahorro (IRPF)',
      key: 'general',
      label: 'general',
      value: '19.0000',
      extra: {
        brackets: [
          { up_to: '6000', rate: '19' },
          { up_to: null, rate: '21' },
        ],
      },
      valid_from: '2026-01-01',
      source: 'guiafiscal.es',
      note: null,
    },
  ],
})

const scenario = (id: string, name: string, inputs: Record<string, unknown>) => ({
  id,
  calculator: 'compound',
  name,
  inputs,
  created_at: '2026-10-15T10:00:00Z',
  updated_at: '2026-10-15T10:00:00Z',
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
    'GET /api/loans': { status: 200, body: [] },
    'GET /api/calculators/context': { status: 200, body: context },
    'GET /api/scenarios': { status: 200, body: [] },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('calculators', () => {
  it('are one tap away from Planificar', async () => {
    renderApp('/planificar')

    const card = await screen.findByRole('region', { name: 'Calculadoras' })
    expect(within(card).getByRole('link', { name: /Vivienda/ })).toHaveAttribute(
      'href',
      '/planificar/calculadoras/comprar-vivienda',
    )
    expect(within(card).getAllByRole('link')).toHaveLength(8)
  })

  it('lists every calculator with a warning that results are approximate', async () => {
    renderApp('/planificar/calculadoras')

    expect(await screen.findByRole('link', { name: /Ahorro e interés compuesto/ })).toBeVisible()
    expect(screen.getByRole('link', { name: /Préstamo personal/ })).toHaveAttribute(
      'href',
      '/planificar/calculadoras/prestamo-personal',
    )
    expect(screen.getByText(/Resultados orientativos/)).toBeInTheDocument()
  })

  it('prefills compound interest with what you save and shows the result', async () => {
    const user = userEvent.setup()
    api.on('POST /api/calculators/compound', { status: 200, body: compoundResult('20020.00') })
    renderApp('/planificar/calculadoras/interes-compuesto')

    expect(await screen.findByLabelText('Aportación al mes (€)')).toHaveValue('1640')
    expect(screen.getByText(/media de tus últimos 3 meses completos/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Calcular' }))

    expect(api.callsTo('POST /api/calculators/compound')[0]?.body).toEqual({
      monthly: '1640.00',
      annual_return: '4',
      years: 10,
      inflation: '2',
      tax_mode: 'end',
    })
    const result = await screen.findByRole('region', { name: 'Resultado' })
    expect(within(result).getByText('20.020,00 €')).toBeInTheDocument()
    await user.click(within(result).getByText('Valores de referencia usados'))
    expect(within(result).getByText(/19 % hasta 6.000 €, 21 % por encima/)).toBeVisible()
    expect(within(result).getByText(/Fuente: guiafiscal.es/)).toBeVisible()
  })

  it('asks for the region before working out a home purchase', async () => {
    const user = userEvent.setup()
    api.on('POST /api/calculators/home', {
      status: 200,
      body: {
        tax_name: 'ITP',
        tax: '12000.00',
        ajd: '0.00',
        notary: '600.00',
        registry: '400.00',
        gestoria: '350.00',
        appraisal: '400.00',
        agency: '0.00',
        costs: '13750.00',
        total: '213750.00',
        mortgage: '160000.00',
        down_payment: '40000.00',
        cash_needed: '53750.00',
        payment: '674.57',
        debt_ratio: '47.8',
        max_payment: '418.18',
        max_price: '123456.00',
        limited_by: 'income',
        months_to_buy: 0,
        buy_date: '2026-10-16',
        references: [],
        warnings: ['Las deudas se llevarían el 47.8 % de tus ingresos.'],
      },
    })
    renderApp('/planificar/calculadoras/comprar-vivienda')

    await user.type(await screen.findByLabelText('Precio de la vivienda (€)'), '200.000')
    await user.type(screen.getByLabelText('TIN (%)'), '3')
    await user.click(screen.getByRole('button', { name: 'Calcular' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Rellena «Comunidad autónoma».')

    await user.selectOptions(screen.getByLabelText('Comunidad autónoma'), 'madrid')
    await user.click(screen.getByRole('button', { name: 'Calcular' }))

    expect(api.callsTo('POST /api/calculators/home')[0]?.body).toEqual({
      price: '200000.00',
      region: 'madrid',
      new_build: false,
      financed_percent: '80',
      annual_rate: '3',
      years: 30,
      net_income: '2000.00',
      other_debts: '281.82',
      max_ratio: '35',
      savings: '8921.00',
      monthly_saving: '1640.00',
    })
    const result = await screen.findByRole('region', { name: 'Resultado' })
    expect(within(result).getByText('53.750,00 €')).toBeInTheDocument()
    expect(within(result).getByText('Precio máximo (por tus ingresos)')).toBeInTheDocument()
    expect(within(result).getByText('Ya tienes el ahorro necesario')).toBeInTheDocument()
    expect(within(result).getByText(/Las deudas se llevarían/)).toBeInTheDocument()
  })

  it('adds up the essential categories for the emergency fund', async () => {
    const user = userEvent.setup()
    renderApp('/planificar/calculadoras/fondo-de-emergencia')

    const essential = await screen.findByLabelText('Gastos esenciales al mes (€)')
    expect(essential).toHaveValue('310') // food and uncategorised; leisure is left out
    await user.click(screen.getByText(/Elegir los gastos esenciales/))
    await user.click(screen.getByRole('checkbox', { name: /Ocio/ }))
    expect(essential).toHaveValue('360')
    expect(screen.getByLabelText('Lo que tienes para emergencias (€)')).toHaveValue('8921')
  })

  it('builds the Euribor scenarios from the latest value', async () => {
    const user = userEvent.setup()
    api.on('POST /api/calculators/mortgage', { status: 422, body: {} })
    renderApp('/planificar/calculadoras/hipoteca')

    expect(await screen.findByLabelText('Euribor, escenario 1 (%)')).toHaveValue('2,17')
    expect(screen.getByLabelText('Euribor, escenario 2 (%)')).toHaveValue('3,17')
    expect(screen.getByLabelText('Euribor, escenario 3 (%)')).toHaveValue('1,67')
    await user.type(screen.getByLabelText('Importe de la hipoteca (€)'), '150000')
    await user.type(screen.getByLabelText('TIN o tipo inicial (%) · Oferta 1'), '2,6')
    await user.type(screen.getByLabelText('TIN o tipo inicial (%) · Oferta 2'), '1,9')
    await user.type(screen.getByLabelText('Diferencial (%) · Oferta 2'), '0,7')
    await user.click(screen.getByRole('button', { name: 'Calcular' }))

    expect(api.callsTo('POST /api/calculators/mortgage')[0]?.body).toMatchObject({
      principal: '150000.00',
      years: 30,
      euribor: ['2.17', '3.17', '1.67'],
      offers: [
        { name: 'Fija', rate_type: 'fixed', fixed_rate: '2.6' },
        {
          name: 'Variable',
          rate_type: 'variable',
          fixed_rate: '1.9',
          fixed_months: 12,
          spread: '0.7',
        },
      ],
    })
  })

  it('saves a scenario', async () => {
    const user = userEvent.setup()
    api.on('POST /api/calculators/compound', { status: 200, body: compoundResult('20020.00') })
    api.on('POST /api/scenarios', (_request, body) => ({
      status: 201,
      body: scenario('s1', 'Plan A', (body as { inputs: Record<string, unknown> }).inputs),
    }))
    renderApp('/planificar/calculadoras/interes-compuesto')

    await user.click(await screen.findByRole('button', { name: 'Calcular' }))
    await user.type(await screen.findByLabelText('Nombre del escenario'), 'Plan A')
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))

    expect(api.callsTo('POST /api/scenarios')[0]?.body).toEqual({
      calculator: 'compound',
      name: 'Plan A',
      inputs: {
        monthly: '1640.00',
        annual_return: '4',
        years: 10,
        inflation: '2',
        tax_mode: 'end',
      },
    })
    expect(await screen.findByText('Escenario «Plan A» guardado.')).toBeInTheDocument()
  })

  it('reopens and compares saved scenarios', async () => {
    const user = userEvent.setup()
    const inputsA = { initial: '1000.00', annual_return: '3.0000', years: 5, tax_mode: 'none' }
    const inputsB = { initial: '1000.00', annual_return: '6.0000', years: 5, tax_mode: 'none' }
    api.on('GET /api/scenarios', {
      status: 200,
      body: [scenario('a', 'Prudente', inputsA), scenario('b', 'Optimista', inputsB)],
    })
    api.on('POST /api/calculators/compound', (_request, body) => ({
      status: 200,
      body: compoundResult(
        (body as { annual_return: string }).annual_return.startsWith('3') ? '1159.27' : '1338.23',
      ),
    }))
    renderApp('/planificar/calculadoras/interes-compuesto')

    await user.click((await screen.findAllByRole('button', { name: 'Abrir' }))[0]!)
    expect(screen.getByLabelText('Rentabilidad anual (%)')).toHaveValue('3')
    expect(screen.getByLabelText('Capital inicial (€)')).toHaveValue('1000')
    expect(await screen.findByText('Estás viendo el escenario «Prudente».')).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: 'Comparar «Prudente»' }))
    await user.click(screen.getByRole('checkbox', { name: 'Comparar «Optimista»' }))
    await user.click(screen.getByRole('button', { name: 'Comparar 2 escenarios' }))

    const table = await screen.findByRole('region', { name: 'Comparación de escenarios' })
    const row = within(table).getByRole('row', { name: /Valor final, tras impuestos/ })
    expect(row).toHaveTextContent('1.159,27 €')
    expect(row).toHaveTextContent('1.338,23 €')
  })

  it('proposes a goal with the amount and date worked out', async () => {
    renderApp(
      '/planificar/objetivos/nuevo?nombre=Fondo%20de%20emergencia&importe=9000&fecha=2027-08-16',
    )

    expect(await screen.findByLabelText('Nombre')).toHaveValue('Fondo de emergencia')
    expect(screen.getByDisplayValue('9000')).toBeInTheDocument()
    expect(screen.getByDisplayValue('2027-08-16')).toBeInTheDocument()
  })
})
