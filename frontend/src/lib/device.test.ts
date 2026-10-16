import { describe, expect, it } from 'vitest'

import { deviceName } from './device'

describe('deviceName', () => {
  it.each([
    ['Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15', 'iPhone'],
    ['Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X)', 'iPad'],
    ['Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36', 'Android'],
    ['Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15', 'Mac'],
    ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Windows'],
    ['curl/8.0', 'Este dispositivo'],
  ])('names %s as %s', (userAgent, expected) => {
    expect(deviceName(userAgent)).toBe(expected)
  })
})
