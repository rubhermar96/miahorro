import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { type Account, refreshFinance, useAccounts } from '../api/finance'
import {
  type Investment,
  type InvestmentDetail,
  investmentKeys,
  investmentsApi,
  type Operation,
  type OperationInput,
  type OperationKind,
  useInvestment,
  useInvestments,
  useOperations,
} from '../api/investments'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { amountToInput, parseAmountInput } from '../lib/amount'
import { messageOf } from '../lib/errors'
import { todayIso } from '../lib/format'
import { formatPrice, parseUnitsInput, unitsToInput } from '../lib/units'

const TRANSFERABLE = ['fund', 'pension_plan']

/** Record or change an operation of an investment (RF-INV-02). */
export function OperationFormPage() {
  const { t } = useTranslation()
  const { id = '', operationId = '' } = useParams()
  const investment = useInvestment(id)
  const operations = useOperations(id)
  const investments = useInvestments(true)
  const accounts = useAccounts()
  const operation = operations.data?.find((op) => op.id === operationId && op.direction === 'out')
  if (
    !investment.data ||
    !investments.data ||
    !accounts.data ||
    (operationId !== '' && !operations.data)
  ) {
    return <PageHeader title={t('inv.opTitle')} back={`/inversiones/${id}`} />
  }
  if (operationId && !operation) {
    return (
      <>
        <PageHeader title={t('inv.opTitle')} back={`/inversiones/${id}`} />
        <p className="card muted">{t('inv.opMissing')}</p>
      </>
    )
  }
  return (
    <OperationForm
      key={operation?.id ?? 'new'}
      investment={investment.data}
      operation={operation}
      investments={investments.data}
      accounts={accounts.data}
    />
  )
}

const text = (value: string | null | undefined) =>
  value && value !== '0.00' ? amountToInput(value) : ''

