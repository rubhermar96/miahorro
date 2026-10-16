import { describe, expect, it } from 'vitest'

import { isServerPage, safeNextPath } from './navigation'

describe('safeNextPath', () => {
  it.each(['/', '/movimientos', '/mas?x=1', '/admin'])('keeps local path %s', (path) => {
    expect(safeNextPath(path)).toBe(path)
  })

  it.each([
    null,
    undefined,
    '',
    'https://evil.example',
    '//evil.example',
    '/\\evil.example',
    'javascript:alert(1)',
  ])('falls back to home for %s', (value) => {
    expect(safeNextPath(value)).toBe('/')
  })
})

describe('isServerPage', () => {
  it('recognises the admin panel', () => {
    expect(isServerPage('/admin')).toBe(true)
    expect(isServerPage('/admin/user/list')).toBe(true)
    expect(isServerPage('/administracion-de-gastos')).toBe(false)
    expect(isServerPage('/')).toBe(false)
  })
})
