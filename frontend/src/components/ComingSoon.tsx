import { useTranslation } from 'react-i18next'

export function ComingSoon({ iteration }: { iteration: number }) {
  const { t } = useTranslation()
  return (
    <section className="card">
      <h2>{t('comingSoon.title')}</h2>
      <p className="muted">{t('comingSoon.body', { iteration })}</p>
    </section>
  )
}
