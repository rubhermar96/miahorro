import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router'

import {
  type CalcBody,
  type CalcContext,
  calcKeys,
  runCalculator,
  type Scenario,
  scenariosApi,
  useCalcContext,
  useScenarios,
} from '../api/calculators'
import { calculatorBySlug } from '../calculators'
import { CompareTable } from '../calculators/parts'
import type { CalculatorDef } from '../calculators/types'
import { CalcForm } from '../components/CalcForm'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { type FormValues, fromBody, toBody } from '../lib/calcForm'
import { messageOf } from '../lib/errors'
import { formatDate, formatShortDate } from '../lib/format'

const BACK = '/planificar/calculadoras'
const MAX_COMPARED = 4

/** One calculator: its form prefilled with the user's figures, the result, and the saved
 * scenarios to reopen or compare side by side (RF-CAL). */
export function CalculatorPage() {
  const { t } = useTranslation()
  const { slug = '' } = useParams()
  const definition = calculatorBySlug(slug)
  const context = useCalcContext()
  if (!definition) {
    return (
      <>
        <PageHeader title={t('calc.title')} back={BACK} />
        <p className="card muted">{t('calc.unknown')}</p>
      </>
    )
  }
  if (context.isPending) {
    return <PageHeader title={t(`calc.${definition.name}.title`)} back={BACK} />
  }
  return <Calculator key={definition.name} definition={definition} context={context.data} />
}

function Calculator({
  definition,
  context,
}: {
  definition: CalculatorDef
  context: CalcContext | undefined
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [values, setValues] = useState<FormValues>(() => definition.defaults(context))
  const [result, setResult] = useState<unknown>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [active, setActive] = useState<Scenario | null>(null)
  const { Result, Extra } = definition

  const change = (next: FormValues) => {
    setValues(next)
    setResult(null) // a result is only shown for the values it was worked out with
  }

  const buildBody = (): CalcBody | null => {
    const built = toBody(definition.sections, values, t)
    if ('error' in built) {
      setError(built.error)
      return null
    }
    return definition.finalize ? definition.finalize(built.body) : built.body
  }

  const run = async (body: CalcBody) => {
    setBusy(true)
    setError(null)
    try {
      setResult(await runCalculator(definition.name, body))
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    } finally {
      setBusy(false)
    }
  }

  const calculate = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    const body = buildBody()
    if (body) {
      await run(body)
    }
  }

  const open = async (scenario: Scenario) => {
    const inputs = definition.restore ? definition.restore(scenario.inputs) : scenario.inputs
    setValues(fromBody(definition.sections, inputs, definition.defaults(context)))
    setActive(scenario)
    window.scrollTo?.({ top: 0 })
    await run(scenario.inputs)
  }

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: [...calcKeys.scenarios, definition.name] })

  return (
    <>
      <PageHeader title={t(`calc.${definition.name}.title`)} back={BACK} />
      <form className="stack" onSubmit={(event) => void calculate(event)} noValidate>
        <p className="muted small">{t(`calc.${definition.name}.description`)}</p>
        {active && (
          <p className="notice small">{t('calc.scenarios.editing', { name: active.name })}</p>
        )}
        {context && context.months > 0 && (
          <p className="notice small">
            {t('calc.prefilled', {
              count: context.months,
              from: context.start ? formatShortDate(context.start) : '',
              to: context.end ? formatShortDate(context.end) : '',
            })}{' '}
            <button
              type="button"
              className="link-button"
              onClick={() => {
                change(definition.defaults(context))
                setActive(null)
              }}
            >
              {t('calc.reset')}
            </button>
          </p>
        )}
        {Extra && context && <Extra context={context} values={values} onChange={change} />}
        <CalcForm sections={definition.sections} values={values} onChange={change} />
        <ErrorMessage message={error} />
        <button type="submit" className="button" disabled={busy}>
          {busy ? t('calc.calculating') : t('calc.calculate')}
        </button>
      </form>

      {result !== null && (
        <section className="card stack calc-result" role="region" aria-label={t('calc.result')}>
          <Result result={result} values={values} context={context} />
          <SaveScenario
            definition={definition}
            active={active}
            buildBody={buildBody}
            onSaved={async (saved) => {
              setActive(saved)
              await refresh()
            }}
          />
        </section>
      )}

      <p className="footnote">{t('calc.disclaimer')}</p>
      <Scenarios definition={definition} active={active} onOpen={(s) => void open(s)} />
    </>
  )
}

