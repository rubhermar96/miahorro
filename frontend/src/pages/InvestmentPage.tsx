import { useQueryClient } from '@tanstack/react-query'
import type { TFunction } from 'i18next'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import { refreshFinance } from '../api/finance'
import {
  type InvestmentDetail,
  investmentKeys,
  investmentsApi,
  type Operation,
  useInvestment,
  useInvestments,
  useOperations,
  usePrices,
} from '../api/investments'
import { ErrorMessage } from '../components/ErrorMessage'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { messageOf } from '../lib/errors'
import { formatAmount, formatDate, formatSignedPercent, todayIso } from '../lib/format'
import { formatPrice, formatUnits, parseUnitsInput } from '../lib/units'

const STALE_DAYS = 31

/** One investment: what it holds and is worth, its operations, lots and prices (RF-INV). */
export function InvestmentPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const investment = useInvestment(id)
  if (!investment.data) {
    return <PageHeader title={t('inv.title')} back="/inversiones" />
  }
  return <Details investment={investment.data} />
}

function useRefresh() {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: investmentKeys.all }),
      refreshFinance(queryClient),
    ])
}

function daysSince(isoDate: string): number {
  const then = new Date(`${isoDate}T12:00:00`)
  const now = new Date(`${todayIso()}T12:00:00`)
  return Math.round((now.getTime() - then.getTime()) / 86_400_000)
}

