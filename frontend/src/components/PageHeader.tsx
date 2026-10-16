import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

/** Page title; sub-pages pass `back` to show a way back to where they came from. */
export function PageHeader({ title, back }: { title: string; back?: string }) {
  const { t } = useTranslation()

  useEffect(() => {
    document.title = `${title} · ${t('app.name')}`
  }, [title, t])

  return (
    <header className="topbar">
      {back && (
        <Link className="topbar__back" to={back}>
          ‹ {t('nav.back')}
        </Link>
      )}
      <h1>{title}</h1>
    </header>
  )
}
