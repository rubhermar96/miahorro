import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useSession } from '../api/auth'
import { ACCOUNT_KINDS, type Account, useAccounts } from '../api/finance'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { ServerStatusLine } from '../components/ServerStatusLine'
import { sumAmounts } from '../lib/amount'
import { formatAmount, formatDate, todayIso } from '../lib/format'

const MATURITY_WINDOW_DAYS = 90

/** Totals per currency; the main currency first. */
function totalsByCurrency(accounts: Account[], main: string): [string, string][] {
  const byCurrency = new Map<string, string[]>()
  for (const account of accounts) {
    byCurrency.set(account.currency, [...(byCurrency.get(account.currency) ?? []), account.balance])
  }
  return [...byCurrency.entries()]
    .map(([currency, balances]): [string, string] => [currency, sumAmounts(balances)])
    .sort(([a], [b]) => (a === main ? -1 : b === main ? 1 : a.localeCompare(b)))
}

function upcomingMaturities(accounts: Account[]): Account[] {
  const today = todayIso()
  const limit = new Date(`${today}T12:00:00`)
  limit.setDate(limit.getDate() + MATURITY_WINDOW_DAYS)
  const last = limit.toISOString().slice(0, 10)
  return accounts
    .filter((a) => a.maturity_date && a.maturity_date >= today && a.maturity_date <= last)
    .sort((a, b) => (a.maturity_date ?? '').localeCompare(b.maturity_date ?? ''))
}

export function HomePage() {
  const { t } = useTranslation()
  const { data: session } = useSession()
  const accounts = useAccounts()
  const mainCurrency = session?.user.preferences.currency ?? 'EUR'

  const list = accounts.data ?? []
  const [main, ...others] = totalsByCurrency(list, mainCurrency)
  const maturities = upcomingMaturities(list)

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

        {list.length > 0 && main && (
          <section className="card" aria-labelledby="total-title">
            <h2 id="total-title">{t('home.totalTitle')}</h2>
            <p className="total">
              <Money value={main[1]} currency={main[0]} />
            </p>
            {others.length > 0 && (
              <p className="muted small">
                {t('home.otherCurrencies', {
                  amounts: others
                    .map(([currency, total]) => formatAmount(total, currency))
                    .join(', '),
                })}
              </p>
            )}
            <p className="muted small">{t('home.totalHelp')}</p>
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
                          <Money value={account.balance} currency={account.currency} />
                        </Link>
                      </li>
                    ))}
                </ul>
              </section>
            ))}
          </section>
        )}

        <p className="footnote">
          <ServerStatusLine />
        </p>
      </div>
    </>
  )
}
