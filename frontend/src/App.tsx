import { useEffect, useState } from "react";
import { api, getAuthToken, setUnauthorizedHandler } from "./services/api";
import Engagements from "./pages/Engagements";
import Diagnostics from "./pages/Diagnostics";
import TaskIntelligence from "./pages/TaskIntelligence";
import ValidationQueue from "./pages/ValidationQueue";
import ScenarioStudio from "./pages/ScenarioStudio";
import WorkflowMapper from "./pages/WorkflowMapper";
import TransitionPlanner from "./pages/TransitionPlanner";
import Deliverables from "./pages/Deliverables";
import Settings from "./pages/Settings";
import Login from "./pages/Login";

type Tab =
  | "engagements"
  | "diagnostics"
  | "task-intel"
  | "validation"
  | "scenarios"
  | "workflows"
  | "transition"
  | "deliverables"
  | "settings";

export default function App() {
  const [authed, setAuthed] = useState(false);
  const [checking, setChecking] = useState(true);
  const [email, setEmail] = useState("");
  const [owner, setOwner] = useState(false);

  const [tab, setTab] = useState<Tab>("engagements");
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [engagementId, setEngagementId] = useState<string | null>(null);
  const [diagTitle, setDiagTitle] = useState<string>("");

  useEffect(() => {
    setUnauthorizedHandler(() => setAuthed(false));
    if (getAuthToken()) {
      api
        .me()
        .then((u) => {
          setEmail(u.email);
          setOwner(u.owner);
          setAuthed(true);
        })
        .catch(() => setAuthed(false))
        .finally(() => setChecking(false));
    } else {
      setChecking(false);
    }
  }, []);

  function openDiagnostics(id: string, engId: string, engagementName: string) {
    setDatasetId(id);
    setEngagementId(engId);
    setDiagTitle(engagementName);
    setTab("diagnostics");
  }

  function logout() {
    api.logout();
    setAuthed(false);
  }

  if (checking) {
    return <div className="flex min-h-screen items-center justify-center text-slate-500">Loading…</div>;
  }
  if (!authed) {
    return (
      <Login
        onLogin={(e, o) => {
          setEmail(e);
          setOwner(o);
          setAuthed(true);
        }}
      />
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "engagements", label: "Engagements" },
    { id: "diagnostics", label: "Diagnostics" },
    { id: "task-intel", label: "Task Intelligence" },
    { id: "validation", label: "Validation Queue" },
    { id: "scenarios", label: "Scenario Studio" },
    { id: "workflows", label: "Workflow Mapper" },
    { id: "transition", label: "Transition Planner" },
    { id: "deliverables", label: "Deliverables" },
    { id: "settings", label: "Settings" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">OrgAI Advisory Workbench</h1>
            <p className="text-xs text-slate-500">Private workspace</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">
              {email}
              {owner ? " · owner" : ""}
            </span>
            <button
              onClick={logout}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
            >
              Sign out
            </button>
          </div>
        </div>
        <nav className="mx-auto mt-2 flex max-w-6xl flex-wrap gap-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                tab === t.id ? "bg-slate-800 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {tab === "engagements" && <Engagements onOpenDiagnostics={openDiagnostics} />}
        {tab === "diagnostics" && <Diagnostics datasetId={datasetId} title={diagTitle} />}
        {tab === "task-intel" && <TaskIntelligence datasetId={datasetId} title={diagTitle} />}
        {tab === "validation" && (
          <ValidationQueue datasetId={datasetId} engagementId={engagementId} />
        )}
        {tab === "scenarios" && (
          <ScenarioStudio datasetId={datasetId} engagementId={engagementId} />
        )}
        {tab === "workflows" && (
          <WorkflowMapper datasetId={datasetId} engagementId={engagementId} />
        )}
        {tab === "transition" && <TransitionPlanner engagementId={engagementId} />}
        {tab === "deliverables" && (
          <Deliverables datasetId={datasetId} engagementId={engagementId} />
        )}
        {tab === "settings" && <Settings owner={owner} />}
      </main>
    </div>
  );
}
