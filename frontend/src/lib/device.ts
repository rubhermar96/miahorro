/** A friendly default name for a passkey created on this device ("iPhone", "Windows"…). */
export function deviceName(userAgent: string = navigator.userAgent): string {
  if (/iPhone/.test(userAgent)) return 'iPhone'
  if (/iPad/.test(userAgent)) return 'iPad'
  if (/Android/.test(userAgent)) return 'Android'
  if (/Macintosh|Mac OS X/.test(userAgent)) return 'Mac'
  if (/Windows/.test(userAgent)) return 'Windows'
  return 'Este dispositivo'
}
