import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { MortgageOutcome, MortgageResult } from '../api/calculators'
import { Money } from '../components/Money'
import type { ItemValues } from '../lib/calcForm'
import { formatAmount, formatRate } from '../lib/format'
import { rateToInput } from '../lib/rate'
import { CompareTable, Headline } from './parts'
import { define, type ResultProps } from './types'

const SCENARIOS = ['euribor_1', 'euribor_2', 'euribor_3'] as const

const isVariable = (own: ItemValues) => own.rate_type !== 'fixed'

const offer = (name: string, rateType: string, fixedMonths: string): ItemValues => ({
  name,
  rate_type: rateType,
  fixed_rate: '',
  fixed_months: fixedMonths,
  spread: '',
  discount: '',
  linked_yearly_cost: '',
  upfront_costs: '',
})

/** A Euribor value moved by `points`, never below zero, as typed text. */
function moved(value: string, points: number): string {
  return rateToInput(Math.max(Number(value) + points, 0).toFixed(2))
}

/** The best way to take an offer: with its discounts if they pay off. */
function chosen(scenario: MortgageResult['offers'][number]['scenarios'][number]) {
  return Number(scenario.discount_saves) > 0 ? scenario.with_discount : scenario.without_discount
}

/** Hipoteca: fija, variable o mixta con escenarios de Euribor y bonificaciones (RF-CAL-03). */
export const mortgage = define<MortgageResult>({
  name: 'mortgage',
  slug: 'hipoteca',
  icon: '🏦',
  group: 'buying',
  sections: [
    {
      fields: [
        { key: 'principal', kind: 'amount', label: 'calc.f.principal' },
        { key: 'years', kind: 'int', label: 'calc.f.termYears' },
      ],
    },
    {
      title: 'calc.mortgage.scenarios',
      fields: [
        { key: 'euribor_1', kind: 'rate', label: 'calc.f.euribor1', help: 'calc.h.euribor' },
        { key: 'euribor_2', kind: 'rate', label: 'calc.f.euribor2', optional: true },
        { key: 'euribor_3', kind: 'rate', label: 'calc.f.euribor3', optional: true },
      ],
    },
    {
      title: 'calc.mortgage.offers',
      fields: [
        {
          kind: 'list',
          key: 'offers',
          item: 'calc.mortgage.offer',
          add: 'calc.mortgage.addOffer',
          min: 1,
          max: 3,
          blank: (index) => offer(`Oferta ${index + 1}`, 'fixed', '0'),
          fields: [
            { key: 'name', kind: 'text', label: 'calc.f.name' },
            {
              key: 'rate_type',
              kind: 'segmented',
              label: 'calc.f.rateType',
              options: [
                { value: 'fixed', label: 'loans.rateTypes.fixed' },
                { value: 'variable', label: 'loans.rateTypes.variable' },
                { value: 'mixed', label: 'loans.rateTypes.mixed' },
              ],
            },
            { key: 'fixed_rate', kind: 'rate', label: 'calc.f.fixedRate' },
            {
              key: 'fixed_months',
              kind: 'int',
              label: 'calc.f.fixedMonths',
              when: isVariable,
            },
            { key: 'spread', kind: 'rate', label: 'calc.f.spread', when: isVariable },
            {
              key: 'discount',
              kind: 'rate',
              label: 'calc.f.discount',
              optional: true,
              help: 'calc.h.discount',
            },
            {
              key: 'linked_yearly_cost',
              kind: 'amount',
              label: 'calc.f.linkedCost',
              optional: true,
            },
            { key: 'upfront_costs', kind: 'amount', label: 'calc.f.upfront', optional: true },
          ],
        },
      ],
    },
  ],
  defaults: (context) => {
    const euribor = context?.euribor?.value
    return {
      principal: '',
      years: '30',
      euribor_1: euribor ? rateToInput(euribor) : '',
      euribor_2: euribor ? moved(euribor, 1) : '',
      euribor_3: euribor ? moved(euribor, -0.5) : '',
      offers: [offer('Fija', 'fixed', '0'), offer('Variable', 'variable', '12')],
    }
  },
  finalize: ({ euribor_1, euribor_2, euribor_3, ...body }) => ({
    ...body,
    euribor: [euribor_1, euribor_2, euribor_3].filter((value) => value !== undefined),
  }),
  restore: ({ euribor, ...body }) => {
    const values = (euribor as string[] | undefined) ?? []
    return Object.fromEntries([
      ...Object.entries(body),
      ...values.map((value, index) => [SCENARIOS[index], value]),
    ]) as Record<string, unknown>
  },
  Result: MortgageView,
  metrics: (result, t) =>
    result.offers.flatMap((item) => {
      const first = item.scenarios[0]
      if (!first) return []
      const best = chosen(first)
      return [
        {
          label: t('calc.mortgage.metricPayment', { name: item.name }),
          value: formatAmount(best.first_payment),
        },
        {
          label: t('calc.mortgage.metricCost', { name: item.name }),
          value: formatAmount(best.total_cost),
        },
      ]
    }),
})

