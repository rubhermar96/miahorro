import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useLoans } from '../api/loans'
import { sumAmounts } from '../lib/amount'
import { formatAmount, formatDate } from '../lib/format'
import { Meter } from './Meter'
import { Money } from './Money'

/** Loans on Planificar: what is owed, to whom, and the next instalment (RF-PRE-09). */
export function LoansSection() {
  const { t } = useTranslation()
  const loans = useLoans()
  const list = loans.data ?? []
  const owe = sumAmounts(list.filter((l) => l.direction === 'owe').map((l) => l.outstanding))
  const owed = sumAmounts(list.filter((l) => l.direction === 'owed').map((l) => l.outstanding))

  return (
    <section className="stack stack--tight" aria-labelledby="loans-title">
      <div className="section-title">
        <h2 id="loans-title">{t('loans.title')}</h2>
        <Link to="/planificar/prestamos/nuevo" aria-label={t('loans.newTitle')}>
          {t('loans.new')}
        </Link>
      </div>
      {loans.isSuccess && list.length === 0 && <p className="card muted">{t('loans.empty')}</p>}
      {list.length > 0 && (
        <p className="muted small">
          {t('loans.totalOwe', { amount: formatAmount(owe) })}
          {owed !== '0.00' && ` · ${t('loans.totalOwed', { amount: formatAmount(owed) })}`}
        </p>
      )}
      {list.map((loan) => {
        const repaid =
          Number(loan.principal) > 0
            ? (Number(loan.principal_paid) / Number(loan.principal)) * 100
            : 0
        return (
          <Link
            key={loan.id}
            className="card card--link goal"
            to={`/planificar/prestamos/${loan.id}`}
          >
            <div className="goal__head">
              <span className="goal__name">{loan.name}</span>
              <span className="goal__percent">
                <Money value={loan.outstanding} />
              </span>
            </div>
            <Meter value={repaid} label={t('loans.repaidOf', { name: loan.name })} />
            <p className="small goal__status">
              {loan.next_payment
                ? t('loans.nextLine', {
                    amount: formatAmount(loan.next_payment.amount),
                    date: formatDate(loan.next_payment.date),
                  })
                : t('loans.finished')}
            </p>
          </Link>
        )
      })}
    </section>
  )
}
