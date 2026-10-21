import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useSession } from '../api/auth'
import { useInbox, useUpcoming } from '../api/capture'
import { ACCOUNT_KINDS, type Account, useAccounts } from '../api/finance'
import { useInvestments } from '../api/investments'
import { useLoans } from '../api/loans'
import { useDashboard } from '../api/reports'
import { BudgetSummaryCard } from '../components/BudgetSummaryCard'
import { GoalsSummary } from '../components/GoalsSummary'
import { InvestmentRow } from '../components/InvestmentRow'
import { Money } from '../components/Money'
import { NetWorthCard } from '../components/NetWorthCard'
import { PageHeader } from '../components/PageHeader'
import { ServerStatusLine } from '../components/ServerStatusLine'
import { negateAmount } from '../lib/amount'
import { formatAmount, formatDate, formatRate, todayIso } from '../lib/format'

const MATURITY_WINDOW_DAYS = 90
const UPCOMING_DAYS = 30
const UPCOMING_SHOWN = 6

function daysFromToday(days: number): string {
  const date = new Date(`${todayIso()}T12:00:00`)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

function upcomingMaturities(accounts: Account[]): Account[] {
  const today = todayIso()
  const last = daysFromToday(MATURITY_WINDOW_DAYS)
  return accounts
    .filter((a) => a.maturity_date && a.maturity_date >= today && a.maturity_date <= last)
    .sort((a, b) => (a.maturity_date ?? '').localeCompare(b.maturity_date ?? ''))
}

type Coming = { key: string; name: string; date: string; amount: string; to: string }

/** The dashboard (RF-INF-01): net worth, money available, this month, budget, goals, what is
 * coming up, and the accounts and investments. */
export function HomePage() {
  const { t } = useTranslation()
  const { data: session } = useSession()
  const accounts = useAccounts()
  const inbox = useInbox()
  const upcoming = useUpcoming(UPCOMING_DAYS)
  const loans = useLoans()
  const dashboard = useDashboard()
  const investments = useInvestments()

  const list = accounts.data ?? []
  // Only what is still held: an emptied fund stays in the portfolio page, not here.
  const held = (investments.data ?? []).filter((investment) => investment.units !== '0')
  const hasInvestments = (investments.data?.length ?? 0) > 0
  const maturities = upcomingMaturities(list)
  const toReview = (inbox.data?.unconfirmed.length ?? 0) + (inbox.data?.overdue.length ?? 0)
  const until = daysFromToday(UPCOMING_DAYS)
  const coming: Coming[] = [
    ...(upcoming.data ?? [])
      .filter((item) => !item.overdue)
      .map((item) => ({
        key: `${item.item_id}-${item.date}`,
        name: item.name,
        date: item.date,
        amount: item.amount,
        to: '/mas/recurrentes',
      })),
    ...(loans.data ?? []).flatMap((loan) => {
      const next = loan.next_payment
      if (!next || next.date > until) {
        return []
      }
      return [
        {
          key: `loan-${loan.id}`,
          name: loan.name,
          date: next.date,
          amount: loan.direction === 'owed' ? next.amount : negateAmount(next.amount),
          to: `/planificar/prestamos/${loan.id}`,
        },
      ]
    }),
  ]
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, UPCOMING_SHOWN)
  const board = dashboard.data
  const month = board?.month

  return (
    <>
      <PageHeader title={t('home.title')} />
      <div className="stack">
        {session && (
          <p className="greeting">{t('home.greeting', { name: session.user.display_name })}</p>
        )}

        {accounts.isSuccess && list.length === 0 && (
          <section className="card stack">
            <h2>{t('home.noAccountsTitle')}</h2>
            <p className="muted">{t('home.noAccounts')}</p>
            <Link className="button" to="/cuentas/nueva">
              {t('home.addAccount')}
            </Link>
          </section>
        )}

        {list.length > 0 && board && <NetWorthCard dashboard={board} />}

        {list.length > 0 && board && month && (
          <section className="kpis" aria-label={t('dashboard.kpis')}>
            <div className="card kpi">
              <span className="muted small">{t('dashboard.available')}</span>
              <span className="kpi__value">
                <Money value={board.available} />
              </span>
              {board.reserved !== '0.00' && (
                <small className="muted">
                  {t('dashboard.reserved', { amount: formatAmount(board.reserved) })}
                </small>
              )}
            </div>
            <Link className="card card--link kpi" to="/informes?vista=flujo">
              <span className="muted small">{t('dashboard.savedThisMonth')}</span>
              <span className="kpi__value">
                <Money value={month.saved} signed />
              </span>
              <small className="muted">
                {t('dashboard.monthLine', {
                  income: formatAmount(month.income),
                  expenses: formatAmount(negateAmount(month.expenses)),
                })}
                {month.rate !== null &&
                  month.rate !== undefined &&
                  ` · ${t('dashboard.rate', { rate: formatRate(String(month.rate)) })}`}
              </small>
            </Link>
          </section>
        )}

        {toReview > 0 && (
          <Link className="card card--link notice" to="/revisar">
            {t('home.toReview', { count: toReview })}
          </Link>
        )}

        <BudgetSummaryCard onlyIfSet />
        <GoalsSummary />

        {coming.length > 0 && (
          <section className="stack stack--tight" aria-labelledby="upcoming-title">
            <div className="section-title">
              <h2 id="upcoming-title">{t('home.upcomingTitle')}</h2>
              <Link to="/mas/recurrentes">{t('home.upcomingAll')}</Link>
            </div>
            <ul className="list card card--flush">
              {coming.map((item) => (
                <li key={item.key}>
                  <Link className="row" to={item.to}>
                    <span className="row__text">
                      <span className="row__title">{item.name}</span>
                      <small className="muted">{formatDate(item.date)}</small>
                    </span>
                    <Money value={item.amount} signed />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        {maturities.length > 0 && (
          <section className="card stack stack--tight">
            <h2>{t('home.maturitiesTitle')}</h2>
            {maturities.map((account) => (
              <Link key={account.id} to={`/cuentas/${account.id}`}>
                {t('home.maturity', {
                  name: account.name,
                  date: formatDate(account.maturity_date ?? ''),
                })}
              </Link>
            ))}
          </section>
        )}

        {list.length > 0 && (
          <section className="stack" aria-labelledby="accounts-title">
            <div className="section-title">
              <h2 id="accounts-title">{t('home.accountsTitle')}</h2>
              <Link to="/cuentas/nueva">{t('home.addAccount')}</Link>
            </div>
            {ACCOUNT_KINDS.filter((kind) => list.some((a) => a.kind === kind)).map((kind) => (
              <section key={kind} aria-label={t(`accounts.kindsPlural.${kind}`)}>
                <h3 className="day">{t(`accounts.kindsPlural.${kind}`)}</h3>
                <ul className="list card card--flush">
                  {list
                    .filter((account) => account.kind === kind)
                    .map((account) => (
                      <li key={account.id}>
                        <Link className="row" to={`/cuentas/${account.id}`}>
                          <span className="row__text">
                            <span className="row__title">{account.name}</span>
                            {account.institution && (
                              <small className="muted">{account.institution}</small>
                            )}
                          </span>
                          <span className="row__amounts">
                            <Money value={account.balance} currency={account.currency} />
                            {account.reserved !== '0.00' && (
                              <small className="muted">
                                {t('accounts.availableShort', {
                                  amount: formatAmount(account.available, account.currency),
                                })}
                              </small>
                            )}
                          </span>
                        </Link>
                      </li>
                    ))}
                </ul>
              </section>
            ))}
          </section>
        )}

        {list.length > 0 && (
          <section className="stack stack--tight" aria-labelledby="home-investments-title">
            <div className="section-title">
              <h2 id="home-investments-title">{t('inv.title')}</h2>
              <Link to={hasInvestments ? '/inversiones' : '/inversiones/nueva'}>
                {hasInvestments ? t('home.portfolio') : t('inv.new')}
              </Link>
            </div>
            {investments.isSuccess && !hasInvestments && (
              <p className="card muted small">{t('home.noInvestments')}</p>
            )}
            {hasInvestments && (
              <ul className="list card card--flush">
                {held.slice(0, 5).map((investment) => (
                  <li key={investment.id}>
                    <InvestmentRow investment={investment} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        <p className="footnote">
          <ServerStatusLine />
        </p>
      </div>
    </>
  )
}
