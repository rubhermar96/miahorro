import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { type Account, useAccounts } from '../api/finance'
import {
  INVESTMENT_KINDS,
  type InvestmentDetail,
  type InvestmentKind,
  investmentKeys,
  investmentsApi,
  useInvestment,
} from '../api/investments'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { messageOf } from '../lib/errors'

/** Create or edit an investment (RF-INV-01, RF-INV-03). */
export function InvestmentFormPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const investment = useInvestment(id)
  const accounts = useAccounts()
  if ((id && !investment.data) || !accounts.data) {
    return <PageHeader title={t('inv.newTitle')} back="/inversiones" />
  }
  return (
    <InvestmentForm
      key={investment.data?.id ?? 'new'}
      investment={investment.data}
      accounts={accounts.data}
    />
  )
}

function InvestmentForm({
  investment,
  accounts,
}: {
  investment?: InvestmentDetail
  accounts: Account[]
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState(investment?.name ?? '')
  const [kind, setKind] = useState<InvestmentKind>(investment?.kind ?? 'fund')
  const [isin, setIsin] = useState(investment?.isin ?? '')
  const [ticker, setTicker] = useState(investment?.ticker ?? '')
  const [accountId, setAccountId] = useState(investment?.account_id ?? '')
  const [note, setNote] = useState(investment?.note ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const back = investment ? `/inversiones/${investment.id}` : '/inversiones'

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setBusy(true)
    const body = {
      name,
      kind,
      isin: isin.trim() || null,
      ticker: ticker.trim() || null,
      account_id: accountId || null,
      note: note.trim() || null,
    }
    try {
      const saved = investment
        ? await investmentsApi.update(investment.id, body)
        : await investmentsApi.create(body)
      await queryClient.invalidateQueries({ queryKey: investmentKeys.all })
      void navigate(`/inversiones/${saved.id}`, { replace: true })
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title={investment ? t('inv.editTitle') : t('inv.newTitle')} back={back} />
      <form className="stack" onSubmit={(event) => void submit(event)}>
        <label className="field">
          <span>{t('inv.name')}</span>
          <input
            required
            maxLength={80}
            placeholder={t('inv.namePlaceholder')}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="field">
          <span>{t('inv.kind')}</span>
          <select value={kind} onChange={(event) => setKind(event.target.value as InvestmentKind)}>
            {INVESTMENT_KINDS.map((option) => (
              <option key={option} value={option}>
                {t(`inv.kinds.${option}`)}
              </option>
            ))}
          </select>
        </label>
        <div className="grid-2">
          <label className="field">
            <span>{t('inv.isin')}</span>
            <input
              maxLength={20}
              autoCapitalize="characters"
              placeholder="IE00B4L5Y983"
              value={isin}
              onChange={(event) => setIsin(event.target.value)}
            />
          </label>
          <label className="field">
            <span>{t('inv.ticker')}</span>
            <input
              maxLength={16}
              autoCapitalize="characters"
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
            />
          </label>
        </div>
        <p className="muted small">{t('inv.isinHelp')}</p>
        <label className="field">
          <span>{t('inv.account')}</span>
          <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
            <option value="">{t('inv.noAccount')}</option>
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name}
              </option>
            ))}
          </select>
          <small className="muted">{t('inv.accountHelp')}</small>
        </label>
        <label className="field">
          <span>{t('add.note')}</span>
          <textarea rows={2} value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
        <ErrorMessage message={error} />
        <button type="submit" className="button" disabled={busy}>
          {investment ? t('add.save') : t('inv.create')}
        </button>
      </form>
    </>
  )
}
