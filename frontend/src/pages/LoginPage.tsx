import { browserSupportsWebAuthn } from '@simplewebauthn/browser'
import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router'

import {
  authApi,
  isPasskeyCancelled,
  SESSION_KEY,
  type SessionInfo,
  useRegistrationOpen,
  useSession,
} from '../api/auth'
import { ErrorMessage } from '../components/ErrorMessage'
import { RecoveryCodes } from '../components/RecoveryCodes'
import { FullScreenMessage } from '../components/RequireSession'
import { TotpSetupForm } from '../components/TotpSetupForm'
import { deviceName } from '../lib/device'
import { messageOf } from '../lib/errors'
import { isServerPage, safeNextPath } from '../lib/navigation'

/**
 * Sign-in and registration in steps, driven by the session level the API reports:
 *   no session -> email + password (or a passkey, which signs in on its own),
 *                 or the registration form at /registro
 *   mfa_pending -> second step: Face ID (passkey) or the 6-digit code, or a recovery code
 *   mfa_setup   -> first time: choose Face ID (one tap) or set up an authenticator app,
 *                  which then shows recovery codes (D23)
 */
export function LoginPage({ mode = 'login' }: { mode?: 'login' | 'register' }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params] = useSearchParams()
  const next = safeNextPath(params.get('siguiente'))
  const { data: session, isPending } = useSession()
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null)
  // After setting up Face ID, the authenticator app is offered too: without it there is no way
  // in from a computer or a device without that passkey.
  const [offerApp, setOfferApp] = useState(false)

  const refreshSession = () => queryClient.invalidateQueries({ queryKey: SESSION_KEY })

  const finished = session?.level === 'full' && !recoveryCodes && !offerApp
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
    const title = mode === 'register' ? t('register.title') : t('login.title')
    document.title = `${title} · ${t('app.name')}`
  }, [mode, t])

  if (isPending || finished) {
    return <FullScreenMessage title={t('app.name')} body={t('app.loading')} />
  }

  let step
  if (recoveryCodes) {
    step = <RecoveryCodes codes={recoveryCodes} onDone={() => setRecoveryCodes(null)} />
  } else if (offerApp && session?.level === 'full') {
    step = (
      <AlsoAddAppStep
        onConfirmed={(codes) => {
          setOfferApp(false)
          setRecoveryCodes(codes)
        }}
        onSkip={() => setOfferApp(false)}
      />
    )
  } else if (session?.level === 'mfa_pending') {
    step = <SecondStep session={session} onDone={refreshSession} />
  } else if (session?.level === 'mfa_setup') {
    step = (
      <ChooseSecondFactorStep
        onPasskey={async () => {
          setOfferApp(true)
          await refreshSession()
        }}
        onTotp={async (codes) => {
          setRecoveryCodes(codes)
          await refreshSession()
        }}
      />
    )
  } else if (mode === 'register') {
    step = <RegisterStep onDone={refreshSession} query={params.toString()} />
  } else {
    step = <CredentialsStep onDone={refreshSession} query={params.toString()} />
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

type StepProps = { onDone: () => Promise<unknown>; query: string }

/** Keeps ?siguiente=… when switching between sign-in and registration. */
function withQuery(path: string, query: string): string {
  return query ? `${path}?${query}` : path
}

function RegisterStep({ onDone, query }: StepProps) {
  const { t } = useTranslation()
  const registration = useRegistrationOpen()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await authApi.register(name, email, password)
      await onDone()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  const signInLink = (
    <p className="switch">
      {t('register.haveAccount')}{' '}
      <Link to={withQuery('/entrar', query)}>{t('register.signIn')}</Link>
    </p>
  )

  if (registration.data === false) {
    return (
      <section className="card stack">
        <p>{t('register.closed')}</p>
        {signInLink}
      </section>
    )
  }

  return (
    <section className="card">
      <form className="stack" onSubmit={(event) => void submit(event)}>
        <h2>{t('register.title')}</h2>
        <label className="field">
          <span>{t('register.name')}</span>
          <input
            autoComplete="name"
            required
            maxLength={100}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
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
        <div className="field">
          <label htmlFor="new-password">{t('login.password')}</label>
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            aria-describedby="new-password-help"
            required
            minLength={12}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <small id="new-password-help" className="muted">
            {t('register.passwordHelp')}
          </small>
        </div>
        <ErrorMessage message={error} />
        <button type="submit" className="button" disabled={busy}>
          {t('register.submit')}
        </button>
        {signInLink}
      </form>
    </section>
  )
}

function CredentialsStep({ onDone, query }: StepProps) {
  const { t } = useTranslation()
  const passkeysSupported = browserSupportsWebAuthn()
  const registration = useRegistrationOpen()
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
      {registration.data && (
        <p className="switch">
          {t('login.noAccount')}{' '}
          <Link to={withQuery('/registro', query)}>{t('login.createAccount')}</Link>
        </p>
      )}
    </section>
  )
}

/** Cancelling a half-finished sign-in goes back to the email and password form. */
function CancelButton({ onDone }: { onDone: () => Promise<unknown> }) {
  const { t } = useTranslation()
  const cancel = async () => {
    await authApi.logout().catch(() => undefined)
    await onDone()
  }
  return (
    <button type="button" className="button button--ghost" onClick={() => void cancel()}>
      {t('login.cancel')}
    </button>
  )
}

