import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import type { HomeResult } from '../api/calculators'
import { Money } from '../components/Money'
import { formatAmount, formatMonthYear } from '../lib/format'
import { Figures, Headline, percent, References, type Row, Warnings } from './parts'
import { contextAmount, define, type ResultProps } from './types'

/** Regions as the API names them (HomeIn.region), in the order people look for them. */
export const REGIONS: { value: string; label: string }[] = [
  { value: 'andalucia', label: 'Andalucía' },
  { value: 'aragon', label: 'Aragón' },
  { value: 'asturias', label: 'Asturias' },
  { value: 'baleares', label: 'Illes Balears' },
  { value: 'canarias', label: 'Canarias' },
  { value: 'cantabria', label: 'Cantabria' },
  { value: 'castilla_la_mancha', label: 'Castilla-La Mancha' },
  { value: 'castilla_y_leon', label: 'Castilla y León' },
  { value: 'cataluna', label: 'Cataluña' },
  { value: 'valencia', label: 'Comunitat Valenciana' },
  { value: 'extremadura', label: 'Extremadura' },
  { value: 'galicia', label: 'Galicia' },
  { value: 'madrid', label: 'Comunidad de Madrid' },
  { value: 'murcia', label: 'Región de Murcia' },
  { value: 'navarra', label: 'Navarra' },
  { value: 'pais_vasco', label: 'País Vasco' },
  { value: 'la_rioja', label: 'La Rioja' },
]

/** Compra de vivienda: impuestos, gastos, hipoteca y si te la puedes permitir (RF-CAL-04). */
export const home = define<HomeResult>({
  name: 'home',
  slug: 'comprar-vivienda',
  icon: '🏠',
  group: 'buying',
  sections: [
    {
      title: 'calc.home.home',
      fields: [
        { key: 'price', kind: 'amount', label: 'calc.f.price' },
        {
          key: 'region',
          kind: 'select',
          label: 'calc.f.region',
          options: [{ value: '', label: 'calc.home.pickRegion' }, ...REGIONS],
        },
        { key: 'new_build', kind: 'check', label: 'calc.f.newBuild' },
        {
          key: 'tax_rate',
          kind: 'rate',
          label: 'calc.f.ownTaxRate',
          optional: true,
          help: 'calc.h.ownTaxRate',
        },
      ],
    },
    {
      title: 'calc.home.mortgage',
      fields: [
        { key: 'financed_percent', kind: 'rate', label: 'calc.f.financed' },
        { key: 'annual_rate', kind: 'rate', label: 'calc.f.tin' },
        { key: 'years', kind: 'int', label: 'calc.f.termYears' },
      ],
    },
    {
      title: 'calc.home.costs',
      fields: [
        {
          key: 'notary',
          kind: 'amount',
          label: 'calc.f.notary',
          optional: true,
          placeholder: 'calc.home.estimate',
        },
        {
          key: 'registry',
          kind: 'amount',
          label: 'calc.f.registry',
          optional: true,
          placeholder: 'calc.home.estimate',
        },
        {
          key: 'gestoria',
          kind: 'amount',
          label: 'calc.f.gestoria',
          optional: true,
          placeholder: 'calc.home.estimate',
        },
        {
          key: 'appraisal',
          kind: 'amount',
          label: 'calc.f.appraisal',
          optional: true,
          placeholder: 'calc.home.estimate',
        },
        { key: 'agency_percent', kind: 'rate', label: 'calc.f.agency', optional: true },
      ],
    },
    {
      title: 'calc.home.you',
      fields: [
        { key: 'net_income', kind: 'amount', label: 'calc.f.netIncome', optional: true },
        { key: 'other_debts', kind: 'amount', label: 'calc.f.otherDebts', optional: true },
        { key: 'max_ratio', kind: 'rate', label: 'calc.f.maxRatio', help: 'calc.h.maxRatio' },
        { key: 'savings', kind: 'amount', label: 'calc.f.savings', optional: true },
        { key: 'monthly_saving', kind: 'amount', label: 'calc.f.savePerMonth', optional: true },
      ],
    },
  ],
  defaults: (context) => ({
    price: '',
    region: '',
    new_build: false,
    tax_rate: '',
    financed_percent: '80',
    annual_rate: '',
    years: '30',
    notary: '',
    registry: '',
    gestoria: '',
    appraisal: '',
    agency_percent: '',
    net_income: contextAmount(context?.income),
    other_debts: contextAmount(context?.loan_payments),
    max_ratio: '35',
    savings: contextAmount(context?.liquidity),
    monthly_saving: contextAmount(context?.saved),
  }),
  Result: HomeView,
  metrics: (result, t) => [
    { label: t('calc.home.tax', { name: result.tax_name }), value: formatAmount(result.tax) },
    { label: t('calc.home.totalCosts'), value: formatAmount(result.costs) },
    { label: t('calc.home.cashNeeded'), value: formatAmount(result.cash_needed) },
    { label: t('calc.home.payment'), value: formatAmount(result.payment) },
    { label: t('calc.home.ratio'), value: percent(result.debt_ratio) },
    {
      label: t('calc.home.maxPrice'),
      value: result.max_price ? formatAmount(result.max_price) : '—',
    },
  ],
})

