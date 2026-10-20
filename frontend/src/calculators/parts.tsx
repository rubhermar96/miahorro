import type { TFunction } from 'i18next'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Reference } from '../api/calculators'
import { formatAmount, formatDate, formatRate } from '../lib/format'

export type Row = { label: string; value: ReactNode; strong?: boolean }

/** Label–value pairs of a result. */
export function Figures({ rows }: { rows: Row[] }) {
  return (
    <dl className="details">
      {rows.map((row) => (
        <div key={row.label} className={row.strong ? 'details__strong' : undefined}>
          <dt>{row.label}</dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Headline({ caption, value }: { caption: string; value: ReactNode }) {
  return (
    <div>
      <p className="muted small">{caption}</p>
      <p className="total">{value}</p>
    </div>
  )
}

export const percent = (value: string | null | undefined) =>
  value === null || value === undefined ? '—' : `${formatRate(String(value))} %`

type Bracket = { up_to: string | null; rate: string }

/** "300000" → "300.000 €": tranche limits have no cents. */
const wholeEuros = (value: string) => formatAmount(value).replace(/,00(?=\s)/, '')

function scaleText(reference: Reference, t: TFunction): string {
  const brackets = (reference.extra?.brackets as Bracket[] | undefined) ?? []
  if (brackets.length < 2) {
    return reference.table === 'home_costs'
      ? formatAmount(reference.value)
      : percent(reference.value)
  }
  return brackets
    .map((b) =>
      b.up_to === null
        ? t('calc.refs.above', { rate: percent(b.rate) })
        : t('calc.refs.upTo', { rate: percent(b.rate), limit: wholeEuros(b.up_to) }),
    )
    .join(', ')
}

/** The reference values a result used, with their date and source, so they can be checked. */
export function References({ references }: { references: Reference[] }) {
  const { t } = useTranslation()
  if (references.length === 0) {
    return null
  }
  return (
    <details className="card">
      <summary>{t('calc.refs.title')}</summary>
      <ul className="details-body stack stack--tight refs">
        {references.map((ref) => (
          <li key={`${ref.table}-${ref.key}`} className="small">
            <strong>
              {ref.table_label}
              {ref.label !== ref.key || ref.table === 'itp' || ref.table === 'ajd'
                ? ` · ${ref.label}`
                : ''}
              :
            </strong>{' '}
            {scaleText(ref, t)}
            <br />
            <span className="muted">
              {t('calc.refs.since', { date: formatDate(ref.valid_from) })} ·{' '}
              {t('calc.refs.source', { source: ref.source })}
            </span>
            {ref.note && (
              <>
                <br />
                <span className="muted">{ref.note}</span>
              </>
            )}
          </li>
        ))}
      </ul>
    </details>
  )
}

export function Warnings({ warnings }: { warnings: string[] }) {
  return (
    <>
      {warnings.map((warning) => (
        <p key={warning} className="notice small">
          {warning}
        </p>
      ))}
    </>
  )
}

/** Options side by side: one column each, the best one marked. */
export function CompareTable({
  label,
  columns,
  rows,
  best,
}: {
  label: string
  columns: string[]
  rows: { label: string; values: ReactNode[] }[]
  best?: number
}) {
  const { t } = useTranslation()
  return (
    <div className="table-scroll" role="region" aria-label={label} tabIndex={0}>
      <table className="sample compare">
        <thead>
          <tr>
            <th scope="col">
              <span className="visually-hidden">{t('calc.concept')}</span>
            </th>
            {columns.map((column, index) => (
              <th
                key={column + index}
                scope="col"
                className={index === best ? 'compare__best' : ''}
              >
                {column}
                {index === best && <span className="tag">{t('calc.best')}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              {row.values.map((value, index) => (
                <td key={index} className={index === best ? 'compare__best' : ''}>
                  {value}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
