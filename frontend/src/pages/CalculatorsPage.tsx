import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { CALCULATORS } from '../calculators'
import { PageHeader } from '../components/PageHeader'

const GROUPS = ['saving', 'buying'] as const

/** Every calculator, grouped (RF-CAL). */
export function CalculatorsPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('calc.title')} back="/planificar" />
      <div className="stack">
        {GROUPS.map((group) => (
          <section key={group} className="stack stack--tight" aria-labelledby={`calc-${group}`}>
            <h2 id={`calc-${group}`} className="section-title">
              {t(`calc.groups.${group}`)}
            </h2>
            <ul className="calc-list">
              {CALCULATORS.filter((calculator) => calculator.group === group).map((calculator) => (
                <li key={calculator.name}>
                  <Link
                    className="card card--link calc-card"
                    to={`/planificar/calculadoras/${calculator.slug}`}
                  >
                    <span className="calc-card__icon" aria-hidden="true">
                      {calculator.icon}
                    </span>
                    <span className="calc-card__text">
                      <span className="row__title">{t(`calc.${calculator.name}.title`)}</span>
                      <small className="muted">{t(`calc.${calculator.name}.summary`)}</small>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
        <p className="footnote">{t('calc.disclaimer')}</p>
      </div>
    </>
  )
}
