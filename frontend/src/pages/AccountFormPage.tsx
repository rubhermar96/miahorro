import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { useSession } from '../api/auth'
import {
  ACCOUNT_KINDS,
  type Account,
  type AccountKind,
  financeApi,
  refreshFinance,
  useAccount,
} from '../api/finance'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { amountToInput, parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'
import { todayIso } from '../lib/format'

const CURRENCIES = ['EUR', 'USD', 'GBP', 'CHF'] as const

/** Create (/cuentas/nueva) or edit (/cuentas/:id/editar) an account. */
export function AccountFormPage() {
  const { t } = useTranslation()
  const { id } = useParams()
  const account = useAccount(id ?? '')
  if (id && !account.data) {
    return <PageHeader title={t('accounts.editTitle')} back={`/cuentas/${id}`} />
  }
  return <AccountForm key={id ?? 'new'} account={id ? account.data : undefined} />
}

function AccountForm({ account }: { account?: Account }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: session } = useSession()
  const [name, setName] = useState(account?.name ?? '')
  const [kind, setKind] = useState<AccountKind>(account?.kind ?? 'checking')
  const [institution, setInstitution] = useState(account?.institution ?? '')
  const [ibanLast4, setIbanLast4] = useState(account?.iban_last4 ?? '')
  const [currency, setCurrency] = useState<(typeof CURRENCIES)[number]>(
    account?.currency ?? session?.user.preferences.currency ?? 'EUR',
  )
  const [balanceText, setBalanceText] = useState(
    account ? amountToInput(account.opening_balance, true) : '',
  )
  const [openingDate, setOpeningDate] = useState(account?.opening_date ?? todayIso())
  const [joint, setJoint] = useState(account?.is_joint ?? false)
  const [maturityDate, setMaturityDate] = useState(account?.maturity_date ?? '')
  const [autoRenew, setAutoRenew] = useState(account?.auto_renew ?? false)
  const [penalty, setPenalty] = useState(account?.early_cancellation_note ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const openingBalance = parseAmountInput(balanceText || '0', {
      allowZero: true,
      allowNegative: true,
    })
    if (openingBalance === null) {
      setError(t('add.invalidAmount'))
      return
    }
    const isDeposit = kind === 'deposit'
    const fields = {
      name,
      kind,
      institution: institution || null,
      iban_last4: ibanLast4 || null,
      opening_balance: openingBalance,
      opening_date: openingDate,
      is_joint: joint,
      maturity_date: isDeposit && maturityDate ? maturityDate : null,
      auto_renew: isDeposit && autoRenew,
      early_cancellation_note: isDeposit && penalty ? penalty : null,
    }
    setBusy(true)
    try {
      const saved = account
        ? await financeApi.updateAccount(account.id, fields)
        : await financeApi.createAccount({ ...fields, currency })
      await refreshFinance(queryClient)
      void navigate(`/cuentas/${saved.id}`, { replace: true })
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title={account ? t('accounts.editTitle') : t('accounts.newTitle')}
        back={account ? `/cuentas/${account.id}` : '/'}
      />
      <form className="stack" onSubmit={(event) => void submit(event)}>
        <label className="field">
          <span>{t('accounts.name')}</span>
          <input
            required
            maxLength={60}
            placeholder={t('accounts.namePlaceholder')}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="field">
          <span>{t('accounts.kind')}</span>
          <select value={kind} onChange={(event) => setKind(event.target.value as AccountKind)}>
            {ACCOUNT_KINDS.map((option) => (
              <option key={option} value={option}>
                {t(`accounts.kinds.${option}`)}
              </option>
            ))}
          </select>
        </label>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="opening-balance">{t('accounts.openingBalance')}</label>
            <input
              id="opening-balance"
              inputMode="decimal"
              placeholder="0,00"
              aria-describedby="opening-balance-help"
              value={balanceText}
              onChange={(event) => setBalanceText(event.target.value)}
            />
          </div>
          <label className="field">
            <span>{t('accounts.openingDate')}</span>
            <input
              type="date"
              required
              value={openingDate}
              onChange={(event) => setOpeningDate(event.target.value)}
            />
          </label>
        </div>
        <small id="opening-balance-help" className="muted">
          {t('accounts.openingBalanceHelp')}
        </small>

        {kind === 'deposit' && (
          <fieldset className="card stack stack--tight">
            <legend>{t('accounts.kinds.deposit')}</legend>
            <label className="field">
              <span>{t('accounts.maturityDate')}</span>
              <input
                type="date"
                value={maturityDate}
                onChange={(event) => setMaturityDate(event.target.value)}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={autoRenew}
                onChange={(event) => setAutoRenew(event.target.checked)}
              />
              {t('accounts.autoRenew')}
            </label>
            <label className="field">
              <span>{t('accounts.earlyCancellation')}</span>
              <input
                maxLength={200}
                value={penalty}
                onChange={(event) => setPenalty(event.target.value)}
              />
            </label>
          </fieldset>
        )}

        <div className="grid-2">
          <label className="field">
            <span>{t('accounts.institution')}</span>
            <input
              maxLength={60}
              placeholder={t('accounts.institutionPlaceholder')}
              value={institution}
              onChange={(event) => setInstitution(event.target.value)}
            />
          </label>
          <label className="field">
            <span>{t('accounts.currency')}</span>
            <select
              value={currency}
              disabled={Boolean(account)}
              onChange={(event) => setCurrency(event.target.value as (typeof CURRENCIES)[number])}
            >
              {CURRENCIES.map((option) => (
                <option key={option}>{option}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="field">
          <label htmlFor="iban-last4">{t('accounts.ibanLast4')}</label>
          <input
            id="iban-last4"
            inputMode="numeric"
            pattern="\d{4}"
            maxLength={4}
            aria-describedby="iban-help"
            value={ibanLast4}
            onChange={(event) => setIbanLast4(event.target.value.replace(/\D/g, ''))}
          />
          <small id="iban-help" className="muted">
            {t('accounts.ibanHelp')}
          </small>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={joint}
            onChange={(event) => setJoint(event.target.checked)}
          />
          {t('accounts.joint')}
        </label>

        <ErrorMessage message={error} />
        <button type="submit" className="button" disabled={busy}>
          {account ? t('accounts.save') : t('accounts.create')}
        </button>
      </form>
    </>
  )
}