function SaveScenario({
  definition,
  active,
  buildBody,
  onSaved,
}: {
  definition: CalculatorDef
  active: Scenario | null
  buildBody: () => CalcBody | null
  onSaved: (scenario: Scenario) => Promise<void>
}) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const save = async (event: FormEvent, update: boolean) => {
    event.preventDefault()
    setMessage(null)
    setError(null)
    const body = buildBody()
    if (!body) {
      return
    }
    try {
      const saved =
        update && active
          ? await scenariosApi.update(active.id, { inputs: body })
          : await scenariosApi.create(definition.name, name.trim(), body)
      setMessage(t('calc.scenarios.saved', { name: saved.name }))
      setName('')
      await onSaved(saved)
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  return (
    <form className="stack stack--tight calc-save" onSubmit={(event) => void save(event, false)}>
      <label className="field">
        <span>{t('calc.scenarios.name')}</span>
        <input
          required
          maxLength={60}
          value={name}
          placeholder={t('calc.scenarios.namePlaceholder')}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <div className="actions">
        <button type="submit" className="button button--secondary" disabled={!name.trim()}>
          {t('calc.scenarios.save')}
        </button>
        {active && (
          <button
            type="button"
            className="button button--secondary"
            onClick={(event) => void save(event, true)}
          >
            {t('calc.scenarios.update', { name: active.name })}
          </button>
        )}
      </div>
      <ErrorMessage message={error} />
      {message && (
        <p className="saved" role="status">
          {message}
        </p>
      )}
    </form>
  )
}

function Scenarios({
  definition,
  active,
  onOpen,
}: {
  definition: CalculatorDef
  active: Scenario | null
  onOpen: (scenario: Scenario) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const scenarios = useScenarios(definition.name)
  const [picked, setPicked] = useState<string[]>([])
  const [compared, setCompared] = useState<{ scenario: Scenario; result: unknown }[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const list = scenarios.data ?? []
  if (list.length === 0) {
    return null
  }

  const toggle = (id: string) => {
    setCompared(null)
    setPicked((current) =>
      current.includes(id) ? current.filter((other) => other !== id) : [...current, id],
    )
  }

  const remove = async (scenario: Scenario) => {
    if (!window.confirm(t('calc.scenarios.confirmDelete', { name: scenario.name }))) {
      return
    }
    await scenariosApi.remove(scenario.id)
    setPicked((current) => current.filter((id) => id !== scenario.id))
    setCompared(null)
    await queryClient.invalidateQueries({ queryKey: [...calcKeys.scenarios, definition.name] })
  }

  const compare = async () => {
    setError(null)
    const chosen = list.filter((scenario) => picked.includes(scenario.id))
    try {
      const results = await Promise.all(
        chosen.map((scenario) => runCalculator(definition.name, scenario.inputs)),
      )
      setCompared(chosen.map((scenario, index) => ({ scenario, result: results[index] })))
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  return (
    <section className="stack stack--tight" aria-labelledby="scenarios-title">
      <h2 id="scenarios-title" className="section-title">
        {t('calc.scenarios.title')}
      </h2>
      <ul className="list card card--flush">
        {list.map((scenario) => (
          <li key={scenario.id} className="row">
            <input
              type="checkbox"
              className="row__check"
              aria-label={t('calc.scenarios.pick', { name: scenario.name })}
              checked={picked.includes(scenario.id)}
              disabled={!picked.includes(scenario.id) && picked.length >= MAX_COMPARED}
              onChange={() => toggle(scenario.id)}
            />
            <span className="row__text">
              <span className="row__title">
                {scenario.name}
                {active?.id === scenario.id && (
                  <span className="tag">{t('calc.scenarios.open')}</span>
                )}
              </span>
              <small className="muted">
                {t('calc.scenarios.updated', {
                  date: formatDate(scenario.updated_at.slice(0, 10)),
                })}
              </small>
            </span>
            <span className="row__actions">
              <button
                type="button"
                className="button button--ghost"
                onClick={() => onOpen(scenario)}
              >
                {t('calc.scenarios.openButton')}
              </button>
              <button
                type="button"
                className="button button--ghost button--danger"
                aria-label={t('calc.scenarios.delete', { name: scenario.name })}
                onClick={() => void remove(scenario)}
              >
                ✕
              </button>
            </span>
          </li>
        ))}
      </ul>
      {list.length > 1 && (
        <button
          type="button"
          className="button button--secondary"
          disabled={picked.length < 2}
          onClick={() => void compare()}
        >
          {picked.length < 2
            ? t('calc.scenarios.pickTwo')
            : t('calc.scenarios.compare', { count: picked.length })}
        </button>
      )}
      <ErrorMessage message={error} />
      {compared && <Comparison definition={definition} compared={compared} />}
    </section>
  )
}

function Comparison({
  definition,
  compared,
}: {
  definition: CalculatorDef
  compared: { scenario: Scenario; result: unknown }[]
}) {
  const { t } = useTranslation()
  const metrics = compared.map(({ result }) => definition.metrics(result, t))
  // Offers may differ between scenarios: one row per label, in the order they appear.
  const labels = [...new Set(metrics.flatMap((list) => list.map((metric) => metric.label)))]
  return (
    <CompareTable
      label={t('calc.scenarios.comparison')}
      columns={compared.map(({ scenario }) => scenario.name)}
      rows={labels.map((label) => ({
        label,
        values: metrics.map((list) => list.find((metric) => metric.label === label)?.value ?? '—'),
      }))}
    />
  )
}
