/// <reference lib="webworker" />
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
} from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'

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

// The update prompt asks the waiting worker to take over.
self.addEventListener('message', (event) => {
  if ((event.data as { type?: string } | null)?.type === 'SKIP_WAITING') {
    void self.skipWaiting()
  }
})
