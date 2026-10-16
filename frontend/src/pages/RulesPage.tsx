import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  type Account,
  categoryIcon,
  categoryLabel,
  refreshFinance,
  useAccounts,
  useCategories,
} from '../api/finance'
import { importApi, importKeys, type Rule, useRules } from '../api/imports'
import { CategorySelect } from '../components/CategorySelect'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'
import { formatAmount } from '../lib/format'

/** Rules that categorise movements by their concept (RF-MOV-07). */
export function RulesPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const rules = useRules()
  const categories = useCategories()
  const accounts = useAccounts()
  const [message, setMessage] = useState<string | null>(null)

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: importKeys.rules }),
      refreshFinance(queryClient),
    ])

  const move = async (rule: Rule, position: number) => {
    await importApi.updateRule(rule.id, { position })
    await refresh()
  }

  const remove = async (rule: Rule) => {
    if (!window.confirm(t('rules.confirmRemove', { text: rule.match_text }))) {
      return
    }
    await importApi.deleteRule(rule.id)
    await refresh()
  }

  const applyAll = async () => {
    const { applied } = await importApi.applyRules()
    await refresh()
    setMessage(t('rules.applied', { count: applied }))
  }

  const list = rules.data ?? []
  return (
    <>
      <PageHeader title={t('rules.title')} back="/mas" />
      <div className="stack">
        <p className="muted small">{t('rules.intro')}</p>
        <RuleForm
          accounts={accounts.data ?? []}
          onCreated={async (text) => {
            await refresh()
            setMessage(text)
          }}
        />
        {message && (
          <p className="notice" role="status">
            {message}
          </p>
        )}
        {rules.isSuccess && list.length === 0 && <p className="card muted">{t('rules.empty')}</p>}
        {list.length > 0 && (
          <>
            <ol className="list card card--flush">
              {list.map((rule, index) => (
                <li key={rule.id} className="row">
                  <span className="row__icon" aria-hidden="true">
                    {categoryIcon(categories.data ?? [], rule.category_id)}
                  </span>
                  <span className="row__text">
                    <span className="row__title">«{rule.match_text}»</span>
                    <small className="muted">
                      {[
                        categoryLabel(categories.data ?? [], rule.category_id),
                        conditions(rule, accounts.data ?? [], t),
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </small>
                  </span>
                  <span className="row__actions">
                    <button
                      type="button"
                      className="button button--ghost"
                      aria-label={t('rules.moveUp', { text: rule.match_text })}
                      disabled={index === 0}
                      onClick={() => void move(rule, index - 1)}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="button button--ghost"
                      aria-label={t('rules.moveDown', { text: rule.match_text })}
                      disabled={index === list.length - 1}
                      onClick={() => void move(rule, index + 1)}
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      className="button button--ghost button--danger"
                      aria-label={t('rules.remove', { text: rule.match_text })}
                      onClick={() => void remove(rule)}
                    >
                      ✕
                    </button>
                  </span>
                </li>
              ))}
            </ol>
            <button
              type="button"
              className="button button--secondary"
              onClick={() => void applyAll()}
            >
              {t('rules.applyAll')}
            </button>
          </>
        )}
      </div>
    </>
  )
}

function conditions(
  rule: Rule,
  accounts: Account[],
  t: ReturnType<typeof useTranslation>['t'],
): string | null {
  const parts: string[] = []
  const account = accounts.find((a) => a.id === rule.account_id)
  if (account) {
    parts.push(t('rules.onlyAccount', { account: account.name }))
  }
  const min = rule.amount_min && formatAmount(rule.amount_min)
  const max = rule.amount_max && formatAmount(rule.amount_max)
  if (min && max) {
    parts.push(t('rules.range', { min, max }))
  } else if (min) {
    parts.push(t('rules.from', { min }))
  } else if (max) {
    parts.push(t('rules.upTo', { max }))
  }
  return parts.join(', ') || null
}

function RuleForm({
  accounts,
  onCreated,
}: {
  accounts: Account[]
  onCreated: (message: string) => Promise<void>
}) {
  const { t } = useTranslation()
  const categories = useCategories()
  const [text, setText] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [accountId, setAccountId] = useState('')
  const [minText, setMinText] = useState('')
  const [maxText, setMaxText] = useState('')
  const [applyExisting, setApplyExisting] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (!categoryId) {
      setError(t('rules.chooseCategory'))
      return
    }
    const amountMin = minText.trim() ? parseAmountInput(minText) : null
    const amountMax = maxText.trim() ? parseAmountInput(maxText) : null
    if ((minText.trim() && !amountMin) || (maxText.trim() && !amountMax)) {
      setError(t('add.invalidAmount'))
      return
    }
    setBusy(true)
    try {
      const { applied } = await importApi.createRule({
        match_text: text,
        category_id: categoryId,
        account_id: accountId || null,
        amount_min: amountMin,
        amount_max: amountMax,
        apply_to_existing: applyExisting,
      })
      setText('')
      setMinText('')
      setMaxText('')
      await onCreated(applied > 0 ? t('rules.added', { count: applied }) : t('rules.addedNone'))
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card stack stack--tight" onSubmit={(event) => void submit(event)}>
      <label className="field">
        <span>{t('rules.text')}</span>
        <input
          required
          minLength={2}
          maxLength={60}
          placeholder={t('rules.textPlaceholder')}
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      </label>
      <div className="field">
        <label htmlFor="rule-category">{t('rules.category')}</label>
        <CategorySelect
          id="rule-category"
          categories={categories.data ?? []}
          value={categoryId}
          onChange={setCategoryId}
          emptyLabel={t('rules.chooseCategory')}
        />
      </div>
      <details>
        <summary>{t('rules.conditions')}</summary>
        <div className="stack stack--tight details-body">
          <label className="field">
            <span>{t('rules.account')}</span>
            <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
              <option value="">{t('rules.anyAccount')}</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          </label>
          <div className="grid-2">
            <label className="field">
              <span>{t('rules.amountMin')}</span>
              <input
                inputMode="decimal"
                value={minText}
                onChange={(event) => setMinText(event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t('rules.amountMax')}</span>
              <input
                inputMode="decimal"
                value={maxText}
                onChange={(event) => setMaxText(event.target.value)}
              />
            </label>
          </div>
        </div>
      </details>
      <label className="check">
        <input
          type="checkbox"
          checked={applyExisting}
          onChange={(event) => setApplyExisting(event.target.checked)}
        />
        <span>{t('rules.applyExisting')}</span>
      </label>
      <ErrorMessage message={error} />
      <button type="submit" className="button" disabled={busy}>
        {t('rules.add')}
      </button>
    </form>
  )
}
