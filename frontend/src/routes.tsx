import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthProvider';
import ProtectedRoute from './components/ProtectedRoute';
import AppShell from './components/AppShell';
import LoginPage from './pages/LoginPage';
import ProfilePage from './pages/ProfilePage';
import AdministrationPage from './pages/AdministrationPage';
import PermissionGate from './components/PermissionGate';
import PortfoliosPage from './pages/PortfoliosPage';
import PortfolioDetailPage from './pages/PortfolioDetailPage';
import PortfolioFormPage from './pages/PortfolioFormPage';
import ApplicationsPage from './pages/ApplicationsPage';
import ApplicationDetailPage from './pages/ApplicationDetailPage';
import ApplicationFormPage from './pages/ApplicationFormPage';
import DashboardPage from './pages/DashboardPage';
import ReportsPage from './pages/ReportsPage';

/** Render the protected placeholder routes backed by the requested API surface. */
function PlaceholderPage(): JSX.Element {
  const { user } = useAuth();
  return (
    <section className="mx-auto max-w-shell px-6 py-12">
      <h1>{window.location.pathname === '/dashboard' ? 'Executive dashboard' : 'Applications'}</h1>
      <p className="text-foreground-muted">Signed in as {user?.name} ({user?.role}).</p>
      <a href="/profile">Manage profile</a>
    </section>
  );
}

/** Define the single route table and API-backed session provider. */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <AuthProvider><AppShell /></AuthProvider>,
    children: [
      { path: 'login', element: <LoginPage /> },
      {
        element: <ProtectedRoute />,
        children: [
          { path: 'profile', element: <ProfilePage /> },
          { path: 'administration', element: <PermissionGate permission="administer"><AdministrationPage /></PermissionGate> },
          { path: 'audit', element: <PermissionGate permission="audit"><AdministrationPage auditOnly /></PermissionGate> },
          { path: 'dashboard', element: <DashboardPage /> },
          { path: 'reports', element: <PermissionGate permission="export"><ReportsPage /></PermissionGate> },
          { path: 'portfolios', element: <PortfoliosPage /> },
          { path: 'portfolios/new', element: <PortfolioFormPage /> },
          { path: 'portfolios/:portfolioId/edit', element: <PortfolioFormPage /> },
          { path: 'portfolios/:portfolioId', element: <PortfolioDetailPage /> },
          { path: 'applications', element: <ApplicationsPage /> },
          { path: 'applications/new', element: <ApplicationFormPage /> },
          { path: 'applications/:applicationId/edit', element: <ApplicationFormPage /> },
          { path: 'applications/:applicationId', element: <ApplicationDetailPage /> },
          { path: '*', element: <PlaceholderPage /> },
        ],
      },
      { index: true, element: <Navigate to="/login" replace /> },
    ],
  },
]);
