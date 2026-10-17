import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import {
  type Account,
  type Category,
  categoryLabel,
  refreshFinance,
  useAccounts,
  useCategories,
} from '../api/finance'
import {
  type ImportBatch,
  importApi,
  importKeys,
  type ImportPreview,
  type Mapping,
  type PreviewRow,
  useImports,
  useTemplates,
} from '../api/imports'
import { ErrorMessage } from '../components/ErrorMessage'
import { Money } from '../components/Money'
import { PageHeader } from '../components/PageHeader'
import { messageOf } from '../lib/errors'
import { formatDate } from '../lib/format'

type Decision = PreviewRow['decisions'][number]
type Decisions = Record<number, Decision>

/** What happens to a row when it is ticked: the server's proposal, never "skip". */
function firstAction(row: PreviewRow): Decision {
  return row.decisions.find((d) => d !== 'skip') ?? 'import'
}

const ACCEPT = '.csv,.txt,.xlsx,.xls,.pdf,text/csv,application/pdf'

/** Import a bank statement: choose the file, check what it adds, import (RF-IMP-01). */
export function ImportPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const queryClient = useQueryClient()
  const accounts = useAccounts()
  const categories = useCategories(true)
  const templates = useTemplates()
  const [chosenAccount, setChosenAccount] = useState(params.get('cuenta') ?? '')
  const [file, setFile] = useState<File | null>(null)
  const [templateId, setTemplateId] = useState('')
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [decisions, setDecisions] = useState<Decisions>({})
  const [saveTemplate, setSaveTemplate] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [done, setDone] = useState<ImportBatch | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const accountId = chosenAccount || accounts.data?.[0]?.id || ''
  const account = accounts.data?.find((a) => a.id === accountId)

  const load = async (mapping?: Mapping) => {
    if (!file || !accountId) {
      return
    }
    setError(null)
    setBusy(true)
    try {
      const result = await importApi.preview({
        file,
        accountId,
        mapping,
        templateId: mapping ? null : templateId || null,
      })
      setPreview(result)
      setDecisions(
        Object.fromEntries(result.rows.map((row) => [row.number, row.decisions[0] ?? 'skip'])),
      )
    } catch (err) {
      setPreview(null)
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  const reset = () => {
    setPreview(null)
    setDone(null)
    setError(null)
    setSaveTemplate(false)
    setTemplateName('')
  }

  const submit = async () => {
    // A PDF statement is read by its bank's reader: there are no columns to map.
    if (!file || (!preview?.mapping && !preview?.reader)) {
      return
    }
    const included = Object.values(decisions).filter((d) => d !== 'skip').length
    if (included === 0) {
      setError(t('imports.nothingSelected'))
      return
    }
    setError(null)
    setBusy(true)
    try {
      const batch = await importApi.create({
        file,
        accountId,
        mapping: preview.mapping ?? null,
        decisions,
        templateId: preview.template_id,
        saveTemplateAs: saveTemplate ? templateName : undefined,
      })
      await Promise.all([
        refreshFinance(queryClient),
        queryClient.invalidateQueries({ queryKey: importKeys.imports }),
        queryClient.invalidateQueries({ queryKey: importKeys.templates }),
      ])
      setDone(batch)
      setPreview(null)
      setFile(null)
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  if (accounts.isSuccess && accounts.data.length === 0) {
    return (
      <>
        <PageHeader title={t('imports.title')} back="/mas" />
        <div className="card stack stack--tight">
          <p>{t('imports.noAccounts')}</p>
          <Link className="button" to="/cuentas/nueva">
            {t('home.addAccount')}
          </Link>
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader title={t('imports.title')} back="/mas" />
      <div className="stack">
        {done && account ? (
          <Done batch={done} account={account} onAnother={reset} />
        ) : (
          <form
            className="card stack"
            onSubmit={(event: FormEvent) => {
              event.preventDefault()
              void load()
            }}
          >
            <p className="muted small">{t('imports.intro')}</p>
            <label className="field">
              <span>{t('imports.account')}</span>
              <select
                value={accountId}
                onChange={(event) => {
                  setChosenAccount(event.target.value)
                  setPreview(null)
                }}
              >
                {accounts.data?.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>{t('imports.file')}</span>
              <input
                type="file"
                accept={ACCEPT}
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null)
                  setPreview(null)
                }}
              />
              <small className="muted">{t('imports.fileHelp')}</small>
            </label>
            {(templates.data?.length ?? 0) > 0 && (
              <label className="field">
                <span>{t('imports.template')}</span>
                <select
                  value={templateId}
                  onChange={(event) => {
                    setTemplateId(event.target.value)
                    setPreview(null)
                  }}
                >
                  <option value="">{t('imports.autoTemplate')}</option>
                  {templates.data?.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {!preview && (
              <button type="submit" className="button" disabled={busy || !file}>
                {busy ? t('imports.reading') : t('imports.preview')}
              </button>
            )}
          </form>
        )}

        {preview?.reader && (
          <p className="notice small" role="status">
            {t('imports.pdfReader', { reader: preview.reader })}
          </p>
        )}

        {preview && !preview.reader && (
          <MappingEditor
            key={JSON.stringify(preview.mapping) + preview.columns.join('|')}
            preview={preview}
            open={preview.mapping === null || preview.error !== null}
            onApply={(mapping) => void load(mapping)}
          />
        )}

        <ErrorMessage message={error ?? preview?.error ?? null} />

        {preview && preview.rows.length > 0 && account && (
          <Review
            preview={preview}
            account={account}
            accounts={accounts.data ?? []}
            categories={categories.data ?? []}
            decisions={decisions}
            onDecide={setDecisions}
          />
        )}

        {preview && preview.rows.length > 0 && (
          <section className="card stack stack--tight">
            {!preview.template_id && !preview.reader && (
              <>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={saveTemplate}
                    onChange={(event) => setSaveTemplate(event.target.checked)}
                  />
                  <span>{t('imports.saveTemplate')}</span>
                </label>
                {saveTemplate && (
                  <label className="field">
                    <span>{t('imports.templateName')}</span>
                    <input
                      required
                      maxLength={60}
                      value={templateName}
                      onChange={(event) => setTemplateName(event.target.value)}
                    />
                    <small className="muted">{t('imports.saveTemplateHelp')}</small>
                  </label>
                )}
              </>
            )}
            <button
              type="button"
              className="button button--large"
              disabled={busy || (saveTemplate && !templateName.trim())}
              onClick={() => void submit()}
            >
              {t('imports.submit', {
                count: Object.values(decisions).filter((d) => d !== 'skip').length,
              })}
            </button>
          </section>
        )}

        {accountId && <History accountId={accountId} />}
      </div>
    </>
  )
}

type Draft = {
  date: string
  description: string
  extra: string
  mode: 'one' | 'two'
  amount: string
  debit: string
  credit: string
  balance: string
  invert: boolean
}

function toDraft(mapping: Mapping | null): Draft {
  return {
    date: mapping?.date ?? '',
    description: mapping?.description[0] ?? '',
    extra: mapping?.description[1] ?? '',
    mode: mapping && mapping.amount == null && (mapping.debit || mapping.credit) ? 'two' : 'one',
    amount: mapping?.amount ?? '',
    debit: mapping?.debit ?? '',
    credit: mapping?.credit ?? '',
    balance: mapping?.balance ?? '',
    invert: mapping?.invert_sign ?? false,
  }
}

function toMapping(draft: Draft): Mapping | null {
  const amounts =
    draft.mode === 'one'
      ? draft.amount && { amount: draft.amount }
      : (draft.debit || draft.credit) && {
          debit: draft.debit || null,
          credit: draft.credit || null,
        }
  if (!draft.date || !draft.description || !amounts) {
    return null
  }
  return {
    date: draft.date,
    description: [draft.description, draft.extra].filter(Boolean),
    ...amounts,
    balance: draft.balance || null,
    invert_sign: draft.invert,
    // Detected again from the chosen columns.
    date_order: null,
    decimal_comma: null,
  }
}

/** Which column is each field. Opens by itself when the file was not recognised. */
function MappingEditor({
  preview,
  open,
  onApply,
}: {
  preview: ImportPreview
  open: boolean
  onApply: (mapping: Mapping) => void
}) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState(() => toDraft(preview.mapping))

  const change = (changes: Partial<Draft>) => {
    const next = { ...draft, ...changes }
    setDraft(next)
    const mapping = toMapping(next)
    if (mapping) {
      onApply(mapping)
    }
  }

  const column = (
    field: 'date' | 'description' | 'extra' | 'amount' | 'debit' | 'credit' | 'balance',
    label: string,
    optional = false,
  ) => (
    <label className="field">
      <span>{label}</span>
      <select value={draft[field]} onChange={(event) => change({ [field]: event.target.value })}>
        <option value="">{optional ? t('imports.none') : t('imports.chooseColumn')}</option>
        {preview.columns.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
    </label>
  )

  return (
    <details className="card" open={open}>
      <summary>{t('imports.columnsTitle')}</summary>
      <div className="stack stack--tight details-body">
        <p className="muted small">{t('imports.columnsHelp')}</p>
        <div className="grid-2">
          {column('date', t('imports.date'))}
          {column('description', t('imports.description'))}
        </div>
        {column('extra', t('imports.extraDescription'), true)}
        <div
          className="segmented segmented--two"
          role="radiogroup"
          aria-label={t('imports.amountMode')}
        >
          {(['one', 'two'] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              role="radio"
              aria-checked={draft.mode === mode}
              className="segmented__option"
              onClick={() => change({ mode })}
            >
              {mode === 'one' ? t('imports.oneColumn') : t('imports.twoColumns')}
            </button>
          ))}
        </div>
        {draft.mode === 'one' ? (
          column('amount', t('imports.amount'))
        ) : (
          <div className="grid-2">
            {column('debit', t('imports.debit'), true)}
            {column('credit', t('imports.credit'), true)}
          </div>
        )}
        {column('balance', t('imports.balance'), true)}
        <label className="check">
          <input
            type="checkbox"
            checked={draft.invert}
            onChange={(event) => change({ invert: event.target.checked })}
          />
          <span>{t('imports.invertSign')}</span>
        </label>
        {preview.sample.length > 0 && (
          <div className="table-scroll" role="region" aria-label={t('imports.sample')} tabIndex={0}>
            <table className="sample">
              <thead>
                <tr>
                  {preview.columns.map((name) => (
                    <th key={name}>{name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.sample.map((row, index) => (
                  <tr key={index}>
                    {preview.columns.map((name, cell) => (
                      <td key={name}>{row[cell] ?? ''}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </details>
  )
}

/** The rows the file would add, each with what will happen to it, plus the balance check. */
function Review({
  preview,
  account,
  accounts,
  categories,
  decisions,
  onDecide,
}: {
  preview: ImportPreview
  account: Account
  accounts: Account[]
  categories: Category[]
  decisions: Decisions
  onDecide: (decisions: Decisions) => void
}) {
  const { t } = useTranslation()
  const count = (status: string) => preview.rows.filter((r) => r.status === status).length
  const summary = [
    t('imports.summaryNew', { count: count('new') }),
    count('duplicate') > 0 && t('imports.summaryDuplicate', { count: count('duplicate') }),
    count('match') > 0 && t('imports.summaryMatch', { count: count('match') }),
    count('transfer') > 0 && t('imports.summaryTransfer', { count: count('transfer') }),
  ].filter(Boolean)
  const included = preview.rows.filter((r) => decisions[r.number] !== 'skip').length
  const accountName = (id: string | null) => accounts.find((a) => a.id === id)?.name ?? ''

  const decide = (number: number, decision: Decision) =>
    onDecide({ ...decisions, [number]: decision })

  const optionLabel = (row: PreviewRow, decision: Decision) =>
    decision === 'transfer'
      ? t('imports.decision.transfer', { account: accountName(row.transfer_account_id) })
      : row.status === 'transfer' && decision === 'import'
        ? t('imports.decision.plain')
        : t(`imports.decision.${decision}`)

  const balanceMatches =
    preview.bank_balance !== null && preview.bank_balance === preview.balance_then

  return (
    <>
      {preview.bank_balance !== null && preview.bank_balance_date && preview.balance_then && (
        <section className="card">
          <dl className="details">
            <div>
              <dt>{t('imports.bankBalance', { date: formatDate(preview.bank_balance_date) })}</dt>
              <dd>
                <Money value={preview.bank_balance} currency={account.currency} />
              </dd>
            </div>
            <div>
              <dt>{t('imports.appBalance')}</dt>
              <dd>
                <Money value={preview.balance_then} currency={account.currency} />
              </dd>
            </div>
          </dl>
          <p className={balanceMatches ? 'status--ok small' : 'notice small'}>
            {balanceMatches ? t('imports.balanceOk') : t('imports.balanceOff')}
          </p>
        </section>
      )}

      <section className="stack stack--tight" aria-label={summary.join(' · ')}>
        <div className="section-title">
          <p className="muted">{summary.join(' · ')}</p>
          <button
            type="button"
            className="button button--ghost"
            onClick={() =>
              onDecide(
                Object.fromEntries(
                  preview.rows.map((row) => [
                    row.number,
                    included === preview.rows.length ? 'skip' : firstAction(row),
                  ]),
                ),
              )
            }
          >
            {included === preview.rows.length ? t('imports.selectNone') : t('imports.selectAll')}
          </button>
        </div>
        {(count('match') > 0 || count('transfer') > 0) && (
          <p className="notice small">{t('imports.reconcileHelp')}</p>
        )}
        <ul className="list card card--flush">
          {preview.rows.map((row) => {
            const decision = decisions[row.number] ?? 'skip'
            const actions = row.decisions.filter((d) => d !== 'skip')
            return (
              <li key={row.number}>
                <label className="row">
                  <input
                    type="checkbox"
                    className="row__check"
                    checked={decision !== 'skip'}
                    onChange={() =>
                      decide(row.number, decision === 'skip' ? firstAction(row) : 'skip')
                    }
                  />
                  <span className="row__text">
                    <span className="row__title">{row.description || '—'}</span>
                    <small className="muted">
                      {[
                        formatDate(row.date),
                        categoryLabel(categories, row.category_id),
                        row.status === 'transfer'
                          ? t('imports.status.transfer', {
                              account: accountName(row.transfer_account_id),
                            })
                          : row.status !== 'new' && t(`imports.status.${row.status}`),
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </small>
                  </span>
                  <Money value={row.amount} currency={account.currency} signed />
                </label>
                {decision !== 'skip' && actions.length > 1 && (
                  <div className="row__choice">
                    <select
                      aria-label={t('imports.decisionFor', { name: row.description })}
                      value={decision}
                      onChange={(event) => decide(row.number, event.target.value as Decision)}
                    >
                      {actions.map((action) => (
                        <option key={action} value={action}>
                          {optionLabel(row, action)}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
        {preview.skipped.length > 0 && (
          <details className="card">
            <summary>{t('imports.skipped', { count: preview.skipped.length })}</summary>
            <ul className="stack stack--tight details-body small">
              {preview.skipped.map((row) => (
                <li key={row.number}>
                  <strong>{t('imports.row', { number: row.number })}:</strong> {row.reason}
                  <br />
                  <span className="muted">{row.text}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>
    </>
  )
}

function Done({
  batch,
  account,
  onAnother,
}: {
  batch: ImportBatch
  account: Account
  onAnother: () => void
}) {
  const { t } = useTranslation()
  return (
    <section className="card stack stack--tight" role="status">
      <p className="saved">
        {t('imports.done', { count: batch.imported, account: account.name })}
        {batch.merged > 0 && ` ${t('imports.doneMerged', { count: batch.merged })}`}
      </p>
      <p className="muted small">{t('imports.uncategorised')}</p>
      <Link className="button" to={`/movimientos?cuenta=${account.id}`}>
        {t('imports.seeTransactions')}
      </Link>
      <Link className="button button--secondary" to="/mas/reglas">
        {t('imports.goRules')}
      </Link>
      <button type="button" className="button button--ghost" onClick={onAnother}>
        {t('imports.another')}
      </button>
    </section>
  )
}

function History({ accountId }: { accountId: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const imports = useImports(accountId)
  const [message, setMessage] = useState<string | null>(null)

  const undo = async (batch: ImportBatch) => {
    if (!window.confirm(t('imports.confirmUndo', { count: batch.imported }))) {
      return
    }
    await importApi.undo(batch.id)
    await Promise.all([
      refreshFinance(queryClient),
      queryClient.invalidateQueries({ queryKey: importKeys.imports }),
    ])
    setMessage(t('imports.undone'))
  }

  if (!imports.data?.length && !message) {
    return null
  }
  return (
    <section className="stack stack--tight" aria-labelledby="imports-history">
      <h2 id="imports-history" className="section-title">
        {t('imports.history')}
      </h2>
      {message && (
        <p className="muted" role="status">
          {message}
        </p>
      )}
      <ul className="list card card--flush">
        {imports.data?.map((batch) => (
          <li key={batch.id} className="row">
            <span className="row__text">
              <span className="row__title">{batch.filename}</span>
              <small className="muted">
                {t('imports.historyItem', {
                  count: batch.imported,
                  from: batch.date_from ? formatDate(batch.date_from) : '—',
                  to: batch.date_to ? formatDate(batch.date_to) : '—',
                })}
              </small>
            </span>
            <button
              type="button"
              className="button button--ghost button--danger"
              onClick={() => void undo(batch)}
            >
              {t('imports.undo')}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
