import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { type Category, categoryTree } from '../api/finance'

const QUICK_COUNT = 8

/**
 * Category choice in one tap: the most used ones first, the whole tree one tap away.
 * Main categories with subcategories are not offered directly in the quick row.
 */
export function CategoryPicker({
  categories,
  kind,
  value,
  onChange,
}: {
  categories: Category[]
  kind: Category['kind']
  value: string | null
  onChange: (id: string | null) => void
}) {
  const { t } = useTranslation()
  const [showAll, setShowAll] = useState(false)
  const tree = categoryTree(categories, kind)
  const leaves = tree.flatMap((main) =>
    main.children.length
      ? main.children.map((child) => ({ ...child, icon: child.icon ?? main.icon }))
      : [main],
  )
  const quick = [...leaves]
    .sort((a, b) => b.recent_uses - a.recent_uses || a.name.localeCompare(b.name, 'es'))
    .slice(0, QUICK_COUNT)
  const selected = leaves.find((leaf) => leaf.id === value)
  if (selected && !quick.some((leaf) => leaf.id === selected.id)) {
    quick[quick.length - 1] = selected
  }

  const chip = (category: Category) => (
    <button
      key={category.id}
      type="button"
      className="chip"
      aria-pressed={value === category.id}
      onClick={() => onChange(value === category.id ? null : category.id)}
    >
      <span aria-hidden="true">{category.icon ?? '·'}</span> {category.name}
    </button>
  )

  return (
    <fieldset className="picker">
      <legend>{t('add.category')}</legend>
      {showAll ? (
        tree.map((main) => (
          <div key={main.id} className="picker__group">
            <h4>
              <span aria-hidden="true">{main.icon}</span> {main.name}
            </h4>
            <div className="chips">
              {(main.children.length ? main.children : [main]).map((category) =>
                chip({ ...category, icon: category.icon ?? null }),
              )}
            </div>
          </div>
        ))
      ) : (
        <div className="chips">{quick.map(chip)}</div>
      )}
      <button type="button" className="button button--ghost" onClick={() => setShowAll(!showAll)}>
        {showAll ? t('add.fewerCategories') : t('add.moreCategories')}
      </button>
    </fieldset>
  )
}
