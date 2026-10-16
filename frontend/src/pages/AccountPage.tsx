import { useQueryClient } from '@tanstack/react-query'
import type { TFunction } from 'i18next'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import {
  type Account,
  type AccountRate,
  type AccountRateInput,
  financeApi,
  refreshFinance,
  useAccount,
  useAccountRates,
  useAccounts,
  useCategories,
  useTransactions,
} from '../api/finance'
import { ErrorMessage } from '../components/ErrorMessage'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { TransactionList } from '../components/TransactionList'
import { parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'
import { formatAmount, formatDate, formatRate, todayIso } from '../lib/format'

const RECENT = 5
const LIQUIDATIONS = [
  'daily',
  'monthly',
  'quarterly',
  'semiannual',
  'annual',
  'at_maturity',
] as const

/** Read a typed rate ("2,15") as the API expects ("2.15"); null if invalid. */
function parseRate(text: string): string | null {
  const value = text.trim().replace(',', '.')
  return /^\d{1,3}(\.\d{1,4})?$/.test(value) ? value : null
}

export function AccountPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const account = useAccount(id)
  if (!account.data) {
    return <PageHeader title={t('home.accountsTitle')} back="/" />
  }
  return <AccountDetails account={account.data} />
}

function AccountDetails({ account }: { account: Account }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const accounts = useAccounts(true)
  const categories = useCategories(true)
  const recent = useTransactions({ account_id: account.id })
  const items = recent.data?.pages[0]?.items ?? []
  const total = recent.data?.pages[0]?.total ?? 0
  const subtitle = [
    t(`accounts.kinds.${account.kind}`),
    account.institution,
    account.iban_last4 && `···· ${account.iban_last4}`,
  ].filter(Boolean)

  const toggleArchive = async () => {
    if (
      !account.archived &&
      !window.confirm(t('accounts.confirmArchive', { name: account.name }))
    ) {
      return
    }
    await financeApi.updateAccount(account.id, { archived: !account.archived })
    await refreshFinance(queryClient)
  }

  const remove = async () => {
    if (!window.confirm(t('accounts.confirmDelete', { name: account.name }))) {
      return
    }
    await financeApi.deleteAccount(account.id)
    await refreshFinance(queryClient)
    void navigate('/', { replace: true })
  }

  return (
    <>
      <PageHeader title={account.name} back="/" />
      <div className="stack">
        <section className="card">
          <p className="muted small">{subtitle.join(' · ')}</p>
          <p className="total">
            <Money value={account.balance} currency={account.currency} />
          </p>
          {account.maturity_date && (
            <p className="muted small">
              {t('home.maturity', { name: account.name, date: formatDate(account.maturity_date) })}
            </p>
          )}
          {account.archived && <p className="notice small">{t('accounts.archivedNote')}</p>}
        </section>

        <section className="stack stack--tight" aria-labelledby="recent-title">
          <div className="section-title">
            <h2 id="recent-title">{t('accounts.recent')}</h2>
            {total > RECENT && (
              <Link to={`/movimientos?cuenta=${account.id}`}>{t('accounts.seeAll')}</Link>
            )}
          </div>
          {recent.isSuccess && items.length === 0 && (
            <p className="card muted">{t('accounts.noTransactions')}</p>
          )}
          <TransactionList
            transactions={items.slice(0, RECENT)}
            accounts={accounts.data ?? []}
            categories={categories.data ?? []}
            showAccount={false}
          />
        </section>

        <ReconcileCard account={account} />
        <RatesCard account={account} />

        <section className="card stack stack--tight">
          <Link className="button button--secondary" to={`/cuentas/${account.id}/editar`}>
            {t('accounts.edit')}
          </Link>
          <button
            type="button"
            className="button button--secondary"
            onClick={() => void toggleArchive()}
          >
            {account.archived ? t('accounts.unarchive') : t('accounts.archive')}
          </button>
          {total === 0 && (
            <button
              type="button"
              className="button button--ghost button--danger"
              onClick={() => void remove()}
            >
              {t('accounts.delete')}
            </button>
          )}
        </section>
      </div>
    </>
  )
}

