import type { PropsWithChildren } from "react";

import { Button } from "../ui/Button";

type AppShellProps = PropsWithChildren<{
  onLogout?: () => void;
  username?: string;
}>;

export function AppShell({ children, onLogout, username }: AppShellProps) {
  return (
    <div className="min-h-screen bg-newsprint text-ink">
      <header className="sticky top-0 z-40 border-b border-ink bg-newsprint/95">
        <div className="mx-auto flex max-w-screen-xl items-center justify-between px-4 py-3">
          <div>
            <p className="font-mono text-xs uppercase tracking-widest">Vol. 1 | Advisor Edition</p>
            <h1 className="font-serif text-2xl font-black leading-none">Student Success Ledger</h1>
          </div>
          {onLogout ? (
            <div className="flex items-center gap-3">
              <p className="hidden font-mono text-xs uppercase tracking-widest sm:block">
                Signed in: {username}
              </p>
              <Button size="sm" variant="secondary" onClick={onLogout}>
                Logout
              </Button>
            </div>
          ) : null}
        </div>
      </header>
      <main>{children}</main>
      <footer className="border-t border-ink bg-ink px-4 py-6 text-newsprint">
        <div className="mx-auto max-w-screen-xl font-mono text-xs uppercase tracking-widest">
          Edition: Vol 1.0 | Printed for academic advisors
        </div>
      </footer>
    </div>
  );
}
