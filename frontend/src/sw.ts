/// <reference lib="webworker" />
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
} from 'workbox-precaching'
import { ExpirationPlugin } from 'workbox-expiration'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { NetworkFirst } from 'workbox-strategies'

declare let self: ServiceWorkerGlobalScope

// App shell: every built asset is precached so the app opens without network.
precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()

// Single-page app: navigations get index.html, except the API and the admin panel.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL('index.html'), {
    denylist: [/^\/api\//, /^\/admin/],
  }),
)

// Reading offline (RNF-02): the API's answers are kept, and served when there is no network.
// The session too, so the app stays open; never the sign-in steps, exports or the health check.
// Signing out deletes this cache (src/lib/outbox.ts).
const API_CACHE = 'miahorro-api'
const NOT_KEPT = [/^\/api\/auth\/(?!session$)/, /^\/api\/export/, /^\/api\/health/]
registerRoute(
  ({ url, request }) =>
    request.method === 'GET' &&
    url.origin === self.location.origin &&
    url.pathname.startsWith('/api/') &&
    !NOT_KEPT.some((pattern) => pattern.test(url.pathname)),
  new NetworkFirst({
    cacheName: API_CACHE,
    networkTimeoutSeconds: 6,
    plugins: [new ExpirationPlugin({ maxEntries: 300, maxAgeSeconds: 60 * 60 * 24 * 30 })],
  }),
)

// The update prompt asks the waiting worker to take over.
self.addEventListener('message', (event) => {
  if ((event.data as { type?: string } | null)?.type === 'SKIP_WAITING') {
    void self.skipWaiting()
  }
})
