import { useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * Shows freshly generated recovery codes once. On phones, "Guardar" opens the share sheet so
 * the codes go to Notes or another app in one tap; elsewhere it copies them.
 */
export function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const { t } = useTranslation()
  const [saved, setSaved] = useState(false)
  const text = `${t('recoveryCodes.shareTitle')}\n\n${codes.join('\n')}`

  const save = async () => {
    try {
      if (typeof navigator.share === 'function') {
        await navigator.share({ title: t('recoveryCodes.shareTitle'), text })
      } else {
        await navigator.clipboard.writeText(text)
      }
      setSaved(true)
    } catch {
      // Cancelled or blocked: the codes stay on screen to copy by hand.
    }
  }

  return (
    <section className="card stack" aria-labelledby="recovery-codes-title">
      <h2 id="recovery-codes-title">{t('recoveryCodes.title')}</h2>
      <p className="muted">{t('recoveryCodes.intro')}</p>
      <ol className="codes">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ol>
      <div className="actions">
        <button type="button" className="button button--secondary" onClick={() => void save()}>
          {saved ? t('recoveryCodes.saved') : t('recoveryCodes.save')}
        </button>
        <button type="button" className="button" onClick={onDone}>
          {t('recoveryCodes.done')}
        </button>
      </div>
    </section>
  )
}
