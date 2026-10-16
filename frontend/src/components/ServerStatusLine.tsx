import { useTranslation } from 'react-i18next'

import { useServerStatus } from '../api/health'

export function ServerStatusLine() {
  const { t } = useTranslation()
  const { data } = useServerStatus()

  if (!data) {
    return <span className="status">{t('server.checking')}</span>
  }
  if (data.state === 'ok') {
    return <span className="status status--ok">{t('server.ok', { version: data.version })}</span>
  }
  return (
    <span className="status status--error">
      {data.state === 'degraded' ? t('server.degraded') : t('server.offline')}
    </span>
  )
}