function ReconcileCard({ account }: { account: Account }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [text, setText] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setMessage(null)
    setError(null)
    const balance = parseAmountInput(text, { allowZero: true, allowNegative: true })
    if (balance === null) {
      setError(t('add.invalidAmount'))
      return
    }
    try {
      const result = await financeApi.reconcile(account.id, balance)
      setMessage(
        result.adjustment
          ? t('accounts.reconciled', {
              amount: formatAmount(result.adjustment.amount, account.currency),
            })
          : t('accounts.alreadyReconciled'),
      )
      setText('')
      await refreshFinance(queryClient)
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  return (
    <details className="card">
      <summary>{t('accounts.reconcileTitle')}</summary>
      <form className="stack stack--tight details-body" onSubmit={(event) => void submit(event)}>
        <p className="muted small">{t('accounts.reconcileHelp')}</p>
        <label className="field">
          <span>{t('accounts.reconcileBalance')}</span>
          <input
            inputMode="decimal"
            required
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </label>
        <ErrorMessage message={error} />
        <button type="submit" className="button button--secondary">
          {t('accounts.reconcile')}
        </button>
        <p role="status" className="small">
          {message}
        </p>
      </form>
    </details>
  )
}

function rateSummary(rate: AccountRate, currency: string, t: TFunction) {
  const parts = rate.tiers.map((tier, index) => {
    const value = formatRate(tier.rate)
    if (tier.up_to) {
      return t('rates.tierUpTo', { rate: value, limit: formatAmount(tier.up_to, currency) })
    }
    return rate.tiers.length > 1 && index > 0
      ? t('rates.tierRest', { rate: value })
      : t('rates.tierAll', { rate: value })
  })
  const tae = rate.tae ? ` · ${t('rates.tae', { tae: formatRate(rate.tae) })}` : ''
  return `${parts.join(', ')}${tae} · ${t(`rates.liquidations.${rate.liquidation}`)}`
}

type TierDraft = { upTo: string; rate: string }

function RatesCard({ account }: { account: Account }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const rates = useAccountRates(account.id)
  const [validFrom, setValidFrom] = useState(todayIso)
  const [tiers, setTiers] = useState<TierDraft[]>([{ upTo: '', rate: '' }])
  const [tae, setTae] = useState('')
  const [liquidation, setLiquidation] = useState<(typeof LIQUIDATIONS)[number]>(
    account.kind === 'deposit' ? 'at_maturity' : 'monthly',
  )
  const [withholding, setWithholding] = useState('19')
  const [error, setError] = useState<string | null>(null)

  const updateTier = (index: number, change: Partial<TierDraft>) =>
    setTiers(tiers.map((tier, i) => (i === index ? { ...tier, ...change } : tier)))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const parsed = tiers.map((tier, index) => ({
      up_to: index === tiers.length - 1 ? null : parseAmountInput(tier.upTo),
      rate: parseRate(tier.rate),
    }))
    const taeValue = tae ? parseRate(tae) : null
    const withholdingValue = parseRate(withholding)
    if (
      parsed.some((tier, index) => !tier.rate || (index < parsed.length - 1 && !tier.up_to)) ||
      (tae && !taeValue) ||
      !withholdingValue
    ) {
      setError(t('errors.generic'))
      return
    }
    const body: AccountRateInput = {
      valid_from: validFrom,
      tiers: parsed.map((tier) => ({ up_to: tier.up_to, rate: tier.rate as string })),
      tae: taeValue,
      liquidation,
      withholding: withholdingValue,
    }
    try {
      await financeApi.addRate(account.id, body)
      setTiers([{ upTo: '', rate: '' }])
      setTae('')
      await refreshFinance(queryClient)
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  const remove = async (rateId: string) => {
    await financeApi.deleteRate(account.id, rateId)
    await refreshFinance(queryClient)
  }

  return (
    <section className="card stack stack--tight" aria-labelledby="rates-title">
      <h2 id="rates-title">{t('rates.title')}</h2>
      {account.current_rate ? (
        <p>
          {t('rates.current', { summary: rateSummary(account.current_rate, account.currency, t) })}
        </p>
      ) : (
        <p className="muted small">{t('rates.none')}</p>
      )}
      {rates.data && rates.data.length > 0 && (
        <ul className="list">
          {[...rates.data].reverse().map((rate) => (
            <li key={rate.id} className="list__row">
              <span className="small">
                {t('rates.since', { date: formatDate(rate.valid_from) })}:{' '}
                {rateSummary(rate, account.currency, t)}
              </span>
              <button
                type="button"
                className="button button--ghost button--danger"
                onClick={() => void remove(rate.id)}
              >
                {t('rates.remove')}
              </button>
            </li>
          ))}
        </ul>
      )}
      <details>
        <summary>{t('rates.add')}</summary>
        <form className="stack stack--tight details-body" onSubmit={(event) => void submit(event)}>
          <p className="muted small">{t('rates.help')}</p>
          <label className="field">
            <span>{t('rates.validFrom')}</span>
            <input
              type="date"
              required
              value={validFrom}
              onChange={(event) => setValidFrom(event.target.value)}
            />
          </label>
          {tiers.map((tier, index) => (
            <div key={index} className="grid-2">
              <label className="field">
                <span>{t('rates.rate')}</span>
                <input
                  inputMode="decimal"
                  required
                  value={tier.rate}
                  onChange={(event) => updateTier(index, { rate: event.target.value })}
                />
              </label>
              <label className="field">
                <span>{t('rates.upTo')}</span>
                <input
                  inputMode="decimal"
                  disabled={index === tiers.length - 1}
                  placeholder={index === tiers.length - 1 ? t('rates.upToHelp') : ''}
                  value={index === tiers.length - 1 ? '' : tier.upTo}
                  onChange={(event) => updateTier(index, { upTo: event.target.value })}
                />
              </label>
            </div>
          ))}
          <div className="actions actions--spread">
            {tiers.length < 5 && (
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setTiers([...tiers, { upTo: '', rate: '' }])}
              >
                {t('rates.addTier')}
              </button>
            )}
            {tiers.length > 1 && (
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setTiers(tiers.slice(0, -1))}
              >
                {t('rates.removeTier')}
              </button>
            )}
          </div>
          <div className="grid-2">
            <label className="field">
              <span>{t('rates.taeLabel')}</span>
              <input
                inputMode="decimal"
                value={tae}
                onChange={(event) => setTae(event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t('rates.withholding')}</span>
              <input
                inputMode="decimal"
                required
                value={withholding}
                onChange={(event) => setWithholding(event.target.value)}
              />
            </label>
          </div>
          <label className="field">
            <span>{t('rates.liquidation')}</span>
            <select
              value={liquidation}
              onChange={(event) =>
                setLiquidation(event.target.value as (typeof LIQUIDATIONS)[number])
              }
            >
              {LIQUIDATIONS.map((option) => (
                <option key={option} value={option}>
                  {t(`rates.liquidations.${option}`)}
                </option>
              ))}
            </select>
          </label>
          <ErrorMessage message={error} />
          <button type="submit" className="button button--secondary">
            {t('rates.add')}
          </button>
        </form>
      </details>
    </section>
  )
}
