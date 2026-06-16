import { useEffect, useState } from "react";

import { AppShell } from "../components/layout/AppShell";
import { LoginPage } from "../features/auth/LoginPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { clearAuthSession, getStoredAuthSession, login, storeAuthSession } from "../shared/api/client";

export function App() {
  const [session, setSession] = useState(getStoredAuthSession);

  useEffect(() => {
    function handleAuthExpired() {
      setSession(null);
    }
    window.addEventListener("auth-expired", handleAuthExpired);
    return () => window.removeEventListener("auth-expired", handleAuthExpired);
  }, []);

  async function handleLogin(username: string, password: string) {
    const nextSession = await login(username, password);
    storeAuthSession(nextSession);
    setSession({ token: nextSession.token, username: nextSession.username });
  }

  function handleLogout() {
    clearAuthSession();
    setSession(null);
  }

  if (!session) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <AppShell username={session.username} onLogout={handleLogout}>
      <DashboardPage />
    </AppShell>
  );
}
