import type { RouteObject } from 'react-router'

import { RequireSession } from './components/RequireSession'
import { AccountFormPage } from './pages/AccountFormPage'
import { AccountPage } from './pages/AccountPage'
import { ArchivedAccountsPage } from './pages/ArchivedAccountsPage'
import { CategoriesPage } from './pages/CategoriesPage'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { MorePage } from './pages/MorePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PlanPage } from './pages/PlaceholderPages'
import { QuickAddPage } from './pages/QuickAddPage'
import { TransactionPage } from './pages/TransactionPage'
import { TransactionsPage } from './pages/TransactionsPage'

// URLs are in Spanish: they are visible to the user.
export const routes: RouteObject[] = [
  { path: 'entrar', element: <LoginPage /> },
  { path: 'registro', element: <LoginPage mode="register" /> },
  {
    // Everything else needs a signed-in user.
    element: <RequireSession />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'movimientos', element: <TransactionsPage /> },
      { path: 'movimientos/:id', element: <TransactionPage /> },
      { path: 'anadir', element: <QuickAddPage /> },
      { path: 'cuentas/nueva', element: <AccountFormPage /> },
      { path: 'cuentas/archivadas', element: <ArchivedAccountsPage /> },
      { path: 'cuentas/:id', element: <AccountPage /> },
      { path: 'cuentas/:id/editar', element: <AccountFormPage /> },
      { path: 'planificar', element: <PlanPage /> },
      { path: 'mas', element: <MorePage /> },
      { path: 'mas/categorias', element: <CategoriesPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
