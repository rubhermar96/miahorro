import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import {
  type TransactionFilters,
  useAccounts,
  useCategories,
  useTransactions,
} from '../api/finance'
import { CategorySelect } from '../components/CategorySelect'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { TransactionList } from '../components/TransactionList'

// Filters live in the URL (in Spanish), so a filtered list can be bookmarked or shared.
const PARAMS: Record<keyof TransactionFilters, string> = {
  account_id: 'cuenta',
  category_id: 'categoria',
  kind: 'tipo',
  tag: 'etiqueta',
  q: 'texto',
  date_from: 'desde',
  date_to: 'hasta',
}
const KINDS = ['expense', 'income', 'transfer', 'adjustment'] as const

function readFilters(params: URLSearchParams): TransactionFilters {
  const filters: Record<string, string> = {}
  for (const [key, param] of Object.entries(PARAMS)) {
    const value = params.get(param)
    if (value) {
      filters[key] = value
    }
  }
  return filters as TransactionFilters
}

/** All transactions with search and filters (RF-MOV-15). */
export function TransactionsPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const filters = readFilters(params)
  const accounts = useAccounts(true)
  const categories = useCategories(true)
  const transactions = useTransactions(filters)
  const [search, setSearch] = useState(filters.q ?? '')

  const setFilter = (key: keyof TransactionFilters, value: string) => {
    const next = new URLSearchParams(params)
    if (value) {
      next.set(PARAMS[key], value)
    } else {
      next.delete(PARAMS[key])
    }
    setParams(next, { replace: true })
  }

  const submitSearch = (event: FormEvent) => {
    event.preventDefault()
    setFilter('q', search.trim())
  }

  const pages = transactions.data?.pages ?? []
  const items = pages.flatMap((page) => page.items)
  const summary = pages[0]
  const filtering = Object.keys(filters).length > 0
  const activeFilters = Object.keys(filters).filter((key) => key !== 'q').length

  return (
    <>
      <PageHeader title={t('transactions.title')} />
      <div className="stack">
        <form role="search" className="search" onSubmit={submitSearch}>
          <input
            type="search"
            enterKeyHint="search"
            aria-label={t('transactions.search')}
            placeholder={t('transactions.searchPlaceholder')}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <button type="submit" className="button button--secondary">
            {t('transactions.search')}
          </button>
        </form>

        <details className="card" open={activeFilters > 0}>
          <summary>
            {t('transactions.filters')}
            {activeFilters > 0 && ` (${activeFilters})`}
          </summary>
          <div className="stack stack--tight details-body">
            <label className="field">
              <span>{t('add.account')}</span>
              <select
                value={filters.account_id ?? ''}
                onChange={(event) => setFilter('account_id', event.target.value)}
              >
                <option value="">{t('transactions.allAccounts')}</option>
                {accounts.data?.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="field">
              <label htmlFor="filter-category">{t('add.category')}</label>
              <CategorySelect
                id="filter-category"
                categories={categories.data ?? []}
                value={filters.category_id ?? ''}
                onChange={(id) => setFilter('category_id', id)}
                emptyLabel={t('transactions.allCategories')}
              />
            </div>
            <label className="field">
              <span>{t('accounts.kind')}</span>
              <select
                value={filters.kind ?? ''}
                onChange={(event) => setFilter('kind', event.target.value)}
              >
                <option value="">{t('transactions.allKinds')}</option>
                {KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {t(`transactions.kinds.${kind}`)}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid-2">
              <label className="field">
                <span>{t('transactions.from')}</span>
                <input
                  type="date"
                  value={filters.date_from ?? ''}
                  onChange={(event) => setFilter('date_from', event.target.value)}
                />
              </label>
              <label className="field">
                <span>{t('transactions.to')}</span>
                <input
                  type="date"
                  value={filters.date_to ?? ''}
                  onChange={(event) => setFilter('date_to', event.target.value)}
                />
              </label>
            </div>
            {filters.tag && (
              <p>
                #{filters.tag}{' '}
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => setFilter('tag', '')}
                >
                  ✕
                </button>
              </p>
            )}
            {filtering && (
              <button
                type="button"
                className="button button--ghost"
                onClick={() => {
                  setSearch('')
                  setParams(new URLSearchParams(), { replace: true })
                }}
              >
                {t('transactions.clearFilters')}
              </button>
            )}
          </div>
        </details>

        {summary && summary.total > 0 && (
          <section
            className="summary"
            aria-label={t('transactions.count', { count: summary.total })}
          >
            <span>{t('transactions.count', { count: summary.total })}</span>
            <span>
              {t('transactions.income')} <Money value={summary.income} signed />
            </span>
            <span>
              {t('transactions.expenses')} <Money value={summary.expenses} signed />
            </span>
          </section>
        )}

        {transactions.isSuccess && items.length === 0 && (
          <p className="card muted">
            {filtering ? t('transactions.empty') : t('transactions.emptyStart')}
          </p>
        )}

        <TransactionList
          transactions={items}
          accounts={accounts.data ?? []}
          categories={categories.data ?? []}
          showAccount={!filters.account_id}
        />

        {transactions.hasNextPage && (
          <button
            type="button"
            className="button button--secondary"
            disabled={transactions.isFetchingNextPage}
            onClick={() => void transactions.fetchNextPage()}
          >
            {t('transactions.loadMore')}
          </button>
        )}
      </div>
    </>
  )
}
