import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { useSession } from '../api/auth'
import {
  type CashFlowPeriod,
  type Grouping,
  type SpendingBy,
  type SpendLine,
  useCashFlowReport,
  useNetWorthReport,
  useSpendingReport,
} from '../api/reports'
import { ColumnPairChart } from '../components/charts/ColumnPairChart'
import { LineChart } from '../components/charts/LineChart'
import { Meter } from '../components/Meter'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { negateAmount, sumAmounts } from '../lib/amount'
import {
  formatAmount,
  formatDate,
  formatMonthTick,
  formatMonthYear,
  formatRate,
  formatShortDate,
  todayIso,
} from '../lib/format'
import { monthsBetween, periodOf, shiftPeriod, yearRange } from '../lib/periods'

const VIEWS = ['patrimonio', 'flujo', 'gastos'] as const
type View = (typeof VIEWS)[number]

/** Reports (RF-INF-02, 03, 04): net worth over time, income against expenses, and where the
 * money goes. */
export function ReportsPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const asked = params.get('vista')
  const view: View = VIEWS.includes(asked as View) ? (asked as View) : 'patrimonio'

  return (
    <>
      <PageHeader title={t('reports.title')} back="/" />
      <div className="stack">
        <div className="segmented" role="radiogroup" aria-label={t('reports.view')}>
          {VIEWS.map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={view === option}
              className="segmented__option"
              onClick={() => setParams({ vista: option }, { replace: true })}
            >
              {t(`reports.views.${option}`)}
            </button>
          ))}
        </div>
        {view === 'patrimonio' && <NetWorthView />}
        {view === 'flujo' && <CashFlowView />}
        {view === 'gastos' && <SpendingView />}
      </div>
    </>
  )
}

// --- Shared bits ------------------------------------------------------------------------------

type Preset<K extends string> = { key: K; label: string }

function Presets<K extends string>({
  presets,
  value,
  onChange,
  label,
}: {
  presets: Preset<K>[]
  value: K
  onChange: (key: K) => void
  label: string
}) {
  return (
    <div className="chips" role="radiogroup" aria-label={label}>
      {presets.map((preset) => (
        <button
          key={preset.key}
          type="button"
          role="radio"
          aria-checked={value === preset.key}
          className="chip"
          onClick={() => onChange(preset.key)}
        >
          {preset.label}
        </button>
      ))}
    </div>
  )
}

function DateRange({
  start,
  end,
  onChange,
}: {
  start: string
  end: string
  onChange: (start: string, end: string) => void
}) {
  const { t } = useTranslation()
  return (
    <div className="filters">
      <label className="field">
        <span>{t('reports.from')}</span>
        <input
          type="date"
          value={start}
          max={end}
          onChange={(event) => onChange(event.target.value, end)}
        />
      </label>
      <label className="field">
        <span>{t('reports.to')}</span>
        <input
          type="date"
          value={end}
          min={start}
          onChange={(event) => onChange(start, event.target.value)}
        />
      </label>
    </div>
  )
}

function TableView({ label, children }: { label: string; children: ReactNode }) {
  const { t } = useTranslation()
  return (
    <details>
      <summary>{t('reports.table')}</summary>
      <div className="details-body table-scroll" role="region" tabIndex={0} aria-label={label}>
        <table className="sample">{children}</table>
      </div>
    </details>
  )
}

function useCustomRange(): [string, string, (start: string, end: string) => void] {
  const today = todayIso()
  const [range, setRange] = useState<[string, string]>([shiftPeriod(today, -2, 1)[0], today])
  return [range[0], range[1], (start, end) => setRange([start, end])]
}

/** "+25 %" against a previous amount; null when there is nothing to compare with. */
function change(current: string, previous: string): string | null {
  const before = Number(previous)
  if (before === 0) {
    return null
  }
  const percent = Math.round(((Number(current) - before) / before) * 100)
  return `${percent > 0 ? '+' : ''}${percent.toLocaleString('es-ES')} %`
}

// --- Net worth --------------------------------------------------------------------------------

type NetWorthPreset = 'year12' | 'thisYear' | 'all' | 'custom'

