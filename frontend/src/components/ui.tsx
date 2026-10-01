import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Download,
  LoaderCircle,
  X,
} from "lucide-react";
import { downloadUrl, request, experimentPath } from "../api";
import type { JsonMap } from "../types";

export const formatNumber = (value: number) =>
  new Intl.NumberFormat("id-ID").format(value);
export const percent = (value: number) =>
  `${(value * 100).toLocaleString("id-ID", { maximumFractionDigits: 2 })}%`;
export const errorMessage = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Terjadi kesalahan yang tidak dikenal.";
export const object = (value: unknown): JsonMap =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonMap)
    : {};
export const number = (value: unknown) =>
  typeof value === "number" ? value : 0;
export const strings = (value: unknown) =>
  Array.isArray(value) ? value.map(String) : [];
export const display = (value: unknown): string =>
  value == null
    ? "—"
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
export const formatDate = (value: string) =>
  new Date(value).toLocaleString("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
  });

export function useResource<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((value) => value + 1), []);
  useEffect(() => {
    setData(null);
    setError(null);
    if (!path) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    request<T>(path, { signal: controller.signal })
      .then((result) => {
        if (active) setData(result);
      })
      .catch((caught) => {
        if (active) setError(errorMessage(caught));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [path, version]);
  return { data, loading, error, reload };
}
export function Notice({
  children,
  tone = "warning",
}: {
  children: ReactNode;
  tone?: "warning" | "success" | "error";
}) {
  return (
    <div
      className={`notice ${tone}`}
      role={tone === "error" ? "alert" : "status"}
    >
      {tone === "success" ? (
        <CheckCircle2 size={18} />
      ) : (
        <AlertTriangle size={18} />
      )}
      <div>{children}</div>
    </div>
  );
}
export function Loading({ label = "Memuat data lokal…" }: { label?: string }) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle className="spin" size={24} />
      <p>{label}</p>
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-index">/</span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function PageHeader({
  index,
  title,
  description,
  action,
}: {
  index: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <section className="page-heading">
      <div>
        <p className="eyebrow">{index} / WORKFLOW</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="page-actions">{action}</div>
    </section>
  );
}
export function Panel({
  title,
  note,
  children,
  className = "",
}: {
  title: string;
  note?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-header">
        <h2>{title}</h2>
        {note && <span>{note}</span>}
      </div>
      {children}
    </section>
  );
}
export function Stat({
  label,
  value,
  note,
  tone = "",
}: {
  label: string;
  value: string | number;
  note?: string;
  tone?: string;
}) {
  return (
    <article className={`stat ${tone}`}>
      <span>{label}</span>
      <strong>{typeof value === "number" ? formatNumber(value) : value}</strong>
      {note && <small>{note}</small>}
    </article>
  );
}
export function DownloadLink({
  jobId,
  artifact,
  children,
  experimentId,
}: {
  jobId: string;
  artifact: string;
  children: ReactNode;
  experimentId?: string | null;
}) {
  return (
    <a className="secondary-button" href={experimentId ? experimentPath(jobId, experimentId, `download/${artifact}`) : downloadUrl(jobId, artifact)}>
      <Download size={16} />
      {children}
    </a>
  );
}
export function Pagination({
  page,
  totalPages,
  total,
  onChange,
}: {
  page: number;
  totalPages: number;
  total: number;
  onChange: (page: number) => void;
}) {
  return (
    <div className="pagination">
      <span>{formatNumber(total)} record · 25 per halaman</span>
      <div>
        <button
          aria-label="Halaman sebelumnya"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ArrowLeft size={16} />
        </button>
        <span>
          {page} / {Math.max(1, totalPages)}
        </span>
        <button
          aria-label="Halaman berikutnya"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
        >
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}
export function DataTable({
  columns,
  items,
}: {
  columns: string[];
  items: JsonMap[];
}) {
  if (!items.length)
    return (
      <Empty title="Tidak ada record">Halaman ini tidak memiliki data.</Empty>
    );
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column.replaceAll("_", " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={display(item.record_id ?? index)}>
              {columns.map((column) => (
                <td key={column}>
                  <div className="table-value" title={display(item[column])}>
                    {display(item[column])}
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function BarChart({
  items,
  percentage = false,
}: {
  items: Array<{ label: string; value: number }>;
  percentage?: boolean;
}) {
  const max = Math.max(...items.map((item) => item.value), 1);
  return (
    <div className="bar-chart">
      {items.map((item) => (
        <div className="bar-row" key={item.label}>
          <div>
            <span title={item.label}>{item.label}</span>
            <strong>
              {percentage ? percent(item.value) : formatNumber(item.value)}
            </strong>
          </div>
          <div className="bar-track">
            <span style={{ width: `${(item.value / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
export function KeyValues({ values }: { values: JsonMap }) {
  return (
    <dl className="key-values">
      {Object.entries(values).map(([key, value]) => (
        <div key={key}>
          <dt>{key.replaceAll("_", " ")}</dt>
          <dd>{display(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Modal({
  titleId,
  busy,
  onClose,
  error,
  children,
}: {
  titleId: string;
  busy: boolean;
  onClose: () => void;
  error?: string | null;
  children: ReactNode;
}) {
  const section = useRef<HTMLElement>(null);
  const callbacks = useRef({ busy, onClose });
  callbacks.current = { busy, onClose };
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const initialFocus =
      section.current?.querySelector<HTMLElement>("textarea, select") ??
      section.current?.querySelector<HTMLElement>("button");
    initialFocus?.focus();
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !callbacks.current.busy) {
        event.preventDefault();
        callbacks.current.onClose();
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        section.current?.querySelectorAll<HTMLElement>(
          "button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href]",
        ) ?? [],
      );
      if (!focusable.length) {
        event.preventDefault();
        section.current?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop">
      <section
        ref={section}
        tabIndex={-1}
        className="reason-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <button
          className="modal-close"
          aria-label="Tutup dialog"
          disabled={busy}
          onClick={onClose}
        >
          <X size={19} />
        </button>
        {error && <Notice tone="error">{error}</Notice>}
        {children}
      </section>
    </div>
  );
}
