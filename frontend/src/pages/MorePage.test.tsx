import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fullSession, healthOk, mockApi, noSession, testUser } from '../test/mockApi'
import { renderApp } from '../test/render'

const webauthn = vi.hoisted(() => ({ startRegistration: vi.fn() }))

vi.mock('@simplewebauthn/browser', () => ({
  browserSupportsWebAuthn: () => true,
  startAuthentication: vi.fn(),
  startRegistration: webauthn.startRegistration,
}))

let api: ReturnType<typeof mockApi>
const passkey = {
  id: '00000000-0000-0000-0000-0000000000aa',
  name: 'iPhone de Ana',
  created_at: '2026-10-01T10:00:00Z',
  last_used_at: '2026-10-14T08:30:00Z',
}

beforeEach(() => {
  api = mockApi({
    'GET /api/auth/session': fullSession,
    'GET /api/health': healthOk,
    'GET /api/auth/passkeys': { status: 200, body: [passkey] },
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  vi.restoreAllMocks()
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

describe('settings', () => {
  it('saves the day the financial month starts', async () => {
    const user = userEvent.setup()
    api.on('PATCH /api/me/preferences', (_, body) => ({
      status: 200,
      body: { ...testUser, preferences: { ...testUser.preferences, ...(body as object) } },
    }))
    renderApp('/mas')

    await user.selectOptions(await screen.findByLabelText('El mes empieza el día'), '25')

    expect(api.callsTo('PATCH /api/me/preferences')[0]?.body).toEqual({ month_start_day: 25 })
    expect(await screen.findByText('Guardado')).toBeInTheDocument()
    expect(screen.getByLabelText('El mes empieza el día')).toHaveValue('25')
  })

  it('applies a new theme at once and saves it', async () => {
    const user = userEvent.setup()
    api.on('PATCH /api/me/preferences', {
      status: 200,
      body: { ...testUser, preferences: { ...testUser.preferences, theme: 'dark' } },
    })
    renderApp('/mas')

    await user.click(await screen.findByRole('radio', { name: 'Oscuro' }))

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(api.callsTo('PATCH /api/me/preferences')[0]?.body).toEqual({ theme: 'dark' })
  })

  it('lists passkeys and removes one after confirmation', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.on('DELETE /api/auth/passkeys/00000000-0000-0000-0000-0000000000aa', { status: 204 })
    renderApp('/mas')

    expect(await screen.findByText('iPhone de Ana')).toBeInTheDocument()
    expect(screen.getByText(/Último uso: 14 oct/)).toBeInTheDocument()
    api.on('GET /api/auth/passkeys', { status: 200, body: [] })
    await user.click(screen.getByRole('button', { name: 'Quitar iPhone de Ana' }))

    expect(await screen.findByText('Todavía no tienes ninguna passkey.')).toBeInTheDocument()
  })

  it('adds a passkey on this device', async () => {
    const user = userEvent.setup()
    webauthn.startRegistration.mockResolvedValue({ id: 'new', rawId: 'new' })
    api.on('POST /api/auth/passkeys/register/options', {
      status: 200,
      body: { challenge_id: 'c2', options: { challenge: 'xyz' } },
    })
    api.on('POST /api/auth/passkeys/register', {
      status: 201,
      body: { ...passkey, id: 'b', name: 'iPad' },
    })
    renderApp('/mas')

    const name = await screen.findByLabelText('Nombre de la passkey')
    await user.clear(name)
    await user.type(name, 'iPad')
    await user.click(screen.getByRole('button', { name: 'Añadir passkey en este dispositivo' }))

    expect(webauthn.startRegistration).toHaveBeenCalledWith({ optionsJSON: { challenge: 'xyz' } })
    expect(api.callsTo('POST /api/auth/passkeys/register')[0]?.body).toEqual({
      challenge_id: 'c2',
      credential: { id: 'new', rawId: 'new' },
      name: 'iPad',
    })
  })

  it('generates new recovery codes after confirmation', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.on('POST /api/auth/recovery-codes', {
      status: 200,
      body: { codes: Array.from({ length: 10 }, (_, i) => `zzzz${i}-yyyyy`) },
    })
    renderApp('/mas')

    await user.click(
      await screen.findByRole('button', { name: 'Generar nuevos códigos de recuperación' }),
    )

    const list = await screen.findByRole('region', { name: 'Códigos de recuperación' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(10)
  })

  it('signs out and goes back to the sign-in page', async () => {
    const user = userEvent.setup()
    api.on('POST /api/auth/logout', () => {
      api.on('GET /api/auth/session', noSession)
      return { status: 204 }
    })
    const { router } = renderApp('/mas')

    await user.click(await screen.findByRole('button', { name: 'Cerrar sesión' }))

    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/entrar')
  })

  it('shows the admin link only to administrators', async () => {
    renderApp('/mas')
    await screen.findByText('iPhone de Ana')
    expect(screen.queryByRole('link', { name: 'Panel de administración' })).not.toBeInTheDocument()
  })
})
