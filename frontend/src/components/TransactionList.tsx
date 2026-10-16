import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import {
  type Account,
  type Category,
  categoryIcon,
  categoryLabel,
  type Transaction,
} from '../api/finance'
import { formatDay } from '../lib/format'
import { Money } from './Money'

/** Transactions grouped by day, newest first, each one a link to edit it. */
export function TransactionList({
  transactions,
  accounts,
  categories,
  showAccount = true,
}: {
  transactions: Transaction[]
  accounts: Account[]
  categories: Category[]
  showAccount?: boolean
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
              const isMove = transaction.kind === 'transfer' || transaction.kind === 'adjustment'
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
              return (
                <li key={transaction.id}>
                  <Link className="row" to={`/movimientos/${transaction.id}`}>
                    <span className="row__icon" aria-hidden="true">
                      {transaction.kind === 'transfer'
                        ? '⇄'
                        : transaction.kind === 'adjustment'
                          ? '≈'
                          : categoryIcon(categories, transaction.category_id)}
                    </span>
                    <span className="row__text">
                      <span className="row__title">{title}</span>
                      <small className="muted">{details.join(' · ')}</small>
                    </span>
                    <Money value={transaction.amount} currency={account?.currency} signed />
                  </Link>
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </div>
  )
}
