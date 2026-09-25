import type { ReactNode } from "react";

export function Card({ title, children, actions }: {
  title?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      {(title || actions) && (
        <div className="mb-3 flex items-center justify-between">
          {title && <h2 className="text-base font-semibold text-slate-800">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-slate-400">{unit}</span>}
      </div>
    </div>
  );
}

export function Button({ children, onClick, disabled, variant = "primary" }: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost" | "danger";
}) {
  const styles: Record<string, string> = {
    primary: "bg-slate-800 text-white hover:bg-slate-700",
    ghost: "border border-slate-300 text-slate-700 hover:bg-slate-100",
    danger: "border border-red-300 text-red-700 hover:bg-red-50",
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition disabled:opacity-50 ${styles[variant]}`}
    >
      {children}
    </button>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      {message}
    </div>
  );
}

export function Empty({ message }: { message: string }) {
  return <div className="py-6 text-center text-sm text-slate-400">{message}</div>;
}

export function Spinner({ label }: { label?: string }) {
  return <div className="py-6 text-center text-sm text-slate-500">{label ?? "Loading…"}</div>;
}
