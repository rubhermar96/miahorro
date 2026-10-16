import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useAccounts } from '../api/finance'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'

export function ArchivedAccountsPage() {
  const { t } = useTranslation()
  const accounts = useAccounts(true)
  const archived = (accounts.data ?? []).filter((account) => account.archived)

  return (
    <>
      <PageHeader title={t('accounts.archivedTitle')} back="/mas" />
      {accounts.isSuccess && archived.length === 0 ? (
        <p className="card muted">—</p>
      ) : (
        <ul className="list card card--flush">
          {archived.map((account) => (
            <li key={account.id}>
              <Link className="row" to={`/cuentas/${account.id}`}>
                <span className="row__text">
                  <span className="row__title">{account.name}</span>
                  <small className="muted">{t(`accounts.kinds.${account.kind}`)}</small>
                </span>
                <Money value={account.balance} currency={account.currency} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
