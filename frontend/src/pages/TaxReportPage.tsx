import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { useTaxReport } from '../api/investments'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { formatAmount, formatDate, todayIso } from '../lib/format'
import { formatUnits } from '../lib/units'

/** Sales by FIFO and dividends of a year, as they go in the tax return (RF-INV-05). */
export function TaxReportPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const current = Number(todayIso().slice(0, 4))
  const year = Number(params.get('anio')) || current
  const report = useTaxReport(year)
  const data = report.data
  const taxable = data?.sales.filter((sale) => sale.taxable) ?? []
  const rescues = data?.sales.filter((sale) => !sale.taxable) ?? []

  return (
    <>
      <PageHeader title={t('inv.report.title')} back="/inversiones" />
      <div className="stack">
        <label className="field">
          <span>{t('inv.report.year')}</span>
          <select
            value={year}
            onChange={(event) => setParams({ anio: event.target.value }, { replace: true })}
          >
            {[0, 1, 2, 3, 4].map((back) => (
              <option key={back} value={current - back}>
                {current - back}
              </option>
            ))}
          </select>
        </label>

        {data && (
          <>
            <section className="card stack stack--tight" aria-label={t('inv.report.summary')}>
              <h2>{t('inv.report.gainsTitle')}</h2>
              <dl className="details">
                <div>
                  <dt>{t('inv.report.gains')}</dt>
                  <dd>
                    <Money value={data.gains} />
                  </dd>
                </div>
                <div>
                  <dt>{t('inv.report.losses')}</dt>
                  <dd>
                    <Money value={data.losses} />
                  </dd>
                </div>
                <div className="details__strong">
                  <dt>{t('inv.report.net')}</dt>
                  <dd>
                    <Money value={data.net} signed />
                  </dd>
                </div>
                <div>
                  <dt>{t('inv.report.saleWithholding')}</dt>
                  <dd>
                    <Money value={data.sale_withholding} />
                  </dd>
                </div>
              </dl>
              <h2>{t('inv.report.dividendsTitle')}</h2>
              <dl className="details">
                <div>
                  <dt>{t('inv.report.dividendsGross')}</dt>
                  <dd>
                    <Money value={data.dividends_gross} />
                  </dd>
                </div>
                <div>
                  <dt>{t('inv.report.dividendsWithholding')}</dt>
                  <dd>
                    <Money value={data.dividends_withholding} />
                  </dd>
                </div>
              </dl>
            </section>

            <section className="stack stack--tight" aria-labelledby="sales-title">
              <h2 id="sales-title" className="section-title">
                {t('inv.report.sales')}
              </h2>
              {taxable.length === 0 && <p className="card muted">{t('inv.report.noSales')}</p>}
              {taxable.map((sale) => (
                <details key={sale.operation_id} className="card">
                  <summary>
                    <span className="report-sale">
                      <span>
                        {sale.name}
                        <br />
                        <small className="muted">
                          {formatDate(sale.date)} ·{' '}
                          {t('inv.report.units', { units: formatUnits(sale.units) })}
                        </small>
                      </span>
                      <Money value={sale.gain} signed />
                    </span>
                  </summary>
                  <div className="details-body stack stack--tight">
                    <dl className="details">
                      <div>
                        <dt>{t('inv.report.proceeds')}</dt>
                        <dd>{formatAmount(sale.proceeds)}</dd>
                      </div>
                      <div>
                        <dt>{t('inv.report.cost')}</dt>
                        <dd>{formatAmount(sale.cost)}</dd>
                      </div>
                      {sale.withholding !== '0.00' && (
                        <div>
                          <dt>{t('inv.report.withheld')}</dt>
                          <dd>{formatAmount(sale.withholding)}</dd>
                        </div>
                      )}
                    </dl>
                    <div
                      className="table-scroll"
                      role="region"
                      tabIndex={0}
                      aria-label={t('inv.report.lotsOf', { name: sale.name })}
                    >
                      <table className="sample">
                        <thead>
                          <tr>
                            <th>{t('inv.acquired')}</th>
                            <th>{t('inv.report.unitsCol')}</th>
                            <th>{t('inv.report.cost')}</th>
                            <th>{t('inv.report.proceeds')}</th>
                            <th>{t('inv.report.result')}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sale.parts.map((part, index) => (
                            <tr key={index}>
                              <td>{formatDate(part.acquired)}</td>
                              <td>{formatUnits(part.units)}</td>
                              <td>{formatAmount(part.cost)}</td>
                              <td>{formatAmount(part.proceeds)}</td>
                              <td>{formatAmount(part.gain)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {sale.repurchase_warning && (
                      <p className="notice small">
                        {t(
                          sale.kind === 'fund'
                            ? 'inv.report.repurchaseYear'
                            : 'inv.report.repurchaseMonths',
                        )}
                      </p>
                    )}
                  </div>
                </details>
              ))}
            </section>

            {data.dividends.length > 0 && (
              <section className="stack stack--tight" aria-labelledby="dividends-title">
                <h2 id="dividends-title" className="section-title">
                  {t('inv.report.dividendsTitle')}
                </h2>
                <ul className="list card card--flush">
                  {data.dividends.map((dividend) => (
                    <li key={dividend.operation_id} className="row">
                      <span className="row__text">
                        <span className="row__title">{dividend.name}</span>
                        <small className="muted">
                          {formatDate(dividend.date)}
                          {dividend.withholding !== '0.00' &&
                            ` · ${t('inv.report.withheldShort', {
                              amount: formatAmount(dividend.withholding),
                            })}`}
                        </small>
                      </span>
                      <Money value={dividend.amount} />
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {rescues.length > 0 && (
              <p className="notice small">
                {t('inv.report.rescues', { amount: formatAmount(data.pension_rescues) })}
              </p>
            )}
            <p className="footnote">{t('inv.report.note')}</p>
          </>
        )}
      </div>
    </>
  )
}
