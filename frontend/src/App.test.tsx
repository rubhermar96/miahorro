import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from './test/render'

function mockHealth(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => Response.json(body, { status })),
  )
}

beforeEach(() => {
  mockHealth(200, { status: 'ok', version: '0.1.0', database: 'ok' })
})

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

describe('app shell', () => {
  it('shows the home page with the main navigation', async () => {
    renderApp('/')

    expect(screen.getByRole('heading', { level: 1, name: 'Inicio' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    for (const label of ['Inicio', 'Movimientos', 'Añadir', 'Planificar', 'Más']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
    }
    expect(await screen.findByText('Conectado · versión 0.1.0')).toBeInTheDocument()
  })

  it('navigates between sections from the bottom bar', async () => {
    const user = userEvent.setup()
    renderApp('/')

    await user.click(screen.getByRole('link', { name: 'Movimientos' }))

    expect(screen.getByRole('heading', { level: 1, name: 'Movimientos' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Movimientos' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('reports when the database is down', async () => {
    mockHealth(503, { status: 'degraded', version: '0.1.0', database: 'unavailable' })
    renderApp('/')

    expect(
      await screen.findByText('El servidor responde, pero la base de datos no está disponible'),
    ).toBeInTheDocument()
  })

  it('reports when the server cannot be reached', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    renderApp('/')

    expect(await screen.findByText('Sin conexión con el servidor')).toBeInTheDocument()
  })

  it('lets the user choose a theme', async () => {
    const user = userEvent.setup()
    renderApp('/mas')

    await user.click(screen.getByRole('radio', { name: 'Oscuro' }))

    expect(screen.getByRole('radio', { name: 'Oscuro' })).toHaveAttribute('aria-checked', 'true')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('shows a not-found page for unknown URLs', () => {
    renderApp('/no-existe')

    expect(screen.getByRole('heading', { name: 'Página no encontrada' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Volver al inicio' })).toHaveAttribute('href', '/')
  })
})
