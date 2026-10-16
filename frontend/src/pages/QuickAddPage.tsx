import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import {
  type Account,
  financeApi,
  refreshFinance,
  useAccounts,
  useCategories,
} from '../api/finance'
import { CategoryPicker } from '../components/CategoryPicker'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'
import { formatAmount, todayIso } from '../lib/format'
import { splitTags } from '../lib/tags'

type Mode = 'expense' | 'income' | 'transfer'
const MODES: Mode[] = ['expense', 'income', 'transfer']
const LAST_ACCOUNT_KEY = 'miahorro.lastAccount'

function rememberedAccount(accounts: Account[]): string {
  let saved: string | null = null
  try {
    saved = localStorage.getItem(LAST_ACCOUNT_KEY)
  } catch {
    // Storage unavailable: fall back to the first account.
  }
  return accounts.find((a) => a.id === saved)?.id ?? accounts[0]?.id ?? ''
}

function rememberAccount(id: string) {
  try {
    localStorage.setItem(LAST_ACCOUNT_KEY, id)
  } catch {
    // Not important: next time the first account is preselected.
  }
}

/**
 * Quick entry (RF-MOV-01): type the amount, tap a category, tap Guardar. The last account
 * used and today's date are already chosen; everything else is optional.
 */
export function QuickAddPage() {
  const { t } = useTranslation()
  const accounts = useAccounts()
  const categories = useCategories()

  if (!accounts.data || !categories.data) {
    return <PageHeader title={t('add.title')} />
  }
  if (accounts.data.length === 0) {
    return (
      <>
        <PageHeader title={t('add.title')} />
        <section className="card stack">
          <p>{t('add.needAccount')}</p>
          <Link className="button" to="/cuentas/nueva">
            {t('home.addAccount')}
          </Link>
        </section>
      </>
    )
  }
  return <QuickAddForm accounts={accounts.data} categories={categories.data} />
}

function QuickAddForm({
  accounts,
  categories,
}: {
  accounts: Account[]
  categories: NonNullable<ReturnType<typeof useCategories>['data']>
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<Mode>('expense')
  const [amountText, setAmountText] = useState('')
  const [accountId, setAccountId] = useState(() => rememberedAccount(accounts))
  const [toAccountId, setToAccountId] = useState(
    () => accounts.find((a) => a.id !== rememberedAccount(accounts))?.id ?? '',
  )
  const [categoryId, setCategoryId] = useState<string | null>(null)
  const [date, setDate] = useState(todayIso)
  const [description, setDescription] = useState('')
  const [note, setNote] = useState('')
  const [tagsText, setTagsText] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const currency = accounts.find((a) => a.id === accountId)?.currency ?? 'EUR'

  const chooseMode = (next: Mode) => {
    setMode(next)
    setCategoryId(null)
    setMessage(null)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setMessage(null)
    setError(null)
    const amount = parseAmountInput(amountText)
    if (!amount) {
      setError(t('add.invalidAmount'))
      return
    }
    setBusy(true)
    try {
      const details = { date, description, note: note || null, tags: splitTags(tagsText) }
      if (mode === 'transfer') {
        await financeApi.createTransfer({
          ...details,
          from_account_id: accountId,
          to_account_id: toAccountId,
          amount,
        })
        setMessage(t('add.savedTransfer', { amount: formatAmount(amount, currency) }))
      } else {
        await financeApi.createTransaction({
          ...details,
          account_id: accountId,
          kind: mode,
          amount,
          category_id: categoryId,
        })
        setMessage(
          t('add.saved', {
            kind: t(`transactions.kinds.${mode}`),
            amount: formatAmount(amount, currency),
          }),
        )
      }
      rememberAccount(accountId)
      await refreshFinance(queryClient)
      setAmountText('')
      setCategoryId(null)
      setDescription('')
      setNote('')
      setTagsText('')
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  const accountOptions = accounts.map((account) => (
    <option key={account.id} value={account.id}>
      {account.name}
    </option>
  ))

  return (
    <>
      <PageHeader title={t('add.title')} />
      <form className="stack" onSubmit={(event) => void submit(event)}>
        <div className="segmented" role="radiogroup" aria-label={t('add.title')}>
          {MODES.map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={mode === option}
              className="segmented__option"
              onClick={() => chooseMode(option)}
            >
              {t(`transactions.kinds.${option}`)}
            </button>
          ))}
        </div>

        <div className="field amount-field">
          <label htmlFor="quick-amount">{t('add.amount')}</label>
          <span className="amount-input">
            <input
              id="quick-amount"
              inputMode="decimal"
              enterKeyHint="done"
              autoComplete="off"
              placeholder="0,00"
              autoFocus
              value={amountText}
              onChange={(event) => setAmountText(event.target.value)}
            />
            <span aria-hidden="true">{currency === 'EUR' ? '€' : currency}</span>
          </span>
        </div>

        {mode === 'transfer' ? (
          accounts.length < 2 ? (
            <p className="notice">{t('add.needTwoAccounts')}</p>
          ) : (
            <div className="grid-2">
              <label className="field">
                <span>{t('add.fromAccount')}</span>
                <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
                  {accountOptions}
                </select>
              </label>
              <label className="field">
                <span>{t('add.toAccount')}</span>
                <select
                  value={toAccountId}
                  onChange={(event) => setToAccountId(event.target.value)}
                >
                  {accountOptions}
                </select>
              </label>
            </div>
          )
        ) : (
          <>
            <CategoryPicker
              categories={categories}
              kind={mode}
              value={categoryId}
              onChange={setCategoryId}
            />
            <label className="field">
              <span>{t('add.account')}</span>
              <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
                {accountOptions}
              </select>
            </label>
          </>
        )}

        <div className="grid-2">
          <label className="field">
            <span>{t('add.date')}</span>
            <input
              type="date"
              required
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          <label className="field">
            <span>{t('add.description')}</span>
            <input
              maxLength={140}
              placeholder={t('add.descriptionPlaceholder')}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
        </div>

        <details className="card">
          <summary>{t('add.details')}</summary>
          <div className="stack stack--tight details-body">
            <label className="field">
              <span>{t('add.note')}</span>
              <textarea rows={2} value={note} onChange={(event) => setNote(event.target.value)} />
            </label>
            <label className="field">
              <span>{t('add.tags')}</span>
              <input value={tagsText} onChange={(event) => setTagsText(event.target.value)} />
              <small className="muted">{t('add.tagsHelp')}</small>
            </label>
          </div>
        </details>

        <ErrorMessage message={error} />
        <button
          type="submit"
          className="button button--large"
          disabled={busy || (mode === 'transfer' && accounts.length < 2)}
        >
          {t('add.save')}
        </button>
        <p className="saved" role="status">
          {message}
        </p>
      </form>
    </>
  )
}