function Details({ investment }: { investment: InvestmentDetail }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const refresh = useRefresh()
  const [error, setError] = useState<string | null>(null)
  const held = investment.units !== '0'
  const stale = held && investment.price_date && daysSince(investment.price_date) > STALE_DAYS

  const toggleArchived = async () => {
    await investmentsApi.update(investment.id, { archived: !investment.archived })
    await refresh()
  }

  const remove = async () => {
    if (!window.confirm(t('inv.confirmDelete', { name: investment.name }))) {
      return
    }
    try {
      await investmentsApi.remove(investment.id)
      await refresh()
      void navigate('/inversiones', { replace: true })
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  return (
    <>
      <PageHeader title={investment.name} back="/inversiones" />
      <div className="stack">
        <section className="card stack stack--tight" aria-label={t('inv.situation')}>
          <p className="muted small">
            {[t(`inv.kinds.${investment.kind}`), investment.isin, investment.ticker]
              .filter(Boolean)
              .join(' · ')}
          </p>
          <p className="total">
            {investment.value !== null && investment.value !== undefined ? (
              <Money value={investment.value} />
            ) : (
              t('inv.noPrice')
            )}
          </p>
          {investment.gain !== null && investment.gain !== undefined && held && (
            <p className="small">
              <Money value={investment.gain} signed />
              {investment.gain_percent !== null && investment.gain_percent !== undefined && (
                <span className="muted"> ({formatSignedPercent(investment.gain_percent)})</span>
              )}{' '}
              <span className="muted">{t('inv.unrealized')}</span>
            </p>
          )}
          <dl className="details">
            <div>
              <dt>{t(`inv.unitsOf.${investment.kind}`)}</dt>
              <dd>{formatUnits(investment.units)}</dd>
            </div>
            {investment.average_cost && (
              <div>
                <dt>{t('inv.averageCost')}</dt>
                <dd>{formatPrice(investment.average_cost)}</dd>
              </div>
            )}
            <div>
              <dt>{t('inv.invested')}</dt>
              <dd>
                <Money value={investment.cost} />
              </dd>
            </div>
            {investment.price && investment.price_date && (
              <div>
                <dt>{t('inv.price')}</dt>
                <dd>
                  {formatPrice(investment.price)}
                  <br />
                  <small className="muted">
                    {t(`inv.priceFrom.${investment.price_source ?? 'manual'}`, {
                      date: formatDate(investment.price_date),
                    })}
                  </small>
                </dd>
              </div>
            )}
            <div>
              <dt>{t('inv.realizedTotal')}</dt>
              <dd>
                <Money value={investment.realized_total} signed />
              </dd>
            </div>
            {investment.dividends_year !== '0.00' && (
              <div>
                <dt>{t('inv.dividendsThisYear')}</dt>
                <dd>
                  <Money value={investment.dividends_year} />
                </dd>
              </div>
            )}
          </dl>
          {stale && investment.price_date && (
            <p className="notice small">
              {t('inv.stalePrice', { date: formatDate(investment.price_date) })}
            </p>
          )}
        </section>

        <Link className="button" to={`/inversiones/${investment.id}/operaciones/nueva`}>
          {t('inv.addOperation')}
        </Link>

        {held && <PriceForm investment={investment} />}
        <Operations investment={investment} />
        <Lots investment={investment} />
        <Prices investment={investment} />

        <section className="card stack stack--tight">
          <Link className="button button--secondary" to={`/inversiones/${investment.id}/editar`}>
            {t('inv.edit')}
          </Link>
          <button
            type="button"
            className="button button--secondary"
            onClick={() => void toggleArchived()}
          >
            {investment.archived ? t('inv.unarchive') : t('inv.archive')}
          </button>
          <button
            type="button"
            className="button button--ghost button--danger"
            onClick={() => void remove()}
          >
            {t('inv.delete')}
          </button>
          <ErrorMessage message={error} />
        </section>
      </div>
    </>
  )
}

function PriceForm({ investment }: { investment: InvestmentDetail }) {
  const { t } = useTranslation()
  const refresh = useRefresh()
  const [date, setDate] = useState(todayIso())
  const [priceText, setPriceText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setMessage(null)
    const price = parseUnitsInput(priceText)
    if (!price) {
      setError(t('inv.invalidPrice'))
      return
    }
    try {
      await investmentsApi.setPrice(investment.id, date, price)
      setPriceText('')
      setMessage(t('inv.priceSaved'))
      await refresh()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  return (
    <form className="card stack stack--tight" onSubmit={(event) => void save(event)}>
      <h2>{t('inv.updatePrice')}</h2>
      <div className="grid-2">
        <label className="field">
          <span>{t('inv.pricePerUnit')}</span>
          <input
            inputMode="decimal"
            required
            value={priceText}
            onChange={(event) => setPriceText(event.target.value)}
          />
        </label>
        <label className="field">
          <span>{t('add.date')}</span>
          <input
            type="date"
            required
            max={todayIso()}
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </label>
      </div>
      <small className="muted">{t('inv.priceHelp')}</small>
      <button type="submit" className="button button--secondary">
        {t('inv.savePrice')}
      </button>
      <ErrorMessage message={error} />
      {message && (
        <p className="saved" role="status">
          {message}
        </p>
      )}
    </form>
  )
}

function operationDetail(
  op: Operation,
  kind: string,
  names: Map<string, string>,
  t: TFunction,
): string {
  const units = formatUnits(op.units)
  switch (op.kind) {
    case 'buy':
    case 'sell':
      return t('inv.opLine.trade', {
        units,
        price: op.price ? formatPrice(op.price) : '—',
      })
    case 'dividend':
      return op.withholding !== '0.00'
        ? t('inv.opLine.withheld', { amount: formatAmount(op.withholding) })
        : ''
    case 'split':
      return t('inv.opLine.split', { from: op.split_from, to: op.split_to })
    case 'transfer':
      return op.direction === 'in'
        ? t('inv.opLine.transferIn', {
            units: formatUnits(op.target_units ?? '0'),
            name: names.get(op.investment_id) ?? '—',
          })
        : t('inv.opLine.transferOut', {
            units,
            name: names.get(op.target_investment_id ?? '') ?? '—',
          })
    default:
      return kind
  }
}

function Operations({ investment }: { investment: InvestmentDetail }) {
  const { t } = useTranslation()
  const operations = useOperations(investment.id)
  const all = useInvestments(true)
  const names = new Map((all.data ?? []).map((item) => [item.id, item.name]))
  const list = operations.data ?? []
  if (list.length === 0) {
    return operations.isSuccess ? <p className="card muted">{t('inv.noOperations')}</p> : null
  }
  return (
    <section className="stack stack--tight" aria-labelledby="operations-title">
      <h2 id="operations-title" className="section-title">
        {t('inv.operations')}
      </h2>
      <ul className="list card card--flush">
        {list.map((op) => {
          const pension =
            investment.kind === 'pension_plan' && (op.kind === 'buy' || op.kind === 'sell')
          const label =
            op.kind === 'transfer'
              ? t(`inv.ops.transfer_${op.direction}`)
              : t(`inv.${pension ? 'opsPension' : 'ops'}.${op.kind}`)
          const detail = operationDetail(op, label, names, t)
          const owner = op.direction === 'in' ? op.investment_id : investment.id
          const shown = op.kind === 'split' ? null : op.amount
          return (
            <li key={`${op.id}-${op.direction}`}>
              <Link className="row" to={`/inversiones/${owner}/operaciones/${op.id}`}>
                <span className="row__text">
                  <span className="row__title">{label}</span>
                  <small className="muted">
                    {[formatDate(op.date), detail].filter(Boolean).join(' · ')}
                  </small>
                </span>
                <span className="row__amounts">
                  {shown && shown !== '0.00' && <Money value={shown} />}
                  {op.gain !== null && op.gain !== undefined && (
                    <small>
                      {t('inv.gainShort')} <Money value={op.gain} signed />
                    </small>
                  )}
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function Lots({ investment }: { investment: InvestmentDetail }) {
  const { t } = useTranslation()
  if (investment.lots.length === 0) {
    return null
  }
  return (
    <details className="card">
      <summary>{t('inv.lots', { count: investment.lots.length })}</summary>
      <div
        className="details-body table-scroll"
        role="region"
        tabIndex={0}
        aria-label={t('inv.lotsTable')}
      >
        <table className="sample">
          <thead>
            <tr>
              <th>{t('inv.acquired')}</th>
              <th>{t(`inv.unitsOf.${investment.kind}`)}</th>
              <th>{t('inv.lotCost')}</th>
            </tr>
          </thead>
          <tbody>
            {investment.lots.map((lot, index) => (
              <tr key={index}>
                <td>{formatDate(lot.acquired)}</td>
                <td>{formatUnits(lot.units)}</td>
                <td>{formatAmount(lot.cost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">{t('inv.lotsHelp')}</p>
    </details>
  )
}

function Prices({ investment }: { investment: InvestmentDetail }) {
  const { t } = useTranslation()
  const refresh = useRefresh()
  const prices = usePrices(investment.id)
  const list = prices.data ?? []
  if (list.length === 0) {
    return null
  }
  const remove = async (id: string, date: string) => {
    if (!window.confirm(t('inv.confirmRemovePrice', { date: formatDate(date) }))) {
      return
    }
    await investmentsApi.removePrice(investment.id, id)
    await refresh()
  }
  return (
    <details className="card">
      <summary>{t('inv.prices', { count: list.length })}</summary>
      <ul className="details-body list">
        {list.map((row) => (
          <li key={row.id} className="list__row">
            <span>{formatDate(row.date)}</span>
            <span>{formatPrice(row.price)}</span>
            <button
              type="button"
              className="button button--ghost button--danger"
              aria-label={t('inv.removePrice', { date: formatDate(row.date) })}
              onClick={() => void remove(row.id, row.date)}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </details>
  )
}