function NetWorthView() {
  const { t } = useTranslation()
  const today = todayIso()
  const [preset, setPreset] = useState<NetWorthPreset>('year12')
  const [start, end, setRange] = useCustomRange()
  const range =
    preset === 'year12'
      ? {}
      : preset === 'thisYear'
        ? { start: yearRange(today)[0] }
        : preset === 'all'
          ? { start: '2000-01-01' }
          : { start, end }
  const report = useNetWorthReport(range)
  const points = report.data?.points ?? []
  const first = points[0]
  const last = points.at(-1)

  return (
    <section className="stack" aria-label={t('reports.views.patrimonio')}>
      <Presets
        label={t('reports.period')}
        value={preset}
        onChange={setPreset}
        presets={[
          { key: 'year12', label: t('reports.presets.year12') },
          { key: 'thisYear', label: t('reports.presets.thisYear') },
          { key: 'all', label: t('reports.presets.all') },
          { key: 'custom', label: t('reports.presets.custom') },
        ]}
      />
      {preset === 'custom' && <DateRange start={start} end={end} onChange={setRange} />}
      {report.isSuccess && points.length === 0 && (
        <p className="card muted">{t('reports.noData')}</p>
      )}
      {last && first && (
        <div className={`card stack stack--tight ${report.isPlaceholderData ? 'is-loading' : ''}`}>
          <p className="muted small">{t('reports.netWorthOn', { date: formatDate(last.date) })}</p>
          <p className="total">
            <Money value={last.total} />
          </p>
          {points.length > 1 && (
            <p className="small">
              <Money value={sumAmounts([last.total, negateAmount(first.total)])} signed />{' '}
              <span className="muted">
                {t('reports.sinceDate', { date: formatDate(first.date) })}
              </span>
            </p>
          )}
          <LineChart
            label={t('reports.netWorthChart')}
            points={points.map((point, index) => ({
              key: point.date,
              label: formatDate(point.date),
              tick: formatMonthTick(point.date, index === 0),
              value: point.total,
            }))}
          />
          <TableView label={t('reports.netWorthTable')}>
            <thead>
              <tr>
                <th>{t('reports.cols.date')}</th>
                <th>{t('dashboard.parts.accounts')}</th>
                <th>{t('dashboard.parts.investments')}</th>
                <th>{t('dashboard.parts.lent')}</th>
                <th>{t('dashboard.parts.debts')}</th>
                <th>{t('reports.cols.total')}</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.date}>
                  <td>{formatDate(point.date)}</td>
                  <td>{formatAmount(point.accounts)}</td>
                  <td>{formatAmount(point.investments)}</td>
                  <td>{formatAmount(point.lent)}</td>
                  <td>{formatAmount(negateAmount(point.debts))}</td>
                  <td>{formatAmount(point.total)}</td>
                </tr>
              ))}
            </tbody>
          </TableView>
          <p className="muted small">{t('reports.netWorthNote')}</p>
        </div>
      )}
    </section>
  )
}

// --- Income and expenses ----------------------------------------------------------------------

type FlowPreset = 'year12' | 'thisYear' | 'byYear' | 'custom'

function periodLabel(period: CashFlowPeriod, group: Grouping): string {
  return group === 'year' ? period.start.slice(0, 4) : formatMonthYear(period.start)
}

