import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import {
  type Account,
  type Category,
  categoryLabel,
  financeApi,
  refreshFinance,
  type Transaction,
  useAccounts,
  useCategories,
  useTransaction,
} from '../api/finance'
import { importApi } from '../api/imports'
import { CategorySelect } from '../components/CategorySelect'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { amountToInput, parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'
import { splitTags } from '../lib/tags'

/** Edit or delete one transaction. Transfers and adjustments only change date, amount and text. */
export function TransactionPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const transaction = useTransaction(id)
  const accounts = useAccounts(true)
  const categories = useCategories(true)

  if (!transaction.data || !accounts.data || !categories.data) {
    return <PageHeader title={t('transactions.editTitle')} back="/movimientos" />
  }
  return (
    <TransactionForm
      key={transaction.data.id}
      transaction={transaction.data}
      accounts={accounts.data}
      categories={categories.data}
    />
  )
}

function TransactionForm({
  transaction,
  accounts,
  categories,
}: {
  transaction: Transaction
  accounts: Account[]
  categories: Category[]
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isEntry = transaction.kind === 'expense' || transaction.kind === 'income'
  const isAdjustment = transaction.kind === 'adjustment'
  const [kind, setKind] = useState(transaction.kind)
  const [amountText, setAmountText] = useState(amountToInput(transaction.amount, isAdjustment))
  const [accountId, setAccountId] = useState(transaction.account_id)
  const [categoryId, setCategoryId] = useState(transaction.category_id ?? '')
  const [date, setDate] = useState(transaction.date)
  const [description, setDescription] = useState(transaction.description)
  const [note, setNote] = useState(transaction.note ?? '')
  const [tagsText, setTagsText] = useState(transaction.tags.join(', '))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [suggestion, setSuggestion] = useState<{ match_text: string; matches: number } | null>(null)

  const done = async () => {
    await refreshFinance(queryClient)
    void navigate(-1)
  }

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const amount = parseAmountInput(amountText, { allowNegative: isAdjustment })
    if (!amount) {
      setError(t('add.invalidAmount'))
      return
    }
    setBusy(true)
    try {
      const shared = { amount, date, description, note: note || null, tags: splitTags(tagsText) }
      await financeApi.updateTransaction(
        transaction.id,
        isEntry
          ? {
              ...shared,
              kind: kind as 'expense' | 'income',
              account_id: accountId,
              category_id: categoryId || null,
            }
          : shared,
      )
      // A category corrected by hand: offer a rule so it is right next time (RF-MOV-07).
      const corrected =
        isEntry &&
        categoryId &&
        categoryId !== (transaction.category_id ?? '') &&
        description.trim()
      if (corrected) {
        const proposal = await importApi.ruleSuggestion(transaction.id).catch(() => null)
        if (proposal) {
          await refreshFinance(queryClient)
          setSuggestion(proposal)
          return
        }
      }
      await done()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    const question =
      transaction.kind === 'transfer'
        ? t('transactions.confirmDeleteTransfer')
        : t('transactions.confirmDelete')
    if (!window.confirm(question)) {
      return
    }
    await financeApi.deleteTransaction(transaction.id)
    await done()
  }

  if (suggestion) {
    return (
      <>
        <PageHeader title={t(`transactions.kinds.${transaction.kind}`)} back="/movimientos" />
        <RuleSuggestion
          suggestion={suggestion}
          categoryId={categoryId}
          categories={categories}
          onDone={() => void done()}
        />
      </>
    )
  }

  return (
    <>
      <PageHeader title={t(`transactions.kinds.${transaction.kind}`)} back="/movimientos" />
      <form className="stack" onSubmit={(event) => void save(event)}>
        {isEntry ? (
          <div
            className="segmented segmented--two"
            role="radiogroup"
            aria-label={t('accounts.kind')}
          >
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
        ) : (
          <p className="notice small">{t('transactions.transferNote')}</p>
        )}

        <label className="field">
          <span>{t('add.amount')}</span>
          <input
            inputMode="decimal"
            required
            value={amountText}
            onChange={(event) => setAmountText(event.target.value)}
          />
        </label>

        {isEntry && (
          <>
            <label className="field">
              <span>{t('add.account')}</span>
              <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
                {accounts
                  .filter((account) => !account.archived || account.id === transaction.account_id)
                  .map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name}
                    </option>
                  ))}
              </select>
            </label>
            <div className="field">
              <label htmlFor="edit-category">{t('add.category')}</label>
              <CategorySelect
                id="edit-category"
                categories={categories.filter(
                  (c) => !c.archived || c.id === transaction.category_id,
                )}
                kinds={[kind as 'expense' | 'income']}
                value={categoryId}
                onChange={setCategoryId}
                emptyLabel={t('transactions.noCategory')}
              />
            </div>
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
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
        </div>
        <label className="field">
          <span>{t('add.note')}</span>
          <textarea rows={2} value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
        <label className="field">
          <span>{t('add.tags')}</span>
          <input value={tagsText} onChange={(event) => setTagsText(event.target.value)} />
          <small className="muted">{t('add.tagsHelp')}</small>
        </label>

        <ErrorMessage message={error} />
        <button type="submit" className="button" disabled={busy}>
          {t('add.save')}
        </button>
        {isEntry && (
          <Link
            className="button button--secondary"
            to={`/mas/recurrentes?desde=${transaction.id}`}
          >
            {t('recurring.fromTransaction')}
          </Link>
        )}
        <button
          type="button"
          className="button button--ghost button--danger"
          onClick={() => void remove()}
        >
          {t('transactions.delete')}
        </button>
      </form>
    </>
  )
}

/** After a category is corrected by hand: "always do it this way?" (RF-MOV-07). */
function RuleSuggestion({
  suggestion,
  categoryId,
  categories,
  onDone,
}: {
  suggestion: { match_text: string; matches: number }
  categoryId: string
  categories: Category[]
  onDone: () => void
}) {
  const { t } = useTranslation()
  const [text, setText] = useState(suggestion.match_text)
  const [applyExisting, setApplyExisting] = useState(suggestion.matches > 0)
  const [error, setError] = useState<string | null>(null)

  const create = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await importApi.createRule({
        match_text: text,
        category_id: categoryId,
        apply_to_existing: applyExisting,
      })
      onDone()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  return (
    <form className="card stack stack--tight" onSubmit={(event) => void create(event)}>
      <h2>{t('rules.suggestTitle')}</h2>
      <label className="field">
        <span>
          {t('rules.suggestBody', { category: categoryLabel(categories, categoryId) ?? '' })}
        </span>
        <input
          required
          minLength={2}
          maxLength={60}
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      </label>
      {suggestion.matches > 0 && (
        <label className="check">
          <input
            type="checkbox"
            checked={applyExisting}
            onChange={(event) => setApplyExisting(event.target.checked)}
          />
          <span>{t('rules.suggestExisting', { count: suggestion.matches })}</span>
        </label>
      )}
      <ErrorMessage message={error} />
      <button type="submit" className="button">
        {t('rules.create')}
      </button>
      <button type="button" className="button button--ghost" onClick={onDone}>
        {t('rules.notNow')}
      </button>
    </form>
  )
}
