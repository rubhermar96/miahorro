import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fullSession, healthOk, mockApi, noSession, testUser } from '../test/mockApi'
import { renderApp } from '../test/render'

const webauthn = vi.hoisted(() => ({
  supported: false,
  startAuthentication: vi.fn(),
  startRegistration: vi.fn(),
}))

vi.mock('@simplewebauthn/browser', () => ({
  browserSupportsWebAuthn: () => webauthn.supported,
  startAuthentication: webauthn.startAuthentication,
  startRegistration: webauthn.startRegistration,
}))

let api: ReturnType<typeof mockApi>

beforeEach(() => {
  webauthn.supported = false
  api = mockApi({ 'GET /api/auth/session': noSession, 'GET /api/health': healthOk })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

const session = (level: string) => ({ status: 200, body: { level, user: testUser } })

describe('sign-in', () => {
  it('signs in with password and authenticator code, then goes where the user was going', async () => {
    const user = userEvent.setup()
    api.on('POST /api/auth/login', () => {
      api.on('GET /api/auth/session', session('mfa_pending'))
      return { status: 200, body: { status: 'mfa_required' } }
    })
    api.on('POST /api/auth/mfa', () => {
      api.on('GET /api/auth/session', fullSession)
      return { status: 200, body: { status: 'authenticated' } }
    })
    const { router } = renderApp('/entrar?siguiente=%2Fmovimientos')

    await user.type(await screen.findByLabelText('Email'), 'ana@example.com')
    await user.type(screen.getByLabelText('Contraseña'), 'una-contraseña-larga')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    await user.type(await screen.findByLabelText('Código'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verificar' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Movimientos' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/movimientos')
    expect(api.callsTo('POST /api/auth/login')[0]?.body).toEqual({
      email: 'ana@example.com',
      password: 'una-contraseña-larga',
    })
    expect(api.callsTo('POST /api/auth/mfa')[0]?.body).toEqual({ code: '123456' })
  })

  it('shows the error message from the server', async () => {
    const user = userEvent.setup()
    api.on('POST /api/auth/login', {
      status: 401,
      body: { error: { code: 'unauthorized', message: 'Email o contraseña incorrectos.' } },
    })
    renderApp('/entrar')

    await user.type(await screen.findByLabelText('Email'), 'ana@example.com')
    await user.type(screen.getByLabelText('Contraseña'), 'mala')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Email o contraseña incorrectos.')
  })

  it('accepts a recovery code instead of the app code', async () => {
    const user = userEvent.setup()
    api.on('GET /api/auth/session', session('mfa_pending'))
    api.on('POST /api/auth/mfa', { status: 200, body: { status: 'authenticated' } })
    renderApp('/entrar')

    await user.click(await screen.findByRole('button', { name: 'Usar un código de recuperación' }))
    await user.type(screen.getByLabelText('Código de recuperación'), 'abcde-fghjk')
    await user.click(screen.getByRole('button', { name: 'Verificar' }))

    expect(api.callsTo('POST /api/auth/mfa')[0]?.body).toEqual({ recovery_code: 'abcde-fghjk' })
  })

  it('walks a new user through setting up the authenticator and shows recovery codes', async () => {
    const user = userEvent.setup()
    const codes = Array.from({ length: 10 }, (_, i) => `aaaa${i}-bbbbb`)
    api.on('GET /api/auth/session', session('mfa_setup'))
    api.on('POST /api/auth/totp/setup', {
      status: 200,
      body: {
        secret: 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP',
        otpauth_uri: 'otpauth://totp/MiAhorro:ana%40example.com?secret=JBSW',
        qr_code: 'data:image/svg+xml;base64,PHN2Zy8+',
      },
    })
    api.on('POST /api/auth/totp/confirm', () => {
      api.on('GET /api/auth/session', fullSession)
      return { status: 200, body: { codes } }
    })
    const { router } = renderApp('/entrar')

    expect(
      await screen.findByRole('img', { name: 'Código QR para la app de autenticación' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Añadir en este dispositivo' })).toHaveAttribute(
      'href',
      'otpauth://totp/MiAhorro:ana%40example.com?secret=JBSW',
    )
    await user.type(screen.getByLabelText('Código'), '654321')
    await user.click(screen.getByRole('button', { name: 'Activar' }))

    expect(
      await screen.findByRole('heading', { name: 'Códigos de recuperación' }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(10)
    expect(router.state.location.pathname).toBe('/entrar') // stays until the user confirms

    await user.click(screen.getByRole('button', { name: 'Ya los he guardado' }))

    expect(await screen.findByText('Hola, Ana')).toBeInTheDocument()
    expect(api.callsTo('POST /api/auth/totp/setup')).toHaveLength(1)
  })

  it('signs in with a passkey alone', async () => {
    const user = userEvent.setup()
    webauthn.supported = true
    webauthn.startAuthentication.mockResolvedValue({ id: 'cred', rawId: 'cred' })
    api.on('POST /api/auth/passkeys/login/options', {
      status: 200,
      body: { challenge_id: 'c1', options: { challenge: 'abc' } },
    })
    api.on('POST /api/auth/passkeys/login', () => {
      api.on('GET /api/auth/session', fullSession)
      return { status: 200, body: { status: 'authenticated' } }
    })
    renderApp('/entrar')

    await user.click(await screen.findByRole('button', { name: 'Entrar con Face ID o passkey' }))

    expect(await screen.findByText('Hola, Ana')).toBeInTheDocument()
    expect(webauthn.startAuthentication).toHaveBeenCalledWith({ optionsJSON: { challenge: 'abc' } })
    expect(api.callsTo('POST /api/auth/passkeys/login')[0]?.body).toEqual({
      challenge_id: 'c1',
      credential: { id: 'cred', rawId: 'cred' },
    })
  })

  it('explains when the Face ID prompt was cancelled', async () => {
    const user = userEvent.setup()
    webauthn.supported = true
    webauthn.startAuthentication.mockRejectedValue(
      Object.assign(new Error('cancelled'), { name: 'NotAllowedError' }),
    )
    api.on('POST /api/auth/passkeys/login/options', {
      status: 200,
      body: { challenge_id: 'c1', options: {} },
    })
    renderApp('/entrar')

    await user.click(await screen.findByRole('button', { name: 'Entrar con Face ID o passkey' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Se ha cancelado')
  })

  it('never redirects to another website after signing in', async () => {
    api.on('GET /api/auth/session', fullSession)
    const { router } = renderApp('/entrar?siguiente=https%3A%2F%2Fevil.example')

    expect(await screen.findByText('Hola, Ana')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
  })
})
