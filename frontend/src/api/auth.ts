import {
  type PublicKeyCredentialCreationOptionsJSON,
  type PublicKeyCredentialRequestOptionsJSON,
  startAuthentication,
  startRegistration,
} from '@simplewebauthn/browser'
import { useQuery } from '@tanstack/react-query'

import { api, toApiError, unwrap } from './client'
import type { components } from './schema'

export type SessionInfo = components['schemas']['SessionOut']
export type UserInfo = components['schemas']['UserOut']
export type Preferences = components['schemas']['Preferences']
export type PreferencesUpdate = components['schemas']['PreferencesUpdate']
export type Passkey = components['schemas']['PasskeyOut']
export type TotpSetup = components['schemas']['TotpSetup']
export type LoginStatus = components['schemas']['LoginResult']['status']

export const SESSION_KEY = ['session'] as const
export const PASSKEYS_KEY = ['passkeys'] as const

/** The current session, or null when signed out. */
export async function fetchSession(): Promise<SessionInfo | null> {
  const { data, error, response } = await api.GET('/api/auth/session')
  if (data) {
    return data
  }
  if (response.status === 401) {
    return null
  }
  throw toApiError(error, response)
}

export function useSession() {
  return useQuery({ queryKey: SESSION_KEY, queryFn: fetchSession, staleTime: 60_000 })
}

type Json = Record<string, unknown>

export const authApi = {
  async login(email: string, password: string): Promise<LoginStatus> {
    const result = await unwrap(api.POST('/api/auth/login', { body: { email, password } }))
    return result.status
  },

  verifyCode: (code: string) => unwrap(api.POST('/api/auth/mfa', { body: { code } })),

  verifyRecoveryCode: (recoveryCode: string) =>
    unwrap(api.POST('/api/auth/mfa', { body: { recovery_code: recoveryCode } })),

  startTotpSetup: () => unwrap(api.POST('/api/auth/totp/setup')),

  async confirmTotp(code: string): Promise<string[]> {
    return (await unwrap(api.POST('/api/auth/totp/confirm', { body: { code } }))).codes
  },

  async regenerateRecoveryCodes(): Promise<string[]> {
    return (await unwrap(api.POST('/api/auth/recovery-codes'))).codes
  },

  logout: () => unwrap(api.POST('/api/auth/logout')),

  logoutEverywhere: () => unwrap(api.POST('/api/auth/logout-all')),

  listPasskeys: () => unwrap(api.GET('/api/auth/passkeys')),

  deletePasskey: (id: string) =>
    unwrap(api.DELETE('/api/auth/passkeys/{passkey_id}', { params: { path: { passkey_id: id } } })),

  /** Ask the phone for a passkey (Face ID) and sign in with it. */
  async signInWithPasskey() {
    const { challenge_id, options } = await unwrap(api.POST('/api/auth/passkeys/login/options'))
    const credential = await startAuthentication({
      optionsJSON: options as unknown as PublicKeyCredentialRequestOptionsJSON,
    })
    return unwrap(
      api.POST('/api/auth/passkeys/login', {
        body: { challenge_id, credential: credential as unknown as Json },
      }),
    )
  },

  /** Create a passkey on this device for the signed-in user. */
  async registerPasskey(name: string): Promise<Passkey> {
    const { challenge_id, options } = await unwrap(api.POST('/api/auth/passkeys/register/options'))
    const credential = await startRegistration({
      optionsJSON: options as unknown as PublicKeyCredentialCreationOptionsJSON,
    })
    return unwrap(
      api.POST('/api/auth/passkeys/register', {
        body: { challenge_id, credential: credential as unknown as Json, name },
      }),
    )
  },

  updatePreferences: (changes: PreferencesUpdate) =>
    unwrap(api.PATCH('/api/me/preferences', { body: changes })),
}

/** True when the user closed or cancelled the Face ID / passkey prompt. */
export function isPasskeyCancelled(error: unknown): boolean {
  return error instanceof Error && (error.name === 'NotAllowedError' || error.name === 'AbortError')
}
