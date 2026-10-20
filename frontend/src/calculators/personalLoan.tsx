import { useTranslation } from 'react-i18next'

import type { PersonalLoanResult } from '../api/calculators'
import type { ItemValues } from '../lib/calcForm'
import { formatAmount } from '../lib/format'
import { CompareTable, Headline, percent } from './parts'
import { define, type ResultProps } from './types'

const offer = (name: string): ItemValues => ({
  name,
  amount: '',
  tin: '',
  months: '60',
  opening_fee_percent: '',
  upfront_costs: '',
  monthly_costs: '',
})

/** Préstamo personal: cuota, TAE real y coste total, comparando ofertas (RF-CAL-09). */
export const personalLoan = define<PersonalLoanResult>({
  name: 'personal_loan',
  slug: 'prestamo-personal',
  icon: '💳',
  group: 'buying',
  sections: [
    {
      fields: [
        {
          kind: 'list',
          key: 'offers',
          item: 'calc.mortgage.offer',
          add: 'calc.mortgage.addOffer',
          min: 1,
          max: 3,
          blank: (index) => offer(`Oferta ${index + 1}`),
          fields: [
            { key: 'name', kind: 'text', label: 'calc.f.name' },
            { key: 'amount', kind: 'amount', label: 'calc.f.loanAmount' },
            { key: 'tin', kind: 'rate', label: 'calc.f.tin' },
            { key: 'months', kind: 'int', label: 'calc.f.termMonths' },
            {
              key: 'opening_fee_percent',
              kind: 'rate',
              label: 'calc.f.openingFee',
              optional: true,
            },
            { key: 'upfront_costs', kind: 'amount', label: 'calc.f.otherUpfront', optional: true },
            {
              key: 'monthly_costs',
              kind: 'amount',
              label: 'calc.f.monthlyCosts',
              optional: true,
              help: 'calc.h.monthlyCosts',
            },
          ],
        },
      ],
    },
  ],
  defaults: () => ({ offers: [offer('Oferta 1'), offer('Oferta 2')] }),
  Result: PersonalLoanView,
  metrics: (result, t) =>
    result.offers.flatMap((item) => [
      { label: t('calc.loan.metricApr', { name: item.name }), value: percent(item.apr) },
      {
        label: t('calc.loan.metricCost', { name: item.name }),
        value: formatAmount(item.total_cost),
      },
    ]),
})

function PersonalLoanView({ result }: ResultProps<PersonalLoanResult>) {
  const { t } = useTranslation()
  const offers = result.offers
  const best = offers[result.cheapest]
  const row = (label: string, pick: (o: (typeof offers)[number]) => string) => ({
    label,
    values: offers.map(pick),
  })
  return (
    <>
      {best && (
        <Headline
          caption={t('calc.loan.cheapest', { name: best.name })}
          value={formatAmount(best.total_cost)}
        />
      )}
      <CompareTable
        label={t('calc.loan.table')}
        columns={offers.map((o) => o.name)}
        best={result.cheapest}
        rows={[
          row(t('calc.loan.payment'), (o) => formatAmount(o.payment)),
          row(t('calc.loan.monthlyTotal'), (o) => formatAmount(o.monthly_total)),
          row(t('calc.loan.apr'), (o) => percent(o.apr)),
          row(t('calc.loan.interest'), (o) => formatAmount(o.interest)),
          row(t('calc.loan.fees'), (o) => formatAmount(o.fees)),
          row(t('calc.loan.extras'), (o) => formatAmount(o.extras)),
          row(t('calc.loan.totalCost'), (o) => formatAmount(o.total_cost)),
          row(t('calc.loan.totalPaid'), (o) => formatAmount(o.total_paid)),
        ]}
      />
      <p className="muted small">{t('calc.loan.note')}</p>
    </>
  )
}
