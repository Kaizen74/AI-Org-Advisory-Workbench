import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { AppSettings } from "../types";
import { Button, Card, ErrorNote, Spinner } from "../components/ui";

const PALETTE_KEYS: [string, string][] = [
  ["ink", "Text / ink"],
  ["accent", "Accent"],
  ["muted", "Muted"],
  ["rule", "Rule / lines"],
  ["ground", "Background"],
];

function Field({ label, value, onChange, type = "text", placeholder }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="text-slate-600">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
      />
    </label>
  );
}

interface AccessUserRow {
  email: string;
  is_owner: boolean;
}

export default function Settings({ owner = false }: { owner?: boolean }) {
  const [s, setS] = useState<AppSettings | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [palette, setPalette] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [logoBump, setLogoBump] = useState(0);

  // Access management (owner only)
  const [accessUsers, setAccessUsers] = useState<AccessUserRow[]>([]);
  const [newUser, setNewUser] = useState({ email: "", passcode: "", is_owner: false });

  async function loadAccess() {
    if (!owner) return;
    try {
      setAccessUsers((await api.listAccess()).users);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function addAccessUser() {
    if (!newUser.email || !newUser.passcode) return;
    try {
      await api.addAccess(newUser.email.trim(), newUser.passcode, newUser.is_owner);
      setNewUser({ email: "", passcode: "", is_owner: false });
      setNote("Access granted.");
      await loadAccess();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function removeAccessUser(emailToRemove: string) {
    try {
      await api.removeAccess(emailToRemove);
      await loadAccess();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function load() {
    try {
      const data = await api.getSettings();
      setS(data);
      setForm({
        llm_provider: data.llm_provider,
        model_extract: data.model_extract,
        model_synth: data.model_synth,
        local_base_url: data.local_base_url,
        local_model: data.local_model,
        brand_name: data.brand_name,
        anthropic_api_key: "",
        local_api_key: "",
      });
      try {
        setPalette(data.brand_palette ? JSON.parse(data.brand_palette) : {});
      } catch {
        setPalette({});
      }
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  useEffect(() => {
    load();
    loadAccess();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function set(k: string, v: string) {
    setForm({ ...form, [k]: v });
  }

  async function save() {
    setError("");
    setNote("");
    const updates: Record<string, string> = { ...form, brand_palette: JSON.stringify(palette) };
    // Don't overwrite stored secrets with blank fields.
    if (!updates.anthropic_api_key) delete updates.anthropic_api_key;
    if (!updates.local_api_key) delete updates.local_api_key;
    try {
      await api.updateSettings(updates);
      setNote("Settings saved.");
      await load();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function uploadLogo(file: File) {
    try {
      await api.uploadBrandLogo(file);
      setNote("Logo uploaded.");
      setLogoBump((n) => n + 1);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function testConnection() {
    setError("");
    setNote("Testing…");
    try {
      const r = await api.testLlm();
      setNote(`Connection OK (${r.provider}). Sample: "${r.sample}"`);
    } catch (e) {
      setNote("");
      setError(String((e as Error).message ?? e));
    }
  }

  if (!s) return <Spinner label="Loading settings…" />;

  return (
    <div className="space-y-5">
      {error && <ErrorNote message={error} />}
      {note && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {note}
        </div>
      )}

      <Card title="AI model provider">
        <p className="mb-3 text-xs text-slate-500">
          Choose the frontier Claude API or a local LLM on your computer (for use when online models
          are disrupted). Your key is stored on the server, never shown back in full.
        </p>
        <div className="mb-3 flex gap-4 text-sm">
          {["anthropic", "local"].map((p) => (
            <label key={p} className="flex items-center gap-2">
              <input
                type="radio"
                checked={form.llm_provider === p}
                onChange={() => set("llm_provider", p)}
              />
              {p === "anthropic" ? "Anthropic (Claude)" : "Local LLM"}
            </label>
          ))}
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <Field
            label={`Anthropic API key ${s.anthropic_api_key_set ? `(set ••••${s.anthropic_api_key_last4})` : "(not set)"}`}
            value={form.anthropic_api_key ?? ""}
            onChange={(v) => set("anthropic_api_key", v)}
            type="password"
            placeholder="sk-ant-… (leave blank to keep)"
          />
          <div />
          <Field label="Extraction model" value={form.model_extract ?? ""} onChange={(v) => set("model_extract", v)} />
          <Field label="Synthesis model" value={form.model_synth ?? ""} onChange={(v) => set("model_synth", v)} />
          <Field label="Local base URL" value={form.local_base_url ?? ""} onChange={(v) => set("local_base_url", v)} placeholder="http://localhost:11434/v1" />
          <Field label="Local model" value={form.local_model ?? ""} onChange={(v) => set("local_model", v)} placeholder="llama3.1" />
          <Field label="Local API key (optional)" value={form.local_api_key ?? ""} onChange={(v) => set("local_api_key", v)} type="password" placeholder="leave blank to keep" />
        </div>
        <div className="mt-3 flex gap-2">
          <Button onClick={save}>Save</Button>
          <Button variant="ghost" onClick={testConnection}>
            Test connection
          </Button>
        </div>
      </Card>

      <Card title="Brand (deck template)">
        <p className="mb-3 text-xs text-slate-500">
          Set a logo and palette; generated decks using the “brand” template adopt them.
        </p>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Brand name" value={form.brand_name ?? ""} onChange={(v) => set("brand_name", v)} />
          <div />
          {PALETTE_KEYS.map(([k, label]) => (
            <Field
              key={k}
              label={`${label} (hex)`}
              value={palette[k] ?? ""}
              onChange={(v) => setPalette({ ...palette, [k]: v })}
              placeholder="2F6F6A"
            />
          ))}
        </div>
        <div className="mt-3 flex items-center gap-4">
          {s.brand_logo_path && (
            <img
              src={api.brandLogoUrl() + `&b=${logoBump}`}
              alt="brand logo"
              className="h-12 w-auto rounded border border-slate-200 bg-white p-1"
            />
          )}
          <label className="text-sm">
            <span className="text-slate-600">Upload logo (png/jpg)</span>
            <input
              type="file"
              accept=".png,.jpg,.jpeg,.gif"
              onChange={(e) => e.target.files?.[0] && uploadLogo(e.target.files[0])}
              className="mt-1 block text-sm"
            />
          </label>
        </div>
        <div className="mt-3">
          <Button onClick={save}>Save brand</Button>
        </div>
      </Card>

      {owner && (
        <Card title="Access control (who can sign in)">
          <p className="mb-3 text-xs text-slate-500">
            This app is private. Only people on this list can sign in with their email + passcode.
          </p>
          {accessUsers.length === 0 ? (
            <p className="text-sm text-slate-400">No users loaded.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                  <th className="py-2">Email</th>
                  <th>Role</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {accessUsers.map((u) => (
                  <tr key={u.email} className="border-b border-slate-100">
                    <td className="py-1">{u.email}</td>
                    <td>{u.is_owner ? "owner" : "user"}</td>
                    <td>
                      <button
                        onClick={() => removeAccessUser(u.email)}
                        className="rounded border border-red-300 px-2 py-0.5 text-xs text-red-700 hover:bg-red-50"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="mt-3 grid gap-2 md:grid-cols-4">
            <input
              value={newUser.email}
              onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
              placeholder="email"
              className="rounded border border-slate-300 px-2 py-1 text-sm md:col-span-2"
            />
            <input
              value={newUser.passcode}
              onChange={(e) => setNewUser({ ...newUser, passcode: e.target.value })}
              placeholder="passcode"
              type="password"
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <label className="flex items-center gap-1 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={newUser.is_owner}
                onChange={(e) => setNewUser({ ...newUser, is_owner: e.target.checked })}
              />
              owner
            </label>
          </div>
          <div className="mt-2">
            <Button onClick={addAccessUser}>Grant access</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
