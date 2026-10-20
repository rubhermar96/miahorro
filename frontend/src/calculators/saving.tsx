import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { CalcContext, EmergencyResult, SavingsGoalResult } from '../api/calculators'
import { Meter } from '../components/Meter'
import { Money } from '../components/Money'
import { sumAmounts } from '../lib/amount'
import { amountText } from '../lib/calcForm'
import { formatAmount, formatMonthYear, formatRate } from '../lib/format'
import { Figures, Headline } from './parts'
import { contextAmount, define, type ExtraProps, type ResultProps } from './types'

function goalLink(fields: { name?: string; amount?: string | null; date?: string | null }) {
  const params = new URLSearchParams()
  if (fields.name) params.set('nombre', fields.name)
  if (fields.amount) params.set('importe', fields.amount)
  if (fields.date) params.set('fecha', fields.date)
  return `/planificar/objetivos/nuevo?${params.toString()}`
}

// --- Savings target (RF-CAL-02) ---------------------------------------------------------------

export const savingsGoal = define<SavingsGoalResult>({
  name: 'savings_goal',
  slug: 'meta-de-ahorro',
  icon: '🎯',
  group: 'saving',
  sections: [
    {
      fields: [
        {
          key: 'mode',
          kind: 'segmented',
          label: 'calc.f.question',
          options: [
            { value: 'monthly', label: 'calc.o.howMuch' },
            { value: 'date', label: 'calc.o.when' },
          ],
        },
        { key: 'target', kind: 'amount', label: 'calc.f.target' },
        { key: 'initial', kind: 'amount', label: 'calc.f.alreadySaved', optional: true },
        {
          key: 'months',
          kind: 'int',
          label: 'calc.f.inMonths',
          when: (own) => own.mode === 'monthly',
        },
        {
          key: 'monthly',
          kind: 'amount',
          label: 'calc.f.savePerMonth',
          when: (own) => own.mode === 'date',
        },
        {
          key: 'annual_return',
          kind: 'rate',
          label: 'calc.f.annualReturn',
          optional: true,
          help: 'calc.h.returnOptional',
        },
      ],
    },
  ],
  defaults: (context) => {
    const saved = contextAmount(context?.saved)
    return {
      mode: saved ? 'date' : 'monthly',
      target: '',
      initial: '',
      months: '24',
      monthly: saved,
      annual_return: '',
    }
  },
  Result: SavingsGoalView,
  metrics: (result, t) => [
    {
      label: t('calc.goal.monthly'),
      value: result.monthly ? formatAmount(result.monthly) : '—',
    },
    {
      label: t('calc.goal.when'),
      value: result.date ? formatMonthYear(result.date) : t('calc.goal.never'),
    },
  ],
})

function SavingsGoalView({ result, values }: ResultProps<SavingsGoalResult>) {
  const { t } = useTranslation()
  if (result.months === null || !result.date) {
    return <p className="notice">{t('calc.goal.notReached')}</p>
  }
  const target = String(values.target ?? '')
  return (
    <>
      {values.mode === 'monthly' ? (
        <Headline
          caption={t('calc.goal.needMonthly')}
          value={<Money value={result.monthly ?? '0'} />}
        />
      ) : (
        <Headline caption={t('calc.goal.reachedOn')} value={formatMonthYear(result.date)} />
      )}
      <Figures
        rows={[
          {
            label: t('calc.goal.term'),
            value: t('calc.goal.months', { count: result.months }),
          },
          {
            label: t('calc.goal.contributed'),
            value: result.contributed ? <Money value={result.contributed} /> : '—',
          },
          {
            label: t('calc.goal.gains'),
            value: result.gains ? <Money value={result.gains} /> : '—',
          },
        ]}
      />
      <Link
        className="button button--secondary"
        to={goalLink({ amount: target, date: result.date })}
      >
        {t('calc.createGoal')}
      </Link>
    </>
  )
}

// --- Emergency fund (RF-CAL-10) ---------------------------------------------------------------

/** Spending that is usually not essential; the rest counts unless the user unticks it. */
const NOT_ESSENTIAL = ['Ocio', 'Compras', 'Cuidado personal', 'Otros gastos']

