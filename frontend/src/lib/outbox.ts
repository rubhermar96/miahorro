/**
 * Entries made without connection (RNF-02): kept on this device and sent when it comes back.
 * Each one carries a reference chosen here (client_ref), so sending it twice after a lost
 * answer never creates it twice. This is per-device state, so it lives in localStorage.
 */
import { ApiError } from '../api/client'

const KEY = 'miahorro.outbox'
export const OUTBOX_EVENT = 'miahorro:outbox'
/** Where the service worker keeps the API's answers for reading offline. */
export const API_CACHE = 'miahorro-api'

export type PendingEntry = {
  ref: string
  createdAt: string
  body: Record<string, unknown>
  /** Why the server refused it, if it did: it stays for the user to see. */
  error?: string
}

export function pendingEntries(): PendingEntry[] {
  try {
    const stored = localStorage.getItem(KEY)
    return stored ? (JSON.parse(stored) as PendingEntry[]) : []
  } catch {
    return []
  }
}

function save(entries: PendingEntry[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(entries))
  } catch {
    // Storage blocked (private mode): nothing else can be done offline.
  }
  window.dispatchEvent(new Event(OUTBOX_EVENT))
}

export function enqueue(body: Record<string, unknown>, ref: string) {
  save([...pendingEntries(), { ref, createdAt: new Date().toISOString(), body }])
}

export function discard(ref: string) {
  save(pendingEntries().filter((entry) => entry.ref !== ref))
}

/** A failure because there is no connection, not because the server said no. */
export function isOffline(error: unknown): boolean {
  return !(error instanceof ApiError) && (error instanceof TypeError || !navigator.onLine)
}

/** Send what is waiting, oldest first. Stops at the first connection failure; an entry the
 * server refuses stays, marked with the reason. Returns how many went. */
export async function flush(send: (body: Record<string, unknown>) => Promise<unknown>) {
  let sent = 0
  for (const entry of pendingEntries()) {
    if (entry.error) {
      continue
    }
    try {
      await send({ ...entry.body, client_ref: entry.ref })
      discard(entry.ref)
      sent += 1
    } catch (error) {
      if (isOffline(error)) {
        break
      }
      const message = error instanceof Error ? error.message : String(error)
      save(pendingEntries().map((e) => (e.ref === entry.ref ? { ...e, error: message } : e)))
    }
  }
  return sent
}

/** On signing out: nothing of this person stays on the device. */
export async function forgetOfflineData() {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // ignore
  }
  if ('caches' in window) {
    await caches.delete(API_CACHE).catch(() => undefined)
  }
}
