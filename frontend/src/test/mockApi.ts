import { vi } from 'vitest'

type Reply = { status: number; body?: unknown }
type Handler = Reply | ((request: Request, body: unknown) => Reply)

export type ApiCall = {
  method: string
  path: string
  query: URLSearchParams
  body: unknown
  headers: Headers
}

/** JSON bodies as objects; multipart forms as {field: value}, with files by name. */
async function readBody(request: Request): Promise<unknown> {
  if ((request.headers.get('content-type') ?? '').startsWith('multipart/form-data')) {
    const form = await request.clone().formData()
    return Object.fromEntries(
      [...form.entries()].map(([name, value]) => [
        name,
        typeof value === 'string' ? value : (value as File).name,
      ]),
    )
  }
  const text = await request.clone().text()
  return text ? (JSON.parse(text) as unknown) : undefined
}

/**
 * Replace fetch with a fake API keyed by "METHOD /path". Unknown routes answer 404.
 * Handlers can be swapped during a test (e.g. the session changes after signing in).
 */
export function mockApi(initial: Record<string, Handler> = {}) {
  const routes = new Map(Object.entries(initial))
  const calls: ApiCall[] = []

  const fetchMock = vi.fn(async (request: Request) => {
    const url = new URL(request.url)
    const path = url.pathname
    const body = request.method === 'GET' ? undefined : await readBody(request)
    calls.push({
      method: request.method,
      path,
      query: url.searchParams,
      body,
      headers: request.headers,
    })

    const handler = routes.get(`${request.method} ${path}`)
    const reply: Reply =
      typeof handler === 'function'
        ? handler(request, body)
        : (handler ?? { status: 404, body: { error: { code: 'not_found', message: 'No mock' } } })
    if (reply.status === 204) {
      return new Response(null, { status: 204 })
    }
    return Response.json(reply.body ?? {}, { status: reply.status })
  })
  vi.stubGlobal('fetch', fetchMock)

  return {
    calls,
    on(route: string, handler: Handler) {
      routes.set(route, handler)
    },
    callsTo(route: string) {
      const [method, path] = route.split(' ')
      return calls.filter((call) => call.method === method && call.path === path)
    },
  }
}

export const testUser = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'ana@example.com',
  display_name: 'Ana',
  is_admin: false,
  has_totp: true,
  has_passkey: false,
  recovery_codes_left: 10,
  preferences: { currency: 'EUR', month_start_day: 1, theme: 'system', language: 'es' },
}

export const fullSession = { status: 200, body: { level: 'full', user: testUser } }
export const noSession = {
  status: 401,
  body: { error: { code: 'unauthorized', message: 'Necesitas iniciar sesión.' } },
}
export const healthOk = { status: 200, body: { status: 'ok', version: '0.1.0', database: 'ok' } }
