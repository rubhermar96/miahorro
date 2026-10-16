import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { captureApi, captureKeys, useInbox } from '../api/capture'
import { financeApi, refreshFinance, useAccounts } from '../api/finance'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { formatDate } from '../lib/format'

/** What needs a look: payments the bank never confirmed and expected movements that did not
 * arrive. */
export function ReviewPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const inbox = useInbox()
  const accounts = useAccounts(true)
  const accountName = (id: string) => accounts.data?.find((a) => a.id === id)?.name ?? ''

  const refresh = () =>
    Promise.all([
      refreshFinance(queryClient),
      queryClient.invalidateQueries({ queryKey: captureKeys.inbox }),
    ])

  const keep = async (id: string) => {
    await captureApi.confirm(id)
    await refresh()
  }

  const discard = async (id: string, name: string) => {
    if (!window.confirm(t('review.confirmDiscard', { name }))) {
      return
    }
    await financeApi.deleteTransaction(id)
    await refresh()
  }

  const unconfirmed = inbox.data?.unconfirmed ?? []
  const overdue = inbox.data?.overdue ?? []

  return (
    <>
      <PageHeader title={t('review.title')} back="/" />
      <div className="stack">
        {inbox.isSuccess && unconfirmed.length === 0 && overdue.length === 0 && (
          <p className="card muted">{t('review.empty')}</p>
        )}

        {unconfirmed.length > 0 && (
          <section className="stack stack--tight" aria-labelledby="unconfirmed-title">
            <h2 id="unconfirmed-title" className="section-title">
              {t('review.unconfirmed')}
            </h2>
            <p className="muted small">{t('review.unconfirmedHelp')}</p>
            <ul className="list card card--flush">
              {unconfirmed.map((row) => (
                <li key={row.id} className="row">
                  <span className="row__text">
                    <span className="row__title">{row.description}</span>
                    <small className="muted">
                      {formatDate(row.date)} · {accountName(row.account_id)}
                    </small>
                  </span>
                  <Money value={row.amount} signed />
                  <span className="row__actions">
                    <button
                      type="button"
                      className="button button--ghost"
                      onClick={() => void keep(row.id)}
                    >
                      {t('review.keep')}
                    </button>
                    <button
                      type="button"
                      className="button button--ghost button--danger"
                      onClick={() => void discard(row.id, row.description)}
                    >
                      {t('review.discard')}
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {overdue.length > 0 && (
          <section className="stack stack--tight" aria-labelledby="overdue-title">
            <h2 id="overdue-title" className="section-title">
              {t('review.overdue')}
            </h2>
            <p className="muted small">{t('review.overdueHelp')}</p>
            <ul className="list card card--flush">
              {overdue.map((item) => (
                <li key={`${item.item_id}-${item.date}`} className="row">
                  <span className="row__text">
                    <span className="row__title">{item.name}</span>
                    <small className="muted">
                      {t('review.expected', { date: formatDate(item.date) })} ·{' '}
                      {accountName(item.account_id)}
                    </small>
                  </span>
                  <Money value={item.amount} signed />
                </li>
              ))}
            </ul>
            <Link to="/mas/recurrentes">{t('review.manageRecurring')}</Link>
          </section>
        )}
      </div>
    </>
  )
}
