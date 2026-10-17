import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import { type Account, refreshFinance, useAccounts } from '../api/finance'
import { type Goal, goalKeys, goalsApi, useContributions, useGoal, useGoals } from '../api/goals'
import { ErrorMessage } from '../components/ErrorMessage'
import { Meter } from '../components/Meter'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'
import { formatDate, formatMonthYear } from '../lib/format'
import { goalStatusText } from '../lib/goals'

/** One goal: progress, forecast and its piggy banks (RF-OBJ-02, RF-OBJ-03). */
export function GoalPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const goal = useGoal(id)
  const accounts = useAccounts(true)
  if (!goal.data || !accounts.data) {
    return <PageHeader title={t('goals.title')} back="/planificar" />
  }
  return <GoalDetails goal={goal.data} accounts={accounts.data} />
}

function GoalDetails({ goal, accounts }: { goal: Goal; accounts: Account[] }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const contributions = useContributions(goal.id)
  const accountName = (id: string) => accounts.find((a) => a.id === id)?.name ?? ''

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: goalKeys.goals }),
      refreshFinance(queryClient),
    ])

  const toggleAchieved = async () => {
    await goalsApi.update(goal.id, { achieved: !goal.achieved })
    await refresh()
  }

  const remove = async () => {
    if (!window.confirm(t('goals.confirmDelete', { name: goal.name }))) {
      return
    }
    await goalsApi.remove(goal.id)
    await refresh()
    void navigate('/planificar', { replace: true })
  }

  const removeContribution = async (contributionId: string) => {
    await goalsApi.removeContribution(goal.id, contributionId)
    await refresh()
  }

  return (
    <>
      <PageHeader title={`${goal.icon ?? '🎯'} ${goal.name}`} back="/planificar" />
      <div className="stack">
        <section
          className="card stack stack--tight"
          aria-label={t('goals.progressOf', { name: goal.name })}
        >
          <p className="total">
            <Money value={goal.saved} />
          </p>
          <p className="muted small">
            {t('goals.of')} <Money value={goal.target_amount} /> · {goal.percent} %
          </p>
          <Meter value={goal.percent} label={t('goals.progressOf', { name: goal.name })} />
          <p className={`small goal__status goal__status--${goal.status}`}>
            {goalStatusText(goal, t)}
          </p>
          <dl className="details">
            <div>
              <dt>{t('goals.remaining')}</dt>
              <dd>
                <Money value={goal.remaining} />
              </dd>
            </div>
            {goal.target_date && (
              <div>
                <dt>{t('goals.deadline')}</dt>
                <dd>{formatDate(goal.target_date)}</dd>
              </div>
            )}
            {goal.required_monthly && !goal.achieved && (
              <div>
                <dt>{t('goals.requiredMonthly')}</dt>
                <dd>
                  <Money value={goal.required_monthly} />
                </dd>
              </div>
            )}
            <div>
              <dt>{t('goals.pace')}</dt>
              <dd>{goal.pace ? <Money value={goal.pace} /> : t('goals.paceUnknown')}</dd>
            </div>
            {goal.estimated_date && !goal.achieved && (
              <div>
                <dt>{t('goals.estimated')}</dt>
                <dd>{formatMonthYear(goal.estimated_date)}</dd>
              </div>
            )}
          </dl>
        </section>

        {!goal.achieved && <ContributionForm goal={goal} accounts={accounts} onSaved={refresh} />}

        {(goal.account_ids.length > 0 || goal.pots.length > 0) && (
          <section className="card stack stack--tight" aria-labelledby="where-title">
            <h2 id="where-title">{t('goals.where')}</h2>
            <dl className="details">
              {goal.account_ids.map((accountId) => (
                <div key={accountId}>
                  <dt>{accountName(accountId)}</dt>
                  <dd>{t('goals.wholeAccount')}</dd>
                </div>
              ))}
              {goal.pots.map((pot) => (
                <div key={pot.account_id}>
                  <dt>{accountName(pot.account_id)}</dt>
                  <dd>
                    <Money value={pot.amount} />
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        )}

        {(contributions.data?.length ?? 0) > 0 && (
          <section className="stack stack--tight" aria-labelledby="history-title">
            <h2 id="history-title" className="section-title">
              {t('goals.history')}
            </h2>
            <ul className="list card card--flush">
              {contributions.data?.map((row) => (
                <li key={row.id} className="row">
                  <span className="row__text">
                    <span className="row__title">
                      {row.amount.startsWith('-') ? t('goals.withdrawn') : t('goals.added')}
                    </span>
                    <small className="muted">
                      {[formatDate(row.date), accountName(row.account_id), row.note]
                        .filter(Boolean)
                        .join(' · ')}
                    </small>
                  </span>
                  <Money value={row.amount} signed />
                  <button
                    type="button"
                    className="button button--ghost button--danger"
                    aria-label={t('goals.removeContribution', { date: formatDate(row.date) })}
                    onClick={() => void removeContribution(row.id)}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="card stack stack--tight">
          <Link className="button button--secondary" to={`/planificar/objetivos/${goal.id}/editar`}>
            {t('goals.edit')}
          </Link>
          <button
            type="button"
            className="button button--secondary"
            onClick={() => void toggleAchieved()}
          >
            {goal.achieved ? t('goals.reopen') : t('goals.markAchieved')}
          </button>
          <button
            type="button"
            className="button button--ghost button--danger"
            onClick={() => void remove()}
          >
            {t('goals.delete')}
          </button>
        </section>
      </div>
    </>
  )
}

/** Set money aside in an account for the goal, or take it back. */
function ContributionForm({
  goal,
  accounts,
  onSaved,
}: {
  goal: Goal
  accounts: Account[]
  onSaved: () => Promise<unknown>
}) {
  const { t } = useTranslation()
  const goals = useGoals()
  // Accounts a goal owns whole have nothing to set aside: all their money is that goal's.
  const whole = new Set((goals.data ?? []).flatMap((g) => g.account_ids))
  const usable = accounts.filter((a) => !a.archived && !whole.has(a.id))
  const [action, setAction] = useState<'add' | 'withdraw'>('add')
  const [accountId, setAccountId] = useState(goal.pots[0]?.account_id ?? usable[0]?.id ?? '')
  const [amountText, setAmountText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const account = accounts.find((a) => a.id === accountId)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setMessage(null)
    const amount = parseAmountInput(amountText)
    if (!amount) {
      setError(t('add.invalidAmount'))
      return
    }
    try {
      await goalsApi.contribute(goal.id, { account_id: accountId, amount, action })
      setAmountText('')
      setMessage(action === 'add' ? t('goals.addedDone') : t('goals.withdrawnDone'))
      await onSaved()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  if (usable.length === 0) {
    return null
  }
  return (
    <form className="card stack stack--tight" onSubmit={(event) => void submit(event)}>
      <h2>{t('goals.piggyBank')}</h2>
      <p className="muted small">{t('goals.piggyHelp')}</p>
      <div className="segmented segmented--two" role="radiogroup" aria-label={t('goals.piggyBank')}>
        {(['add', 'withdraw'] as const).map((option) => (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={action === option}
            className="segmented__option"
            onClick={() => setAction(option)}
          >
            {t(`goals.actions.${option}`)}
          </button>
        ))}
      </div>
      <div className="grid-2">
        <label className="field">
          <span>{t('add.account')}</span>
          <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
            {usable.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t('add.amount')}</span>
          <input
            inputMode="decimal"
            required
            value={amountText}
            onChange={(event) => setAmountText(event.target.value)}
          />
        </label>
      </div>
      {account && (
        <p className="muted small">
          {t('goals.availableIn', { account: account.name })} <Money value={account.available} />
        </p>
      )}
      <ErrorMessage message={error} />
      {message && (
        <p className="saved" role="status">
          {message}
        </p>
      )}
      <button type="submit" className="button">
        {action === 'add' ? t('goals.actions.add') : t('goals.actions.withdraw')}
      </button>
    </form>
  )
}
