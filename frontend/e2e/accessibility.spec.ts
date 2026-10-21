import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

// Signed in (see auth.setup.ts). An automatic accessibility audit (WCAG 2.1 AA) of the main
// screens, in light and dark mode. It cannot catch everything, but nothing it finds may stay.

const SCREENS = [
  '/',
  '/movimientos',
  '/anadir',
  '/planificar',
  '/planificar/presupuesto',
  '/planificar/calculadoras',
  '/planificar/calculadoras/comprar-vivienda',
  '/inversiones',
  '/informes',
  '/informes?vista=flujo',
  '/informes?vista=gastos',
  '/importar',
  '/mas',
]

for (const scheme of ['light', 'dark'] as const) {
  test(`pantallas principales sin problemas de accesibilidad (${scheme})`, async ({ page }) => {
    test.setTimeout(150_000) // thirteen screens, each analysed whole
    await page.emulateMedia({ colorScheme: scheme })
    const problems: string[] = []
    for (const url of SCREENS) {
      await page.goto(url)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      await page.waitForLoadState('networkidle')
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze()
      expect(results.passes.length, url).toBeGreaterThan(10) // the audit did run
      for (const violation of results.violations) {
        const where = violation.nodes
          .slice(0, 3)
          .map((node) => node.target.join(' '))
          .join(' | ')
        problems.push(`${url} · ${violation.id} (${violation.impact}): ${where}`)
      }
    }
    expect(problems).toEqual([])
  })
}
