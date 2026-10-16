import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import {
  captureApi,
  captureKeys,
  type RecurringInput,
  type RecurringItem,
  useRecurring,
} from '../api/capture'
import {
  type Account,
  type Category,
  type Transaction,
  useAccounts,
  useCategories,
  useTransaction,
} from '../api/finance'
import { importApi } from '../api/imports'
import { CategorySelect } from '../components/CategorySelect'
import { ErrorMessage } from '../components/ErrorMessage'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { amountToInput, parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'
import { formatDate, todayIso } from '../lib/format'

const FREQUENCIES = ['weekly', 'monthly', 'quarterly', 'semiannual', 'yearly'] as const

/** Same day, one period later (the server keeps the exact rules; this only proposes a date). */
function nextAfter(date: string, frequency: RecurringInput['frequency']): string {
  const today = todayIso()
  let next = new Date(`${date}T12:00:00`)
  const step = (d: Date) => {
    const copy = new Date(d)
    if (frequency === 'weekly') {
      copy.setDate(copy.getDate() + 7)
    } else {
      const months = { monthly: 1, quarterly: 3, semiannual: 6, yearly: 12 }[frequency ?? 'monthly']
      copy.setMonth(copy.getMonth() + months)
    }
    return copy
  }
  do {
    next = step(next)
  } while (next.toISOString().slice(0, 10) <= today)
  return next.toISOString().slice(0, 10)
}

/** Recurring income and expenses (RF-MOV-06). */
export function RecurringPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const from = params.get('desde')
  const items = useRecurring()
  const accounts = useAccounts()
  const categories = useCategories()
  const source = useTransaction(from ?? '')
  const [editing, setEditing] = useState<RecurringItem | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: captureKeys.recurring }),
      queryClient.invalidateQueries({ queryKey: captureKeys.inbox }),
    ])

  const remove = async (item: RecurringItem) => {
    if (!window.confirm(t('recurring.confirmDelete', { name: item.name }))) {
      return
    }
    await captureApi.deleteRecurring(item.id)
    await refresh()
  }

  const ready = accounts.data && categories.data && (!from || source.data)
  const accountName = (id: string) => accounts.data?.find((a) => a.id === id)?.name ?? ''

  return (
    <>
      <PageHeader title={t('recurring.title')} back="/mas" />
      <div className="stack">
        <p className="muted small">{t('recurring.intro')}</p>
        {ready && (
          <RecurringForm
            key={editing?.id ?? from ?? 'new'}
            item={editing}
            source={from ? source.data : undefined}
            accounts={accounts.data ?? []}
            categories={categories.data ?? []}
            onSaved={async (text) => {
              setEditing(null)
              setMessage(text)
              await refresh()
            }}
            onCancel={editing ? () => setEditing(null) : undefined}
          />
        )}
        {message && (
          <p className="notice" role="status">
            {message}
          </p>
        )}
        {items.isSuccess && items.data.length === 0 && (
          <p className="card muted">{t('recurring.empty')}</p>
        )}
        {(items.data?.length ?? 0) > 0 && (
          <ul className="list card card--flush">
            {items.data?.map((item) => (
              <li key={item.id} className="row">
                <span className="row__text">
                  <span className="row__title">{item.name}</span>
                  <small className="muted">
                    {[
                      t(`recurring.frequencies.${item.frequency}`),
                      t('recurring.next', { date: formatDate(item.next_date) }),
                      accountName(item.account_id),
                    ].join(' · ')}
                  </small>
                </span>
                <Money value={item.kind === 'expense' ? `-${item.amount}` : item.amount} signed />
                <span className="row__actions">
                  <button
                    type="button"
                    className="button button--ghost"
                    onClick={() => setEditing(item)}
                  >
                    {t('recurring.edit')}
                  </button>
                  <button
                    type="button"
                    className="button button--ghost button--danger"
                    aria-label={t('recurring.delete', { name: item.name })}
                    onClick={() => void remove(item)}
                  >
                    ✕
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}

function RecurringForm({
  item,
  source,
  accounts,
  categories,
  onSaved,
  onCancel,
}: {
  item: RecurringItem | null
  source?: Transaction
  accounts: Account[]
  categories: Category[]
  onSaved: (message: string) => Promise<void>
  onCancel?: () => void
}) {
  const { t } = useTranslation()
  const sourceKind = source?.kind === 'income' ? 'income' : 'expense'
  const [name, setName] = useState(item?.name ?? source?.description ?? '')
  const [accountId, setAccountId] = useState(
    item?.account_id ?? source?.account_id ?? accounts[0]?.id ?? '',
  )
  const [kind, setKind] = useState<RecurringInput['kind']>(item?.kind ?? sourceKind)
  const [amountText, setAmountText] = useState(
    item ? amountToInput(item.amount) : source ? amountToInput(source.amount) : '',
  )
  const [categoryId, setCategoryId] = useState(item?.category_id ?? source?.category_id ?? '')
  const [matchText, setMatchText] = useState(item?.match_text ?? '')
  const [frequency, setFrequency] = useState<RecurringInput['frequency']>(
    item?.frequency ?? 'monthly',
  )
  const [nextDate, setNextDate] = useState(
    item?.next_date ?? (source ? nextAfter(source.date, 'monthly') : todayIso()),
  )
  const [error, setError] = useState<string | null>(null)

  // From a movement: propose the text that identifies it, as rules do.
  useEffect(() => {
    if (!source || item) {
      return
    }
    importApi
      .ruleSuggestion(source.id)
      .then((s) => setMatchText((current) => current || s.match_text))
      .catch(() => setMatchText((current) => current || source.description.slice(0, 60)))
  }, [source, item])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const amount = parseAmountInput(amountText)
    if (!amount) {
      setError(t('add.invalidAmount'))
      return
    }
    const body: RecurringInput = {
      name,
      account_id: accountId,
      kind,
      amount,
      tolerance: item?.tolerance ?? '10',
      category_id: categoryId || null,
      match_text: matchText,
      frequency,
      next_date: nextDate,
    }
    try {
      if (item) {
        await captureApi.updateRecurring(item.id, body)
      } else {
        await captureApi.createRecurring(body)
      }
      await onSaved(t('recurring.saved', { name }))
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  return (
    <form className="card stack stack--tight" onSubmit={(event) => void submit(event)}>
      <h2>{item ? t('recurring.editTitle') : t('recurring.newTitle')}</h2>
      <div className="segmented segmented--two" role="radiogroup" aria-label={t('accounts.kind')}>
        {(['expense', 'income'] as const).map((option) => (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={kind === option}
            className="segmented__option"
            onClick={() => {
              setKind(option)
              setCategoryId('')
            }}
          >
            {t(`transactions.kinds.${option}`)}
          </button>
        ))}
      </div>
      <label className="field">
        <span>{t('recurring.name')}</span>
        <input required maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <div className="grid-2">
        <label className="field">
          <span>{t('recurring.amount')}</span>
          <input
            inputMode="decimal"
            required
            value={amountText}
            onChange={(e) => setAmountText(e.target.value)}
          />
        </label>
        <label className="field">
          <span>{t('recurring.frequency')}</span>
          <select
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as RecurringInput['frequency'])}
          >
            {FREQUENCIES.map((option) => (
              <option key={option} value={option}>
                {t(`recurring.frequencies.${option}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="grid-2">
        <label className="field">
          <span>{t('recurring.nextDate')}</span>
          <input
            type="date"
            required
            value={nextDate}
            onChange={(e) => setNextDate(e.target.value)}
          />
        </label>
        <label className="field">
          <span>{t('add.account')}</span>
          <select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="field">
        <span>{t('recurring.matchText')}</span>
        <input
          required
          minLength={2}
          maxLength={60}
          value={matchText}
          onChange={(e) => setMatchText(e.target.value)}
        />
        <small className="muted">{t('recurring.matchHelp')}</small>
      </label>
      <div className="field">
        <label htmlFor="recurring-category">{t('add.category')}</label>
        <CategorySelect
          id="recurring-category"
          categories={categories}
          kinds={[kind]}
          value={categoryId}
          onChange={setCategoryId}
          emptyLabel={t('transactions.noCategory')}
        />
      </div>
      <ErrorMessage message={error} />
      <button type="submit" className="button">
        {item ? t('add.save') : t('recurring.create')}
      </button>
      {onCancel && (
        <button type="button" className="button button--ghost" onClick={onCancel}>
          {t('bulk.cancel')}
        </button>
      )}
    </form>
  )
}
