import { Outlet } from 'react-router-dom';

/** Provide the restrained shared frame for public account entry routes. */
export default function AppShell(): JSX.Element {
  return (
    <div className="min-h-screen bg-surface text-foreground">
      <header className="border-b border-border bg-surface-container-lowest">
        <div className="mx-auto flex min-h-16 max-w-shell items-center px-4 sm:px-6 lg:px-12">
          <a className="font-semibold tracking-tight text-foreground no-underline" href="/">
            KP ETSIP
          </a>
          <span className="ml-3 border-l border-border pl-3 text-sm text-foreground-muted">
            Platform
          </span>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
