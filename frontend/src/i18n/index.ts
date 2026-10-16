import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { es } from './es'

void i18n.use(initReactI18next).init({
  resources: { es: { translation: es } },
  lng: 'es',
  fallbackLng: 'es',
  interpolation: { escapeValue: false }, // React already escapes
})

export default i18n
