import { useQuery } from '@tanstack/react-query'
import { type FormEvent, type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { authApi } from '../api/auth'
import { messageOf } from '../lib/errors'
import { ErrorMessage } from './ErrorMessage'

/** Set up an authenticator app: QR code (or "add on this device"), then a code to confirm. */
export function TotpSetupForm({
  title,
  onConfirmed,
  footer,
}: {
  title: string
  onConfirmed: (recoveryCodes: string[]) => Promise<unknown> | void
  footer?: ReactNode
}) {
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
      await onConfirmed(await authApi.confirmTotp(code))
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
      setCode('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="stack" onSubmit={(event) => void submit(event)}>
      <h2>{title}</h2>
      <p className="muted">{t('setup.intro')}</p>
      <ol className="steps">
        <li>{t('setup.step1')}</li>
        <li>{t('setup.step2')}</li>
        <li>{t('setup.step3')}</li>
      </ol>
      {setup.data ? (
        <div className="totp">
          <a className="button button--secondary" href={setup.data.otpauth_uri}>
            {t('setup.addOnDevice')}
          </a>
          <img src={setup.data.qr_code} alt={t('setup.qrAlt')} className="totp__qr" />
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
      {footer}
    </form>
  )
}
