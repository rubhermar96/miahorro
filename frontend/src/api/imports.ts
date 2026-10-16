import { useQuery } from '@tanstack/react-query'

import { api, CSRF_HEADER, toApiError, unwrap } from './client'
import type { components } from './schema'

export type ImportPreview = components['schemas']['ImportPreview']
export type PreviewRow = components['schemas']['PreviewRow']
export type Mapping = components['schemas']['Mapping']
export type ImportBatch = components['schemas']['ImportOut']
export type ImportTemplate = components['schemas']['TemplateOut']
export type Rule = components['schemas']['RuleOut']
export type RuleInput = components['schemas']['RuleIn']
export type RuleUpdate = components['schemas']['RuleUpdate']
export type BulkEdit = components['schemas']['BulkEdit']

export const importKeys = {
  imports: ['imports'] as const,
  templates: ['import-templates'] as const,
  rules: ['rules'] as const,
}

/** Files go as multipart forms, which the typed JSON client does not build. */
async function postForm<T>(path: string, fields: Record<string, string | File | null>): Promise<T> {
  const form = new FormData()
  for (const [name, value] of Object.entries(fields)) {
    if (value !== null) {
      form.append(name, value)
    }
  }
  const request = new Request(new URL(path, window.location.origin), {
    method: 'POST',
    body: form,
    headers: { [CSRF_HEADER]: '1' },
    credentials: 'same-origin',
  })
  const response = await globalThis.fetch(request)
  const body: unknown = await response.json().catch(() => undefined)
  if (!response.ok) {
    throw toApiError(body, response)
  }
  return body as T
}

export function useImports(accountId?: string) {
  return useQuery({
    queryKey: [...importKeys.imports, accountId ?? 'all'],
    queryFn: () =>
      unwrap(api.GET('/api/imports', { params: { query: { account_id: accountId } } })),
  })
}

export function useTemplates() {
  return useQuery({
    queryKey: importKeys.templates,
    queryFn: () => unwrap(api.GET('/api/import-templates')),
  })
}

export function useRules() {
  return useQuery({ queryKey: importKeys.rules, queryFn: () => unwrap(api.GET('/api/rules')) })
}

export type PreviewRequest = {
  file: File
  accountId: string
  mapping?: Mapping | null
  templateId?: string | null
}

const ruleId = (id: string) => ({ params: { path: { rule_id: id } } })

export const importApi = {
  preview: ({ file, accountId, mapping, templateId }: PreviewRequest) =>
    postForm<ImportPreview>('/api/imports/preview', {
      file,
      account_id: accountId,
      mapping: mapping ? JSON.stringify(mapping) : null,
      template_id: templateId ?? null,
    }),
  create: (
    request: PreviewRequest & { mapping: Mapping; rows: number[]; saveTemplateAs?: string },
  ) =>
    postForm<ImportBatch>('/api/imports', {
      file: request.file,
      account_id: request.accountId,
      mapping: JSON.stringify(request.mapping),
      rows: JSON.stringify(request.rows),
      template_id: request.templateId ?? null,
      save_template_as: request.saveTemplateAs?.trim() || null,
    }),
  undo: (id: string) =>
    unwrap(api.DELETE('/api/imports/{import_id}', { params: { path: { import_id: id } } })),
  deleteTemplate: (id: string) =>
    unwrap(
      api.DELETE('/api/import-templates/{template_id}', {
        params: { path: { template_id: id } },
      }),
    ),

  createRule: (body: RuleInput) => unwrap(api.POST('/api/rules', { body })),
  updateRule: (id: string, body: RuleUpdate) =>
    unwrap(api.PATCH('/api/rules/{rule_id}', { ...ruleId(id), body })),
  deleteRule: (id: string) => unwrap(api.DELETE('/api/rules/{rule_id}', ruleId(id))),
  applyRules: () => unwrap(api.POST('/api/rules/apply', { body: { only_uncategorised: true } })),
  ruleSuggestion: (transactionId: string) =>
    unwrap(
      api.GET('/api/rules/suggestion', { params: { query: { transaction_id: transactionId } } }),
    ),

  bulkEdit: (body: BulkEdit) => unwrap(api.POST('/api/transactions/bulk', { body })),
}
