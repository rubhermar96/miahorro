import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  type Category,
  categoryTree,
  financeApi,
  refreshFinance,
  useCategories,
} from '../api/finance'
import { ErrorMessage } from '../components/ErrorMessage'
import { PageHeader } from '../components/PageHeader'
import { messageOf } from '../lib/errors'

type Kind = Category['kind']

/** Rename, archive and add categories (RF-MOV-02). */
export function CategoriesPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [kind, setKind] = useState<Kind>('expense')
  const [showArchived, setShowArchived] = useState(false)
  const categories = useCategories(showArchived)
  const [name, setName] = useState('')
  const [parentId, setParentId] = useState('')
  const [icon, setIcon] = useState('')
  const [error, setError] = useState<string | null>(null)

  const tree = categoryTree(categories.data ?? [], kind)

  const run = async (action: () => Promise<unknown>) => {
    setError(null)
    try {
      await action()
      await refreshFinance(queryClient)
    } catch (err) {
      setError(messageOf(err, t('errors.generic')))
    }
  }

  const add = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      await financeApi.createCategory({
        name,
        kind,
        parent_id: parentId || null,
        icon: icon || null,
      })
      setName('')
      setIcon('')
    })
  }

  const rename = (category: Category) => {
    const next = window.prompt(t('categories.renamePrompt', { name: category.name }), category.name)
    if (next && next.trim() && next.trim() !== category.name) {
      void run(() => financeApi.updateCategory(category.id, { name: next.trim() }))
    }
  }

  const row = (category: Category, isChild: boolean) => (
    <li key={category.id} className={isChild ? 'list__row list__row--child' : 'list__row'}>
      <span className={category.archived ? 'muted' : ''}>
        {!isChild && <span aria-hidden="true">{category.icon ?? '·'} </span>}
        {category.name}
        {category.archived && ` (${t('categories.archived')})`}
      </span>
      <span className="actions">
        <button type="button" className="button button--ghost" onClick={() => rename(category)}>
          {t('categories.rename')}
        </button>
        <button
          type="button"
          className="button button--ghost"
          onClick={() =>
            void run(() => financeApi.updateCategory(category.id, { archived: !category.archived }))
          }
        >
          {category.archived ? t('categories.unarchive') : t('categories.archive')}
        </button>
      </span>
    </li>
  )

  return (
    <>
      <PageHeader title={t('categories.title')} back="/mas" />
      <div className="stack">
        <div
          className="segmented segmented--two"
          role="radiogroup"
          aria-label={t('categories.title')}
        >
          {(['expense', 'income'] as const).map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={kind === option}
              className="segmented__option"
              onClick={() => {
                setKind(option)
                setParentId('')
              }}
            >
              {t(`categories.${option}`)}
            </button>
          ))}
        </div>

        <ul className="list card">
          {tree.map((main) => [
            row(main, false),
            ...main.children.map((child) => row(child, true)),
          ])}
        </ul>
        <label className="check">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(event) => setShowArchived(event.target.checked)}
          />
          {t('categories.showArchived')}
        </label>

        <form className="card stack stack--tight" onSubmit={add}>
          <h2>{t('categories.add')}</h2>
          <label className="field">
            <span>{t('categories.name')}</span>
            <input
              required
              maxLength={40}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="field">
            <span>{t('categories.parent')}</span>
            <select value={parentId} onChange={(event) => setParentId(event.target.value)}>
              <option value="">{t('categories.noParent')}</option>
              {tree.map((main) => (
                <option key={main.id} value={main.id}>
                  {main.name}
                </option>
              ))}
            </select>
          </label>
          {!parentId && (
            <label className="field">
              <span>{t('categories.icon')}</span>
              <input maxLength={8} value={icon} onChange={(event) => setIcon(event.target.value)} />
            </label>
          )}
          <ErrorMessage message={error} />
          <button type="submit" className="button button--secondary">
            {t('categories.add')}
          </button>
        </form>
      </div>
    </>
  )
}
