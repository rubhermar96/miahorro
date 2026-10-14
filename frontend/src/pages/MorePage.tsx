import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../components/PageHeader'
import { ServerStatusLine } from '../components/ServerStatusLine'
import { getThemePreference, setThemePreference, type ThemePreference } from '../lib/theme'

const THEMES: ThemePreference[] = ['system', 'light', 'dark']

export function MorePage() {
  const { t } = useTranslation()
  const [theme, setTheme] = useState<ThemePreference>(getThemePreference)

  const chooseTheme = (preference: ThemePreference) => {
    setTheme(preference)
    setThemePreference(preference)
  }

  return (
    <>
      <PageHeader title={t('more.title')} />
      <div className="stack">
        <section className="card">
          <h2>{t('more.appearance')}</h2>
          <div className="segmented" role="radiogroup" aria-label={t('more.theme.label')}>
            {THEMES.map((preference) => (
              <button
                key={preference}
                type="button"
                role="radio"
                aria-checked={theme === preference}
                className="segmented__option"
                onClick={() => chooseTheme(preference)}
              >
                {t(`more.theme.${preference}`)}
              </button>
            ))}
          </div>
        </section>

        <section className="card">
          <h2>{t('more.about')}</h2>
          <dl className="details">
            <div>
              <dt>{t('more.appVersion')}</dt>
              <dd>{__APP_VERSION__}</dd>
            </div>
            <div>
              <dt>{t('more.server')}</dt>
              <dd>
                <ServerStatusLine />
              </dd>
            </div>
          </dl>
        </section>
      </div>
    </>
  )
}
