import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { Client, Dataset, Engagement } from "../types";
import { Button, Card, Empty, ErrorNote, Spinner } from "../components/ui";
import { CompassImport, CompassRolesPanel } from "../components/Compass";

export default function Engagements({
  onOpenDiagnostics,
}: {
  onOpenDiagnostics: (datasetId: string, engagementId: string, engagementName: string) => void;
}) {
  const [clients, setClients] = useState<Client[]>([]);
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedClient, setSelectedClient] = useState<string>("");
  const [selectedEngagement, setSelectedEngagement] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [newClient, setNewClient] = useState("");
  const [newEngagement, setNewEngagement] = useState("");
  const [compassTick, setCompassTick] = useState(0); // bumps to refresh the Compass roles panel

  async function onCompassImported(r: { engagement_id: string; client_id: string }) {
    try {
      await refreshClients();
      setSelectedClient(r.client_id);
      setEngagements(await api.listEngagements(r.client_id));
      setSelectedEngagement(r.engagement_id);
      setCompassTick((t) => t + 1);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function refreshClients() {
    setClients(await api.listClients());
  }

  useEffect(() => {
    refreshClients()
      .catch((e) => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedClient) {
      setEngagements([]);
      return;
    }
    api.listEngagements(selectedClient).then(setEngagements).catch((e) => setError(String(e)));
  }, [selectedClient]);

  useEffect(() => {
    if (!selectedEngagement) {
      setDatasets([]);
      return;
    }
    api.listDatasets(selectedEngagement).then(setDatasets).catch((e) => setError(String(e)));
  }, [selectedEngagement]);

  async function addClient() {
    if (!newClient.trim()) return;
    try {
      const c = await api.createClient(newClient.trim());
      setNewClient("");
      await refreshClients();
      setSelectedClient(c.id);
    } catch (e) {
      setError(String(e));
    }
  }

  async function addEngagement() {
    if (!selectedClient || !newEngagement.trim()) return;
    try {
      const e = await api.createEngagement(selectedClient, newEngagement.trim());
      setNewEngagement("");
      setEngagements(await api.listEngagements(selectedClient));
      setSelectedEngagement(e.id);
    } catch (err) {
      setError(String(err));
    }
  }

  async function upload(file: File) {
    if (!selectedEngagement) return;
    try {
      await api.uploadDataset(selectedEngagement, file);
      setDatasets(await api.listDatasets(selectedEngagement));
      setCompassTick((t) => t + 1);
    } catch (e) {
      setError(String(e));
    }
  }

  async function delClient(id: string, name: string) {
    if (!window.confirm(`Delete client "${name}" and ALL its engagements, datasets and analysis? This cannot be undone.`)) return;
    try {
      await api.deleteClient(id);
      if (selectedClient === id) {
        setSelectedClient("");
        setSelectedEngagement("");
      }
      await refreshClients();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function delEngagement(id: string, name: string) {
    if (!window.confirm(`Delete engagement "${name}" and all its datasets/analysis? This cannot be undone.`)) return;
    try {
      await api.deleteEngagement(id);
      if (selectedEngagement === id) setSelectedEngagement("");
      if (selectedClient) setEngagements(await api.listEngagements(selectedClient));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function delDataset(id: string) {
    if (!window.confirm("Delete this CSV upload and everything derived from it (tasks, scores, mappings)? This cannot be undone.")) return;
    try {
      await api.deleteDataset(id);
      if (selectedEngagement) setDatasets(await api.listDatasets(selectedEngagement));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  if (loading) return <Spinner label="Loading engagements…" />;

  const engagementName =
    engagements.find((e) => e.id === selectedEngagement)?.name ?? "engagement";

  return (
    <div className="grid gap-5 md:grid-cols-3">
      {error && (
        <div className="md:col-span-3">
          <ErrorNote message={error} />
        </div>
      )}

      <Card title="Clients">
        {clients.length === 0 ? (
          <Empty message="No clients yet. Create one below." />
        ) : (
          <ul className="space-y-1">
            {clients.map((c) => (
              <li key={c.id} className="flex items-center gap-1">
                <button
                  onClick={() => setSelectedClient(c.id)}
                  className={`flex-1 rounded px-2 py-1 text-left text-sm ${
                    selectedClient === c.id ? "bg-slate-800 text-white" : "hover:bg-slate-100"
                  }`}
                >
                  {c.name}
                </button>
                <button
                  onClick={() => delClient(c.id, c.name)}
                  title="Delete client"
                  className="rounded px-1.5 py-1 text-xs text-slate-400 hover:bg-red-50 hover:text-red-600"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 flex gap-2">
          <input
            value={newClient}
            onChange={(e) => setNewClient(e.target.value)}
            placeholder="New client name"
            className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <Button onClick={addClient}>Add</Button>
        </div>
      </Card>

      <Card title="Engagements">
        {!selectedClient ? (
          <Empty message="Select a client first." />
        ) : engagements.length === 0 ? (
          <Empty message="No engagements for this client." />
        ) : (
          <ul className="space-y-1">
            {engagements.map((e) => (
              <li key={e.id} className="flex items-center gap-1">
                <button
                  onClick={() => setSelectedEngagement(e.id)}
                  className={`flex-1 rounded px-2 py-1 text-left text-sm ${
                    selectedEngagement === e.id ? "bg-slate-800 text-white" : "hover:bg-slate-100"
                  }`}
                >
                  {e.name}
                  {e.compass_key && (
                    <span
                      title="Linked to Capability Compass — engagement key"
                      className="ml-2 rounded bg-teal-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-teal-800"
                    >
                      {e.compass_key}
                    </span>
                  )}
                </button>
                <button
                  onClick={() => delEngagement(e.id, e.name)}
                  title="Delete engagement"
                  className="rounded px-1.5 py-1 text-xs text-slate-400 hover:bg-red-50 hover:text-red-600"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
        {selectedClient && (
          <div className="mt-3 flex gap-2">
            <input
              value={newEngagement}
              onChange={(e) => setNewEngagement(e.target.value)}
              placeholder="New engagement name"
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <Button onClick={addEngagement}>Add</Button>
          </div>
        )}
      </Card>

      <Card title="Datasets">
        {!selectedEngagement ? (
          <Empty message="Select an engagement to upload an org CSV." />
        ) : (
          <>
            <label className="mb-3 block">
              <span className="text-sm text-slate-600">Upload org structure CSV</span>
              <input
                type="file"
                accept=".csv"
                onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
                className="mt-1 block w-full text-sm"
              />
            </label>
            {datasets.length === 0 ? (
              <Empty message="No datasets uploaded yet." />
            ) : (
              <ul className="space-y-2">
                {datasets.map((d) => (
                  <li key={d.id} className="rounded border border-slate-200 p-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span>
                        v{d.version} · {d.row_count} positions
                      </span>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          onClick={() => onOpenDiagnostics(d.id, selectedEngagement, engagementName)}
                        >
                          Diagnose →
                        </Button>
                        <button
                          onClick={() => delDataset(d.id)}
                          title="Delete this CSV upload"
                          className="rounded px-1.5 py-1 text-xs text-slate-400 hover:bg-red-50 hover:text-red-600"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                    {d.validation_warnings && d.validation_warnings.length > 0 && (
                      <div className="mt-1 text-xs text-amber-600">
                        {d.validation_warnings.length} validation warning(s)
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Card>

      <div className="md:col-span-3">
        <CompassImport
          selectedEngagementId={selectedEngagement || null}
          selectedEngagementName={engagementName}
          onImported={onCompassImported}
        />
      </div>
      {selectedEngagement && (
        <div className="md:col-span-3">
          <CompassRolesPanel
            engagementId={selectedEngagement}
            refreshKey={compassTick}
            title="Capability Compass roles for this engagement"
          />
        </div>
      )}
    </div>
  );
}
