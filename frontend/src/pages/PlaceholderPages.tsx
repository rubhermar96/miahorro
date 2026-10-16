import { useTranslation } from 'react-i18next'

import { ComingSoon } from '../components/ComingSoon'
import { PageHeader } from '../components/PageHeader'

// Sections that arrive in later iterations of docs/plan-mvp.md.

export function PlanPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('plan.title')} />
      <ComingSoon iteration={5} />
    </>
  )
}