function CashFlowView() {
  const { t } = useTranslation()
  const today = todayIso()
  const [preset, setPreset] = useState<FlowPreset>('year12')
  const [start, end, setRange] = useCustomRange()
  const currentYear = Number(today.slice(0, 4))
  const query =
    preset === 'year12'
      ? { group: 'month' as const }
      : preset === 'thisYear'
        ? { start: yearRange(today)[0], end: today, group: 'month' as const }
        : preset === 'byYear'
          ? { start: `${currentYear - 4}-01-01`, end: today, group: 'year' as const }
          : {
              start,
              end,
              group: monthsBetween(start, end) > 24 ? ('year' as const) : ('month' as const),
            }
  const report = useCashFlowReport(query)
  const data = report.data
  const periods = data?.periods ?? []
  const target = data?.savings_target ?? null
  const highest = Math.max(50, target ?? 0, ...periods.map((p) => Number(p.rate ?? 0)))

  return (
    <section className="stack" aria-label={t('reports.views.flujo')}>
      <Presets
        label={t('reports.period')}
        value={preset}
        onChange={setPreset}
        presets={[
          { key: 'year12', label: t('reports.presets.year12') },
          { key: 'thisYear', label: t('reports.presets.thisYear') },
          { key: 'byYear', label: t('reports.presets.byYear') },
          { key: 'custom', label: t('reports.presets.custom') },
        ]}
      />
      {preset === 'custom' && <DateRange start={start} end={end} onChange={setRange} />}
      {data && (
        <>
          <div className="kpis" aria-label={t('reports.flowTotals')}>
            <div className="card kpi">
              <span className="muted small">{t('reports.income')}</span>
              <span className="kpi__value">
                <Money value={data.total.income} />
              </span>
            </div>
            <div className="card kpi">
              <span className="muted small">{t('reports.expenses')}</span>
              <span className="kpi__value">
                <Money value={negateAmount(data.total.expenses)} />
              </span>
            </div>
            <div className="card kpi">
              <span className="muted small">{t('reports.saved')}</span>
              <span className="kpi__value">
                <Money value={data.total.saved} signed />
              </span>
              {data.total.rate !== null && data.total.rate !== undefined && (
                <small className="muted">
                  {t('dashboard.rate', { rate: formatRate(String(data.total.rate)) })}
                </small>
              )}
            </div>
          </div>
          <div
            className={`card stack stack--tight ${report.isPlaceholderData ? 'is-loading' : ''}`}
          >
            <h2>{t('reports.flowChartTitle')}</h2>
            <ColumnPairChart
              label={t('reports.flowChart')}
              names={[t('reports.income'), t('reports.expenses')]}
              pairs={periods.map((period, index) => ({
                key: period.start,
                label: periodLabel(period, query.group),
                tick:
                  query.group === 'year'
                    ? period.start.slice(0, 4)
                    : formatMonthTick(period.start, index === 0),
                first: period.income,
                second: negateAmount(period.expenses),
              }))}
            />
            <TableView label={t('reports.flowTable')}>
              <thead>
                <tr>
                  <th>{t('reports.cols.period')}</th>
                  <th>{t('reports.income')}</th>
                  <th>{t('reports.expenses')}</th>
                  <th>{t('reports.saved')}</th>
                  <th>{t('reports.cols.rate')}</th>
                </tr>
              </thead>
              <tbody>
                {periods.map((period) => (
                  <tr key={period.start}>
                    <td>{periodLabel(period, query.group)}</td>
                    <td>{formatAmount(period.income)}</td>
                    <td>{formatAmount(negateAmount(period.expenses))}</td>
                    <td>{formatAmount(period.saved)}</td>
                    <td>
                      {period.rate === null || period.rate === undefined
                        ? '—'
                        : `${formatRate(String(period.rate))} %`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </TableView>
          </div>
          <section className="card stack stack--tight" aria-labelledby="flow-rate-title">
            <h2 id="flow-rate-title">{t('savingsRate.title')}</h2>
            <ol className="rate-list" aria-label={t('savingsRate.history')}>
              {periods.map((period) => {
                const value =
                  period.rate === null || period.rate === undefined ? null : Number(period.rate)
                return (
                  <li key={period.start} className="rate-list__row">
                    <span className="rate-list__label">{periodLabel(period, query.group)}</span>
                    <Meter
                      value={Math.max(value ?? 0, 0)}
                      max={highest}
                      marker={target ?? undefined}
                      markerLabel={
                        target !== null ? t('savingsRate.targetMark', { target }) : undefined
                      }
                      label={t('reports.rateOf', { period: periodLabel(period, query.group) })}
                    />
                    <span className="rate-list__value">
                      {value === null ? '—' : `${formatRate(String(period.rate))} %`}
                    </span>
                  </li>
                )
              })}
            </ol>
            {target !== null && (
              <p className="muted small">{t('savingsRate.target', { target })}</p>
            )}
          </section>
        </>
      )}
    </section>
  )
}

// --- Spending ---------------------------------------------------------------------------------

type SpendPreset = 'thisMonth' | 'lastMonth' | 'thisYear' | 'custom'

function SpendRow({
  line,
  highest,
  depth = 0,
}: {
  line: SpendLine
  highest: number
  depth?: number
}) {
  const { t } = useTranslation()
  const versusPrevious = change(line.amount, line.previous)
  const versusYear = change(line.amount, line.last_year)
  const share = highest > 0 ? (Number(line.amount) / highest) * 100 : 0
  return (
    <li>
      <div className="spend-line">
        <div className="spend-line__head">
          <span className={depth ? '' : 'row__title'}>
            {line.icon ? `${line.icon} ` : ''}
            {line.label}
          </span>
          <Money value={line.amount} />
        </div>
        <div
          className="spend-bar"
          style={{ width: `${Math.max(share, 0.5)}%` }}
          aria-hidden="true"
        />
        <small className="muted">
          {t('reports.previous', { amount: formatAmount(line.previous) })}
          {versusPrevious && ` (${versusPrevious})`}
          {' · '}
          {t('reports.lastYear', { amount: formatAmount(line.last_year) })}
          {versusYear && ` (${versusYear})`}
        </small>
        {line.children.length > 0 && (
          <details>
            <summary className="small">
              {t('reports.subcategories', { count: line.children.length })}
            </summary>
            <ul className="spend-line__children">
              {line.children.map((child) => (
                <SpendRow key={child.key} line={child} highest={highest} depth={depth + 1} />
              ))}
            </ul>
          </details>
        )}
      </div>
    </li>
  )
}

function SpendingView() {
  const { t } = useTranslation()
  const { data: session } = useSession()
  const startDay = session?.user.preferences.month_start_day ?? 1
  const today = todayIso()
  const [preset, setPreset] = useState<SpendPreset>('thisMonth')
  const [by, setBy] = useState<SpendingBy>('category')
  const [start, end, setRange] = useCustomRange()
  const [lastStart, lastEnd] = shiftPeriod(today, -1, startDay)
  const [yearStart, yearEnd] = yearRange(today)
  const range =
    preset === 'thisMonth'
      ? periodOf(today, startDay)
      : preset === 'lastMonth'
        ? [lastStart, lastEnd]
        : preset === 'thisYear'
          ? [yearStart, yearEnd]
          : [start, end]
  const report = useSpendingReport({ start: range[0], end: range[1], by })
  const data = report.data
  const lines = data?.lines ?? []
  const highest = Math.max(...lines.map((line) => Number(line.amount)), 0)
  const versusPrevious = data ? change(data.total, data.total_previous) : null

  return (
    <section className="stack" aria-label={t('reports.views.gastos')}>
      <Presets
        label={t('reports.period')}
        value={preset}
        onChange={setPreset}
        presets={[
          { key: 'thisMonth', label: t('reports.presets.thisMonth') },
          { key: 'lastMonth', label: t('reports.presets.lastMonth') },
          { key: 'thisYear', label: t('reports.presets.thisYear') },
          { key: 'custom', label: t('reports.presets.custom') },
        ]}
      />
      {preset === 'custom' && <DateRange start={start} end={end} onChange={setRange} />}
      <div className="segmented" role="radiogroup" aria-label={t('reports.groupBy')}>
        {(['category', 'merchant', 'tag'] as const).map((option) => (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={by === option}
            className="segmented__option"
            onClick={() => setBy(option)}
          >
            {t(`reports.by.${option}`)}
          </button>
        ))}
      </div>
      {data && (
        <>
          <div className="card stack stack--tight" aria-label={t('reports.spendTotal')}>
            <p className="muted small">
              {t('reports.spentBetween', {
                from: formatDate(data.current.start),
                to: formatDate(data.current.end),
              })}
            </p>
            <p className="total">
              <Money value={data.total} />
            </p>
            <p className="small muted">
              {t('reports.previousRange', {
                amount: formatAmount(data.total_previous),
                from: formatShortDate(data.previous.start),
                to: formatDate(data.previous.end),
              })}
              {versusPrevious && ` (${versusPrevious})`}
              <br />
              {t('reports.lastYearRange', {
                amount: formatAmount(data.total_last_year),
                from: formatShortDate(data.last_year.start),
                to: formatDate(data.last_year.end),
              })}
            </p>
          </div>
          {lines.length === 0 ? (
            <p className="card muted">
              {t(by === 'tag' ? 'reports.noTags' : 'reports.noSpending')}
            </p>
          ) : (
            <ul
              className={`list card card--flush ${report.isPlaceholderData ? 'is-loading' : ''}`}
              aria-label={t('reports.spendLines')}
            >
              {lines.map((line) => (
                <SpendRow key={line.key} line={line} highest={highest} />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}
