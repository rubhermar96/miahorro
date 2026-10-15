import createClient, { type Middleware } from 'openapi-fetch'

import i18n from '../i18n'
import type { paths } from './schema'

/** Required by the API on every change (CSRF protection, see backend app/auth/csrf.py). */
export const CSRF_HEADER = 'X-MiAhorro-CSRF'

const csrfHeader: Middleware = {
  onRequest({ request }) {
    request.headers.set(CSRF_HEADER, '1')
    return request
  },
}

/**
 * Typed API client. Types come from src/api/schema.d.ts, generated from the backend's OpenAPI
 * schema (`npm run api:generate`). Same origin as the app, so session cookies just work.
 */
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  // Resolve fetch on each call (openapi-fetch would otherwise keep the one present at startup).
  fetch: (request) => globalThis.fetch(request),
})
api.use(csrfHeader)

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

type ErrorBody = { error?: { message?: string } }

/** The API's uniform error body carries a message in Spanish; fall back to a generic one. */
export function toApiError(error: unknown, response: Response): ApiError {
  const message = (error as ErrorBody | undefined)?.error?.message
  return new ApiError(message ?? i18n.t('errors.generic'), response.status)
}

/** Await an openapi-fetch call and return its data, or throw an ApiError. */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call
  if (!response.ok) {
    throw toApiError(error, response)
  }
  return data as T
}
