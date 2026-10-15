import { useState } from 'react'
import { useTranslation } from 'react-i18next'

/** Shows freshly generated recovery codes once, with a copy button. */
export function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(codes.join('\n'))
      setCopied(true)
    } catch {
      // Clipboard blocked: the codes are on screen to copy by hand.
    }
  }

  return (
    <section className="card" aria-labelledby="recovery-codes-title">
      <h2 id="recovery-codes-title">{t('recoveryCodes.title')}</h2>
      <p className="muted">{t('recoveryCodes.intro')}</p>
      <ol className="codes">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ol>
      <div className="actions">
        <button type="button" className="button button--secondary" onClick={() => void copy()}>
          {copied ? t('recoveryCodes.copied') : t('recoveryCodes.copy')}
        </button>
        <button type="button" className="button" onClick={onDone}>
          {t('recoveryCodes.done')}
        </button>
      </div>
    </section>
  )
}
