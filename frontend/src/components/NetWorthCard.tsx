import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { Dashboard } from '../api/reports'
import { negateAmount, sumAmounts } from '../lib/amount'
import { formatAmount, formatDate } from '../lib/format'
import { Money } from './Money'

/** Net worth, the dashboard's one big number, with what it is made of (RF-INF-01). */
export function NetWorthCard({ dashboard }: { dashboard: Dashboard }) {
  const { t } = useTranslation()
  const now = dashboard.net_worth
  const before = dashboard.previous
  const change = before ? sumAmounts([now.total, negateAmount(before.total)]) : null
  const others = Object.entries(now.other_currencies)
  const rows = [
    { key: 'accounts', value: now.accounts, show: true },
    { key: 'investments', value: now.investments, show: now.investments !== '0.00' },
    { key: 'lent', value: now.lent, show: now.lent !== '0.00' },
    { key: 'debts', value: negateAmount(now.debts), show: now.debts !== '0.00' },
  ].filter((row) => row.show)

  return (
    <section className="card stack stack--tight" aria-labelledby="net-worth-title">
      <h2 id="net-worth-title" className="muted small">
        {t('dashboard.netWorth')}
      </h2>
      <p className="hero-figure">
        <Money value={now.total} />
      </p>
      {change && before && (
        <p className="small">
          <Money value={change} signed />{' '}
          <span className="muted">{t('dashboard.since', { date: formatDate(before.date) })}</span>
        </p>
      )}
      <dl className="details">
        {rows.map((row) => (
          <div key={row.key}>
            <dt>{t(`dashboard.parts.${row.key}`)}</dt>
            <dd>
              <Money value={row.value} />
            </dd>
          </div>
        ))}
      </dl>
      {others.length > 0 && (
        <p className="muted small">
          {t('home.otherCurrencies', {
            amounts: others.map(([code, total]) => formatAmount(total, code)).join(', '),
          })}
        </p>
      )}
      <Link to="/informes">{t('dashboard.evolution')}</Link>
    </section>
  )
}
