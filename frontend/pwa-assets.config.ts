import { defineConfig, minimal2023Preset } from '@vite-pwa/assets-generator/config'

// Regenerate the icons in public/ with `npm run icons` after editing public/icon.svg.
const background = { background: '#0f766e' }

export default defineConfig({
  preset: {
    ...minimal2023Preset,
    maskable: { ...minimal2023Preset.maskable, resizeOptions: background },
    apple: { ...minimal2023Preset.apple, resizeOptions: background },
  },
  images: ['public/icon.svg'],
})
