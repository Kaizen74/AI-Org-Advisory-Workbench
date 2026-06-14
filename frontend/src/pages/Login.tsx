import { useState } from "react";
import { api } from "../services/api";
import { Button, ErrorNote } from "../components/ui";

/**
 * Neutral (un-branded) sign-in gate. The app's content and brand look-and-feel are only shown
 * after a valid email + passcode (D13 — private, controlled access).
 */
export default function Login({ onLogin }: { onLogin: (email: string, owner: boolean) => void }) {
  const [email, setEmail] = useState("");
  const [passcode, setPasscode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await api.login(email.trim(), passcode);
      onLogin(data.email, data.owner);
    } catch (err) {
      setError(String((err as Error).message ?? err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-4 rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <div>
          <h1 className="text-lg font-semibold text-slate-800">OrgAI Advisory Workbench</h1>
          <p className="text-sm text-slate-500">Private access — please sign in.</p>
        </div>
        {error && <ErrorNote message={error} />}
        <label className="block text-sm">
          <span className="text-slate-600">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-600">Passcode</span>
          <input
            type="password"
            value={passcode}
            onChange={(e) => setPasscode(e.target.value)}
            autoComplete="current-password"
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            required
          />
        </label>
        <Button onClick={() => {}} disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}
