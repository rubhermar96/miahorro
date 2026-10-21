import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import {
  type Account,
  type Category,
  categoryIcon,
  categoryLabel,
  type Transaction,
} from '../api/finance'
import { formatAmount, formatDay } from '../lib/format'
import { Money } from './Money'

export type Selection = { selected: Set<string>; onToggle: (id: string) => void }

/** Transactions grouped by day, newest first, each one a link to edit it, or a checkbox to
 * pick it when `selection` is given (bulk edit). */
export function TransactionList({
  transactions,
  accounts,
  categories,
  showAccount = true,
  showBalance = false,
  selection,
}: {
  transactions: Transaction[]
  accounts: Account[]
  categories: Category[]
  showAccount?: boolean
  /** The account's balance after each movement; only meaningful for a single account. */
  showBalance?: boolean
  selection?: Selection
}) {
  const { t } = useTranslation()
  const days: { date: string; items: Transaction[] }[] = []
  for (const transaction of transactions) {
    const last = days.at(-1)
    if (last?.date === transaction.date) {
      last.items.push(transaction)
    } else {
      days.push({ date: transaction.date, items: [transaction] })
    }
  }
  const accountById = new Map(accounts.map((account) => [account.id, account]))

  return (
    <div className="stack">
      {days.map((day) => (
        <section key={day.date} aria-label={formatDay(day.date)}>
          <h3 className="day">{formatDay(day.date)}</h3>
          <ul className="list card card--flush">
            {day.items.map((transaction) => {
              const account = accountById.get(transaction.account_id)
              const category = categories.find((c) => c.id === transaction.category_id)
              const parent = categories.find((c) => c.id === category?.parent_id)
              const isMove =
                transaction.kind === 'transfer' ||
                transaction.kind === 'adjustment' ||
                transaction.kind === 'investment'
              const kindLabel = t(`transactions.kinds.${transaction.kind}`)
              // Without a concept, the category is the title and its main category the detail.
              const title = transaction.description || category?.name || kindLabel
              const categoryDetail = transaction.description
                ? categoryLabel(categories, transaction.category_id)
                : (parent?.name ?? null)
              const details = [
                isMove
                  ? kindLabel
                  : (categoryDetail ?? (category ? null : t('transactions.noCategory'))),
                showAccount ? account?.name : null,
              ].filter(Boolean)
              const content = (
                <>
                  <span className="row__icon" aria-hidden="true">
                    {transaction.kind === 'transfer'
                      ? '⇄'
                      : transaction.kind === 'adjustment'
                        ? '≈'
                        : transaction.kind === 'investment'
                          ? '📈'
                          : categoryIcon(categories, transaction.category_id)}
                  </span>
                  <span className="row__text">
                    <span className="row__title">{title}</span>
                    <small className="muted">
                      {transaction.pending && (
                        <span className="tag tag--pending">{t('transactions.pending')}</span>
                      )}
                      {details.join(' · ')}
                    </small>
                  </span>
                  <span className="row__amounts">
                    <Money value={transaction.amount} currency={account?.currency} signed />
                    {showBalance && transaction.balance_after != null && (
                      <small className="muted">
                        {t('transactions.balanceAfter', {
                          amount: formatAmount(transaction.balance_after, account?.currency),
                        })}
                      </small>
                    )}
                  </span>
                </>
              )
              return (
                <li key={transaction.id}>
                  {selection ? (
                    <label className="row">
                      <input
                        type="checkbox"
                        className="row__check"
                        checked={selection.selected.has(transaction.id)}
                        onChange={() => selection.onToggle(transaction.id)}
                      />
                      {content}
                    </label>
                  ) : (
                    <Link className="row" to={`/movimientos/${transaction.id}`}>
                      {content}
                    </Link>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </div>
  )
}
