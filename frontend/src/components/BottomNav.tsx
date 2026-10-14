import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router'

import { HomeIcon, ListIcon, MenuIcon, PlusIcon, TargetIcon } from './icons'

type Item = { to: string; label: string; icon: ReactNode; primary?: boolean }

export function BottomNav() {
  const { t } = useTranslation()
  const items: Item[] = [
    { to: '/', label: t('nav.home'), icon: <HomeIcon /> },
    { to: '/movimientos', label: t('nav.transactions'), icon: <ListIcon /> },
    { to: '/anadir', label: t('nav.add'), icon: <PlusIcon />, primary: true },
    { to: '/planificar', label: t('nav.plan'), icon: <TargetIcon /> },
    { to: '/mas', label: t('nav.more'), icon: <MenuIcon /> },
  ]

  return (
    <nav className="bottom-nav" aria-label={t('nav.label')}>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            ['nav-link', item.primary && 'nav-link--primary', isActive && 'is-active']
              .filter(Boolean)
              .join(' ')
          }
        >
          <span className="nav-link__icon">{item.icon}</span>
          <span className="nav-link__label">{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