function whenToBuy(result: HomeResult, t: TFunction): string {
  if (result.months_to_buy === 0) return t('calc.home.buyNow')
  if (result.months_to_buy && result.buy_date) {
    return t('calc.home.buyOn', {
      date: formatMonthYear(result.buy_date),
      count: result.months_to_buy,
    })
  }
  return t('calc.home.buyNever')
}

function HomeView({ result, values }: ResultProps<HomeResult>) {
  const { t } = useTranslation()
  const optional = (label: string, amount: string): Row[] =>
    amount === '0.00' ? [] : [{ label, value: <Money value={amount} /> }]
  const hasSavings = String(values.savings ?? '').trim() !== ''
  return (
    <>
      <Headline caption={t('calc.home.cashNeeded')} value={<Money value={result.cash_needed} />} />
      <p className="muted small">
        {t('calc.home.cashExplained', {
          down: formatAmount(result.down_payment),
          costs: formatAmount(result.costs),
        })}
      </p>
      <Figures
        rows={[
          {
            label: t('calc.home.tax', { name: result.tax_name }),
            value: <Money value={result.tax} />,
          },
          ...optional(t('calc.home.ajd'), result.ajd),
          { label: t('calc.home.notary'), value: <Money value={result.notary} /> },
          { label: t('calc.home.registry'), value: <Money value={result.registry} /> },
          { label: t('calc.home.gestoria'), value: <Money value={result.gestoria} /> },
          ...optional(t('calc.home.appraisal'), result.appraisal),
          ...optional(t('calc.home.agency'), result.agency),
          { label: t('calc.home.totalCosts'), value: <Money value={result.costs} />, strong: true },
          { label: t('calc.home.mortgageAmount'), value: <Money value={result.mortgage} /> },
          { label: t('calc.home.total'), value: <Money value={result.total} /> },
        ]}
      />
      <h3>{t('calc.home.afford')}</h3>
      <Figures
        rows={[
          { label: t('calc.home.payment'), value: <Money value={result.payment} /> },
          ...(result.debt_ratio !== null && result.debt_ratio !== undefined
            ? [{ label: t('calc.home.ratio'), value: percent(result.debt_ratio) }]
            : []),
          { label: t('calc.home.maxPayment'), value: <Money value={result.max_payment} /> },
          ...(result.max_price
            ? [
                {
                  label: t(`calc.home.maxPriceBy.${result.limited_by ?? 'income'}`),
                  value: <Money value={result.max_price} />,
                },
              ]
            : []),
          ...(hasSavings ? [{ label: t('calc.home.when'), value: whenToBuy(result, t) }] : []),
        ]}
      />
      <Warnings warnings={result.warnings} />
      <References references={result.references} />
    </>
  )
}
