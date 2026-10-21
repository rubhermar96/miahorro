import type { RouteObject } from 'react-router'

import { RequireSession } from './components/RequireSession'
import { AccountFormPage } from './pages/AccountFormPage'
import { AccountPage } from './pages/AccountPage'
import { ArchivedAccountsPage } from './pages/ArchivedAccountsPage'
import { BudgetPage } from './pages/BudgetPage'
import { CalculatorPage } from './pages/CalculatorPage'
import { CalculatorsPage } from './pages/CalculatorsPage'
import { CapturePage } from './pages/CapturePage'
import { CategoriesPage } from './pages/CategoriesPage'
import { EuriborPage } from './pages/EuriborPage'
import { GoalFormPage } from './pages/GoalFormPage'
import { GoalPage } from './pages/GoalPage'
import { HomePage } from './pages/HomePage'
import { ImportPage } from './pages/ImportPage'
import { InvestmentFormPage } from './pages/InvestmentFormPage'
import { InvestmentPage } from './pages/InvestmentPage'
import { InvestmentsPage } from './pages/InvestmentsPage'
import { LoanFormPage } from './pages/LoanFormPage'
import { LoanPage } from './pages/LoanPage'
import { LoginPage } from './pages/LoginPage'
import { MorePage } from './pages/MorePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { OperationFormPage } from './pages/OperationFormPage'
import { PlanPage } from './pages/PlanPage'
import { QuickAddPage } from './pages/QuickAddPage'
import { RecurringPage } from './pages/RecurringPage'
import { ReviewPage } from './pages/ReviewPage'
import { RulesPage } from './pages/RulesPage'
import { TaxReportPage } from './pages/TaxReportPage'
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
      { path: 'planificar/presupuesto', element: <BudgetPage /> },
      { path: 'planificar/prestamos/nuevo', element: <LoanFormPage /> },
      { path: 'planificar/prestamos/:id', element: <LoanPage /> },
      { path: 'planificar/prestamos/:id/editar', element: <LoanFormPage /> },
      { path: 'planificar/euribor', element: <EuriborPage /> },
      { path: 'planificar/calculadoras', element: <CalculatorsPage /> },
      { path: 'planificar/calculadoras/:slug', element: <CalculatorPage /> },
      { path: 'planificar/objetivos/nuevo', element: <GoalFormPage /> },
      { path: 'planificar/objetivos/:id', element: <GoalPage /> },
      { path: 'planificar/objetivos/:id/editar', element: <GoalFormPage /> },
      { path: 'inversiones', element: <InvestmentsPage /> },
      { path: 'inversiones/nueva', element: <InvestmentFormPage /> },
      { path: 'inversiones/informe-fiscal', element: <TaxReportPage /> },
      { path: 'inversiones/:id', element: <InvestmentPage /> },
      { path: 'inversiones/:id/editar', element: <InvestmentFormPage /> },
      { path: 'inversiones/:id/operaciones/nueva', element: <OperationFormPage /> },
      { path: 'inversiones/:id/operaciones/:operationId', element: <OperationFormPage /> },
      { path: 'mas', element: <MorePage /> },
      { path: 'mas/categorias', element: <CategoriesPage /> },
      { path: 'mas/reglas', element: <RulesPage /> },
      { path: 'mas/captura', element: <CapturePage /> },
      { path: 'mas/recurrentes', element: <RecurringPage /> },
      { path: 'revisar', element: <ReviewPage /> },
      { path: 'importar', element: <ImportPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
