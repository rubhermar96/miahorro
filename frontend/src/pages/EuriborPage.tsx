import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useSession } from '../api/auth'
import { loanKeys, loansApi, useReferenceRates } from '../api/loans'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { messageOf } from '../lib/errors'
import { formatMonthYear, formatRate, todayIso } from '../lib/format'
import { parseRateInput } from '../lib/rate'

/** Euribor 12 months, typed in by hand and shared by everyone (RF-PRE-03). */
export function EuriborPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data: session } = useSession()
  const rates = useReferenceRates()
  const [month, setMonth] = useState(todayIso().slice(0, 7))
  const [valueText, setValueText] = useState('')
  const [error, setError] = useState<string | null>(null)

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: loanKeys.loans }),
      queryClient.invalidateQueries({ queryKey: loanKeys.rates }),
    ])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const value = parseRateInput(valueText, { allowNegative: true })
    if (value === null) {
      setError(t('loans.invalidRate'))
      return
    }
    try {
      await loansApi.setRate(`${month}-01`, value)
      setValueText('')
      await refresh()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  const remove = async (id: string) => {
    try {
      await loansApi.removeRate(id)
      await refresh()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  return (
    <>
      <PageHeader title={t('euribor.title')} back="/planificar" />
      <div className="stack">
        <p className="muted small">{t('euribor.intro')}</p>
        <form className="card stack stack--tight" onSubmit={(event) => void submit(event)}>
          <div className="search">
            <label className="field">
              <span>{t('euribor.month')}</span>
              <input
                type="month"
                required
                value={month}
                onChange={(event) => setMonth(event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t('euribor.value')}</span>
              <input
                inputMode="decimal"
                required
                value={valueText}
                onChange={(event) => setValueText(event.target.value)}
              />
            </label>
            <button type="submit" className="button">
              {t('add.save')}
            </button>
          </div>
          <ErrorMessage message={error} />
        </form>
        {rates.isSuccess && rates.data.length === 0 && (
          <p className="card muted">{t('euribor.empty')}</p>
        )}
        {(rates.data?.length ?? 0) > 0 && (
          <ul className="list card card--flush" aria-label={t('euribor.title')}>
            {rates.data?.map((rate) => (
              <li key={rate.id} className="row">
                <span className="row__text">
                  <span className="row__title">{formatMonthYear(rate.month)}</span>
                </span>
                <span>{formatRate(rate.value)} %</span>
                {session?.user.is_admin && (
                  <button
                    type="button"
                    className="button button--ghost button--danger"
                    aria-label={t('euribor.remove', { month: formatMonthYear(rate.month) })}
                    onClick={() => void remove(rate.id)}
                  >
                    ✕
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}
