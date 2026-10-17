import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  captureApi,
  captureKeys,
  type NewCaptureToken,
  useCaptureCards,
  useCaptureTokens,
} from '../api/capture'
import { useAccounts } from '../api/finance'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { deviceName } from '../lib/device'
import { messageOf } from '../lib/errors'
import { formatDate } from '../lib/format'

/** Payments captured from the phone (RF-MOV-17): tokens, cards and the Shortcut guide. */
export function CapturePage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const accounts = useAccounts()
  const tokens = useCaptureTokens()
  const cards = useCaptureCards()
  const [created, setCreated] = useState<NewCaptureToken | null>(null)

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: captureKeys.tokens }),
      queryClient.invalidateQueries({ queryKey: captureKeys.cards }),
    ])

  const revoke = async (id: string, name: string) => {
    if (!window.confirm(t('capture.confirmRevoke', { name }))) {
      return
    }
    await captureApi.revokeToken(id)
    await refresh()
  }

  const accountName = (id: string) => accounts.data?.find((a) => a.id === id)?.name ?? ''

  return (
    <>
      <PageHeader title={t('capture.title')} back="/mas" />
      <div className="stack">
        <p className="muted small">{t('capture.intro')}</p>

        {created ? (
          <TokenCreated created={created} onDone={() => setCreated(null)} />
        ) : (
          <NewTokenForm
            onCreated={async (result) => {
              setCreated(result)
              await refresh()
            }}
          />
        )}

        {(tokens.data?.length ?? 0) > 0 && (
          <section className="stack stack--tight" aria-labelledby="tokens-title">
            <h2 id="tokens-title" className="section-title">
              {t('capture.tokens')}
            </h2>
            <ul className="list card card--flush">
              {tokens.data?.map((token) => (
                <li key={token.id} className="row">
                  <span className="row__text">
                    <span className="row__title">{token.name}</span>
                    <small className="muted">
                      {[
                        `${token.hint}…`,
                        t('capture.defaultAccount', {
                          account: accountName(token.default_account_id),
                        }),
                        token.last_used_at
                          ? t('capture.lastUsed', {
                              date: formatDate(token.last_used_at.slice(0, 10)),
                            })
                          : t('capture.neverUsed'),
                      ].join(' · ')}
                    </small>
                  </span>
                  <button
                    type="button"
                    className="button button--ghost button--danger"
                    onClick={() => void revoke(token.id, token.name)}
                  >
                    {t('capture.revoke')}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {(cards.data?.length ?? 0) > 0 && (
          <section className="card stack stack--tight" aria-labelledby="cards-title">
            <h2 id="cards-title">{t('capture.cards')}</h2>
            <p className="muted small">{t('capture.cardsHelp')}</p>
            {cards.data?.map((card) => (
              <label key={card.id} className="field">
                <span>{card.name}</span>
                <select
                  value={card.account_id}
                  onChange={async (event) => {
                    await captureApi.mapCard(card.id, event.target.value)
                    await refresh()
                  }}
                >
                  {accounts.data?.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </section>
        )}
      </div>
    </>
  )
}

function NewTokenForm({ onCreated }: { onCreated: (created: NewCaptureToken) => Promise<void> }) {
  const { t } = useTranslation()
  const accounts = useAccounts()
  const [name, setName] = useState(deviceName)
  const [chosenAccount, setChosenAccount] = useState('')
  const [error, setError] = useState<string | null>(null)
  const accountId = chosenAccount || accounts.data?.[0]?.id || ''

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      await onCreated(await captureApi.createToken(name.trim(), accountId))
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  if (accounts.isSuccess && accounts.data.length === 0) {
    return <p className="card muted">{t('capture.needAccount')}</p>
  }
  return (
    <form className="card stack stack--tight" onSubmit={(event) => void submit(event)}>
      <h2>{t('capture.newToken')}</h2>
      <label className="field">
        <span>{t('capture.tokenName')}</span>
        <input required maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="field">
        <span>{t('capture.account')}</span>
        <select value={accountId} onChange={(e) => setChosenAccount(e.target.value)}>
          {accounts.data?.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
        <small className="muted">{t('capture.accountHelp')}</small>
      </label>
      <ErrorMessage message={error} />
      <button type="submit" className="button">
        {t('capture.create')}
      </button>
    </form>
  )
}

/** The token is shown only now: the guide uses it, with buttons to copy each value. */
function TokenCreated({ created, onDone }: { created: NewCaptureToken; onDone: () => void }) {
  const { t } = useTranslation()
  const url = new URL(created.url, window.location.origin).toString()
  const authorization = `Bearer ${created.secret}`

  return (
    <section className="card stack" aria-labelledby="guide-title">
      <h2 id="guide-title">{t('capture.guideTitle')}</h2>
      <p className="notice small">{t('capture.onlyNow')}</p>
      <ol className="guide stack stack--tight">
        <li>{t('capture.step1')}</li>
        <li>{t('capture.step2')}</li>
        <li>{t('capture.step3')}</li>
        <li>
          {t('capture.step4')}
          <CopyValue label={t('capture.url')} value={url} />
        </li>
        <li>
          {t('capture.step5')}
          <CopyValue label="Authorization" value={authorization} />
        </li>
        <li>
          {t('capture.step6')}
          <dl className="details small">
            <div>
              <dt>amount</dt>
              <dd>{t('capture.fieldAmount')}</dd>
            </div>
            <div>
              <dt>merchant</dt>
              <dd>{t('capture.fieldMerchant')}</dd>
            </div>
            <div>
              <dt>card</dt>
              <dd>{t('capture.fieldCard')}</dd>
            </div>
          </dl>
        </li>
        <li>{t('capture.step7')}</li>
      </ol>
      <p className="muted small">{t('capture.guideNote')}</p>
      <button type="button" className="button button--secondary" onClick={onDone}>
        {t('capture.done')}
      </button>
    </section>
  )
}

function CopyValue({ label, value }: { label: string; value: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  return (
    <div className="copy">
      <code aria-label={label}>{value}</code>
      <button
        type="button"
        className="button button--ghost"
        onClick={async () => {
          await navigator.clipboard.writeText(value)
          setCopied(true)
        }}
      >
        {copied ? t('capture.copied') : t('capture.copy')}
      </button>
    </div>
  )
}
