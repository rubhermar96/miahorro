import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { PageHeader } from '../components/PageHeader'

export function NotFoundPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('notFound.title')} />
      <section className="card">
        <Link to="/">{t('notFound.back')}</Link>
      </section>
    </>
  )
}
