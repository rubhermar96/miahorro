import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { authApi, SESSION_KEY, type SessionInfo } from '../api/auth'
import {
  type Budget,
  budgetApi,
  budgetKeys,
  type BudgetLine,
  type BudgetMode,
  useBudget,
} from '../api/budget'
import { type Category, categoryIcon, categoryLabel, useCategories } from '../api/finance'
import { CategorySelect } from '../components/CategorySelect'
import { ErrorMessage } from '../components/ErrorMessage'
import { Meter } from '../components/Meter'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { amountToInput, parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'
import { formatAmount, formatShortDate } from '../lib/format'

/** The month's budget, in the mode the user chose (RF-PRS-01…04). */
export function BudgetPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const date = params.get('mes') ?? ''
  const budget = useBudget(date)
  const categories = useCategories()

  const go = (start: string) => setParams({ mes: start }, { replace: true })

  if (!budget.data || !categories.data) {
    return <PageHeader title={t('budget.title')} back="/planificar" />
  }
  const data = budget.data
  if (!data.mode) {
    return (
      <>
        <PageHeader title={t('budget.title')} back="/planificar" />
        <ModeChooser />
      </>
    )
  }
  return (
    <>
      <PageHeader title={t('budget.title')} back="/planificar" />
      <div className="stack">
        <nav className="month-nav" aria-label={t('budget.months')}>
          <button
            type="button"
            className="button button--ghost"
            aria-label={t('budget.previous')}
            onClick={() => go(data.previous_start)}
          >
            ‹
          </button>
          <span className="month-nav__label">
            {formatShortDate(data.start)} – {formatShortDate(data.end)}
          </span>
          <button
            type="button"
            className="button button--ghost"
            aria-label={t('budget.next')}
            onClick={() => go(data.next_start)}
          >
            ›
          </button>
        </nav>

        {data.mode === 'zero_based' ? <ToAssign budget={data} /> : <LimitsSummary budget={data} />}

        <Lines budget={data} categories={categories.data} />
        <AddLine budget={data} categories={categories.data} />
        <Settings budget={data} />
      </div>
    </>
  )
}

function useRefresh() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: budgetKeys.budget })
}

function useSetPreferences() {
  const queryClient = useQueryClient()
  const refresh = useRefresh()
  return useMutation({
    mutationFn: authApi.updatePreferences,
    onSuccess: async (user) => {
      queryClient.setQueryData<SessionInfo | null>(SESSION_KEY, (current) =>
        current ? { ...current, user } : current,
      )
      await refresh()
    },
  })
}

function ModeChooser() {
  const { t } = useTranslation()
  const save = useSetPreferences()
  return (
    <div className="stack">
      <p className="muted small">{t('budget.chooseIntro')}</p>
      {(['limits', 'zero_based'] as const).map((mode) => (
        <section key={mode} className="card stack stack--tight" aria-labelledby={`mode-${mode}`}>
          <h2 id={`mode-${mode}`}>{t(`budget.modes.${mode}.name`)}</h2>
          <p className="small">{t(`budget.modes.${mode}.description`)}</p>
          <button
            type="button"
            className="button"
            disabled={save.isPending}
            onClick={() => save.mutate({ budget_mode: mode })}
          >
            {t('budget.choose', { name: t(`budget.modes.${mode}.name`) })}
          </button>
        </section>
      ))}
    </div>
  )
}

