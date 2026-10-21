import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { financeApi, refreshFinance } from '../api/finance'
import { discard, flush, OUTBOX_EVENT, pendingEntries } from '../lib/outbox'

/** Says when there is no connection and how many entries wait to be sent, and sends them as
 * soon as the connection is back (RNF-02). */
export function OfflineStatus() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [online, setOnline] = useState(() => navigator.onLine)
  const [entries, setEntries] = useState(pendingEntries)
  const busy = useRef(false)

  const send = useCallback(async () => {
    if (busy.current || pendingEntries().every((entry) => entry.error)) {
      return
    }
    busy.current = true
    try {
      const sent = await flush((body) =>
        financeApi.createTransaction(body as Parameters<typeof financeApi.createTransaction>[0]),
      )
      if (sent > 0) {
        await refreshFinance(queryClient)
      }
    } finally {
      busy.current = false
    }
  }, [queryClient])

  useEffect(() => {
    const update = () => setEntries(pendingEntries())
    const goOnline = () => {
      setOnline(true)
      void send()
    }
    const goOffline = () => setOnline(false)
    window.addEventListener(OUTBOX_EVENT, update)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener(OUTBOX_EVENT, update)
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
    }
  }, [send])

  // Whatever waited from an earlier visit goes as soon as the app opens with connection.
  useEffect(() => {
    if (navigator.onLine) {
      void send()
    }
  }, [send])

  const waiting = entries.filter((entry) => !entry.error)
  const refused = entries.filter((entry) => entry.error)
  if (online && entries.length === 0) {
    return null
  }
  return (
    <div className="offline" role="status">
      {!online && <p>{t('offline.notConnected')}</p>}
      {waiting.length > 0 && (
        <p>
          {t('offline.pending', { count: waiting.length })}
          {online && (
            <>
              {' '}
              <button type="button" className="link-button" onClick={() => void send()}>
                {t('offline.sendNow')}
              </button>
            </>
          )}
        </p>
      )}
      {refused.map((entry) => (
        <p key={entry.ref}>
          {t('offline.refused', {
            what: String(entry.body.description || entry.body.amount || ''),
            reason: entry.error,
          })}{' '}
          <button type="button" className="link-button" onClick={() => discard(entry.ref)}>
            {t('offline.discard')}
          </button>
        </p>
      ))}
    </div>
  )
}
