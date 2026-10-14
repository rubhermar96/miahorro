import { useTranslation } from 'react-i18next'

import { PageHeader } from '../components/PageHeader'
import { ServerStatusLine } from '../components/ServerStatusLine'

export function HomePage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('home.title')} />
      <div className="stack">
        <section className="card">
          <h2>{t('home.netWorthTitle')}</h2>
          <p className="muted">{t('home.netWorthEmpty')}</p>
        </section>
        <p className="footnote">
          <ServerStatusLine />
        </p>
      </div>
    </>
  )
}