function ToAssign({ budget }: { budget: Budget }) {
  const { t } = useTranslation()
  const refresh = useRefresh()
  const [error, setError] = useState<string | null>(null)
  const amount = budget.to_assign ?? '0.00'
  const negative = amount.startsWith('-')

  const copy = async () => {
    setError(null)
    try {
      await budgetApi.copyPrevious(budget.start)
      await refresh()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  return (
    <section className="card stack stack--tight" aria-labelledby="to-assign-title">
      <h2 id="to-assign-title">{t('budget.toAssign')}</h2>
      <p className="total">
        <Money value={amount} />
      </p>
      <p className={negative ? 'notice small' : 'muted small'}>
        {negative
          ? t('budget.overAssigned')
          : t('budget.cashLine', { cash: formatAmount(budget.cash ?? '0.00') })}
      </p>
      <button type="button" className="button button--secondary" onClick={() => void copy()}>
        {t('budget.copyPrevious')}
      </button>
      <ErrorMessage message={error} />
      <p className="muted small">
        {t('budget.goalsHint')} <Link to="/planificar">{t('budget.goalsLink')}</Link>
      </p>
    </section>
  )
}

function LimitsSummary({ budget }: { budget: Budget }) {
  const { t } = useTranslation()
  const spent = budget.activity.startsWith('-') ? budget.activity.slice(1) : '0.00'
  const share = Number(budget.assigned) > 0 ? (Number(spent) / Number(budget.assigned)) * 100 : 0
  return (
    <section className="card stack stack--tight" aria-labelledby="limits-title">
      <h2 id="limits-title">{t('budget.thisMonth')}</h2>
      <p className="total">
        <Money value={spent} />
      </p>
      <p className="muted small">{t('budget.spentOf', { limit: formatAmount(budget.assigned) })}</p>
      <Meter value={Math.min(share, 100)} label={t('budget.totalProgress')} />
    </section>
  )
}

function Lines({ budget, categories }: { budget: Budget; categories: Category[] }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState<string | null>(null)
  if (budget.lines.length === 0) {
    return <p className="card muted">{t(`budget.empty.${budget.mode ?? 'limits'}`)}</p>
  }
  return (
    <section className="stack stack--tight" aria-labelledby="lines-title">
      <h2 id="lines-title" className="section-title">
        {t('budget.lines')}
      </h2>
      <ul className="list card card--flush">
        {budget.lines.map((line) => (
          <li key={line.category_id}>
            <LineRow
              budget={budget}
              line={line}
              categories={categories}
              open={open === line.category_id}
              onToggle={() => setOpen(open === line.category_id ? null : line.category_id)}
            />
          </li>
        ))}
        {budget.unbudgeted !== '0.00' && (
          <li className="row">
            <span className="row__text">
              <span className="row__title">{t('budget.unbudgeted')}</span>
              <small className="muted">{t('budget.unbudgetedHelp')}</small>
            </span>
            <Money value={budget.unbudgeted} signed />
          </li>
        )}
      </ul>
    </section>
  )
}

function LineRow({
  budget,
  line,
  categories,
  open,
  onToggle,
}: {
  budget: Budget
  line: BudgetLine
  categories: Category[]
  open: boolean
  onToggle: () => void
}) {
  const { t } = useTranslation()
  const name = categoryLabel(categories, line.category_id) ?? ''
  const spent = line.activity.startsWith('-') ? line.activity.slice(1) : '0.00'
  const over = line.available.startsWith('-')
  const limit = Number(line.assigned) + Number(line.carried)
  const share = limit > 0 ? (Number(spent) / limit) * 100 : over ? 100 : 0

  return (
    <div className="budget-line">
      <button
        type="button"
        className="row budget-line__summary"
        aria-expanded={open}
        onClick={onToggle}
      >
        <span className="row__icon" aria-hidden="true">
          {categoryIcon(categories, line.category_id)}
        </span>
        <span className="row__text">
          <span className="row__title">{name}</span>
          <small className="muted">
            {budget.mode === 'limits'
              ? t('budget.lineLimits', {
                  spent: formatAmount(spent),
                  limit: formatAmount(line.assigned),
                })
              : t('budget.lineZero', {
                  assigned: formatAmount(line.assigned),
                  spent: formatAmount(spent),
                })}
          </small>
          {budget.mode === 'limits' && (
            <Meter value={Math.min(share, 100)} label={t('budget.lineProgress', { name })} />
          )}
        </span>
        <span className="row__amounts">
          <span className={over ? 'amount amount--out' : 'amount'}>
            {formatAmount(line.available)}
          </span>
          <small className="muted">{over ? t('budget.over') : t('budget.left')}</small>
        </span>
      </button>
      {open && <LineEditor budget={budget} line={line} categories={categories} name={name} />}
    </div>
  )
}

function LineEditor({
  budget,
  line,
  categories,
  name,
}: {
  budget: Budget
  line: BudgetLine
  categories: Category[]
  name: string
}) {
  const { t } = useTranslation()
  const refresh = useRefresh()
  const [amountText, setAmountText] = useState(amountToInput(line.assigned))
  const [moveTo, setMoveTo] = useState('')
  const [moveText, setMoveText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const zeroBased = budget.mode === 'zero_based'

  const run = async (action: () => Promise<unknown>) => {
    setError(null)
    try {
      await action()
      await refresh()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  const save = (event: FormEvent) => {
    event.preventDefault()
    const amount = parseAmountInput(amountText || '0', { allowZero: true })
    if (amount === null) {
      setError(t('add.invalidAmount'))
      return
    }
    void run(() => budgetApi.setLine(line.category_id, amount, budget.start))
  }

  const move = (event: FormEvent) => {
    event.preventDefault()
    const amount = parseAmountInput(moveText)
    if (!amount || !moveTo) {
      setError(t('budget.moveInvalid'))
      return
    }
    void run(() => budgetApi.move(line.category_id, moveTo, amount, budget.start))
  }

  return (
    <div className="budget-line__editor stack stack--tight">
      {line.carried !== '0.00' && (
        <p className="muted small">{t('budget.carried', { amount: formatAmount(line.carried) })}</p>
      )}
      <form className="search" onSubmit={save}>
        <label className="field">
          <span>{zeroBased ? t('budget.assigned') : t('budget.limit')}</span>
          <input
            inputMode="decimal"
            value={amountText}
            onChange={(event) => setAmountText(event.target.value)}
          />
        </label>
        <button type="submit" className="button button--secondary">
          {t('add.save')}
        </button>
      </form>
      {zeroBased && (
        <form className="stack stack--tight" onSubmit={move}>
          <div className="field">
            <label htmlFor={`move-${line.category_id}`}>{t('budget.moveTo')}</label>
            <CategorySelect
              id={`move-${line.category_id}`}
              categories={categories.filter((c) => c.id !== line.category_id && !c.archived)}
              kinds={['expense']}
              value={moveTo}
              onChange={setMoveTo}
              emptyLabel={t('budget.chooseCategory')}
            />
          </div>
          <div className="search">
            <label className="field">
              <span>{t('budget.moveAmount')}</span>
              <input
                inputMode="decimal"
                value={moveText}
                onChange={(event) => setMoveText(event.target.value)}
              />
            </label>
            <button type="submit" className="button button--secondary">
              {t('budget.move')}
            </button>
          </div>
        </form>
      )}
      <ErrorMessage message={error} />
      <button
        type="button"
        className="button button--ghost button--danger"
        onClick={() => void run(() => budgetApi.removeLine(line.category_id, budget.start))}
      >
        {t('budget.remove', { name })}
      </button>
    </div>
  )
}

function AddLine({ budget, categories }: { budget: Budget; categories: Category[] }) {
  const { t } = useTranslation()
  const refresh = useRefresh()
  const [categoryId, setCategoryId] = useState('')
  const [amountText, setAmountText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const taken = new Set(budget.lines.map((line) => line.category_id))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const amount = parseAmountInput(amountText)
    if (!categoryId || !amount) {
      setError(t('budget.addInvalid'))
      return
    }
    try {
      await budgetApi.setLine(categoryId, amount, budget.start)
      setCategoryId('')
      setAmountText('')
      await refresh()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  return (
    <form className="card stack stack--tight" onSubmit={(event) => void submit(event)}>
      <h2>{t('budget.addTitle')}</h2>
      <div className="field">
        <label htmlFor="budget-category">{t('add.category')}</label>
        <CategorySelect
          id="budget-category"
          categories={categories.filter((c) => !taken.has(c.id) && !c.archived)}
          kinds={['expense']}
          value={categoryId}
          onChange={setCategoryId}
          emptyLabel={t('budget.chooseCategory')}
        />
      </div>
      <div className="search">
        <label className="field">
          <span>{budget.mode === 'zero_based' ? t('budget.assigned') : t('budget.limit')}</span>
          <input
            inputMode="decimal"
            value={amountText}
            onChange={(event) => setAmountText(event.target.value)}
          />
        </label>
        <button type="submit" className="button">
          {t('budget.add')}
        </button>
      </div>
      <ErrorMessage message={error} />
    </form>
  )
}

function Settings({ budget }: { budget: Budget }) {
  const { t } = useTranslation()
  const save = useSetPreferences()
  const other: BudgetMode = budget.mode === 'limits' ? 'zero_based' : 'limits'
  return (
    <section className="card stack stack--tight" aria-labelledby="budget-settings">
      <h2 id="budget-settings">{t('budget.settings')}</h2>
      {budget.mode === 'limits' && (
        <label className="check">
          <input
            type="checkbox"
            checked={budget.rollover}
            onChange={(event) => save.mutate({ budget_rollover: event.target.checked })}
          />
          <span>{t('budget.rollover')}</span>
        </label>
      )}
      <p className="muted small">
        {t('budget.currentMode', { name: t(`budget.modes.${budget.mode ?? 'limits'}.name`) })}{' '}
        {t('budget.switchHelp')}
      </p>
      <button
        type="button"
        className="button button--secondary"
        onClick={() => save.mutate({ budget_mode: other })}
      >
        {t('budget.switchTo', { name: t(`budget.modes.${other}.name`) })}
      </button>
    </section>
  )
}
