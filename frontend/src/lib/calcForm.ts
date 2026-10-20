/**
 * Calculator forms described as data: the fields, how the typed text becomes the API body and
 * back (to reopen a saved scenario). Amounts and rates stay strings end to end (RNF-04).
 */
import type { TFunction } from 'i18next'

import { amountToInput, parseAmountInput } from './amount'
import { parseRateInput, rateToInput } from './rate'

export type ItemValues = Record<string, string | boolean>
export type FormValues = Record<string, string | boolean | ItemValues[]>
export type Body = Record<string, unknown>

export type Option = { value: string; label: string }

type Base = {
  key: string
  /** i18n key */
  label: string
  help?: string
  placeholder?: string
  /** Left empty, it is not sent and the API uses its default. */
  optional?: boolean
  /** Shown (and sent) only when this holds; `own` are the item's values inside a list. */
  when?: (own: ItemValues, all: FormValues) => boolean
}

export type FieldSpec =
  | (Base & { kind: 'amount' | 'rate' | 'int' | 'check' | 'text' })
  | (Base & { kind: 'select' | 'segmented'; options: Option[] })

export type ListSpec = {
  kind: 'list'
  key: string
  /** i18n key with {{n}} for each item's title */
  item: string
  /** i18n key of the add button */
  add: string
  min: number
  max: number
  fields: FieldSpec[]
  blank: (index: number) => ItemValues
}

export type SectionSpec = { title?: string; fields: (FieldSpec | ListSpec)[] }

type Converted = { ok: true; value: unknown } | { ok: false; error: string }

function convert(field: FieldSpec, raw: string | boolean | undefined, t: TFunction): Converted {
  if (field.kind === 'check') {
    return { ok: true, value: Boolean(raw) }
  }
  const text = typeof raw === 'string' ? raw.trim() : ''
  if (field.kind === 'segmented' || ((field.kind === 'select' || field.kind === 'text') && text)) {
    return { ok: true, value: text }
  }
  if (!text) {
    return field.optional
      ? { ok: true, value: undefined }
      : { ok: false, error: t('calc.required', { field: t(field.label) }) }
  }
  let value: unknown = null
  if (field.kind === 'amount') {
    value = parseAmountInput(text, { allowZero: true })
  } else if (field.kind === 'rate') {
    value = parseRateInput(text)
  } else if (/^\d{1,7}$/.test(text.replace(/\./g, ''))) {
    value = Number(text.replace(/\./g, ''))
  }
  return value === null
    ? { ok: false, error: t('calc.invalid', { field: t(field.label) }) }
    : { ok: true, value }
}

function convertFields(
  fields: FieldSpec[],
  own: ItemValues,
  all: FormValues,
  t: TFunction,
): { body: Body } | { error: string } {
  const body: Body = {}
  for (const field of fields) {
    if (field.when && !field.when(own, all)) {
      continue
    }
    const result = convert(field, own[field.key], t)
    if (!result.ok) {
      return { error: result.error }
    }
    if (result.value !== undefined) {
      body[field.key] = result.value
    }
  }
  return { body }
}

/** The API body for the typed values, or the first problem found. */
export function toBody(
  sections: SectionSpec[],
  values: FormValues,
  t: TFunction,
): { body: Body } | { error: string } {
  const body: Body = {}
  const flat = values as ItemValues
  for (const section of sections) {
    for (const field of section.fields) {
      if (field.kind === 'list') {
        const items = (values[field.key] as ItemValues[] | undefined) ?? []
        const converted: Body[] = []
        for (const item of items) {
          const result = convertFields(field.fields, item, values, t)
          if ('error' in result) {
            return result
          }
          converted.push(result.body)
        }
        body[field.key] = converted
      } else {
        const result = convertFields([field], flat, values, t)
        if ('error' in result) {
          return result
        }
        Object.assign(body, result.body)
      }
    }
  }
  return { body }
}

/** "1000.00" → "1000", "1234.50" → "1234,50": how a person would type it. */
export function amountText(value: string): string {
  return amountToInput(value).replace(/,00$/, '')
}

function toText(field: FieldSpec, value: unknown): string | boolean {
  if (field.kind === 'check') {
    return Boolean(value)
  }
  if (value === null || value === undefined) {
    return ''
  }
  if (field.kind === 'amount') {
    return amountText(String(value))
  }
  if (field.kind === 'rate') {
    return rateToInput(String(value))
  }
  return String(value)
}

/** Form values from a saved body, over the defaults (fields the body lacks keep them). */
export function fromBody(sections: SectionSpec[], body: Body, defaults: FormValues): FormValues {
  const values: FormValues = { ...defaults }
  for (const section of sections) {
    for (const field of section.fields) {
      if (!(field.key in body)) {
        continue
      }
      if (field.kind === 'list') {
        const items = (body[field.key] as Body[] | undefined) ?? []
        values[field.key] = items.map((item, index) => {
          const own: ItemValues = { ...field.blank(index) }
          for (const sub of field.fields) {
            if (sub.key in item) {
              own[sub.key] = toText(sub, item[sub.key])
            }
          }
          return own
        })
      } else {
        values[field.key] = toText(field, body[field.key])
      }
    }
  }
  return values
}
