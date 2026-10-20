import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { type Account, useAccounts } from '../api/finance'
import { type Loan, LOAN_KINDS, type LoanInput, loanKeys, loansApi, useLoan } from '../api/loans'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { amountToInput, parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'
import { todayIso } from '../lib/format'
import { parseRateInput, rateToInput } from '../lib/rate'

type RateType = NonNullable<LoanInput['rate_type']>

/** Create or edit a loan (RF-PRE-01…03). */
export function LoanFormPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const loan = useLoan(id)
  const accounts = useAccounts()
  if ((id && !loan.data) || !accounts.data) {
    return <PageHeader title={t('loans.newTitle')} back="/planificar" />
  }
  return <LoanForm key={loan.data?.id ?? 'new'} loan={loan.data} accounts={accounts.data} />
}

function LoanForm({ loan, accounts }: { loan?: Loan; accounts: Account[] }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState(loan?.name ?? '')
  const [kind, setKind] = useState<NonNullable<LoanInput['kind']>>(loan?.kind ?? 'personal')
  const [lender, setLender] = useState(loan?.lender ?? '')
  const [principalText, setPrincipalText] = useState(loan ? amountToInput(loan.principal) : '')
  const [signedOn, setSignedOn] = useState(loan?.signed_on ?? todayIso())
  const [firstPayment, setFirstPayment] = useState(loan?.first_payment ?? '')
  const [termText, setTermText] = useState(loan ? String(loan.term_months) : '')
  const [system, setSystem] = useState<NonNullable<LoanInput['system']>>(loan?.system ?? 'french')
  const [graceText, setGraceText] = useState(loan ? String(loan.grace_months) : '0')
  const [rateType, setRateType] = useState<RateType>(loan?.rate_type ?? 'fixed')
  const [rateText, setRateText] = useState(rateToInput(loan?.fixed_rate))
  const [fixedMonthsText, setFixedMonthsText] = useState(loan ? String(loan.fixed_months) : '12')
  const [spreadText, setSpreadText] = useState(rateToInput(loan?.spread))
  const [reviewMonths, setReviewMonths] = useState<6 | 12>(loan?.review_months ?? 12)
  const [taeText, setTaeText] = useState(rateToInput(loan?.tae))
  const [feeText, setFeeText] = useState(rateToInput(loan?.early_repayment_fee ?? '0'))
  const [openingText, setOpeningText] = useState(
    loan?.opening_fee ? amountToInput(loan.opening_fee) : '',
  )
  const [accountId, setAccountId] = useState(loan?.account_id ?? '')
  const [note, setNote] = useState(loan?.note ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const variable = rateType !== 'fixed'
  const person = kind === 'p2p_owe' || kind === 'p2p_lent'

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const principal = parseAmountInput(principalText)
    const rate = parseRateInput(rateText)
    const spread = variable ? parseRateInput(spreadText, { allowNegative: true }) : null
    const fee = parseRateInput(feeText || '0')
    const tae = taeText.trim() ? parseRateInput(taeText) : null
    const opening = openingText.trim() ? parseAmountInput(openingText) : null
    const term = Number(termText)
    if (!principal || !Number.isInteger(term) || term < 1) {
      setError(t('loans.invalidAmounts'))
      return
    }
    if (rate === null || fee === null || (variable && spread === null)) {
      setError(t('loans.invalidRate'))
      return
    }
    const body: LoanInput = {
      name,
      kind,
      lender: lender || null,
      principal,
      signed_on: signedOn,
      first_payment: firstPayment,
      term_months: term,
      system,
      grace_months: Number(graceText) || 0,
      rate_type: rateType,
      fixed_rate: rate,
      fixed_months: variable ? Number(fixedMonthsText) || 0 : 0,
      index: variable ? 'euribor_12m' : null,
      spread,
      review_months: reviewMonths,
      tae,
      opening_fee: opening,
      early_repayment_fee: fee,
      account_id: accountId || null,
      note: note || null,
    }
    setBusy(true)
    try {
      const saved = loan ? await loansApi.update(loan.id, body) : await loansApi.create(body)
      await queryClient.invalidateQueries({ queryKey: loanKeys.loans })
      void navigate(`/planificar/prestamos/${saved.id}`, { replace: true })
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title={loan ? t('loans.editTitle') : t('loans.newTitle')}
        back={loan ? `/planificar/prestamos/${loan.id}` : '/planificar'}
      />
      <form className="stack" onSubmit={(event) => void submit(event)}>
        <label className="field">
          <span>{t('loans.name')}</span>
          <input
            required
            maxLength={60}
            placeholder={t('loans.namePlaceholder')}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <div className="grid-2">
          <label className="field">
            <span>{t('loans.kind')}</span>
            <select value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}>
              {LOAN_KINDS.map((option) => (
                <option key={option} value={option}>
                  {t(`loans.kinds.${option}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{person ? t('loans.person') : t('loans.lender')}</span>
            <input
              maxLength={60}
              value={lender}
              onChange={(event) => setLender(event.target.value)}
            />
          </label>
        </div>

        <fieldset className="card stack stack--tight">
          <legend>{t('loans.amounts')}</legend>
          <div className="grid-2">
            <label className="field">
              <span>{t('loans.principal')}</span>
              <input
                inputMode="decimal"
                required
                value={principalText}
                onChange={(event) => setPrincipalText(event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t('loans.term')}</span>
              <input
                inputMode="numeric"
                required
                value={termText}
                onChange={(event) => setTermText(event.target.value)}
              />
              {Number(termText) >= 12 && (
                <small className="muted">
                  {t('loans.termYears', { years: (Number(termText) / 12).toLocaleString('es-ES') })}
                </small>
              )}
            </label>
          </div>
          <div className="grid-2">
            <label className="field">
              <span>{t('loans.signedOn')}</span>
              <input
                type="date"
                required
                value={signedOn}
                onChange={(event) => setSignedOn(event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t('loans.firstPayment')}</span>
              <input
                type="date"
                required
                value={firstPayment}
                onChange={(event) => setFirstPayment(event.target.value)}
              />
            </label>
          </div>
          <div className="grid-2">
            <label className="field">
              <span>{t('loans.system')}</span>
              <select
                value={system}
                onChange={(event) => setSystem(event.target.value as typeof system)}
              >
                <option value="french">{t('loans.systems.french')}</option>
                <option value="linear">{t('loans.systems.linear')}</option>
              </select>
            </label>
            <label className="field">
              <span>{t('loans.grace')}</span>
              <input
                inputMode="numeric"
                value={graceText}
                onChange={(event) => setGraceText(event.target.value)}
              />
            </label>
          </div>
        </fieldset>

        <fieldset className="card stack stack--tight">
          <legend>{t('loans.interest')}</legend>
          <div className="segmented" role="radiogroup" aria-label={t('loans.rateType')}>
            {(['fixed', 'variable', 'mixed'] as const).map((option) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={rateType === option}
                className="segmented__option"
                onClick={() => setRateType(option)}
              >
                {t(`loans.rateTypes.${option}`)}
              </button>
            ))}
          </div>
          <div className="grid-2">
            <label className="field">
              <span>{variable ? t('loans.initialRate') : t('loans.tin')}</span>
              <input
                inputMode="decimal"
                required
                value={rateText}
                onChange={(event) => setRateText(event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t('loans.tae')}</span>
              <input
                inputMode="decimal"
                value={taeText}
                onChange={(event) => setTaeText(event.target.value)}
              />
            </label>
          </div>
          {variable && (
            <>
              <div className="grid-2">
                <label className="field">
                  <span>{t('loans.fixedMonths')}</span>
                  <input
                    inputMode="numeric"
                    value={fixedMonthsText}
                    onChange={(event) => setFixedMonthsText(event.target.value)}
                  />
                </label>
                <label className="field">
                  <span>{t('loans.spread')}</span>
                  <input
                    inputMode="decimal"
                    required
                    value={spreadText}
                    onChange={(event) => setSpreadText(event.target.value)}
                  />
                </label>
              </div>
              <label className="field">
                <span>{t('loans.review')}</span>
                <select
                  value={reviewMonths}
                  onChange={(event) => setReviewMonths(Number(event.target.value) as 6 | 12)}
                >
                  <option value={12}>{t('loans.reviews.12')}</option>
                  <option value={6}>{t('loans.reviews.6')}</option>
                </select>
                <small className="muted">{t('loans.euriborHelp')}</small>
              </label>
            </>
          )}
        </fieldset>

        <fieldset className="card stack stack--tight">
          <legend>{t('loans.fees')}</legend>
          <div className="grid-2">
            <label className="field">
              <span>{t('loans.earlyFee')}</span>
              <input
                inputMode="decimal"
                value={feeText}
                onChange={(event) => setFeeText(event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t('loans.openingFee')}</span>
              <input
                inputMode="decimal"
                value={openingText}
                onChange={(event) => setOpeningText(event.target.value)}
              />
            </label>
          </div>
          <label className="field">
            <span>{t('loans.account')}</span>
            <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
              <option value="">{t('loans.noAccount')}</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          </label>
        </fieldset>

        <label className="field">
          <span>{t('add.note')}</span>
          <textarea rows={2} value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
        <ErrorMessage message={error} />
        <button type="submit" className="button" disabled={busy}>
          {loan ? t('add.save') : t('loans.create')}
        </button>
      </form>
    </>
  )
}
