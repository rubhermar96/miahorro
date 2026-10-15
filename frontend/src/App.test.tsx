import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fullSession, healthOk, mockApi, noSession } from './test/mockApi'
import { renderApp } from './test/render'

let api: ReturnType<typeof mockApi>

beforeEach(() => {
  api = mockApi({ 'GET /api/auth/session': fullSession, 'GET /api/health': healthOk })
})

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

describe('app shell', () => {
  it('shows the home page with the main navigation', async () => {
    renderApp('/')

    expect(await screen.findByRole('heading', { level: 1, name: 'Inicio' })).toBeInTheDocument()
    expect(screen.getByText('Hola, Ana')).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    for (const label of ['Inicio', 'Movimientos', 'Añadir', 'Planificar', 'Más']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
    }
    expect(await screen.findByText('Conectado · versión 0.1.0')).toBeInTheDocument()
  })

  it('navigates between sections from the bottom bar', async () => {
    const user = userEvent.setup()
    renderApp('/')

    await user.click(await screen.findByRole('link', { name: 'Movimientos' }))

    expect(screen.getByRole('heading', { level: 1, name: 'Movimientos' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Movimientos' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('sends signed-out visitors to the sign-in page, remembering where they were going', async () => {
    api.on('GET /api/auth/session', noSession)
    const { router } = renderApp('/movimientos')

    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/entrar')
    expect(router.state.location.search).toBe('?siguiente=%2Fmovimientos')
  })

  it('shows a retry screen when the server cannot be reached', async () => {
    api.on('GET /api/auth/session', { status: 500, body: {} })
    renderApp('/')

    expect(await screen.findByRole('heading', { name: 'No se puede conectar' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument()
  })

  it('reports when the database is down', async () => {
    api.on('GET /api/health', {
      status: 503,
      body: { status: 'degraded', version: '0.1.0', database: 'unavailable' },
    })
    renderApp('/')

    expect(
      await screen.findByText('El servidor responde, pero la base de datos no está disponible'),
    ).toBeInTheDocument()
  })

  it('applies the theme saved on the server', async () => {
    api.on('GET /api/auth/session', {
      status: 200,
      body: {
        ...fullSession.body,
        user: {
          ...fullSession.body.user,
          preferences: { ...fullSession.body.user.preferences, theme: 'dark' },
        },
      },
    })
    renderApp('/')

    await screen.findByText('Hola, Ana')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('shows a not-found page for unknown URLs', async () => {
    renderApp('/no-existe')

    expect(await screen.findByRole('heading', { name: 'Página no encontrada' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Volver al inicio' })).toHaveAttribute('href', '/')
  })

  it('sends the anti-CSRF header with every request', async () => {
    renderApp('/')
    await screen.findByText('Hola, Ana')

    expect(api.calls.length).toBeGreaterThan(0)
    for (const call of api.calls) {
      expect(call.headers.get('X-MiAhorro-CSRF')).toBe('1')
    }
  })
})
