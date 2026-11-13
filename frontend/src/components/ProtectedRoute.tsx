import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';

/** Guard protected pages, route first-login users to profile, and secure unknown paths. */
export default function ProtectedRoute(): JSX.Element {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <p className="mx-auto max-w-shell px-6 py-12" role="status">Checking your session…</p>;
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (user.mustChangePassword && location.pathname !== '/profile') {
    return <Navigate to="/profile" replace />;
  }
  if (location.pathname === '/dashboard' && !user.allowedLandingPages.includes('/dashboard')) {
    return <Navigate to={user.landingPage} replace />;
  }
  return <Outlet />;
}
