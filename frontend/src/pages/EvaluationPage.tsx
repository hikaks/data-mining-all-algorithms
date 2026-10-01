import { useState, useRef, useEffect } from "react";
import { Activity, ArrowRight, LoaderCircle } from "lucide-react";
import { experimentPath, runExperiment, activateExperiment } from "../api";
import { ExperimentPicker, useExperiments } from '../components/experiments';
import {
  BarChart,
  DataTable,
  DownloadLink,
  Empty,
  errorMessage,
  Loading,
  Notice,
  PageHeader,
  Panel,
  percent,
  Stat,
  useResource,
} from "../components/ui";
import type { EvaluationReport, WorkspaceProps } from "../types";

export default function EvaluationPage(props: WorkspaceProps) {
  const {job, refresh, navigate} = props;
  const experiments = useExperiments(props);
  const selected = experiments.selected;
  const selection = useRef(experiments.id);
  selection.current = experiments.id;
  const mounted = useRef(true);
  useEffect(() => {mounted.current = true; return () => {mounted.current = false;};}, []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const report = useResource<EvaluationReport>(
    selected?.status === 'EVALUATED' ? experimentPath(job.job_id, selected.experiment_id, "evaluation") : null,
  );
  async function evaluate() {
    if (!selected) return;
    const id = selected.experiment_id;
    setBusy(true);
    setError(null);
    try {
      await runExperiment(job.job_id, id, "evaluate");
      if (!mounted.current || selection.current !== id) return;
      await refresh();
      if (!mounted.current || selection.current !== id) return;
      experiments.reload();
      report.reload();
    } catch (caught) {
      if (mounted.current && selection.current === id) {
        setError(`${errorMessage(caught)} Baca ulang status sebelum mencoba kembali.`);
        experiments.reload(); report.reload();
      }
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  async function activate() {
    if (!selected || !window.confirm(`Gunakan ${selected.model_id} untuk prediksi baru? Riwayat dan model sebelumnya tetap disimpan.`)) return;
    const id = selected.experiment_id;
    setBusy(true); setError(null);
    try {
      await activateExperiment(job.job_id, id);
      if (!mounted.current) return;
      await refresh();
      if (!mounted.current) return;
      experiments.reload();
    } catch (caught) {
      if (mounted.current) {setError(errorMessage(caught)); experiments.reload();}
    } finally {if (mounted.current) setBusy(false);}
  }
  const data = report.data;
  const highlight = data?.metrics.highlighted_class ?? 'TINDAK_LANJUT';
  const highlightIndex = data?.confusion_matrix.label_order.indexOf(highlight) ?? -1;
  const highlightMetrics = data?.metrics.per_class[highlight];
  const found = data?.confusion_matrix.values[highlightIndex]?.[highlightIndex] ?? 0;
  const support = highlightMetrics?.support ?? 0;
  return (
    <>
      <PageHeader
        index="06"
        title="Ukur yang benar-benar penting."
        description="Evaluasi hanya menggunakan test record ID pada manifest. Profil Umum menyoroti recall terendah; preset PT menyoroti TINDAK_LANJUT."
        action={
          selected?.status === 'EVALUATED' ? (
            <>
              <DownloadLink jobId={job.job_id} experimentId={selected.experiment_id} artifact="evaluation">
                Evaluation JSON
              </DownloadLink>
              <button
                className="primary-button"
                disabled={!job.prediction_ready}
                onClick={() => navigate("prediction")}
              >
                Ke prediksi <ArrowRight size={17} />
              </button>
            </>
          ) : (
            <button
              className="primary-button"
              disabled={
                busy || selected?.status !== 'TRAINED'
              }
              onClick={() => void evaluate()}
            >
              {busy ? (
                <LoaderCircle size={17} className="spin" />
              ) : (
                <Activity size={17} />
              )}
              Evaluasi model
            </button>
          )
        }
      />
      <ExperimentPicker props={props} experiments={experiments} disabled={busy} />
      <div className="panel-body"><button className="secondary-button" disabled={busy} onClick={() => {experiments.reload(); report.reload();}}>Baca ulang status</button></div>
      {selected?.status === 'EVALUATED' && <Panel title="Model untuk prediksi">
        <div className="panel-body">
          <p>Ditampilkan: {selected.model_id}. Model aktif: {job.model_id ?? 'Belum dipilih'}.</p>
          <button className="primary-button" disabled={busy || selected.active} onClick={() => void activate()}>{selected.active ? 'Aktif untuk prediksi' : 'Gunakan untuk prediksi'}</button>
        </div>
      </Panel>}
      {error && <Notice tone="error">{error}</Notice>}
      {busy && (
        <Loading label="Memproses eksperimen dan memverifikasi artifact…" />
      )}
      {report.loading && <Loading />}
      {report.error && <Notice tone="error">{report.error}</Notice>}
      {selected?.status !== 'EVALUATED' && !busy && (
        <Empty title="Evaluasi belum tersedia">
          Model harus selesai dilatih sebelum test set dievaluasi.
        </Empty>
      )}
      {data && (
        <>
          <section className="evaluation-callout">
            <div>
              <span>PRIORITAS · {highlight}</span>
              <strong>{percent(highlightMetrics?.recall ?? 0)}</strong>
              <h2>{job.profile === 'generic' ? 'Recall kelas terendah' : 'Recall tindak lanjut'}</h2>
            </div>
            <div>
              <p>
                Model menemukan{" "}
                <strong>
                  {found} dari {support}
                </strong>{" "}
                kasus {highlight} pada test set.
              </p>
              <p>
                <strong>
                  {support - found} kasus terlewat.
                </strong>{" "}
                Hasil prediksi adalah rekomendasi, bukan keputusan operasional
                final.
              </p>
              <small>
                Confidence tidak sama dengan jaminan ketepatan atau probabilitas
                terkalibrasi.
              </small>
            </div>
          </section>
          <div className="stats-grid">
            <Stat
              label="MACRO F1"
              value={percent(data.metrics.macro_average.f1)}
            />
            <Stat
              label={data.metrics.weighted_average ? 'WEIGHTED F1' : 'HIGHLIGHTED F1'}
              value={percent(data.metrics.weighted_average?.f1 ?? highlightMetrics?.f1 ?? 0)}
            />
            <Stat
              label="BALANCED ACCURACY"
              value={percent(data.metrics.balanced_accuracy)}
              tone="teal"
            />
            <Stat
              label="ACCURACY"
              value={percent(data.metrics.accuracy)}
              note={`${data.metrics.correct_count} / ${data.metrics.total_count} benar`}
            />
          </div>
          <div className="two-columns">
            <Panel
              title="Confusion matrix"
              note="ROW: ACTUAL · COLUMN: PREDICTED"
            >
              <div className="confusion-wrap">
                <table className="confusion-matrix">
                  <thead>
                    <tr>
                      <th>Actual ↓ / Predicted →</th>
                      {data.confusion_matrix.label_order.map((label) => (
                        <th key={label}>{label.replaceAll("_", " ")}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.confusion_matrix.values.map((row, rowIndex) => (
                      <tr key={rowIndex}>
                        <th>
                          {data.confusion_matrix.label_order[
                            rowIndex
                          ].replaceAll("_", " ")}
                        </th>
                        {row.map((value, columnIndex) => (
                          <td
                            className={
                              rowIndex === columnIndex ? "correct" : "incorrect"
                            }
                            key={columnIndex}
                          >
                            <strong>{value}</strong>
                            <small>
                              {rowIndex === columnIndex
                                ? "correct"
                                : "misclassified"}
                            </small>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          <Panel title="Metrik per kelas">
              <DataTable
                columns={["kelas", "precision", "recall", "f1", "support"]}
                items={Object.entries(data.metrics.per_class).map(
                  ([kelas, values]) => ({
                    kelas,
                    precision: percent(values.precision),
                    recall: percent(values.recall),
                    f1: percent(values.f1),
                    support: values.support,
                  }),
                )}
              />
              <div className="panel-body muted-copy">
                Model {data.model_id}
                <br />
                Evaluation {data.evaluation_id}
              </div>
            </Panel>
          </div>
          <Panel title="Feature importance" note={data.feature_importance.available === false ? 'Tidak tersedia' : '10 TERATAS · IMPURITY BASED'}>
            {data.feature_importance.available === false ? <div className="panel-body">Tidak tersedia untuk algoritma ini.</div> : <BarChart
              percentage
              items={data.feature_importance.top_features
                .slice(0, 10)
                .map((feature) => ({
                  label: feature.feature,
                  value: feature.importance,
                }))}
            />}
            <div className="panel-body">
              <DownloadLink jobId={job.job_id} experimentId={selected?.experiment_id} artifact="feature-importance">
                Seluruh feature importance
              </DownloadLink>
            </div>
            <Notice>{data.feature_importance.limitations.join(" ")}</Notice>
          </Panel>
          <Panel title="Batas interpretasi" note="WAJIB DIBACA">
            <ol className="limitations-list">
              {data.limitations.map((limitation, index) => (
                <li key={index}>{limitation}</li>
              ))}
            </ol>
          </Panel>
        </>
      )}
    </>
  );
}
