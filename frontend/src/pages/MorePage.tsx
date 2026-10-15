import { browserSupportsWebAuthn } from '@simplewebauthn/browser'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'

import {
  authApi,
  isPasskeyCancelled,
  PASSKEYS_KEY,
  type PreferencesUpdate,
  SESSION_KEY,
  type SessionInfo,
  useSession,
} from '../api/auth'
import { PageHeader } from '../components/PageHeader'
import { RecoveryCodes } from '../components/RecoveryCodes'
import { ServerStatusLine } from '../components/ServerStatusLine'
import { formatDate } from '../lib/format'
import { setThemePreference, type ThemePreference } from '../lib/theme'

const THEMES: ThemePreference[] = ['system', 'light', 'dark']
const CURRENCIES = ['EUR', 'USD', 'GBP', 'CHF'] as const
const MONTH_DAYS = Array.from({ length: 28 }, (_, index) => index + 1)

export function MorePage() {
  const { t } = useTranslation()
  const { data: session } = useSession()
  if (!session) {
    return null // RequireSession guarantees a session; this only narrows the type
  }
  const { user } = session

  return (
    <>
      <PageHeader title={t('more.title')} />
      <div className="stack">
        <section className="card">
          <h2>{t('more.account')}</h2>
          <p>
            {user.display_name}
            <br />
            <span className="muted">{user.email}</span>
          </p>
        </section>
        <PreferencesCard session={session} />
        <SecurityCard />
        {user.is_admin && (
          <a className="card card--link" href="/admin">
            {t('more.admin')}
          </a>
        )}
        <section className="card">
          <h2>{t('more.about')}</h2>
          <dl className="details">
            <div>
              <dt>{t('more.appVersion')}</dt>
              <dd>{__APP_VERSION__}</dd>
            </div>
            <div>
              <dt>{t('more.server')}</dt>
              <dd>
                <ServerStatusLine />
              </dd>
            </div>
          </dl>
        </section>
      </div>
    </>
  )
}

function PreferencesCard({ session }: { session: SessionInfo }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const preferences = session.user.preferences

  const save = useMutation({
    mutationFn: (changes: PreferencesUpdate) => authApi.updatePreferences(changes),
    onSuccess: (user) => {
      queryClient.setQueryData<SessionInfo | null>(SESSION_KEY, (current) =>
        current ? { ...current, user } : current,
      )
    },
  })

  const chooseTheme = (theme: ThemePreference) => {
    setThemePreference(theme) // immediately, even before the server answers
    save.mutate({ theme })
  }

  return (
    <section className="card stack">
      <h2>{t('more.preferences')}</h2>
      <div className="field">
        <span id="theme-label">{t('more.theme.label')}</span>
        <div className="segmented" role="radiogroup" aria-labelledby="theme-label">
          {THEMES.map((theme) => (
            <button
              key={theme}
              type="button"
              role="radio"
              aria-checked={preferences.theme === theme}
              className="segmented__option"
              onClick={() => chooseTheme(theme)}
            >
              {t(`more.theme.${theme}`)}
            </button>
          ))}
        </div>
      </div>
      <label className="field">
        <span>{t('more.currency')}</span>
        <select
          value={preferences.currency}
          onChange={(event) =>
            save.mutate({ currency: event.target.value as (typeof CURRENCIES)[number] })
          }
        >
          {CURRENCIES.map((currency) => (
            <option key={currency} value={currency}>
              {currency}
            </option>
          ))}
        </select>
      </label>
      <div className="field">
        <label htmlFor="month-start">{t('more.monthStart')}</label>
        <select
          id="month-start"
          aria-describedby="month-start-help"
          value={preferences.month_start_day}
          onChange={(event) => save.mutate({ month_start_day: Number(event.target.value) })}
        >
          {MONTH_DAYS.map((day) => (
            <option key={day} value={day}>
              {day}
            </option>
          ))}
        </select>
        <small id="month-start-help" className="muted">
          {t('more.monthStartHelp')}
        </small>
      </div>
      <label className="field">
        <span>{t('more.language')}</span>
        <select value="es" disabled>
          <option value="es">{t('more.languageSpanish')}</option>
        </select>
      </label>
      <p className="muted" role="status">
        {save.isSuccess && t('more.saved')}
        {save.isError && (save.error.message || t('errors.generic'))}
      </p>
    </section>
  )
}

