import { useTranslation } from 'react-i18next'
import { useRegisterSW } from 'virtual:pwa-register/react'

/** Offers to reload when a new version of the app has been downloaded. */
export function UpdatePrompt() {
  const { t } = useTranslation()
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW()

  if (!needRefresh) {
    return null
  }

  return (
    <div className="update-prompt" role="status">
      <span>{t('update.available')}</span>
      <div className="update-prompt__actions">
        <button
          type="button"
          className="button button--ghost"
          onClick={() => setNeedRefresh(false)}
        >
          {t('update.dismiss')}
        </button>
        <button type="button" className="button" onClick={() => void updateServiceWorker(true)}>
          {t('update.reload')}
        </button>
      </div>
    </div>
  )
}
