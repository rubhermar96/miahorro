import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import {
  type Loan,
  loanKeys,
  loansApi,
  type Simulation,
  useLoan,
  usePrepayments,
  useSchedule,
} from '../api/loans'
import { ErrorMessage } from '../components/ErrorMessage'
import { Meter } from '../components/Meter'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'
import { formatAmount, formatDate, formatMonthYear, formatRate, todayIso } from '../lib/format'

/** One loan: where it stands, early repayments and its amortization table (RF-PRE-05…09). */
export function LoanPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const loan = useLoan(id)
  if (!loan.data) {
    return <PageHeader title={t('loans.title')} back="/planificar" />
  }
  return <LoanDetails loan={loan.data} />
}

function useRefresh() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: loanKeys.loans })
}

function LoanDetails({ loan }: { loan: Loan }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const refresh = useRefresh()
  const repaid =
    Number(loan.principal) > 0 ? (Number(loan.principal_paid) / Number(loan.principal)) * 100 : 0

  const toggleArchived = async () => {
    await loansApi.update(loan.id, { archived: !loan.archived })
    await refresh()
  }

  const remove = async () => {
    if (!window.confirm(t('loans.confirmDelete', { name: loan.name }))) {
      return
    }
    await loansApi.remove(loan.id)
    await refresh()
    void navigate('/planificar', { replace: true })
  }

  return (
    <>
      <PageHeader title={loan.name} back="/planificar" />
      <div className="stack">
        <section className="card stack stack--tight" aria-label={t('loans.summary')}>
          <p className="muted small">
            {[t(`loans.kinds.${loan.kind}`), loan.lender].filter(Boolean).join(' · ')}
          </p>
          <p className="total">
            <Money value={loan.outstanding} />
          </p>
          <p className="muted small">
            {loan.direction === 'owed' ? t('loans.owedLeft') : t('loans.left')}{' '}
            {t('loans.ofPrincipal', { principal: formatAmount(loan.principal) })}
          </p>
          <Meter value={repaid} label={t('loans.repaidShare')} />
          <dl className="details">
            {loan.next_payment && (
              <div>
                <dt>{t('loans.nextPayment', { date: formatDate(loan.next_payment.date) })}</dt>
                <dd>
                  <Money value={loan.next_payment.amount} />
                </dd>
              </div>
            )}
            <div>
              <dt>{t('loans.currentRate')}</dt>
              <dd>{formatRate(loan.current_rate)} %</dd>
            </div>
            <div>
              <dt>{t('loans.interestPaid')}</dt>
              <dd>
                <Money value={loan.interest_paid} />
              </dd>
            </div>
            <div>
              <dt>{t('loans.interestLeft')}</dt>
              <dd>
                <Money value={loan.interest_left} />
              </dd>
            </div>
            {loan.end_date && (
              <div>
                <dt>{t('loans.endDate')}</dt>
                <dd>
                  {formatMonthYear(loan.end_date)} ·{' '}
                  {t('loans.paymentsLeft', { count: loan.payments_left })}
                </dd>
              </div>
            )}
          </dl>
          {loan.warnings.map((warning) => (
            <p key={warning} className="notice small">
              {warning} <Link to="/planificar/euribor">{t('loans.goEuribor')}</Link>
            </p>
          ))}
        </section>

        {loan.payments_left > 0 && <EarlyRepayment loan={loan} />}
        <Prepayments loan={loan} />
        <Schedule loan={loan} />

        <section className="card stack stack--tight">
          <Link className="button button--secondary" to={`/planificar/prestamos/${loan.id}/editar`}>
            {t('loans.edit')}
          </Link>
          {loan.rate_type !== 'fixed' && (
            <Link className="button button--secondary" to="/planificar/euribor">
              {t('loans.euriborTable')}
            </Link>
          )}
          <button
            type="button"
            className="button button--secondary"
            onClick={() => void toggleArchived()}
          >
            {loan.archived ? t('loans.unarchive') : t('loans.archive')}
          </button>
          <button
            type="button"
            className="button button--ghost button--danger"
            onClick={() => void remove()}
          >
            {t('loans.delete')}
          </button>
        </section>
      </div>
    </>
  )
}

