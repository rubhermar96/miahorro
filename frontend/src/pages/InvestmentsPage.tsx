import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useInvestments, usePortfolio } from '../api/investments'
import { InvestmentRow } from '../components/InvestmentRow'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { formatSignedPercent } from '../lib/format'

/** The portfolio: what it is worth, what it cost and each investment (RF-INV). */
export function InvestmentsPage() {
  const { t } = useTranslation()
  const [showArchived, setShowArchived] = useState(false)
  const portfolio = usePortfolio()
  const investments = useInvestments(showArchived)
  const list = investments.data ?? []
  const total = portfolio.data

  return (
    <>
      <PageHeader title={t('inv.title')} back="/" />
      <div className="stack">
        {total && list.length > 0 && (
          <section className="card stack stack--tight" aria-label={t('inv.summary')}>
            <p className="muted small">{t('inv.value')}</p>
            <p className="total">
              <Money value={total.value} />
            </p>
            <p className="small">
              <Money value={total.gain} signed />
              {total.gain_percent !== null && total.gain_percent !== undefined && (
                <span className="muted"> ({formatSignedPercent(total.gain_percent)})</span>
              )}{' '}
              <span className="muted">{t('inv.unrealized')}</span>
            </p>
            <dl className="details">
              <div>
                <dt>{t('inv.invested')}</dt>
                <dd>
                  <Money value={total.cost} />
                </dd>
              </div>
              <div>
                <dt>{t('inv.realizedYear', { year: total.year })}</dt>
                <dd>
                  <Money value={total.realized_year} signed />
                </dd>
              </div>
              <div>
                <dt>{t('inv.dividendsYear', { year: total.year })}</dt>
                <dd>
                  <Money value={total.dividends_year} />
                </dd>
              </div>
            </dl>
            {total.unpriced > 0 && (
              <p className="notice small">{t('inv.unpriced', { count: total.unpriced })}</p>
            )}
            <Link className="button button--secondary" to="/inversiones/informe-fiscal">
              {t('inv.taxReport', { year: total.year })}
            </Link>
          </section>
        )}

        <section className="stack stack--tight" aria-labelledby="investments-title">
          <div className="section-title">
            <h2 id="investments-title">{t('inv.list')}</h2>
            <Link to="/inversiones/nueva" aria-label={t('inv.newTitle')}>
              {t('inv.new')}
            </Link>
          </div>
          {investments.isSuccess && list.length === 0 && (
            <div className="card stack stack--tight">
              <p className="muted">{t('inv.empty')}</p>
              <Link className="button" to="/inversiones/nueva">
                {t('inv.create')}
              </Link>
            </div>
          )}
          {list.length > 0 && (
            <ul className="list card card--flush">
              {list.map((investment) => (
                <li key={investment.id}>
                  <InvestmentRow investment={investment} />
                </li>
              ))}
            </ul>
          )}
          <button
            type="button"
            className="button button--ghost"
            onClick={() => setShowArchived((current) => !current)}
          >
            {showArchived ? t('inv.hideArchived') : t('inv.showArchived')}
          </button>
        </section>
        <p className="footnote">{t('inv.disclaimer')}</p>
      </div>
    </>
  )
}
