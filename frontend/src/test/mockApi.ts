import { vi } from 'vitest'

type Reply = { status: number; body?: unknown }
type Handler = Reply | ((request: Request, body: unknown) => Reply)

export type ApiCall = { method: string; path: string; body: unknown; headers: Headers }

/**
 * Replace fetch with a fake API keyed by "METHOD /path". Unknown routes answer 404.
 * Handlers can be swapped during a test (e.g. the session changes after signing in).
 */
export function mockApi(initial: Record<string, Handler> = {}) {
  const routes = new Map(Object.entries(initial))
  const calls: ApiCall[] = []

  const fetchMock = vi.fn(async (request: Request) => {
    const path = new URL(request.url).pathname
    const text = request.method === 'GET' ? '' : await request.clone().text()
    const body: unknown = text ? JSON.parse(text) : undefined
    calls.push({ method: request.method, path, body, headers: request.headers })

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