function OperationForm({
  investment,
  operation,
  investments,
  accounts,
}: {
  investment: InvestmentDetail
  operation?: Operation
  investments: Investment[]
  accounts: Account[]
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const pension = investment.kind === 'pension_plan'
  const kinds: OperationKind[] = [
    'buy',
    'sell',
    ...(pension ? [] : (['dividend', 'fee'] as OperationKind[])),
    ...(investment.kind === 'stock' || investment.kind === 'etf' ? (['split'] as const) : []),
    ...(TRANSFERABLE.includes(investment.kind) ? (['transfer'] as const) : []),
  ]
  const targets = investments.filter(
    (other) =>
      other.id !== investment.id &&
      other.kind === investment.kind &&
      (!other.archived || other.id === operation?.target_investment_id),
  )
  const [kind, setKind] = useState<OperationKind>(operation?.kind ?? 'buy')
  const [date, setDate] = useState(operation?.date ?? todayIso())
  const [unitsText, setUnitsText] = useState(
    unitsToInput(operation?.units === '0' ? '' : operation?.units),
  )
  const [amountText, setAmountText] = useState(text(operation?.amount))
  const [feeText, setFeeText] = useState(text(operation?.fee))
  const [withholdingText, setWithholdingText] = useState(text(operation?.withholding))
  const [splitFrom, setSplitFrom] = useState(String(operation?.split_from ?? 1))
  const [splitTo, setSplitTo] = useState(String(operation?.split_to ?? 2))
  const [targetId, setTargetId] = useState(operation?.target_investment_id ?? targets[0]?.id ?? '')
  const [targetUnitsText, setTargetUnitsText] = useState(unitsToInput(operation?.target_units))
  const [accountId, setAccountId] = useState(
    operation ? (operation.cash_account_id ?? '') : (investment.account_id ?? ''),
  )
  const [note, setNote] = useState(operation?.note ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const back = `/inversiones/${investment.id}`
  const withUnits = kind === 'buy' || kind === 'sell' || kind === 'transfer'
  const withCash = kind !== 'split' && kind !== 'transfer'
  const units = parseUnitsInput(unitsText)
  const amount = parseAmountInput(amountText)
  const price =
    (kind === 'buy' || kind === 'sell') && units && amount
      ? (Number(amount) / Number(units)).toFixed(6)
      : null

  const done = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: investmentKeys.all }),
      refreshFinance(queryClient),
    ])
    void navigate(back, { replace: true })
  }

  const optionalAmount = (value: string) =>
    value.trim() ? parseAmountInput(value, { allowZero: true }) : '0.00'

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const fee = optionalAmount(feeText)
    const withholding = optionalAmount(withholdingText)
    if (withUnits && !units) {
      setError(t('inv.invalidUnits'))
      return
    }
    if (kind !== 'split' && kind !== 'transfer' && !amount) {
      setError(t('add.invalidAmount'))
      return
    }
    if (fee === null || withholding === null) {
      setError(t('add.invalidAmount'))
      return
    }
    const body: OperationInput = {
      date,
      kind,
      units: withUnits && units ? units : '0',
      amount: kind === 'split' ? '0.00' : (amount ?? '0.00'),
      fee: kind === 'buy' || kind === 'sell' ? fee : '0.00',
      withholding: kind === 'sell' || kind === 'dividend' ? withholding : '0.00',
      note: note.trim() || null,
      cash_account_id: withCash && accountId ? accountId : null,
    }
    if (kind === 'split') {
      body.split_from = Number(splitFrom)
      body.split_to = Number(splitTo)
    }
    if (kind === 'transfer') {
      const received = parseUnitsInput(targetUnitsText)
      if (!targetId || !received) {
        setError(t('inv.invalidTransfer'))
        return
      }
      body.target_investment_id = targetId
      body.target_units = received
    }
    setBusy(true)
    try {
      if (operation) {
        await investmentsApi.replaceOperation(investment.id, operation.id, body)
      } else {
        await investmentsApi.addOperation(investment.id, body)
      }
      await done()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!operation || !window.confirm(t('inv.confirmDeleteOperation'))) {
      return
    }
    try {
      await investmentsApi.removeOperation(investment.id, operation.id)
      await done()
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  const kindLabel = (option: OperationKind) =>
    pension && (option === 'buy' || option === 'sell')
      ? t(`inv.opsPension.${option}`)
      : t(`inv.ops.${option}`)

  return (
    <>
      <PageHeader title={operation ? t('inv.opEditTitle') : t('inv.opTitle')} back={back} />
      <form className="stack" onSubmit={(event) => void submit(event)}>
        <p className="muted">{investment.name}</p>
        <div className="grid-2">
          <label className="field">
            <span>{t('inv.opKind')}</span>
            <select value={kind} onChange={(event) => setKind(event.target.value as OperationKind)}>
              {kinds.map((option) => (
                <option key={option} value={option}>
                  {kindLabel(option)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t('add.date')}</span>
            <input
              type="date"
              required
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
        </div>

        {withUnits && (
          <div className="grid-2">
            <div className="field">
              <label htmlFor="op-units">{t(`inv.unitsOf.${investment.kind}`)}</label>
              <input
                id="op-units"
                inputMode="decimal"
                required
                value={unitsText}
                onChange={(event) => setUnitsText(event.target.value)}
              />
              {(kind === 'sell' || kind === 'transfer') && investment.units !== '0' && (
                <button
                  type="button"
                  className="link-button small"
                  onClick={() => setUnitsText(unitsToInput(investment.units))}
                >
                  {t('inv.allUnits')}
                </button>
              )}
            </div>
            {kind !== 'transfer' && (
              <label className="field">
                <span>{t(kind === 'buy' ? 'inv.amountPaid' : 'inv.amountReceived')}</span>
                <input
                  inputMode="decimal"
                  required
                  value={amountText}
                  onChange={(event) => setAmountText(event.target.value)}
                />
                <small className="muted">
                  {price
                    ? `${t('inv.amountHelp')} ${t('inv.impliedPrice', { price: formatPrice(price) })}`
                    : t('inv.amountHelp')}
                </small>
              </label>
            )}
          </div>
        )}

        {(kind === 'dividend' || kind === 'fee') && (
          <label className="field">
            <span>{t(kind === 'dividend' ? 'inv.grossDividend' : 'inv.feeAmount')}</span>
            <input
              inputMode="decimal"
              required
              value={amountText}
              onChange={(event) => setAmountText(event.target.value)}
            />
          </label>
        )}

        {(kind === 'buy' || kind === 'sell' || kind === 'dividend') && (
          <div className="grid-2">
            {kind !== 'dividend' && (
              <label className="field">
                <span>{t('inv.commission')}</span>
                <input
                  inputMode="decimal"
                  value={feeText}
                  onChange={(event) => setFeeText(event.target.value)}
                />
              </label>
            )}
            {kind !== 'buy' && (
              <label className="field">
                <span>{t('inv.withholding')}</span>
                <input
                  inputMode="decimal"
                  value={withholdingText}
                  onChange={(event) => setWithholdingText(event.target.value)}
                />
              </label>
            )}
          </div>
        )}

        {kind === 'split' && (
          <fieldset className="card stack stack--tight">
            <legend>{t('inv.splitTitle')}</legend>
            <div className="grid-2">
              <label className="field">
                <span>{t('inv.splitFrom')}</span>
                <input
                  inputMode="numeric"
                  value={splitFrom}
                  onChange={(event) => setSplitFrom(event.target.value)}
                />
              </label>
              <label className="field">
                <span>{t('inv.splitTo')}</span>
                <input
                  inputMode="numeric"
                  value={splitTo}
                  onChange={(event) => setSplitTo(event.target.value)}
                />
              </label>
            </div>
            <small className="muted">{t('inv.splitHelp')}</small>
          </fieldset>
        )}

        {kind === 'transfer' && (
          <fieldset className="card stack stack--tight">
            <legend>{t('inv.transferTitle')}</legend>
            {targets.length === 0 ? (
              <p className="muted small">{t('inv.noTargets')}</p>
            ) : (
              <>
                <label className="field">
                  <span>{t('inv.target')}</span>
                  <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
                    {targets.map((target) => (
                      <option key={target.id} value={target.id}>
                        {target.name}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="grid-2">
                  <label className="field">
                    <span>{t('inv.targetUnits')}</span>
                    <input
                      inputMode="decimal"
                      required
                      value={targetUnitsText}
                      onChange={(event) => setTargetUnitsText(event.target.value)}
                    />
                  </label>
                  <label className="field">
                    <span>{t('inv.transferValue')}</span>
                    <input
                      inputMode="decimal"
                      value={amountText}
                      onChange={(event) => setAmountText(event.target.value)}
                    />
                  </label>
                </div>
              </>
            )}
            <small className="muted">{t('inv.transferHelp')}</small>
          </fieldset>
        )}

        {withCash && (
          <label className="field">
            <span>{t('inv.cashAccount')}</span>
            <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
              <option value="">{t('inv.noCash')}</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
            <small className="muted">{t('inv.cashHelp')}</small>
          </label>
        )}

        <label className="field">
          <span>{t('add.note')}</span>
          <textarea rows={2} value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
        <ErrorMessage message={error} />
        <button type="submit" className="button" disabled={busy}>
          {operation ? t('add.save') : t('inv.saveOperation')}
        </button>
        {operation && (
          <button
            type="button"
            className="button button--ghost button--danger"
            onClick={() => void remove()}
          >
            {t('inv.deleteOperation')}
          </button>
        )}
      </form>
    </>
  )
}
