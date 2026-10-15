import { browserSupportsWebAuthn } from '@simplewebauthn/browser'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router'

import { authApi, isPasskeyCancelled, SESSION_KEY, useSession } from '../api/auth'
import { FullScreenMessage } from '../components/RequireSession'
import { RecoveryCodes } from '../components/RecoveryCodes'
import { isServerPage, safeNextPath } from '../lib/navigation'

/**
 * Sign-in in steps, driven by the session level the API reports:
 *   no session -> email + password (or a passkey, which signs in on its own)
 *   mfa_pending -> 6-digit code (or a recovery code)
 *   mfa_setup   -> first time: set up the authenticator app, then show recovery codes
 */
export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params] = useSearchParams()
  const next = safeNextPath(params.get('siguiente'))
  const { data: session, isPending } = useSession()
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null)

  const refreshSession = () => queryClient.invalidateQueries({ queryKey: SESSION_KEY })

  const finished = session?.level === 'full' && !recoveryCodes
  useEffect(() => {
    if (!finished) {
      return
    }
    if (isServerPage(next)) {
      window.location.assign(next)
    } else {
      void navigate(next, { replace: true })
    }
  }, [finished, next, navigate])

  useEffect(() => {
    document.title = `${t('login.title')} · ${t('app.name')}`
  }, [t])

  if (isPending || finished) {
    return <FullScreenMessage title={t('app.name')} body={t('app.loading')} />
  }

  let step
  if (recoveryCodes) {
    step = <RecoveryCodes codes={recoveryCodes} onDone={() => setRecoveryCodes(null)} />
  } else if (session?.level === 'mfa_pending') {
    step = <CodeStep onDone={refreshSession} />
  } else if (session?.level === 'mfa_setup') {
    step = (
      <SetupStep
        onDone={async (codes) => {
          setRecoveryCodes(codes)
          await refreshSession()
        }}
      />
    )
  } else {
    step = <CredentialsStep onDone={refreshSession} />
  }

  return (
    <div className="screen-center">
      <div className="login stack">
        <header className="stack login__header">
          <img src="/pwa-192x192.png" alt="" width="64" height="64" className="login__logo" />
          <h1 className="brand">{t('app.name')}</h1>
          <p className="muted">{t('login.tagline')}</p>
        </header>
        {step}
      </div>
    </div>
  )
}

function ErrorMessage({ message }: { message: string | null }) {
  return message ? (
    <p className="alert" role="alert">
      {message}
    </p>
  ) : null
}

function messageOf(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

function CredentialsStep({ onDone }: { onDone: () => Promise<unknown> }) {
  const { t } = useTranslation()
  const passkeysSupported = browserSupportsWebAuthn()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    try {
      await action()
      await onDone()
    } catch (err) {
      setError(
        isPasskeyCancelled(err) ? t('login.passkeyCancelled') : messageOf(err, t('errors.generic')),
      )
    } finally {
      setBusy(false)
    }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void run(() => authApi.login(email, password))
  }

  return (
    <section className="card stack">
      {passkeysSupported && (
        <>
          <button
            type="button"
            className="button"
            disabled={busy}
            onClick={() => void run(() => authApi.signInWithPasskey())}
          >
            {t('login.passkey')}
          </button>
          <p className="divider">{t('login.or')}</p>
        </>
      )}
      <form className="stack" onSubmit={submit}>
        <label className="field">
          <span>{t('login.email')}</span>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label className="field">
          <span>{t('login.password')}</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <ErrorMessage message={error} />
        <button
          type="submit"
          className={passkeysSupported ? 'button button--secondary' : 'button'}
          disabled={busy}
        >
          {t('login.submit')}
        </button>
      </form>
    </section>
  )
}

function CodeStep({ onDone }: { onDone: () => Promise<unknown> }) {
  const { t } = useTranslation()
  const [useRecovery, setUseRecovery] = useState(false)
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await (useRecovery ? authApi.verifyRecoveryCode(code) : authApi.verifyCode(code))
      await onDone()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
      setCode('')
    } finally {
      setBusy(false)
    }
  }

  const cancel = async () => {
    await authApi.logout().catch(() => undefined)
    await onDone()
  }

  return (
    <section className="card">
      <form className="stack" onSubmit={(event) => void submit(event)}>
        <h2>{t('login.codeTitle')}</h2>
        {!useRecovery && <p className="muted">{t('login.codeHelp')}</p>}
        <label className="field">
          <span>{useRecovery ? t('login.recoveryCode') : t('login.code')}</span>
          <input
            key={useRecovery ? 'recovery' : 'totp'}
            autoComplete="one-time-code"
            inputMode={useRecovery ? 'text' : 'numeric'}
            maxLength={useRecovery ? 16 : 6}
            required
            autoFocus
            value={code}
            onChange={(event) => setCode(event.target.value)}
          />
        </label>
        <ErrorMessage message={error} />
        <button type="submit" className="button" disabled={busy}>
          {t('login.verify')}
        </button>
        <div className="actions actions--spread">
          <button
            type="button"
            className="button button--ghost"
            onClick={() => {
              setUseRecovery(!useRecovery)
              setCode('')
              setError(null)
            }}
          >
            {useRecovery ? t('login.useApp') : t('login.useRecovery')}
          </button>
          <button type="button" className="button button--ghost" onClick={() => void cancel()}>
            {t('login.cancel')}
          </button>
        </div>
      </form>
    </section>
  )
}

function SetupStep({ onDone }: { onDone: (codes: string[]) => Promise<unknown> }) {
  const { t } = useTranslation()
  // A query (not an effect) so React's double rendering in development asks only once.
  const setup = useQuery({
    queryKey: ['totp-setup'],
    queryFn: authApi.startTotpSetup,
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
  })
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onDone(await authApi.confirmTotp(code))
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
      setCode('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <form className="stack" onSubmit={(event) => void submit(event)}>
        <h2>{t('setup.title')}</h2>
        <p className="muted">{t('setup.intro')}</p>
        <ol className="steps">
          <li>{t('setup.step1')}</li>
          <li>{t('setup.step2')}</li>
          <li>{t('setup.step3')}</li>
        </ol>
        {setup.data ? (
          <div className="totp">
            <img src={setup.data.qr_code} alt={t('setup.qrAlt')} className="totp__qr" />
            <a className="button button--secondary" href={setup.data.otpauth_uri}>
              {t('setup.addOnDevice')}
            </a>
            <details>
              <summary>{t('setup.manual')}</summary>
              <code className="totp__secret">{setup.data.secret.match(/.{1,4}/g)?.join(' ')}</code>
            </details>
          </div>
        ) : (
          <ErrorMessage
            message={setup.isError ? messageOf(setup.error, t('errors.generic')) : null}
          />
        )}
        <label className="field">
          <span>{t('login.code')}</span>
          <input
            autoComplete="one-time-code"
            inputMode="numeric"
            maxLength={6}
            required
            value={code}
            onChange={(event) => setCode(event.target.value)}
          />
        </label>
        <ErrorMessage message={error} />
        <button type="submit" className="button" disabled={busy || !setup.data}>
          {t('setup.confirm')}
        </button>
      </form>
    </section>
  )
}
