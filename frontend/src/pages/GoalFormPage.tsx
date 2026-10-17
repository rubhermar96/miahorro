import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { type Account, refreshFinance, useAccounts } from '../api/finance'
import { type Goal, goalKeys, goalsApi, useGoal, useGoals } from '../api/goals'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { amountToInput, parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'

const ICONS = ['🏠', '🚗', '✈️', '🛟', '💍', '🎓', '👶', '💻', '🏖️', '🎁', '🐶', '🎯']
const PRIORITIES = [1, 2, 3] as const

/** Create or edit a savings goal (RF-OBJ-01, RF-OBJ-03). */
export function GoalFormPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const goal = useGoal(id)
  const goals = useGoals()
  const accounts = useAccounts()

  if ((id && !goal.data) || !accounts.data || !goals.data) {
    return <PageHeader title={t('goals.newTitle')} back="/planificar" />
  }
  return (
    <GoalForm
      key={goal.data?.id ?? 'new'}
      goal={goal.data}
      accounts={accounts.data}
      otherGoals={goals.data.filter((other) => other.id !== goal.data?.id)}
    />
  )
}

function GoalForm({
  goal,
  accounts,
  otherGoals,
}: {
  goal?: Goal
  accounts: Account[]
  otherGoals: Goal[]
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState(goal?.name ?? '')
  const [icon, setIcon] = useState(goal?.icon ?? '🎯')
  const [amountText, setAmountText] = useState(goal ? amountToInput(goal.target_amount) : '')
  const [date, setDate] = useState(goal?.target_date ?? '')
  const [priority, setPriority] = useState<1 | 2 | 3>(goal?.priority ?? 2)
  const [whole, setWhole] = useState<string[]>(goal?.account_ids ?? [])
  const [note, setNote] = useState(goal?.note ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Accounts other goals already own whole, or hold piggy banks in, cannot be whole here.
  const takenWhole = new Set(otherGoals.flatMap((other) => other.account_ids))
  const withPots = new Set(otherGoals.flatMap((other) => other.pots.map((pot) => pot.account_id)))

  const toggle = (accountId: string) =>
    setWhole((current) =>
      current.includes(accountId)
        ? current.filter((idInList) => idInList !== accountId)
        : [...current, accountId],
    )

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const amount = parseAmountInput(amountText)
    if (!amount) {
      setError(t('add.invalidAmount'))
      return
    }
    setBusy(true)
    try {
      const body = {
        name,
        icon,
        target_amount: amount,
        target_date: date || null,
        priority,
        note: note || null,
        account_ids: whole,
      }
      const saved = goal ? await goalsApi.update(goal.id, body) : await goalsApi.create(body)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: goalKeys.goals }),
        refreshFinance(queryClient),
      ])
      void navigate(`/planificar/objetivos/${saved.id}`, { replace: true })
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title={goal ? t('goals.editTitle') : t('goals.newTitle')}
        back={goal ? `/planificar/objetivos/${goal.id}` : '/planificar'}
      />
      <form className="stack" onSubmit={(event) => void submit(event)}>
        <label className="field">
          <span>{t('goals.name')}</span>
          <input
            required
            maxLength={60}
            placeholder={t('goals.namePlaceholder')}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <fieldset className="field">
          <legend>{t('goals.icon')}</legend>
          <div className="chips">
            {ICONS.map((option) => (
              <button
                key={option}
                type="button"
                className="chip"
                aria-pressed={icon === option}
                aria-label={t('goals.iconOption', { icon: option })}
                onClick={() => setIcon(option)}
              >
                {option}
              </button>
            ))}
          </div>
        </fieldset>
        <div className="grid-2">
          <label className="field">
            <span>{t('goals.amount')}</span>
            <input
              inputMode="decimal"
              required
              value={amountText}
              onChange={(event) => setAmountText(event.target.value)}
            />
          </label>
          <label className="field">
            <span>{t('goals.date')}</span>
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </label>
        </div>
        <div className="field">
          <span id="priority-label">{t('goals.priority')}</span>
          <div className="segmented" role="radiogroup" aria-labelledby="priority-label">
            {PRIORITIES.map((option) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={priority === option}
                className="segmented__option"
                onClick={() => setPriority(option)}
              >
                {t(`goals.priorities.${option}`)}
              </button>
            ))}
          </div>
        </div>
        <fieldset className="card stack stack--tight">
          <legend>{t('goals.wholeAccounts')}</legend>
          <p className="muted small">{t('goals.wholeHelp')}</p>
          {accounts.map((account) => {
            const blocked = takenWhole.has(account.id) || withPots.has(account.id)
            return (
              <label key={account.id} className="check">
                <input
                  type="checkbox"
                  checked={whole.includes(account.id)}
                  disabled={blocked && !whole.includes(account.id)}
                  onChange={() => toggle(account.id)}
                />
                <span>
                  {account.name}
                  {blocked && <small className="muted"> · {t('goals.accountTaken')}</small>}
                </span>
              </label>
            )
          })}
        </fieldset>
        <label className="field">
          <span>{t('add.note')}</span>
          <textarea rows={2} value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
        <ErrorMessage message={error} />
        <button type="submit" className="button" disabled={busy}>
          {goal ? t('add.save') : t('goals.create')}
        </button>
      </form>
    </>
  )
}
