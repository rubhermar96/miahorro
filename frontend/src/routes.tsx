import type { RouteObject } from 'react-router'

import { RequireSession } from './components/RequireSession'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { MorePage } from './pages/MorePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { AddPage, PlanPage, TransactionsPage } from './pages/PlaceholderPages'

// URLs are in Spanish: they are visible to the user.
export const routes: RouteObject[] = [
  { path: 'entrar', element: <LoginPage /> },
  {
    // Everything else needs a signed-in user.
    element: <RequireSession />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'movimientos', element: <TransactionsPage /> },
      { path: 'anadir', element: <AddPage /> },
      { path: 'planificar', element: <PlanPage /> },
      { path: 'mas', element: <MorePage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
