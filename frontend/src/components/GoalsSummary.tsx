import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useGoals } from '../api/goals'
import { goalStatusText } from '../lib/goals'
import { Meter } from './Meter'

const SHOWN = 3

/** The first pending goals, by priority, with how far along they are (RF-INF-01). */
export function GoalsSummary() {
  const { t } = useTranslation()
  const goals = useGoals()
  const pending = (goals.data ?? []).filter((goal) => !goal.achieved).slice(0, SHOWN)
  if (pending.length === 0) {
    return null
  }
  return (
    <section className="stack stack--tight" aria-labelledby="dashboard-goals-title">
      <div className="section-title">
        <h2 id="dashboard-goals-title">{t('goals.title')}</h2>
        <Link to="/planificar">{t('dashboard.allGoals')}</Link>
      </div>
      <ul className="list card card--flush">
        {pending.map((goal) => (
          <li key={goal.id}>
            <Link className="spend-line card--link" to={`/planificar/objetivos/${goal.id}`}>
              <span className="spend-line__head">
                <span className="row__title">
                  {goal.icon ?? '🎯'} {goal.name}
                </span>
                <span className="amount">{goal.percent} %</span>
              </span>
              <Meter value={goal.percent} label={t('goals.progressOf', { name: goal.name })} />
              <small className={`goal__status goal__status--${goal.status}`}>
                {goalStatusText(goal, t)}
              </small>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
