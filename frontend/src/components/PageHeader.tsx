import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

export function PageHeader({ title }: { title: string }) {
  const { t } = useTranslation()

  useEffect(() => {
    document.title = `${title} · ${t('app.name')}`
  }, [title, t])

  return (
    <header className="topbar">
      <h1>{title}</h1>
    </header>
  )
}