/** After the password: Face ID, the authenticator code or, as a last resort, a recovery code. */
function SecondStep({ session, onDone }: { session: SessionInfo; onDone: () => Promise<unknown> }) {
  const { t } = useTranslation()
  const { has_passkey: hasPasskey, has_totp: hasTotp } = session.user
  const canUsePasskey = hasPasskey && browserSupportsWebAuthn()
  const canUseRecovery = session.user.recovery_codes_left > 0
  const [useRecovery, setUseRecovery] = useState(!canUsePasskey && !hasTotp)
  const [code, setCode] = useState('')
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
      setCode('')
    } finally {
      setBusy(false)
    }
  }

  const submitCode = (event: FormEvent) => {
    event.preventDefault()
    void run(() => (useRecovery ? authApi.verifyRecoveryCode(code) : authApi.verifyCode(code)))
  }

  const showCodeForm = useRecovery || hasTotp

  return (
    <section className="card stack">
      <h2>{t('login.secondTitle')}</h2>
      {canUsePasskey && !useRecovery && (
        <>
          <button
            type="button"
            className="button"
            disabled={busy}
            onClick={() => void run(() => authApi.signInWithPasskey())}
          >
            {t('login.confirmFaceId')}
          </button>
          <p className="muted small">{t('login.computerHint')}</p>
          {hasTotp && <p className="divider">{t('login.or')}</p>}
        </>
      )}
      {showCodeForm && (
        <form className="stack" onSubmit={submitCode}>
          {!useRecovery && <p className="muted">{t('login.codeHelp')}</p>}
          <label className="field">
            <span>{useRecovery ? t('login.recoveryCode') : t('login.code')}</span>
            <input
              key={useRecovery ? 'recovery' : 'totp'}
              autoComplete="one-time-code"
              inputMode={useRecovery ? 'text' : 'numeric'}
              maxLength={useRecovery ? 16 : 6}
              required
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
          </label>
          <button
            type="submit"
            className={canUsePasskey && !useRecovery ? 'button button--secondary' : 'button'}
            disabled={busy}
          >
            {t('login.verify')}
          </button>
        </form>
      )}
      {!hasTotp && !useRecovery && <p className="notice small">{t('login.onlyFaceId')}</p>}
      <ErrorMessage message={error} />
      <div className="actions actions--spread">
        {canUseRecovery && (
          <button
            type="button"
            className="button button--ghost"
            onClick={() => {
              setUseRecovery(!useRecovery)
              setCode('')
              setError(null)
            }}
          >
            {useRecovery ? t('login.back') : t('login.useRecovery')}
          </button>
        )}
        <CancelButton onDone={onDone} />
      </div>
    </section>
  )
}

/** Right after setting up Face ID: the authenticator app as well, to sign in from a computer. */
function AlsoAddAppStep({
  onConfirmed,
  onSkip,
}: {
  onConfirmed: (recoveryCodes: string[]) => void
  onSkip: () => void
}) {
  const { t } = useTranslation()
  return (
    <section className="card stack">
      <p className="saved">{t('setup.faceIdReady')}</p>
      <p className="muted">{t('setup.alsoAppIntro')}</p>
      <TotpSetupForm
        title={t('setup.alsoAppTitle')}
        onConfirmed={async (codes) => onConfirmed(codes)}
        footer={
          <button type="button" className="button button--ghost" onClick={onSkip}>
            {t('setup.notNow')}
          </button>
        }
      />
    </section>
  )
}

/** First sign-in: Face ID in one tap, or an authenticator app for devices without it. */
function ChooseSecondFactorStep({
  onPasskey,
  onTotp,
}: {
  onPasskey: () => Promise<unknown>
  onTotp: (recoveryCodes: string[]) => Promise<unknown>
}) {
  const { t } = useTranslation()
  const passkeysSupported = browserSupportsWebAuthn()
  const [useApp, setUseApp] = useState(!passkeysSupported)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (useApp) {
    return (
      <section className="card">
        <TotpSetupForm
          title={t('setup.title')}
          onConfirmed={onTotp}
          footer={
            passkeysSupported && (
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setUseApp(false)}
              >
                {t('login.back')}
              </button>
            )
          }
        />
      </section>
    )
  }

  const enrollFaceId = async () => {
    setBusy(true)
    setError(null)
    try {
      await authApi.registerPasskey(deviceName())
      await onPasskey()
    } catch (err) {
      setError(
        isPasskeyCancelled(err) ? t('login.passkeyCancelled') : messageOf(err, t('errors.generic')),
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card stack">
      <h2>{t('setup.title')}</h2>
      <p className="muted">{t('setup.chooseIntro')}</p>
      <button type="button" className="button" disabled={busy} onClick={() => void enrollFaceId()}>
        {t('setup.faceId')}
      </button>
      <p className="muted small">{t('setup.faceIdHelp')}</p>
      <ErrorMessage message={error} />
      <p className="divider">{t('login.or')}</p>
      <button type="button" className="button button--secondary" onClick={() => setUseApp(true)}>
        {t('setup.useApp')}
      </button>
      <p className="muted small">{t('setup.useAppHelp')}</p>
    </section>
  )
}