type Spend = CalcContext['categories'][number]
const spendKey = (spend: Spend) => spend.category_id ?? 'none'

function essentialSum(categories: Spend[], picked: (spend: Spend) => boolean): string {
  return sumAmounts(categories.filter(picked).map((c) => c.monthly))
}

const isDefaultEssential = (spend: Spend) => !NOT_ESSENTIAL.includes(spend.name)

export const emergency = define<EmergencyResult>({
  name: 'emergency',
  slug: 'fondo-de-emergencia',
  icon: '🛟',
  group: 'saving',
  sections: [
    {
      fields: [
        { key: 'essential_monthly', kind: 'amount', label: 'calc.f.essential' },
        { key: 'months', kind: 'int', label: 'calc.f.monthsCovered', help: 'calc.h.months' },
        { key: 'current', kind: 'amount', label: 'calc.f.currentFund', optional: true },
        { key: 'monthly_saving', kind: 'amount', label: 'calc.f.savePerMonth', optional: true },
      ],
    },
  ],
  defaults: (context) => ({
    essential_monthly: context?.categories.length
      ? contextAmount(essentialSum(context.categories, isDefaultEssential))
      : '',
    months: '6',
    current: contextAmount(context?.liquidity),
    monthly_saving: contextAmount(context?.saved),
  }),
  Result: EmergencyView,
  Extra: EssentialPicker,
  metrics: (result, t) => [
    { label: t('calc.emergency.covered'), value: formatRate(result.covered_months) },
    { label: t('calc.emergency.target'), value: formatAmount(result.target) },
    { label: t('calc.emergency.missing'), value: formatAmount(result.missing) },
  ],
})

function EssentialPicker({ context, values, onChange }: ExtraProps) {
  const { t } = useTranslation()
  const categories = context.categories
  if (categories.length === 0) {
    return null
  }
  const picked = new Set(
    (values.essential_picked as string | undefined)?.split(',') ??
      categories.filter(isDefaultEssential).map(spendKey),
  )
  const toggle = (spend: Spend) => {
    const key = spendKey(spend)
    const next = new Set(picked)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    const total = essentialSum(categories, (c) => next.has(spendKey(c)))
    onChange({
      ...values,
      essential_picked: [...next].join(','),
      essential_monthly: total === '0.00' ? '' : amountText(total),
    })
  }
  return (
    <details className="card">
      <summary>{t('calc.emergency.pick', { count: context.months })}</summary>
      <ul className="details-body list">
        {categories.map((spend) => (
          <li key={spendKey(spend)}>
            <label className="check">
              <input
                type="checkbox"
                checked={picked.has(spendKey(spend))}
                onChange={() => toggle(spend)}
              />
              <span className="row__text">
                {spend.icon ? `${spend.icon} ` : ''}
                {spend.name}
              </span>
              <span className="amount">{formatAmount(spend.monthly)}</span>
            </label>
          </li>
        ))}
      </ul>
    </details>
  )
}

function EmergencyView({ result, values }: ResultProps<EmergencyResult>) {
  const { t } = useTranslation()
  const months = Number(values.months) || 0
  const covered = Number(result.covered_months)
  return (
    <>
      <Headline
        caption={t('calc.emergency.covered')}
        value={t('calc.emergency.monthsValue', { value: formatRate(result.covered_months) })}
      />
      <Meter value={covered} max={months || 1} label={t('calc.emergency.progress')} />
      <Figures
        rows={[
          {
            label: t('calc.emergency.target', { count: months }),
            value: <Money value={result.target} />,
          },
          { label: t('calc.emergency.missing'), value: <Money value={result.missing} /> },
          ...(result.months_to_complete && result.date_complete
            ? [
                {
                  label: t('calc.emergency.complete'),
                  value: `${formatMonthYear(result.date_complete)} · ${t('calc.goal.months', {
                    count: result.months_to_complete,
                  })}`,
                },
              ]
            : []),
        ]}
      />
      {result.missing !== '0.00' && (
        <Link
          className="button button--secondary"
          to={goalLink({
            name: t('calc.emergency.goalName'),
            amount: amountText(result.target),
            date: result.date_complete,
          })}
        >
          {t('calc.createGoal')}
        </Link>
      )}
    </>
  )
}
