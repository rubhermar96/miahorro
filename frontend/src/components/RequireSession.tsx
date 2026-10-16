import { type ReactNode, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation } from 'react-router'

import { useSession } from '../api/auth'
import { setThemePreference } from '../lib/theme'
import { Layout } from './Layout'

/** Every page except the sign-in screen goes through here. */
export function RequireSession() {
  const { t } = useTranslation()
  const location = useLocation()
  const { data: session, isPending, isError, refetch } = useSession()
  const theme = session?.user.preferences.theme

  // The theme saved on the server wins, so it follows the user across devices.
  useEffect(() => {
    if (theme) {
      setThemePreference(theme)
    }
  }, [theme])

  if (isPending) {
    return <FullScreenMessage title={t('app.name')} body={t('app.loading')} />
  }
  if (isError) {
    return (
      <FullScreenMessage title={t('errors.offlineTitle')} body={t('errors.offlineBody')}>
        <button type="button" className="button" onClick={() => void refetch()}>
          {t('errors.retry')}
        </button>
      </FullScreenMessage>
    )
  }
  if (!session || session.level !== 'full') {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/entrar?siguiente=${next}`} replace />
  }
  return <Layout />
}

export function FullScreenMessage({
  title,
  body,
  children,
}: {
  title: string
  body: string
  children?: ReactNode
}) {
  return (
    <div className="screen-center">
      <div className="stack">
        <h1 className="brand">{title}</h1>
        <p className="muted">{body}</p>
        {children}
      </div>
    </div>
  )
}
