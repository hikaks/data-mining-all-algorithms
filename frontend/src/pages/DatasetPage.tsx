import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowRight,
  FileSpreadsheet,
  FolderOpen,
  LoaderCircle,
  Upload,
} from "lucide-react";
import { jobPath, uploadDataset } from "../api";
import {
  DataTable,
  DownloadLink,
  Empty,
  errorMessage,
  formatDate,
  formatNumber,
  Loading,
  Notice,
  PageHeader,
  Pagination,
  Panel,
  Stat,
  useResource,
} from "../components/ui";
import type { DatasetPreview, JobOverview, PageId } from "../types";
import { validateDatasetFile } from "../validation";
import DatasetConfigurationPanel from '../components/DatasetConfigurationPanel';

interface Props {
  job: JobOverview | null;
  connect: (id: string) => Promise<void>;
  refresh: () => Promise<void>;
  navigate: (page: PageId) => void;
}

export default function DatasetPage({ job, connect, navigate, refresh }: Props) {
  const [draft, setDraft] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<"dataset" | "cleaned">("dataset");
  const [page, setPage] = useState(1);
  const preview = useResource<DatasetPreview>(
    job
      ? `${jobPath(job.job_id, `${source}/preview`)}?page=${page}&page_size=25`
      : null,
  );
  useEffect(() => {preview.reload(); setPage(1);}, [job?.sheet_name, job?.raw_rows, job?.configuration_ready, preview.reload]);

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const validationError = validateDatasetFile(file);
    if (validationError || !file) {
      setError(validationError);
      return;
    }
    setBusy(true);
    try {
      const uploaded = await uploadDataset(file);
      await connect(uploaded.job_id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  async function handleConnect(event: FormEvent) {
    event.preventDefault();
    if (!draft.trim()) {
      setError("Masukkan job ID yang ingin dibuka.");
      return;
    }
    setBusy(true);
    try {
      await connect(draft);
    } catch {
      /* App menampilkan kegagalan koneksi. */
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader
        index="01"
        title={job ? "Dataset workspace" : "Dari laporan ke keputusan."}
        description="Upload Excel/CSV, pilih sheet, target dan fitur, lalu simpan konfigurasi. Profil Umum memakai label yang tersedia; preset PT Maxkomp mempertahankan identifikasi otomatis."
        action={
          job && (
            <DownloadLink jobId={job.job_id} artifact="raw">
              Raw {job.file_format?.toUpperCase() ?? 'XLSX'}
            </DownloadLink>
          )
        }
      />
      {!job && (
        <div className="welcome-banner">
          <div>
            <span className="eyebrow">CONTROLLED · AUDITABLE · LOCAL</span>
            <h2>Satu alur, dari awal hingga rekomendasi.</h2>
            <p>
              Upload berlabel → memahami data → cleaning → preprocessing → model
              → prediksi.
            </p>
          </div>
          <FileSpreadsheet size={70} strokeWidth={1} />
        </div>
      )}
      {job && (
        <>
          <div className="stats-grid">
            <Stat
              label="RAW RECORDS"
              value={job.raw_rows}
              note={
                job.raw_columns === 19
                  ? "12 kolom sumber + 7 kolom label/audit"
                  : `${job.raw_columns} kolom sumber`
              }
            />
            <Stat
              label="CLEANED"
              value={job.cleaned_rows}
              note="Exact duplicate & baris kosong disaring"
              tone="teal"
            />
            <Stat
              label="MODEL CANDIDATES"
              value={job.preprocessed_rows}
              note="Target dan fitur memenuhi kontrak profil"
            />
            <Stat
              label="MODEL"
              value={job.model_id ? "Tersedia" : "Belum dilatih"}
              note={job.model_id ?? "Lanjutkan workflow secara berurutan"}
              tone="amber"
            />
          </div>
          <Panel
            title="Jejak artifact"
            note={`Dibuat ${formatDate(job.created_at)}`}
          >
            <div className="artifact-strip">
              {[
                {
                  label: "Raw",
                  count: job.raw_rows,
                  target: "dataset",
                  ready: job.artifacts.raw,
                },
                {
                  label: "Cleaned",
                  count: job.cleaned_rows,
                  target: "cleaning",
                  ready: job.artifacts.cleaned,
                },
                {
                  label: "Label final",
                  count: job.labeled_rows,
                  target: "dataset",
                  ready: job.artifacts.labeled,
                },
                {
                  label: "Features",
                  count: job.preprocessed_rows,
                  target: "preprocessing",
                  ready: job.artifacts.preprocessed,
                },
                {
                  label: "Train / Test",
                  count: `${formatNumber(job.split_train_rows)} / ${formatNumber(job.split_test_rows)}`,
                  target: "training",
                  ready: job.artifacts.split,
                },
              ].map((item, index) => (
                <button
                  key={item.label}
                  className={item.ready ? "available" : ""}
                  onClick={() => navigate(item.target as PageId)}
                >
                  <small>0{index + 1}</small>
                  <strong>
                    {typeof item.count === "number"
                      ? formatNumber(item.count)
                      : item.count}
                  </strong>
                  <span>{item.label}</span>
                  <ArrowRight size={15} />
                </button>
              ))}
            </div>
          </Panel>
        </>
      )}
      {error && <Notice tone="error">{error}</Notice>}
      <div className="two-columns upload-columns">
        <Panel title="Upload dataset baru" note=".XLSX / .CSV / MAKS. 25 MB">
          <form onSubmit={handleUpload} className="upload-form">
            <label className={`upload-zone ${file ? "selected" : ""}`}>
              <Upload size={24} />
              <strong>{file?.name ?? "Pilih dataset Excel / CSV"}</strong>
              <span>
                {file
                  ? `${(file.size / 1024).toFixed(0)} KB · siap divalidasi`
                  : "Header pada baris pertama, label sudah tersedia"}
              </span>
              <input
                aria-label="Pilih workbook dataset"
                type="file"
                accept=".xlsx,.csv"
                disabled={busy}
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                  setError(null);
                }}
              />
            </label>
            <button className="primary-button" disabled={busy || !file}>
              {busy ? (
                <LoaderCircle size={17} className="spin" />
              ) : (
                <Upload size={17} />
              )}
              Upload & validasi
            </button>
            <small>
              Upload membuat job baru, tidak menimpa job yang sedang dibuka.
              File siap pakai: dataset/Data_Berlabel_Gabungan_PT_MAXKOMP.xlsx.
              Workbook mentah 12 kolom didukung melalui preset PT Maxkomp.
              Pilih konfigurasi setelah upload sebelum processing.
            </small>
          </form>
        </Panel>
        <Panel title="Buka job lokal" note="READ-ONLY CONNECTION">
          <form onSubmit={handleConnect} className="connect-form">
            <p>
              Lanjutkan artifact yang sudah ada menggunakan job ID.
              Menghubungkan job tidak menjalankan pemrosesan atau mengubah
              label.
            </p>
            <label htmlFor="connect-id">Job ID</label>
            <input
              id="connect-id"
              placeholder="Masukkan job ID"
              value={draft}
              disabled={busy}
              onChange={(event) => setDraft(event.target.value)}
              autoComplete="off"
            />
            <button
              className="secondary-button"
              disabled={busy || !draft.trim()}
            >
              <FolderOpen size={17} />
              Hubungkan job
            </button>
          </form>
        </Panel>
      </div>
      {job && <DatasetConfigurationPanel job={job} refresh={refresh}/>}
      {job && job.configuration_ready && job.profile !== 'generic' && (
        <Panel title="Label dataset" note="TANPA LABELING MANUAL">
          {job.input_label_source && (
            <>
              <Notice tone="success">
                {job.input_label_source === "IMPORTED"
                  ? "Label workbook sudah diimpor."
                  : "Workbook sudah diidentifikasi otomatis melalui preset PT."}{" "}
                {job.artifacts.cleaned
                  ? "Label hasil cleaning sudah tersedia."
                  : "Lanjutkan cleaning."}{" "}
                Tidak ada langkah labeling yang perlu Anda kerjakan.
              </Notice>
              <div className="stats-grid">
                {Object.entries(job.input_label_counts).map(
                  ([label, count]) => (
                    <Stat
                      key={label}
                      label={`INPUT · ${label}`}
                      value={count}
                    />
                  ),
                )}
              </div>
            </>
          )}
          <p className="muted-copy">
            {job.input_label_source
              ? "Label input dihitung sebelum penghapusan duplicate dan baris kosong."
              : "Keputusan label job lama dipertahankan; membuka job tidak mengubah artifact."}{" "}
            Setelah cleaning: {formatNumber(job.labeled_rows)} target final,{" "}
            {formatNumber(job.needs_review_rows)} Needs Review. Needs Review
            tidak menjadi target training. Label AI-assisted bukan ground-truth
            manusia independen.
          </p>
          {job.artifacts.labeled && (
            <DownloadLink jobId={job.job_id} artifact="labeled">
              Dataset berlabel hasil cleaning
            </DownloadLink>
          )}
        </Panel>
      )}
      {job ? (
        <Panel title="Preview dataset" note="SERVER-SIDE PAGINATION">
          <div className="panel-toolbar">
            <div className="segmented">
              <button
                className={source === "dataset" ? "active" : ""}
                onClick={() => {
                  setSource("dataset");
                  setPage(1);
                }}
              >
                Raw
              </button>
              <button
                className={source === "cleaned" ? "active" : ""}
                disabled={!job.artifacts.cleaned}
                onClick={() => {
                  setSource("cleaned");
                  setPage(1);
                }}
              >
                Cleaned
              </button>
            </div>
            <button
              className="text-button"
              disabled={job.configuration_ready === false}
              onClick={() => navigate("understanding")}
            >
              Data Understanding <ArrowRight size={15} />
            </button>
          </div>
          {preview.loading ? (
            <Loading />
          ) : preview.error ? (
            <Notice tone="error">{preview.error}</Notice>
          ) : (
            preview.data && (
              <>
                <DataTable
                  columns={preview.data.columns}
                  items={preview.data.items}
                />
                <Pagination
                  page={page}
                  totalPages={preview.data.total_pages}
                  total={preview.data.total_rows}
                  onChange={setPage}
                />
              </>
            )
          )}
        </Panel>
      ) : (
        <Empty title="Workspace belum memiliki job aktif">
          Upload workbook untuk membuka seluruh workflow.
        </Empty>
      )}
    </>
  );
}
