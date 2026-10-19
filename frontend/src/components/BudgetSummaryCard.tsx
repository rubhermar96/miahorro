import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useBudget } from '../api/budget'
import { formatAmount } from '../lib/format'
import { Meter } from './Meter'
import { Money } from './Money'

/** This month's budget at a glance, on Planificar. */
export function BudgetSummaryCard() {
  const { t } = useTranslation()
  const budget = useBudget('')
  const data = budget.data
  if (!data) {
    return null
  }
  const spent = data.activity.startsWith('-') ? data.activity.slice(1) : '0.00'
  return (
    <Link className="card card--link goal" to="/planificar/presupuesto">
      <div className="goal__head">
        <span className="goal__name">{t('budget.title')}</span>
        <span aria-hidden="true">›</span>
      </div>
      {!data.mode && <p className="small muted">{t('budget.summaryChoose')}</p>}
      {data.mode === 'zero_based' && (
        <p className="small">
          {t('budget.toAssign')}: <Money value={data.to_assign ?? '0.00'} />
        </p>
      )}
      {data.mode === 'limits' && (
        <>
          <Meter
            value={
              Number(data.assigned) > 0
                ? Math.min((Number(spent) / Number(data.assigned)) * 100, 100)
                : 0
            }
            label={t('budget.totalProgress')}
          />
          <p className="small">
            {t('budget.summaryLimits', {
              spent: formatAmount(spent),
              limit: formatAmount(data.assigned),
            })}
          </p>
        </>
      )}
    </Link>
  )
}
