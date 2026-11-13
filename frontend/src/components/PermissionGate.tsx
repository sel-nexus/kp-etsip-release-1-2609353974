import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';

interface PermissionGateProps {
  permission: string;
  children: ReactNode;
}

/** Provide a client-side visibility gate while leaving authorization to the API. */
export default function PermissionGate({ permission, children }: PermissionGateProps): JSX.Element {
  const { user } = useAuth();
  const allowed = permission === 'audit'
    ? Boolean(user?.permissions.includes('administer') || user?.role === 'Auditor')
    : Boolean(user?.permissions.includes(permission));
  if (!allowed) {
    return <Navigate to="/applications" replace />;
  }
  return <>{children}</>;
}
