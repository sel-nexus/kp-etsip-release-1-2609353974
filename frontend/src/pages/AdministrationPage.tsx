import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import {
  type AdminPermission,
  type AdminRole,
  type AuditAction,
  type AuditEntry,
  type ManagedRole,
  type ManagedUser,
  createManagedUser,
  deactivateManagedUser,
  listManagedRoles,
  listManagedUsers,
  searchAudit,
  updateManagedRole,
  updateManagedUser,
} from '../api/administration';
import { downloadCsv, fetchAuditCsv } from '../api/reports';

const permissions: AdminPermission[] = ['view', 'create', 'edit', 'delete', 'export', 'administer'];
const auditActions: AuditAction[] = ['login', 'create', 'edit', 'delete', 'roleChange', 'permissionChange', 'export'];
const roles: AdminRole[] = ['Administrator', 'Executive', 'Portfolio Leader', 'Engineer', 'Auditor', 'Read Only'];
type Tab = 'users' | 'roles' | 'audit';

interface AdministrationPageProps {
  auditOnly?: boolean;
}

/** Render live account, role, and audit administration for authorized users. */
export default function AdministrationPage({ auditOnly = false }: AdministrationPageProps): JSX.Element {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const auditorOnly = auditOnly || (user?.role === 'Auditor' && !user.permissions.includes('administer'));
  const [tab, setTab] = useState<Tab>(auditorOnly ? 'audit' : 'users');
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [roleDrafts, setRoleDrafts] = useState<Record<string, AdminRole>>({});
  const [managedRoles, setManagedRoles] = useState<ManagedRole[]>([]);
  const [auditItems, setAuditItems] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<AdminRole>('Read Only');
  const [password, setPassword] = useState('');
  const [auditUser, setAuditUser] = useState('');
  const [auditAction, setAuditAction] = useState('');
  const [auditFrom, setAuditFrom] = useState('');
  const [auditTo, setAuditTo] = useState('');
  const [auditExporting, setAuditExporting] = useState(false);

  const loadUsers = useCallback(async (): Promise<void> => {
    const response = await listManagedUsers();
    setUsers(response.items);
  }, []);

  const loadRoles = useCallback(async (): Promise<void> => {
    setManagedRoles(await listManagedRoles());
  }, []);

  const loadAudit = useCallback(async (): Promise<void> => {
    const response = await searchAudit({
      userId: auditUser || undefined,
      action: (auditAction || undefined) as AuditAction | undefined,
      from: auditFrom || undefined,
      to: auditTo || undefined,
    });
    setAuditItems(response.items);
  }, [auditAction, auditFrom, auditTo, auditUser]);

  const runOperation = useCallback(async (operation: () => Promise<void>): Promise<void> => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await operation();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The operation could not be completed.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === 'audit') void runOperation(loadAudit);
    if (tab === 'users' && !auditorOnly) void runOperation(loadUsers);
    if (tab === 'roles' && !auditorOnly) void runOperation(loadRoles);
  }, [auditorOnly, loadAudit, loadRoles, loadUsers, runOperation, tab]);

  async function submitCreate(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await runOperation(async () => {
      const created = await createManagedUser({ name, email, role, portfolioAccess: [], password });
      setUsers((current) => [...current, created]);
      setName('');
      setEmail('');
      setPassword('');
      setSuccess(`Created ${created.name}.`);
    });
  }

  async function toggleUserStatus(account: ManagedUser): Promise<void> {
    await runOperation(async () => {
      const updated = account.status === 'Active'
        ? await deactivateManagedUser(account.id)
        : await updateManagedUser(account.id, { status: 'Active' });
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item));
      setSuccess(`${updated.name} is now ${updated.status.toLowerCase()}.`);
    });
  }

  async function saveUserRole(account: ManagedUser): Promise<void> {
    const updatedRole = roleDrafts[account.id] ?? account.role;
    if (updatedRole === account.role) return;
    await runOperation(async () => {
      const updated = await updateManagedUser(account.id, { role: updatedRole });
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item));
      setSuccess(`Updated ${updated.name}'s role.`);
    });
  }

  async function saveRole(roleItem: ManagedRole, permission: AdminPermission): Promise<void> {
    await runOperation(async () => {
      const next = roleItem.permissions.includes(permission)
        ? roleItem.permissions.filter((value) => value !== permission)
        : [...roleItem.permissions, permission];
      const updated = await updateManagedRole(roleItem.name, roleItem.description, next);
      setManagedRoles((current) => current.map((item) => item.name === updated.name ? updated : item));
      setSuccess(`Saved permissions for ${updated.name}.`);
    });
  }

  async function submitAuditSearch(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await runOperation(loadAudit);
  }

  async function exportAuditCsv(): Promise<void> {
    setAuditExporting(true);
    setError('');
    setSuccess('');
    try {
      const download = await fetchAuditCsv({
        userId: auditUser || undefined,
        action: auditAction || undefined,
        from: auditFrom || undefined,
        to: auditTo || undefined,
      });
      downloadCsv(download);
      setSuccess('Audit CSV download is ready.');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The audit CSV could not be downloaded.');
    } finally {
      setAuditExporting(false);
    }
  }

  async function handleSignOut(): Promise<void> {
    await signOut();
    navigate('/login', { replace: true });
  }

  return (
    <section className="mx-auto max-w-shell px-4 py-10 sm:px-6 lg:px-12" aria-labelledby="administration-title">
      <header className="mb-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="mb-2 text-sm font-semibold tracking-wide text-foreground-muted">{auditorOnly ? 'AUDIT REVIEW' : 'PLATFORM CONTROLS'}</p>
            <h1 id="administration-title" className="mb-2">{auditorOnly ? 'Audit history' : 'Administration'}</h1>
            <p className="text-foreground-muted">{auditorOnly ? 'Review recorded platform activity.' : 'Manage access and review recorded platform activity.'}</p>
          </div>
          <button className="secondary-button" type="button" onClick={() => void handleSignOut()}>Sign out</button>
        </div>
      </header>
      <div className="mb-6 flex flex-wrap gap-3" role="tablist" aria-label="Administration sections">
        {!auditorOnly && <button type="button" className="secondary-button" role="tab" aria-selected={tab === 'users'} onClick={() => setTab('users')}>Users</button>}
        {!auditorOnly && <button type="button" className="secondary-button" role="tab" aria-selected={tab === 'roles'} onClick={() => setTab('roles')}>Roles</button>}
        <button type="button" className="secondary-button" role="tab" aria-selected={tab === 'audit'} onClick={() => setTab('audit')}>Audit history</button>
      </div>
      {loading && <p className="mb-4 text-foreground-muted" role="status">Loading administration data…</p>}
      {error && <p className="mb-4 text-error" role="alert">{error}</p>}
      {success && <p className="mb-4 text-foreground-muted" role="status" aria-live="polite">{success}</p>}

      {tab === 'users' && !auditorOnly && (
        <div className="space-y-8">
          <form className="quiet-card grid gap-4 p-5 sm:grid-cols-2" onSubmit={(event) => void submitCreate(event)} aria-label="Create user">
            <h2 className="sm:col-span-2">Create account</h2>
            <div><label htmlFor="new-user-name">Name</label><input id="new-user-name" required value={name} onChange={(event) => setName(event.currentTarget.value)} /></div>
            <div><label htmlFor="new-user-email">Email</label><input id="new-user-email" type="email" required value={email} onChange={(event) => setEmail(event.currentTarget.value)} /></div>
            <div><label htmlFor="new-user-role">Role</label><select id="new-user-role" value={role} onChange={(event) => setRole(event.currentTarget.value as AdminRole)}>{roles.map((item) => <option key={item}>{item}</option>)}</select></div>
            <div><label htmlFor="new-user-password">Temporary password</label><input id="new-user-password" type="password" minLength={12} required value={password} onChange={(event) => setPassword(event.currentTarget.value)} /></div>
            <button className="primary-button justify-self-start" type="submit" disabled={loading}>Create user</button>
          </form>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <caption className="mb-3 text-left text-lg font-semibold">User accounts</caption>
              <thead><tr><th scope="col">Name</th><th scope="col">Email</th><th scope="col">Role</th><th scope="col">Status</th><th scope="col">Action</th></tr></thead>
              <tbody>{users.map((account) => (
                <tr key={account.id}>
                  <td>{account.name}</td><td>{account.email}</td><td>{account.role}</td><td>{account.status}</td>
                  <td>
                    <div className="flex flex-wrap items-center gap-2">
                      <label className="sr-only" htmlFor={`user-role-${account.id}`}>Role for {account.name}</label>
                      <select id={`user-role-${account.id}`} value={roleDrafts[account.id] ?? account.role} disabled={loading} onChange={(event) => setRoleDrafts((current) => ({ ...current, [account.id]: event.currentTarget.value as AdminRole }))}>
                        {roles.map((item) => <option key={item}>{item}</option>)}
                      </select>
                      <button className="secondary-button" type="button" disabled={loading || (roleDrafts[account.id] ?? account.role) === account.role} onClick={() => void saveUserRole(account)}>Save user</button>
                      <button className="secondary-button" type="button" disabled={loading} onClick={() => void toggleUserStatus(account)}>{account.status === 'Active' ? 'Deactivate' : 'Reactivate'}</button>
                    </div>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'roles' && !auditorOnly && (
        <section className="space-y-5" aria-label="Role permissions">
          {managedRoles.map((roleItem) => (
            <article className="quiet-card p-5" key={roleItem.id}>
              <h2 className="mb-1">{roleItem.name}</h2>
              <p className="mb-4 text-sm text-foreground-muted">{roleItem.description}</p>
              <div className="flex flex-wrap gap-x-5 gap-y-2">
                {permissions.map((permission) => (
                  <label className="flex items-center gap-2" key={permission}>
                    <input type="checkbox" aria-label={`${roleItem.name} ${permission}`} checked={roleItem.permissions.includes(permission)} disabled={loading} onChange={() => void saveRole(roleItem, permission)} />
                    {permission}
                  </label>
                ))}
              </div>
            </article>
          ))}
        </section>
      )}

      {tab === 'audit' && (
        <section aria-label="Audit history">
          <form className="quiet-card mb-6 grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4" onSubmit={(event) => void submitAuditSearch(event)} aria-label="Search audit history">
            <div><label htmlFor="audit-user-id">User ID</label><input id="audit-user-id" value={auditUser} onChange={(event) => setAuditUser(event.currentTarget.value)} /></div>
            <div><label htmlFor="audit-action">Action</label><select id="audit-action" value={auditAction} onChange={(event) => setAuditAction(event.currentTarget.value)}><option value="">All actions</option>{auditActions.map((item) => <option key={item}>{item}</option>)}</select></div>
            <div><label htmlFor="audit-from">From</label><input id="audit-from" type="datetime-local" value={auditFrom ? auditFrom.slice(0, 16) : ''} onChange={(event) => setAuditFrom(event.currentTarget.value ? new Date(event.currentTarget.value).toISOString() : '')} /></div>
            <div><label htmlFor="audit-to">To</label><input id="audit-to" type="datetime-local" value={auditTo ? auditTo.slice(0, 16) : ''} onChange={(event) => setAuditTo(event.currentTarget.value ? new Date(event.currentTarget.value).toISOString() : '')} /></div>
            <div className="flex flex-wrap gap-3 sm:col-span-2 lg:col-span-4">
              <button className="primary-button" type="submit" disabled={loading}>Search audit history</button>
              {(user?.permissions.includes('administer') || user?.role === 'Auditor') && (
                <button className="secondary-button" type="button" disabled={loading || auditExporting} onClick={() => void exportAuditCsv()}>
                  {auditExporting ? 'Preparing CSV…' : 'Export audit CSV'}
                </button>
              )}
            </div>
          </form>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <caption className="mb-3 text-left text-lg font-semibold">Recorded events</caption>
              <thead><tr><th scope="col">Time (UTC)</th><th scope="col">User</th><th scope="col">Action</th><th scope="col">Entity</th><th scope="col">Details</th></tr></thead>
              <tbody>{auditItems.map((entry) => <tr key={entry.id}><td>{new Date(entry.timestamp).toLocaleString()}</td><td>{entry.userName}</td><td>{entry.action}</td><td>{entry.entityType}</td><td>{entry.details}</td></tr>)}</tbody>
            </table>
          </div>
        </section>
      )}
    </section>
  );
}
