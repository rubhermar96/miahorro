/**
 * Where to go after signing in. Only paths on this site are accepted, so a crafted link like
 * /entrar?siguiente=https://evil.example cannot send the user elsewhere.
 */
export function safeNextPath(value: string | null | undefined): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\')) {
    return '/'
  }
  return value
}

/** Pages served by the API (the admin panel) need a full page load, not a client-side route. */
export function isServerPage(path: string): boolean {
  return path === '/admin' || path.startsWith('/admin/')
}
