import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import type { CarOutcome, CarResult } from '../api/calculators'
import type { ItemValues } from '../lib/calcForm'
import { formatAmount } from '../lib/format'
import { CompareTable, Headline, percent, References } from './parts'
import { define, type ResultProps } from './types'

const financed = (own: ItemValues) => own.kind === 'loan' || own.kind === 'pcp'
const notCash = (own: ItemValues) => own.kind !== 'cash'

const option = (name: string, kind: string): ItemValues => ({
  name,
  kind,
  down_payment: '',
  rate: '',
  months: kind === 'cash' ? '' : '60',
  opening_fee_percent: '',
  final_payment: '',
  keep: true,
  monthly_fee: '',
})

const perKm = (value: string | null | undefined) =>
  value === null || value === undefined ? '—' : `${value.replace('.', ',')} €`

/** Compra de coche: contado, préstamo, multiopción o renting por coste total (RF-CAL-07). */
export const car = define<CarResult>({
  name: 'car',
  slug: 'comprar-coche',
  icon: '🚗',
  group: 'buying',
  sections: [
    {
      title: 'calc.car.car',
      fields: [
        { key: 'price', kind: 'amount', label: 'calc.f.carPrice' },
        { key: 'co2', kind: 'int', label: 'calc.f.co2', help: 'calc.h.co2' },
        { key: 'registration_included', kind: 'check', label: 'calc.f.registrationIncluded' },
        { key: 'years', kind: 'int', label: 'calc.f.useYears' },
        { key: 'km_per_year', kind: 'int', label: 'calc.f.kmPerYear' },
        {
          key: 'resale_value',
          kind: 'amount',
          label: 'calc.f.resale',
          optional: true,
          placeholder: 'calc.car.estimated',
        },
      ],
    },
    {
      title: 'calc.car.running',
      fields: [
        { key: 'consumption', kind: 'rate', label: 'calc.f.consumption' },
        { key: 'energy_price', kind: 'rate', label: 'calc.f.energyPrice' },
        { key: 'insurance', kind: 'amount', label: 'calc.f.insurance', optional: true },
        { key: 'road_tax', kind: 'amount', label: 'calc.f.roadTax', optional: true },
        { key: 'maintenance', kind: 'amount', label: 'calc.f.maintenance', optional: true },
        { key: 'itv_cost', kind: 'amount', label: 'calc.f.itvCost', optional: true },
      ],
    },
    {
      title: 'calc.car.options',
      fields: [
        {
          kind: 'list',
          key: 'options',
          item: 'calc.car.option',
          add: 'calc.car.addOption',
          min: 1,
          max: 4,
          blank: (index) => option(`Opción ${index + 1}`, 'loan'),
          fields: [
            { key: 'name', kind: 'text', label: 'calc.f.name' },
            {
              key: 'kind',
              kind: 'select',
              label: 'calc.f.payment',
              options: [
                { value: 'cash', label: 'calc.car.kinds.cash' },
                { value: 'loan', label: 'calc.car.kinds.loan' },
                { value: 'pcp', label: 'calc.car.kinds.pcp' },
                { value: 'renting', label: 'calc.car.kinds.renting' },
              ],
            },
            {
              key: 'down_payment',
              kind: 'amount',
              label: 'calc.f.downPayment',
              optional: true,
              when: notCash,
            },
            { key: 'months', kind: 'int', label: 'calc.f.termMonths', when: notCash },
            { key: 'rate', kind: 'rate', label: 'calc.f.tin', optional: true, when: financed },
            {
              key: 'opening_fee_percent',
              kind: 'rate',
              label: 'calc.f.openingFee',
              optional: true,
              when: financed,
            },
            {
              key: 'final_payment',
              kind: 'amount',
              label: 'calc.f.finalPayment',
              when: (own) => own.kind === 'pcp',
            },
            {
              key: 'keep',
              kind: 'check',
              label: 'calc.f.keepCar',
              when: (own) => own.kind === 'pcp',
            },
            {
              key: 'monthly_fee',
              kind: 'amount',
              label: 'calc.f.rentingFee',
              when: (own) => own.kind === 'renting',
            },
          ],
        },
      ],
    },
  ],
  defaults: () => ({
    price: '',
    co2: '',
    registration_included: true,
    years: '8',
    km_per_year: '15000',
    resale_value: '',
    consumption: '',
    energy_price: '',
    insurance: '',
    road_tax: '',
    maintenance: '',
    itv_cost: '45',
    options: [option('Contado', 'cash'), option('Préstamo', 'loan')],
  }),
  Result: CarView,
  metrics: (result, t) =>
    result.options.map((item) => ({
      label: t('calc.car.metric', { name: item.name }),
      value: formatAmount(item.per_year),
    })),
})

function horizon(outcome: CarOutcome, t: TFunction) {
  const years = outcome.months / 12
  return Number.isInteger(years)
    ? t('calc.car.years', { count: years })
    : t('calc.goal.months', { count: outcome.months })
}

function CarView({ result }: ResultProps<CarResult>) {
  const { t } = useTranslation()
  const options = result.options
  const best = options[result.cheapest]
  const row = (label: string, pick: (o: CarOutcome) => string) => ({
    label,
    values: options.map(pick),
  })
  return (
    <>
      {best && (
        <Headline
          caption={t('calc.car.cheapest', { name: best.name })}
          value={t('calc.car.perYearValue', { amount: formatAmount(best.per_year) })}
        />
      )}
      <p className="muted small">
        {t('calc.car.registration', {
          amount: formatAmount(result.registration),
          rate: percent(result.registration_rate),
        })}
      </p>
      <CompareTable
        label={t('calc.car.table')}
        columns={options.map((o) => o.name)}
        best={result.cheapest}
        rows={[
          row(t('calc.car.upfront'), (o) => formatAmount(o.upfront)),
          row(t('calc.car.monthly'), (o) => (o.monthly === '0.00' ? '—' : formatAmount(o.monthly))),
          row(t('calc.car.final'), (o) =>
            o.final_payment === '0.00' ? '—' : formatAmount(o.final_payment),
          ),
          row(t('calc.car.financing'), (o) => formatAmount(o.financing)),
          row(t('calc.car.apr'), (o) => percent(o.apr)),
          row(t('calc.car.energy'), (o) => formatAmount(o.running.energy)),
          row(t('calc.car.insurance'), (o) => formatAmount(o.running.insurance)),
          row(t('calc.car.roadTax'), (o) => formatAmount(o.running.road_tax)),
          row(t('calc.car.maintenance'), (o) => formatAmount(o.running.maintenance)),
          row(t('calc.car.itv'), (o) => formatAmount(o.running.itv)),
          row(t('calc.car.resale'), (o) =>
            o.resale === '0.00' ? '—' : `−${formatAmount(o.resale)}`,
          ),
          {
            label: t('calc.car.total'),
            values: options.map((o) => (
              <strong key="total">
                {formatAmount(o.total)}
                <br />
                <small className="muted">{horizon(o, t)}</small>
              </strong>
            )),
          },
          row(t('calc.car.perYear'), (o) => formatAmount(o.per_year)),
          row(t('calc.car.perKm'), (o) => perKm(o.per_km)),
        ]}
      />
      {result.resale_estimated && <p className="muted small">{t('calc.car.resaleNote')}</p>}
      <p className="muted small">{t('calc.car.note')}</p>
      <References references={result.references} />
    </>
  )
}
