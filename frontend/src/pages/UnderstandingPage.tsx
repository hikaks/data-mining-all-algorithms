import { ArrowRight } from "lucide-react";
import { jobPath } from "../api";
import {
  BarChart,
  DataTable,
  display,
  Loading,
  Notice,
  PageHeader,
  Panel,
  Stat,
  useResource,
} from "../components/ui";
import type { DatasetSummary, WorkspaceProps } from "../types";

export default function UnderstandingPage({ job, navigate }: WorkspaceProps) {
  const report = useResource<DatasetSummary>(
    jobPath(job.job_id, "dataset/summary"),
  );
  const data = report.data;
  return (
    <>
      <PageHeader
        index="02"
        title="Pahami sebelum memproses."
        description={job.profile === 'generic' ? 'Statistik dataset mentah dan distribusi kolom target terpilih. Tidak ada pemetaan domain atau cutoff penelitian PT.' : 'Statistik dihitung dari dataset mentah. Distribusi sumber adalah konteks data, bukan label keputusan model.'}
        action={
          <button
            className="primary-button"
            onClick={() => navigate("cleaning")}
          >
            Lanjut cleaning <ArrowRight size={17} />
          </button>
        }
      />
      {report.loading && <Loading />}
      {report.error && <Notice tone="error">{report.error}</Notice>}
      {data && (
        <>
          <div className="stats-grid">
            <Stat label="BARIS SUMBER" value={data.row_count} />
            <Stat label="KOLOM" value={data.column_count} />
            <Stat
              label="RAW DUPLICATE"
              value={data.duplicate_rows}
              note="Belum fingerprint canonical"
              tone="amber"
            />
            <Stat
              label="OPERATIONALLY EMPTY"
              value={data.operationally_empty_rows}
              tone="amber"
            />
          </div>
          {job.profile !== 'generic' && <div className="date-ribbon">
            <span>RENTANG TANGGAL</span>
            <strong>
              {display(data.date_range.minimum)} <span>→</span>{" "}
              {display(data.date_range.maximum)}
            </strong>
            <small>
              {display(data.date_range.invalid_or_missing)} tanggal invalid /
              kosong · {display(data.date_range.after_research_period)} setelah
              periode penelitian
            </small>
          </div>}
          <div className="two-columns">
            {(job.profile === 'generic' ? [{key: 'target', title: `Target: ${job.target_column}`, note: 'KELAS DARI DATASET'}] : [
              { key: "customer", title: "Customer", note: "10 TERATAS" },
              { key: "technician", title: "Teknisi", note: "10 TERATAS" },
              { key: "year", title: "Tahun sumber", note: "DISTRIBUSI" },
              {
                key: "status",
                title: "Status asli",
                note: "EVIDENCE · BUKAN TARGET",
              },
            ]).map((chart) => (
              <Panel key={chart.key} title={chart.title} note={chart.note}>
                <BarChart
                  items={(data.distributions[chart.key] ?? [])
                    .slice(0, 10)
                    .map((item) => ({
                      label: item.value === "nan" ? "(kosong)" : item.value,
                      value: item.count,
                    }))}
                />
              </Panel>
            ))}
          </div>
          <Panel title="Kualitas per kolom" note="MISSING / UNIQUE">
            <DataTable
              columns={["kolom", "tipe", "missing", "missing_persen", "unique"]}
              items={data.columns.map((column) => ({
                kolom: column.name,
                tipe: column.dtype,
                missing: column.missing_count,
                missing_persen: `${column.missing_percentage.toFixed(2)}%`,
                unique: column.unique_count,
              }))}
            />
          </Panel>
        </>
      )}
    </>
  );
}
