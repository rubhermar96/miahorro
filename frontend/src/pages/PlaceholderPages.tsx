import { useTranslation } from 'react-i18next'

import { ComingSoon } from '../components/ComingSoon'
import { PageHeader } from '../components/PageHeader'

// Sections that arrive in later iterations of docs/plan-mvp.md.

export function TransactionsPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('transactions.title')} />
      <ComingSoon iteration={2} />
    </>
  )
}

export function AddPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('add.title')} />
      <ComingSoon iteration={2} />
    </>
  )
}

export function PlanPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('plan.title')} />
      <ComingSoon iteration={5} />
    </>
  )
}
