import { useTranslation } from 'react-i18next'

import { type Category, categoryTree } from '../api/finance'

/** A <select> of categories grouped by main category (for forms and filters). */
export function CategorySelect({
  id,
  categories,
  kinds = ['expense', 'income'],
  value,
  onChange,
  emptyLabel,
}: {
  id: string
  categories: Category[]
  kinds?: Category['kind'][]
  value: string
  onChange: (id: string) => void
  emptyLabel: string
}) {
  const { t } = useTranslation()
  return (
    <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">{emptyLabel}</option>
      {kinds.map((kind) =>
        categoryTree(categories, kind).map((main) => (
          <optgroup
            key={main.id}
            label={kinds.length > 1 ? `${t(`categories.${kind}`)} · ${main.name}` : main.name}
          >
            <option value={main.id}>
              {main.icon} {main.name}
            </option>
            {main.children.map((child) => (
              <option key={child.id} value={child.id}>
                {'   '}
                {child.name}
              </option>
            ))}
          </optgroup>
        )),
      )}
    </select>
  )
}
