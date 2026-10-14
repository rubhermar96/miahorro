import createClient from 'openapi-fetch'

import type { paths } from './schema'

/**
 * Typed API client. Types come from src/api/schema.d.ts, generated from the backend's OpenAPI
 * schema (`npm run api:generate`). Same origin as the app, so session cookies just work.
 */
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  // Resolve fetch on each call (openapi-fetch would otherwise keep the one present at startup).
  fetch: (request) => globalThis.fetch(request),
})