function EarlyRepayment({ loan }: { loan: Loan }) {
  const { t } = useTranslation()
  const refresh = useRefresh()
  const [date, setDate] = useState(todayIso())
  const [amountText, setAmountText] = useState('')
  const [mode, setMode] = useState<'reduce_term' | 'reduce_payment'>('reduce_term')
  const [result, setResult] = useState<Simulation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const request = () => {
    const amount = parseAmountInput(amountText)
    if (!amount) {
      setError(t('add.invalidAmount'))
      return null
    }
    return { date, amount, mode }
  }

  const simulate = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setMessage(null)
    const body = request()
    if (!body) {
      return
    }
    try {
      setResult(await loansApi.simulate(loan.id, body))
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  const register = async () => {
    const body = request()
    if (!body || !window.confirm(t('loans.confirmRegister'))) {
      return
    }
    try {
      await loansApi.addPrepayment(loan.id, body)
      setResult(null)
      setAmountText('')
      setMessage(t('loans.registered'))
      await refresh()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  return (
    <form className="card stack stack--tight" onSubmit={(event) => void simulate(event)}>
      <h2>{t('loans.earlyTitle')}</h2>
      <div className="grid-2">
        <label className="field">
          <span>{t('loans.earlyAmount')}</span>
          <input
            inputMode="decimal"
            required
            value={amountText}
            onChange={(event) => {
              setAmountText(event.target.value)
              setResult(null)
            }}
          />
        </label>
        <label className="field">
          <span>{t('add.date')}</span>
          <input
            type="date"
            required
            value={date}
            onChange={(event) => {
              setDate(event.target.value)
              setResult(null)
            }}
          />
        </label>
      </div>
      <div className="segmented segmented--two" role="radiogroup" aria-label={t('loans.earlyMode')}>
        {(['reduce_term', 'reduce_payment'] as const).map((option) => (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={mode === option}
            className="segmented__option"
            onClick={() => {
              setMode(option)
              setResult(null)
            }}
          >
            {t(`loans.modes.${option}`)}
          </button>
        ))}
      </div>
      <button type="submit" className="button button--secondary">
        {t('loans.simulate')}
      </button>
      {result && (
        <div className="stack stack--tight" role="status">
          <dl className="details">
            <div>
              <dt>{t('loans.interestSaved')}</dt>
              <dd>
                <Money value={result.interest_saved} />
              </dd>
            </div>
            <div>
              <dt>
                {t('loans.fee', { percent: formatRate(result.fee_percent) })}
                {result.legal_cap !== null && result.legal_cap !== undefined && (
                  <small className="muted">
                    {' '}
                    {t('loans.legalCap', { percent: formatRate(result.legal_cap) })}
                  </small>
                )}
              </dt>
              <dd>
                <Money value={result.fee} />
              </dd>
            </div>
            {mode === 'reduce_payment' && result.payment_after && result.payment_before && (
              <div>
                <dt>{t('loans.newPayment')}</dt>
                <dd>
                  {formatAmount(result.payment_before)} → {formatAmount(result.payment_after)}
                </dd>
              </div>
            )}
            {mode === 'reduce_term' && result.end_after && (
              <div>
                <dt>{t('loans.newEnd')}</dt>
                <dd>
                  {formatMonthYear(result.end_after)} ·{' '}
                  {t('loans.paymentsSaved', { count: result.payments_saved })}
                </dd>
              </div>
            )}
          </dl>
          <button type="button" className="button" onClick={() => void register()}>
            {t('loans.register')}
          </button>
        </div>
      )}
      <ErrorMessage message={error} />
      {message && (
        <p className="saved" role="status">
          {message}
        </p>
      )}
    </form>
  )
}

function Prepayments({ loan }: { loan: Loan }) {
  const { t } = useTranslation()
  const refresh = useRefresh()
  const prepayments = usePrepayments(loan.id)
  if (!prepayments.data?.length) {
    return null
  }
  const remove = async (id: string) => {
    if (!window.confirm(t('loans.confirmRemovePrepayment'))) {
      return
    }
    await loansApi.removePrepayment(loan.id, id)
    await refresh()
  }
  return (
    <section className="stack stack--tight" aria-labelledby="prepayments-title">
      <h2 id="prepayments-title" className="section-title">
        {t('loans.prepayments')}
      </h2>
      <ul className="list card card--flush">
        {prepayments.data.map((row) => (
          <li key={row.id} className="row">
            <span className="row__text">
              <span className="row__title">
                <Money value={row.amount} />
              </span>
              <small className="muted">
                {[
                  formatDate(row.date),
                  t(`loans.modes.${row.mode}`),
                  t('loans.feePaid', { fee: formatAmount(row.fee) }),
                ].join(' · ')}
              </small>
            </span>
            <button
              type="button"
              className="button button--ghost button--danger"
              aria-label={t('loans.removePrepayment', { date: formatDate(row.date) })}
              onClick={() => void remove(row.id)}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Schedule({ loan }: { loan: Loan }) {
  const { t } = useTranslation()
  const rows = useSchedule(loan.id)
  const [open, setOpen] = useState(false)
  return (
    <details className="card" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>{t('loans.schedule', { count: rows.data?.length ?? loan.term_months })}</summary>
      {open && rows.data && (
        <div
          className="details-body table-scroll"
          tabIndex={0}
          role="region"
          aria-label={t('loans.scheduleTable')}
        >
          <table className="sample loan-table">
            <thead>
              <tr>
                <th>{t('loans.cols.number')}</th>
                <th>{t('loans.cols.date')}</th>
                <th>{t('loans.cols.rate')}</th>
                <th>{t('loans.cols.payment')}</th>
                <th>{t('loans.cols.interest')}</th>
                <th>{t('loans.cols.principal')}</th>
                <th>{t('loans.cols.outstanding')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.data.map((row) => (
                <tr
                  key={row.number}
                  className={[
                    row.paid ? 'loan-table__paid' : '',
                    row.review ? 'loan-table__review' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  <td>{row.number}</td>
                  <td>{formatDate(row.date)}</td>
                  <td>{formatRate(row.rate)} %</td>
                  <td>{formatAmount(row.payment)}</td>
                  <td>{formatAmount(row.interest)}</td>
                  <td>{formatAmount(row.principal)}</td>
                  <td>{formatAmount(row.outstanding)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </details>
  )
}
