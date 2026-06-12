import { useState } from "react";
import Engagements from "./pages/Engagements";
import Diagnostics from "./pages/Diagnostics";
import TaskIntelligence from "./pages/TaskIntelligence";

type Tab = "engagements" | "diagnostics" | "task-intel";

export default function App() {
  const [tab, setTab] = useState<Tab>("engagements");
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [diagTitle, setDiagTitle] = useState<string>("");

  function openDiagnostics(id: string, engagementName: string) {
    setDatasetId(id);
    setDiagTitle(engagementName);
    setTab("diagnostics");
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "engagements", label: "Engagements" },
    { id: "diagnostics", label: "Diagnostics" },
    { id: "task-intel", label: "Task Intelligence" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">OrgAI Advisory Workbench</h1>
            <p className="text-xs text-slate-500">Phase 1 — Engagement core + diagnostics</p>
          </div>
          <nav className="flex gap-1">
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
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {tab === "engagements" && <Engagements onOpenDiagnostics={openDiagnostics} />}
        {tab === "diagnostics" && <Diagnostics datasetId={datasetId} title={diagTitle} />}
        {tab === "task-intel" && (
          <TaskIntelligence datasetId={datasetId} title={diagTitle} />
        )}
      </main>
    </div>
  );
}