function SecurityCard() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const passkeys = useQuery({ queryKey: PASSKEYS_KEY, queryFn: authApi.listPasskeys })
  const [name, setName] = useState(t('security.passkeyDefaultName'))
  const [codes, setCodes] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshPasskeys = () => queryClient.invalidateQueries({ queryKey: PASSKEYS_KEY })

  const addPasskey = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      await authApi.registerPasskey(name.trim())
      await refreshPasskeys()
    } catch (err) {
      if (!isPasskeyCancelled(err)) {
        setError(err instanceof Error ? err.message : t('errors.generic'))
      }
    }
  }

  const removePasskey = async (id: string, passkeyName: string) => {
    if (!window.confirm(t('security.confirmRemovePasskey', { name: passkeyName }))) {
      return
    }
    await authApi.deletePasskey(id)
    await refreshPasskeys()
  }

  const newRecoveryCodes = async () => {
    if (window.confirm(t('security.confirmNewRecoveryCodes'))) {
      setCodes(await authApi.regenerateRecoveryCodes())
    }
  }

  const signOut = async (everywhere: boolean) => {
    await (everywhere ? authApi.logoutEverywhere() : authApi.logout())
    queryClient.setQueryData(SESSION_KEY, null)
    void navigate('/entrar', { replace: true })
  }

  return (
    <section className="card stack">
      <h2>{t('security.title')}</h2>

      <div className="stack stack--tight">
        <h3>{t('security.passkeys')}</h3>
        <p className="muted">{t('security.passkeysHelp')}</p>
        {passkeys.data?.length === 0 && <p>{t('security.noPasskeys')}</p>}
        <ul className="list">
          {passkeys.data?.map((passkey) => (
            <li key={passkey.id} className="list__row">
              <div>
                {passkey.name}
                <br />
                <small className="muted">
                  {passkey.last_used_at
                    ? t('security.lastUsed', {
                        date: formatDate(passkey.last_used_at.slice(0, 10)),
                      })
                    : t('security.neverUsed')}
                </small>
              </div>
              <button
                type="button"
                className="button button--ghost button--danger"
                aria-label={t('security.removePasskey', { name: passkey.name })}
                onClick={() => void removePasskey(passkey.id, passkey.name)}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
        {browserSupportsWebAuthn() && (
          <form className="stack stack--tight" onSubmit={(event) => void addPasskey(event)}>
            <label className="field">
              <span>{t('security.passkeyName')}</span>
              <input
                required
                maxLength={60}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <button type="submit" className="button button--secondary">
              {t('security.addPasskey')}
            </button>
          </form>
        )}
        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}
      </div>

      <div className="stack stack--tight">
        <h3>{t('security.totpOn')}</h3>
        {codes ? (
          <RecoveryCodes codes={codes} onDone={() => setCodes(null)} />
        ) : (
          <button
            type="button"
            className="button button--secondary"
            onClick={() => void newRecoveryCodes()}
          >
            {t('security.newRecoveryCodes')}
          </button>
        )}
      </div>

      <div className="stack stack--tight">
        <button
          type="button"
          className="button button--secondary"
          onClick={() => void signOut(false)}
        >
          {t('security.logout')}
        </button>
        <button
          type="button"
          className="button button--ghost button--danger"
          onClick={() => void signOut(true)}
        >
          {t('security.logoutEverywhere')}
        </button>
      </div>
    </section>
  )
}
