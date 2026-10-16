import { useTranslation } from 'react-i18next'

import { useSession } from '../api/auth'
import { PageHeader } from '../components/PageHeader'
import { ServerStatusLine } from '../components/ServerStatusLine'

export function HomePage() {
  const { t } = useTranslation()
  const { data: session } = useSession()
  return (
    <>
      <PageHeader title={t('home.title')} />
      <div className="stack">
        {session && (
          <p className="greeting">{t('home.greeting', { name: session.user.display_name })}</p>
        )}
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
