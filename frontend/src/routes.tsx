import type { RouteObject } from 'react-router'

import { Layout } from './components/Layout'
import { HomePage } from './pages/HomePage'
import { MorePage } from './pages/MorePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { AddPage, PlanPage, TransactionsPage } from './pages/PlaceholderPages'

// URLs are in Spanish: they are visible to the user.
export const routes: RouteObject[] = [
  {
    element: <Layout />,
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