function laterPayment(outcome: MortgageOutcome) {
  return outcome.later_payment ? formatAmount(outcome.later_payment) : '—'
}

function MortgageView({ result }: ResultProps<MortgageResult>) {
  const { t } = useTranslation()
  const [index, setIndex] = useState(0)
  const count = result.offers[0]?.scenarios.length ?? 0
  const current = Math.min(index, count - 1)
  const scenarios = result.offers.map((item) => item.scenarios[current]!)
  const best = result.cheapest[current] ?? 0
  const bestOffer = result.offers[best]
  const columns = result.offers.map((item) => item.name)

  return (
    <>
      {count > 1 && (
        <div className="segmented" role="radiogroup" aria-label={t('calc.mortgage.scenario')}>
          {result.offers[0]!.scenarios.map((scenario, i) => (
            <button
              key={i}
              type="button"
              role="radio"
              aria-checked={i === current}
              className="segmented__option"
              onClick={() => setIndex(i)}
            >
              {t('calc.mortgage.euriborAt', { value: formatRate(scenario.euribor) })}
            </button>
          ))}
        </div>
      )}
      {bestOffer && (
        <Headline
          caption={t('calc.mortgage.cheapest', { name: bestOffer.name })}
          value={<Money value={chosen(scenarios[best]!).total_cost} />}
        />
      )}
      <CompareTable
        label={t('calc.mortgage.table')}
        columns={columns}
        best={best}
        rows={[
          {
            label: t('calc.mortgage.firstPayment'),
            values: scenarios.map((s) => formatAmount(chosen(s).first_payment)),
          },
          {
            label: t('calc.mortgage.laterPayment'),
            values: scenarios.map((s) => laterPayment(chosen(s))),
          },
          {
            label: t('calc.mortgage.interest'),
            values: scenarios.map((s) => formatAmount(chosen(s).interest)),
          },
          {
            label: t('calc.mortgage.linked'),
            values: scenarios.map((s) => formatAmount(chosen(s).linked_cost)),
          },
          {
            label: t('calc.mortgage.totalCost'),
            values: scenarios.map((s) => (
              <strong key="total">{formatAmount(chosen(s).total_cost)}</strong>
            )),
          },
          {
            label: t('calc.mortgage.discounts'),
            values: scenarios.map((s) => {
              const saves = Number(s.discount_saves)
              if (s.with_discount.total_cost === s.without_discount.total_cost) {
                return t('calc.mortgage.noDiscount')
              }
              return saves > 0
                ? t('calc.mortgage.discountPays', { amount: formatAmount(s.discount_saves) })
                : t('calc.mortgage.discountCosts', {
                    amount: formatAmount(String(-saves)),
                  })
            }),
          },
        ]}
      />
      <p className="muted small">{t('calc.mortgage.note')}</p>
      {result.offers.map((item, i) => {
        const outcome = chosen(scenarios[i]!)
        return (
          <details key={item.name + i} className="card">
            <summary>{t('calc.mortgage.yearly', { name: item.name })}</summary>
            <div
              className="details-body table-scroll"
              role="region"
              tabIndex={0}
              aria-label={t('calc.mortgage.yearly', { name: item.name })}
            >
              <table className="sample">
                <thead>
                  <tr>
                    <th>{t('calc.compound.year')}</th>
                    <th>{t('loans.cols.payment')}</th>
                    <th>{t('loans.cols.interest')}</th>
                    <th>{t('loans.cols.principal')}</th>
                    <th>{t('loans.cols.outstanding')}</th>
                  </tr>
                </thead>
                <tbody>
                  {outcome.years.map((row) => (
                    <tr key={row.year}>
                      <td>{row.year}</td>
                      <td>{formatAmount(row.payment)}</td>
                      <td>{formatAmount(row.interest)}</td>
                      <td>{formatAmount(row.principal)}</td>
                      <td>{formatAmount(row.outstanding)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )
      })}
      <EuriborHint />
    </>
  )
}

function EuriborHint() {
  const { t } = useTranslation()
  return (
    <p className="muted small">
      {t('calc.mortgage.euriborHint')}{' '}
      <Link to="/planificar/euribor">{t('loans.euriborTable')}</Link>
    </p>
  )
}
