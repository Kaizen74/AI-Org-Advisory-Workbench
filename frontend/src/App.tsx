import { useEffect, useState } from "react";

/**
 * Phase 0 placeholder shell. It checks that the backend is reachable and shows which modules
 * are live. Real pages (Engagements, Diagnostics, ...) replace this as phases ship.
 */
export default function App() {
  const [health, setHealth] = useState<"checking" | "ok" | "down">("checking");

  useEffect(() => {
    fetch("/api/../health")
      .then((r) => (r.ok ? setHealth("ok") : setHealth("down")))
      .catch(() => setHealth("down"));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-xl font-semibold">OrgAI Advisory Workbench</h1>
        <p className="text-sm text-slate-500">Phase 0 — foundations</p>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-10">
        <section className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="mb-2 text-lg font-medium">Build status</h2>
          <p className="text-sm">
            Backend health:{" "}
            <span
              className={
                health === "ok"
                  ? "font-semibold text-green-600"
                  : health === "down"
                    ? "font-semibold text-red-600"
                    : "text-slate-500"
              }
            >
              {health}
            </span>
          </p>
          <p className="mt-4 text-sm text-slate-500">
            Modules ship from Phase 1 onward: Engagement Hub, Diagnostics, Task Intelligence,
            Validation Queue, Scenario Studio, Workflow Mapper, Transition Planner, Deliverables.
          </p>
        </section>
      </main>
    </div>
  );
}
