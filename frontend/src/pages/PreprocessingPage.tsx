import { useState } from "react";
import { ArrowRight, Layers3, LoaderCircle, ShieldCheck } from "lucide-react";
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
  Panel,
  Stat,
  strings,
  useResource,
} from "../components/ui";
import type { PreprocessingReport, WorkspaceProps } from "../types";

export default function PreprocessingPage({
  job,
  refresh,
  navigate,
}: WorkspaceProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const report = useResource<PreprocessingReport>(
    job.artifacts.preprocessed
      ? jobPath(job.job_id, "preprocessing-report")
      : null,
  );
  async function preprocess() {
    setBusy(true);
    setError(null);
    try {
      await runStage(job.job_id, "preprocess");
      await refresh();
      report.reload();
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
        index="04"
        title="Fitur yang dapat ditelusuri."
        description="Feature engineering stateless dilakukan sekarang. Vocabulary, encoding, dan imputasi dipelajari hanya dari train set saat fitting model."
        action={
          job.artifacts.preprocessed ? (
            <>
              <DownloadLink jobId={job.job_id} artifact="preprocessed">
                Features XLSX
              </DownloadLink>
              <button
                className="primary-button"
                onClick={() => navigate("training")}
              >
                Split & training <ArrowRight size={17} />
              </button>
            </>
          ) : (
            <button
              className="primary-button"
              disabled={
                busy ||
                !job.artifacts.cleaned ||
                !["CLEANED", "LABELING", "LABELED"].includes(job.status)
              }
              onClick={() => void preprocess()}
            >
              {busy ? (
                <LoaderCircle size={17} className="spin" />
              ) : (
                <Layers3 size={17} />
              )}
              Jalankan preprocessing
            </button>
          )
        }
      />
      {error && <Notice tone="error">{error}</Notice>}
      {success && (
        <Notice tone="success">
          Artifact preprocessing selesai; learned transformer belum di-fit.
        </Notice>
      )}
      {busy && (
        <Loading label="Feature engineering, pemeriksaan leakage, dan near-duplicate grouping…" />
      )}
      {report.loading && <Loading />}
      {report.error && <Notice tone="error">{report.error}</Notice>}
      {!job.artifacts.preprocessed && !busy && (
        <Empty title="Preprocessing belum dijalankan">
          {job.profile === 'generic' ? 'Lanjutkan setelah cleaning. Target kosong dikecualikan dengan audit; tanggal di luar periode PT tetap valid untuk profil Umum. Seluruh fitur mengikuti konfigurasi tersimpan.' : <>
          Lanjutkan langsung setelah cleaning. Label upload sudah tersedia;
          label kosong pada job lama diidentifikasi otomatis tanpa menimpa
          keputusan yang sudah ada. Needs Review serta tanggal di luar kontrak
          akan dikecualikan dengan alasan. Dua kelas final dengan minimal dua
          record per kelas diperlukan.
          </>}
        </Empty>
      )}
      {data && (
        <>
          <div className="stats-grid">
            <Stat label="SUMBER BERLABEL" value={data.source_rows} />
            <Stat
              label="OUTPUT FEATURES"
              value={data.output_rows}
              tone="teal"
            />
            <Stat
              label="DIKECUALIKAN"
              value={data.excluded_rows}
              tone="amber"
            />
            <Stat
              label="FIT POLICY"
              value="Train-only"
              note={data.preprocessing_version}
            />
          </div>
          <div className="two-columns">
            <Panel
              title="Kontrak fitur model"
              note={`${strings(data.feature_contract.model_feature_columns).length} FITUR`}
            >
              <div className="feature-groups">
                {[
                  ["Teks", "text_features"],
                  ["Kategori", "categorical_features"],
                  ["Numerik", "numeric_features"],
                  ['Tanggal', 'date_features'],
                ].map(([title, key]) => (
                  <div key={key}>
                    <span>{title}</span>
                    <div>
                      {strings(data.feature_contract[key]).map((feature) => (
                        <code key={feature}>{feature}</code>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
            <Panel title="Distribusi target final">
              <BarChart
                items={Object.entries(data.target_distribution).map(
                  ([label, value]) => ({ label, value }),
                )}
              />
              <Notice>
                Distribusi tidak seimbang. Split menjaga group isolation; model
                menggunakan class_weight balanced.
              </Notice>
            </Panel>
          </div>
          <div className="two-columns">
            <Panel title="Pengecualian yang diaudit">
              <BarChart
                items={Object.entries(data.excluded_counts).map(
                  ([label, value]) => ({
                    label: label.replaceAll("_", " "),
                    value,
                  }),
                )}
              />
            </Panel>
            <Panel
              title="Leakage guard"
              note={data.leakage_audit.passed ? "PASSED" : "CHECK REQUIRED"}
            >
              <ul className="check-list">
                {Object.entries(data.leakage_audit)
                  .filter(([, value]) => typeof value === "boolean")
                  .map(([key, value]) => (
                    <li key={key}>
                      <ShieldCheck size={17} />
                      <span>{key.replaceAll("_", " ")}</span>
                      <strong>{value ? "PASS" : "FAIL"}</strong>
                    </li>
                  ))}
              </ul>
            </Panel>
          </div>
          {data.leakage_audit.weak_supervision_warning && <Notice>
            {display(data.leakage_audit.weak_supervision_warning)}
          </Notice>}
          <Panel title="Near-duplicate grouping" note="TIDAK DIHAPUS OTOMATIS">
            <KeyValues
              values={{
                metode: data.near_duplicate_evaluation.method,
                threshold: data.near_duplicate_evaluation.threshold,
                group: data.near_duplicate_evaluation.group_count,
                pasangan: data.near_duplicate_evaluation.pair_count,
                group_konflik_label:
                  data.near_duplicate_evaluation.conflicting_label_groups
                    .length,
                penghapusan_otomatis:
                  data.near_duplicate_evaluation.automatic_removal,
              }}
            />
            <Notice>
              {job.profile === 'generic' ? 'Fitur terpilih yang identik ditempatkan pada group yang sama, termasuk jika target berbeda. Konflik target dipertahankan dan diaudit.' : <>
              Near duplicate pada customer yang sama disatukan sebagai group
              untuk isolasi train/test, bukan dibuang otomatis.
              </>}
            </Notice>
          </Panel>
          <Panel
            title="Transformer specification"
            note="BELUM FIT PADA DATA PENUH"
          >
            <div className="transformer-cards">
              <article>
                <span>TEXT</span>
                <h3>TF-IDF</h3>
                <p>{job.profile === 'generic' ? 'TF-IDF per kolom teks.' : 'Unigram & bigram.'} Vocabulary dipelajari dari train set.</p>
              </article>
              <article>
                <span>CATEGORICAL</span>
                <h3>One-hot encoding</h3>
                <p>
                  {job.profile === 'generic' ? 'Kategori kosong eksplisit;' : 'Most-frequent imputation;'} kategori baru ditangani dengan
                  ignore.
                </p>
              </article>
              <article>
                <span>NUMERIC</span>
                <h3>Median imputation</h3>
                <p>Scaling tidak diperlukan untuk baseline Random Forest.</p>
              </article>
            </div>
          </Panel>
        </>
      )}
    </>
  );
}
