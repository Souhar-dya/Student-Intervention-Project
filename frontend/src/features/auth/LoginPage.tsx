import { useState } from "react";
import type { FormEvent } from "react";
import { LockKeyhole } from "lucide-react";

import { Button } from "../../components/ui/Button";

export function LoginPage({
  onLogin,
}: {
  onLogin: (username: string, password: string) => Promise<void>;
}) {
  const [username, setUsername] = useState("advisor");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("Sign in to open the advisor desk.");
  const [isLoading, setIsLoading] = useState(false);

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setStatus("Checking credentials");
    try {
      await onLogin(username, password);
      setStatus("Opening dashboard");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Login failed");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="newsprint-texture min-h-screen border-b border-ink">
      <div className="mx-auto grid min-h-screen max-w-screen-xl border-l border-r border-ink lg:grid-cols-12">
        <div className="border-b border-ink p-6 lg:col-span-7 lg:border-b-0 lg:border-r lg:p-10">
          <p className="font-mono text-xs uppercase tracking-widest text-red-700">Restricted edition</p>
          <h1 className="mt-4 max-w-3xl font-serif text-5xl font-black leading-[0.9] sm:text-6xl lg:text-7xl">
            Student Success Ledger
          </h1>
          <p className="mt-6 max-w-2xl text-justify font-body text-lg leading-relaxed">
            Advisor access is required because the dashboard can expose student risk, parent contact,
            and intervention notes.
          </p>
          <div className="mt-8 grid max-w-xl border-l border-t border-ink sm:grid-cols-2">
            {["Risk signals", "Parent mail", "Advisor notes", "Case evidence"].map((item) => (
              <p className="border-b border-r border-ink p-4 font-mono text-xs uppercase tracking-widest" key={item}>
                {item}
              </p>
            ))}
          </div>
        </div>
        <form className="p-6 lg:col-span-5 lg:p-10" onSubmit={submitLogin}>
          <div className="flex items-start gap-3">
            <LockKeyhole aria-hidden="true" className="mt-1 h-5 w-5 stroke-1 text-red-700" />
            <div>
              <p className="font-mono text-xs uppercase tracking-widest text-red-700">Advisor login</p>
              <h2 className="mt-3 font-serif text-4xl font-black leading-none">Open desk</h2>
            </div>
          </div>
          <label className="field-label mt-8 block">
            Username
            <input
              className="newsprint-input mt-2 w-full"
              disabled={isLoading}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label className="field-label mt-4 block">
            Password
            <input
              className="newsprint-input mt-2 w-full"
              disabled={isLoading}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <Button
            className="mt-6 w-full"
            disabled={!username.trim() || !password}
            isLoading={isLoading}
            loadingLabel="Signing in"
            type="submit"
          >
            Sign in
          </Button>
          <p className="mt-4 border border-ink p-3 font-mono text-xs uppercase tracking-widest">{status}</p>
        </form>
      </div>
    </section>
  );
}
