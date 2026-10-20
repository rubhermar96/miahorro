import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { authApi, SESSION_KEY, type SessionInfo, useSession } from '../api/auth'
import { type Goal, goalKeys, useGoals, useSavingsRate } from '../api/goals'
import { goalStatusText } from '../lib/goals'
import { CALCULATORS } from '../calculators'
import { BudgetSummaryCard } from '../components/BudgetSummaryCard'
import { LoansSection } from '../components/LoansSection'
import { Meter } from '../components/Meter'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { formatAmount, formatDate, formatRate, formatShortDate } from '../lib/format'

const TARGETS = [5, 10, 15, 20, 25, 30, 35, 40, 50]

/** Planificar: savings goals and the savings rate (RF-OBJ-01…06). */
export function PlanPage() {
  const { t } = useTranslation()
  const goals = useGoals()
  const pending = (goals.data ?? []).filter((goal) => !goal.achieved)
  const achieved = (goals.data ?? []).filter((goal) => goal.achieved)

  return (
    <>
      <PageHeader title={t('plan.title')} />
      <div className="stack">
        <BudgetSummaryCard />

        <section className="stack stack--tight" aria-labelledby="goals-title">
          <div className="section-title">
            <h2 id="goals-title">{t('goals.title')}</h2>
            <Link to="/planificar/objetivos/nuevo" aria-label={t('goals.newTitle')}>
              {t('goals.new')}
            </Link>
          </div>
          {goals.isSuccess && goals.data.length === 0 && (
            <div className="card stack stack--tight">
              <p className="muted">{t('goals.empty')}</p>
              <Link className="button" to="/planificar/objetivos/nuevo">
                {t('goals.create')}
              </Link>
            </div>
          )}
          {pending.map((goal) => (
            <GoalCard key={goal.id} goal={goal} />
          ))}
          {achieved.length > 0 && (
            <>
              <h3 className="day">{t('goals.achievedTitle')}</h3>
              {achieved.map((goal) => (
                <GoalCard key={goal.id} goal={goal} />
              ))}
            </>
          )}
        </section>

        <LoansSection />

        <SavingsRateCard />

        <CalculatorsCard />
      </div>
    </>
  )
}

function GoalCard({ goal }: { goal: Goal }) {
  const { t } = useTranslation()
  return (
    <Link className="card card--link goal" to={`/planificar/objetivos/${goal.id}`}>
      <div className="goal__head">
        <span className="goal__icon" aria-hidden="true">
          {goal.icon ?? '🎯'}
        </span>
        <span className="goal__name">{goal.name}</span>
        <span className="goal__percent">{goal.percent} %</span>
      </div>
      <Meter value={goal.percent} label={t('goals.progressOf', { name: goal.name })} />
      <p className="small">
        <Money value={goal.saved} /> {t('goals.of')} <Money value={goal.target_amount} />
        {goal.target_date && (
          <span className="muted"> · {t('goals.by', { date: formatDate(goal.target_date) })}</span>
        )}
      </p>
      <p className={`small goal__status goal__status--${goal.status}`}>{goalStatusText(goal, t)}</p>
    </Link>
  )
}

function SavingsRateCard() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data: session } = useSession()
  const rate = useSavingsRate(6)
  const save = useMutation({
    mutationFn: (target: number | null) =>
      authApi.updatePreferences({ savings_rate_target: target }),
    onSuccess: async (user) => {
      queryClient.setQueryData<SessionInfo | null>(SESSION_KEY, (current) =>
        current ? { ...current, user } : current,
      )
      await queryClient.invalidateQueries({ queryKey: goalKeys.savingsRate })
    },
  })

  const periods = rate.data?.periods ?? []
  const current = periods.at(-1)
  const target = rate.data?.target ?? session?.user.preferences.savings_rate_target ?? null
  const highest = Math.max(50, target ?? 0, ...periods.map((p) => Number(p.rate ?? 0)))

  return (
    <section className="card stack stack--tight" aria-labelledby="rate-title">
      <h2 id="rate-title">{t('savingsRate.title')}</h2>
      {current && (
        <p className="total">
          {current.rate === null || current.rate === undefined
            ? '—'
            : `${formatRate(String(current.rate))} %`}
        </p>
      )}
      <p className="muted small">
        {current &&
          t('savingsRate.current', {
            from: formatShortDate(current.start),
            saved: formatAmount(current.saved),
          })}
        {target !== null && ` ${t('savingsRate.target', { target })}`}
      </p>
      <ol className="rate-list" aria-label={t('savingsRate.history')}>
        {periods.map((period) => {
          const value =
            period.rate === null || period.rate === undefined ? null : Number(period.rate)
          return (
            <li key={period.start} className="rate-list__row">
              <span className="rate-list__label">{formatShortDate(period.start)}</span>
              <Meter
                value={Math.max(value ?? 0, 0)}
                max={highest}
                marker={target ?? undefined}
                markerLabel={target !== null ? t('savingsRate.targetMark', { target }) : undefined}
                label={t('savingsRate.rowLabel', { from: formatShortDate(period.start) })}
              />
              <span className="rate-list__value">
                {value === null ? '—' : `${formatRate(String(period.rate))} %`}
              </span>
            </li>
          )
        })}
      </ol>
      <label className="field">
        <span>{t('savingsRate.targetLabel')}</span>
        <select
          value={target ?? ''}
          onChange={(event) => save.mutate(event.target.value ? Number(event.target.value) : null)}
        >
          <option value="">{t('savingsRate.noTarget')}</option>
          {TARGETS.map((value) => (
            <option key={value} value={value}>
              {value} %
            </option>
          ))}
        </select>
        <small className="muted">{t('savingsRate.help')}</small>
      </label>
    </section>
  )
}

function CalculatorsCard() {
  const { t } = useTranslation()
  return (
    <section className="card stack stack--tight" aria-labelledby="calculators-title">
      <div className="section-title">
        <h2 id="calculators-title">{t('calc.title')}</h2>
        <Link to="/planificar/calculadoras">{t('calc.all')}</Link>
      </div>
      <p className="muted small">{t('calc.intro')}</p>
      <ul className="chips">
        {CALCULATORS.map((calculator) => (
          <li key={calculator.name}>
            <Link className="chip" to={`/planificar/calculadoras/${calculator.slug}`}>
              <span aria-hidden="true">{calculator.icon}</span> {t(`calc.${calculator.name}.short`)}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
