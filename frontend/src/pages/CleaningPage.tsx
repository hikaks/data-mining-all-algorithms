import { useState } from "react";
import { ArrowRight, FlaskConical, LoaderCircle } from "lucide-react";
import { jobPath, runStage } from "../api";
import {
  BarChart,
  display,
  DownloadLink,
  Empty,
  errorMessage,
  KeyValues,
  Loading,
  Notice,
  PageHeader,
  Pagination,
  Panel,
  Stat,
  useResource,
} from "../components/ui";
import type { AuditPage, CleaningReport, WorkspaceProps } from "../types";

const sections = [
  ["operations", "Operasi normalisasi"],
  ["duplicate_records", "Exact duplicate"],
  ["removed_empty_records", "Baris kosong dibuang"],
  ["invalid_dates", "Tanggal invalid"],
  ["incomplete_records", "Record incomplete"],
  ["potential_duplicates", "Near duplicate"],
];
export default function CleaningPage({
  job,
  refresh,
  navigate,
}: WorkspaceProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [section, setSection] = useState("operations");
  const [page, setPage] = useState(1);
  const report = useResource<CleaningReport>(
    job.artifacts.cleaned
      ? jobPath(job.job_id, "cleaning-report?include_details=false")
      : null,
  );
  const audit = useResource<AuditPage>(
    job.artifacts.cleaned
      ? jobPath(
          job.job_id,
          `cleaning-report/audit?section=${section}&page=${page}&page_size=25`,
        )
      : null,
  );
  async function clean() {
    setBusy(true);
    setError(null);
    setSuccess(false);
    try {
      await runStage(job.job_id, "clean");
      await refresh();
      report.reload();
      audit.reload();
      setSuccess(true);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  const data = report.data;
  return (
    <>
      <PageHeader
        index="03"
        title="Bersih, tanpa kehilangan jejak."
        description="Normalisasi menghasilkan dataset baru. Exact duplicate dibuang; near duplicate dan tanggal bermasalah tetap memiliki audit."
        action={
          job.artifacts.cleaned ? (
            <>
              <DownloadLink jobId={job.job_id} artifact="cleaned">
                Cleaned XLSX
              </DownloadLink>
              <button
                className="primary-button"
                onClick={() => navigate("preprocessing")}
              >
                Ke preprocessing <ArrowRight size={17} />
              </button>
            </>
          ) : (
            <button
              className="primary-button"
              disabled={
                busy ||
                job.configuration_ready === false ||
                !["UPLOADED", "ANALYZED", "CLEANED"].includes(job.status)
              }
              onClick={() => void clean()}
            >
              {busy ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <FlaskConical size={17} />
              )}
              {busy ? "Cleaning berjalan…" : "Jalankan cleaning"}
            </button>
          )
        }
      />
      {error && <Notice tone="error">{error}</Notice>}
      {success && (
        <Notice tone="success">
          Cleaning selesai. Label upload dipertahankan; Anda bisa langsung
          preprocessing. Raw dataset tidak ditimpa.
        </Notice>
      )}
      {busy && (
        <Loading label="Normalisasi, fingerprint duplicate, dan penulisan audit…" />
      )}
      {report.loading && <Loading />}
      {report.error && <Notice tone="error">{report.error}</Notice>}
      {!job.artifacts.cleaned && !busy && (
        <Empty title="Cleaning belum dijalankan">
          Mulai cleaning untuk menghasilkan artifact dan laporan kualitas.
        </Empty>
      )}
      {data && (
        <>
          <div className="stats-grid">
            <Stat label="SEBELUM" value={data.rows_before} />
            <Stat label="SESUDAH" value={data.rows_after} tone="teal" />
            <Stat
              label="RECORD DIHAPUS"
              value={data.rows_before - data.rows_after}
              note="Exact duplicate & operationally empty"
              tone="amber"
            />
            <Stat
              label="NEAR DUPLICATE"
              value={
                job.artifacts.preprocessed
                  ? "Di preprocessing"
                  : "Belum dinilai"
              }
              note="Tidak dihapus otomatis"
            />
          </div>
          <div className="two-columns">
            <Panel title="Penghapusan terkontrol">
              <BarChart
                items={Object.entries(data.removed).map(([label, value]) => ({
                  label: label.replaceAll("_", " "),
                  value,
                }))}
              />
              <div className="panel-body muted-copy">
                Hanya exact duplicate dan record operasional kosong yang dibuang
                dari output.
              </div>
            </Panel>
            <Panel title="Ringkasan normalisasi">
              <KeyValues values={data.normalization} />
            </Panel>
          </div>
          <Panel title="Keputusan cleaning" note="DOMAIN POLICY">
            <div className="policy-grid">
              {Object.entries(data.decisions).map(([key, value]) => (
                <div key={key}>
                  <span>{key.replaceAll("_", " ")}</span>
                  <p>{value}</p>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title="Audit detail" note="25 RECORD / PAGE">
            <div className="panel-toolbar">
              <label className="inline-field">
                Bagian audit
                <select
                  aria-label="Bagian audit cleaning"
                  value={section}
                  onChange={(event) => {
                    setSection(event.target.value);
                    setPage(1);
                  }}
                >
                  {sections.map(([value, label]) => (
                    <option value={value} key={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {audit.loading ? (
              <Loading />
            ) : audit.error ? (
              <Notice tone="error">{audit.error}</Notice>
            ) : (
              audit.data && (
                <>
                  {audit.data.items.length ? (
                    <div className="audit-details">
                      {audit.data.items.map((item, index) => (
                        <details key={`${page}-${index}`}>
                          <summary>
                            <code>
                              {display(
                                item.record_id ??
                                  item.source_row ??
                                  `#${(page - 1) * 25 + index + 1}`,
                              )}
                            </code>
                            <span>
                              {display(
                                item.operation ??
                                  item.reason ??
                                  item.status ??
                                  item.field ??
                                  "Detail audit",
                              )}
                            </span>
                          </summary>
                          <pre>{JSON.stringify(item, null, 2)}</pre>
                        </details>
                      ))}
                    </div>
                  ) : (
                    <Empty title="Tidak ada temuan">
                      Bagian audit ini kosong.
                    </Empty>
                  )}
                  <Pagination
                    page={page}
                    totalPages={audit.data.total_pages}
                    total={audit.data.total_items}
                    onChange={setPage}
                  />
                </>
              )
            )}
          </Panel>
        </>
      )}
    </>
  );
}
