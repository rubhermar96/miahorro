import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { Investment } from '../api/investments'
import { formatSignedPercent } from '../lib/format'
import { Money } from './Money'

/** One investment in a list: what it is worth and how much it is up or down. */
export function InvestmentRow({ investment }: { investment: Investment }) {
  const { t } = useTranslation()
  return (
    <Link className="row" to={`/inversiones/${investment.id}`}>
      <span className="row__text">
        <span className="row__title">
          {investment.name}
          {investment.archived && <span className="tag">{t('inv.archived')}</span>}
        </span>
        <small className="muted">
          {[t(`inv.kinds.${investment.kind}`), investment.isin ?? investment.ticker]
            .filter(Boolean)
            .join(' · ')}
        </small>
      </span>
      <span className="row__amounts">
        {investment.value !== null && investment.value !== undefined ? (
          <Money value={investment.value} />
        ) : (
          <span className="muted small">{t('inv.noPrice')}</span>
        )}
        {investment.gain_percent !== null && investment.gain_percent !== undefined && (
          <small className={Number(investment.gain_percent) < 0 ? 'amount--out' : 'amount--in'}>
            {formatSignedPercent(investment.gain_percent)}
          </small>
        )}
      </span>
    </Link>
  )
}
