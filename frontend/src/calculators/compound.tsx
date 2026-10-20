import { useTranslation } from 'react-i18next'

import type { CompoundResult } from '../api/calculators'
import { Money } from '../components/Money'
import { formatAmount } from '../lib/format'
import { Figures, Headline, References } from './parts'
import { contextAmount, define, type ResultProps } from './types'

/** Ahorro e interés compuesto (RF-CAL-01). */
export const compound = define<CompoundResult>({
  name: 'compound',
  slug: 'interes-compuesto',
  icon: '📈',
  group: 'saving',
  sections: [
    {
      fields: [
        { key: 'initial', kind: 'amount', label: 'calc.f.initial', optional: true },
        { key: 'monthly', kind: 'amount', label: 'calc.f.monthly', optional: true },
        { key: 'annual_return', kind: 'rate', label: 'calc.f.annualReturn', help: 'calc.h.return' },
        { key: 'years', kind: 'int', label: 'calc.f.years' },
        { key: 'inflation', kind: 'rate', label: 'calc.f.inflation', optional: true },
        {
          key: 'yearly_increase',
          kind: 'rate',
          label: 'calc.f.yearlyIncrease',
          optional: true,
        },
        {
          key: 'tax_mode',
          kind: 'segmented',
          label: 'calc.f.taxMode',
          help: 'calc.h.taxMode',
          options: [
            { value: 'end', label: 'calc.o.taxEnd' },
            { value: 'yearly', label: 'calc.o.taxYearly' },
            { value: 'none', label: 'calc.o.taxNone' },
          ],
        },
      ],
    },
  ],
  defaults: (context) => ({
    initial: '',
    monthly: contextAmount(context?.saved),
    annual_return: '4',
    years: '10',
    inflation: '2',
    yearly_increase: '',
    tax_mode: 'end',
  }),
  Result: CompoundView,
  metrics: (result, t) => [
    { label: t('calc.compound.final'), value: formatAmount(result.final) },
    { label: t('calc.compound.real'), value: formatAmount(result.final_real) },
    { label: t('calc.compound.contributed'), value: formatAmount(result.contributed) },
    { label: t('calc.compound.tax'), value: formatAmount(result.tax) },
  ],
})

function CompoundView({ result }: ResultProps<CompoundResult>) {
  const { t } = useTranslation()
  const years = result.years
  const highest = Math.max(...years.map((y) => Number(y.balance)), 1)
  return (
    <>
      <Headline caption={t('calc.compound.final')} value={<Money value={result.final} />} />
      <Figures
        rows={[
          { label: t('calc.compound.contributed'), value: <Money value={result.contributed} /> },
          { label: t('calc.compound.gains'), value: <Money value={result.gains} /> },
          { label: t('calc.compound.tax'), value: <Money value={result.tax} /> },
          { label: t('calc.compound.real'), value: <Money value={result.final_real} /> },
        ]}
      />
      <figure className="growth" aria-label={t('calc.compound.chart')}>
        <div className="growth__bars" aria-hidden="true">
          {years.map((year) => {
            const contributed = Math.min(Number(year.contributed), Number(year.balance))
            const gains = Math.max(Number(year.balance) - contributed, 0)
            return (
              <div key={year.year} className="growth__bar" title={`${year.year}`}>
                <span className="growth__gains" style={{ height: `${(gains / highest) * 100}%` }} />
                <span
                  className="growth__contributed"
                  style={{ height: `${(contributed / highest) * 100}%` }}
                />
              </div>
            )
          })}
        </div>
        <figcaption className="legend small">
          <span className="legend__item">
            <span className="legend__swatch growth__contributed" />
            {t('calc.compound.contributed')}
          </span>
          <span className="legend__item">
            <span className="legend__swatch growth__gains" />
            {t('calc.compound.gainsLegend')}
          </span>
          <span className="muted">{t('calc.compound.axis', { count: years.length })}</span>
        </figcaption>
      </figure>
      <details>
        <summary>{t('calc.compound.table')}</summary>
        <div
          className="details-body table-scroll"
          role="region"
          tabIndex={0}
          aria-label={t('calc.compound.table')}
        >
          <table className="sample">
            <thead>
              <tr>
                <th>{t('calc.compound.year')}</th>
                <th>{t('calc.compound.contributed')}</th>
                <th>{t('calc.compound.gains')}</th>
                <th>{t('calc.compound.tax')}</th>
                <th>{t('calc.compound.balance')}</th>
                <th>{t('calc.compound.realShort')}</th>
              </tr>
            </thead>
            <tbody>
              {years.map((year) => (
                <tr key={year.year}>
                  <td>{year.year}</td>
                  <td>{formatAmount(year.contributed)}</td>
                  <td>{formatAmount(year.gains)}</td>
                  <td>{formatAmount(year.tax)}</td>
                  <td>{formatAmount(year.balance)}</td>
                  <td>{formatAmount(year.real_balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <References references={result.references} />
    </>
  )
}
