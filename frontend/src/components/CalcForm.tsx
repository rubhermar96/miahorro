import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import type { FieldSpec, FormValues, ItemValues, ListSpec, SectionSpec } from '../lib/calcForm'

type Props = {
  sections: SectionSpec[]
  values: FormValues
  onChange: (values: FormValues) => void
}

/** The fields of a calculator, drawn from its description (src/calculators). */
export function CalcForm({ sections, values, onChange }: Props) {
  const { t } = useTranslation()
  const flat = values as ItemValues
  const set = (key: string, value: string | boolean) => onChange({ ...values, [key]: value })

  return (
    <>
      {sections.map((section, index) => {
        const visible = section.fields.filter(
          (field) => field.kind === 'list' || !field.when || field.when(flat, values),
        )
        if (visible.length === 0) {
          return null
        }
        return (
          <fieldset key={section.title ?? index} className="card stack stack--tight">
            {section.title && <legend>{t(section.title)}</legend>}
            <div className="calc-fields">
              {visible.map((field) =>
                field.kind === 'list' ? (
                  <ListField
                    key={field.key}
                    spec={field}
                    values={values}
                    onChange={(items) => onChange({ ...values, [field.key]: items })}
                  />
                ) : (
                  <Field
                    key={field.key}
                    spec={field}
                    value={flat[field.key]}
                    onChange={(value) => set(field.key, value)}
                  />
                ),
              )}
            </div>
          </fieldset>
        )
      })}
    </>
  )
}

function Field({
  spec,
  value,
  onChange,
  context,
}: {
  spec: FieldSpec
  value: string | boolean | undefined
  onChange: (value: string | boolean) => void
  /** Inside a list: the item's title, so every input keeps a distinct name. */
  context?: string
}) {
  const { t } = useTranslation()
  const id = useId()
  const label = t(spec.label)
  const name = context ? `${label} · ${context}` : undefined
  const helpId = spec.help ? `${id}-help` : undefined
  const help = spec.help ? (
    <small id={helpId} className="muted">
      {t(spec.help)}
    </small>
  ) : null

  if (spec.kind === 'check') {
    return (
      <label className="check field--wide">
        <input
          type="checkbox"
          checked={Boolean(value)}
          aria-label={name}
          onChange={(event) => onChange(event.target.checked)}
        />
        <span>{label}</span>
      </label>
    )
  }
  if (spec.kind === 'segmented') {
    return (
      <div className="field field--wide">
        <span id={id}>{label}</span>
        <div
          className={`segmented ${spec.options.length === 2 ? 'segmented--two' : ''}`}
          role="radiogroup"
          aria-label={name}
          aria-labelledby={name ? undefined : id}
          aria-describedby={helpId}
        >
          {spec.options.map((option) => (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={value === option.value}
              className="segmented__option"
              onClick={() => onChange(option.value)}
            >
              {t(option.label)}
            </button>
          ))}
        </div>
        {help}
      </div>
    )
  }
  const common = {
    id,
    value: String(value ?? ''),
    'aria-label': name,
    'aria-describedby': helpId,
  }
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {spec.kind === 'select' ? (
        <select {...common} onChange={(event) => onChange(event.target.value)}>
          {spec.options.map((option) => (
            <option key={option.value} value={option.value}>
              {t(option.label)}
            </option>
          ))}
        </select>
      ) : (
        <input
          {...common}
          maxLength={spec.kind === 'text' ? 40 : undefined}
          inputMode={spec.kind === 'text' ? undefined : spec.kind === 'int' ? 'numeric' : 'decimal'}
          placeholder={spec.placeholder ? t(spec.placeholder) : undefined}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
      {help}
    </div>
  )
}

function ListField({
  spec,
  values,
  onChange,
}: {
  spec: ListSpec
  values: FormValues
  onChange: (items: ItemValues[]) => void
}) {
  const { t } = useTranslation()
  const items = (values[spec.key] as ItemValues[] | undefined) ?? []
  const update = (index: number, key: string, value: string | boolean) =>
    onChange(items.map((item, i) => (i === index ? { ...item, [key]: value } : item)))

  return (
    <div className="field--wide stack stack--tight">
      {items.map((item, index) => {
        const title = String(item.name || t(spec.item, { n: index + 1 }))
        return (
          <div key={index} className="calc-item stack stack--tight">
            <div className="section-title">
              <h3>{title}</h3>
              {items.length > spec.min && (
                <button
                  type="button"
                  className="button button--ghost button--danger"
                  aria-label={t('calc.removeItem', { name: title })}
                  onClick={() => onChange(items.filter((_, i) => i !== index))}
                >
                  ✕
                </button>
              )}
            </div>
            <div className="calc-fields">
              {spec.fields
                .filter((field) => !field.when || field.when(item, values))
                .map((field) => (
                  <Field
                    key={field.key}
                    spec={field}
                    value={item[field.key]}
                    context={t(spec.item, { n: index + 1 })}
                    onChange={(value) => update(index, field.key, value)}
                  />
                ))}
            </div>
          </div>
        )
      })}
      {items.length < spec.max && (
        <button
          type="button"
          className="button button--secondary"
          onClick={() => onChange([...items, spec.blank(items.length)])}
        >
          {t(spec.add)}
        </button>
      )}
    </div>
  )
}
