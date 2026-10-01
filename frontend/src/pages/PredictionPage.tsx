import { useState, type FormEvent } from "react";
import {
  CheckCircle2,
  ClipboardCheck,
  LoaderCircle,
  Sparkles,
} from "lucide-react";
import { jobPath, request } from "../api";
import {
  BarChart,
  DownloadLink,
  Empty,
  errorMessage,
  formatDate,
  Loading,
  Modal,
  Notice,
  PageHeader,
  Pagination,
  Panel,
  percent,
  useResource,
} from "../components/ui";
import type {
  PredictionHistoryItem,
  PredictionHistoryPage,
  PredictionInput,
  PredictionResult,
  PredictionSchema,
  WorkspaceProps,
} from "../types";
import { requiresActualReason, validatePrediction } from "../validation";

export default function PredictionPage({ job, refresh }: WorkspaceProps) {
  const [input, setInput] = useState<PredictionInput>({
    tanggal: new Date().toLocaleDateString("en-CA"),
    customer: "",
    teknisi: "UNKNOWN",
    text_laporan: "",
  });
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [pending, setPending] = useState<PredictionHistoryItem | null>(null);
  const [decision, setDecision] = useState<string>(
    "SELESAI",
  );
  const [reason, setReason] = useState("");
  const available = job.prediction_ready ?? job.artifacts.evaluation;
  const schema = useResource<PredictionSchema>(available ? jobPath(job.job_id, 'prediction/schema') : null);
  const [features, setFeatures] = useState<Record<string, string>>({});
  const generic = schema.data?.profile === 'generic' || (!schema.data && job.profile === 'generic');
  const history = useResource<PredictionHistoryPage>(
    available
      ? jobPath(job.job_id, `predictions?page=${page}&page_size=25`)
      : null,
  );
  async function predict(event: FormEvent) {
    event.preventDefault();
    const submitted = new FormData(event.currentTarget as HTMLFormElement);
    setError(null);
    setSuccess(null);
    if (!schema.data) {setError('Schema input model belum tersedia.'); return;}
    const validationError = generic ? null : validatePrediction(input);
    if (validationError) {
      setError(validationError);
      return;
    }
    setBusy(true);
    try {
      const next = await request<PredictionResult>(
        jobPath(job.job_id, "predict"),
        {
          method: "POST",
          body: JSON.stringify(generic ? {features: Object.fromEntries(schema.data.features.map(feature => [feature.name, String(submitted.get(feature.name) ?? '').trim() || null]))} : {
            ...input,
            customer: input.customer.trim(),
            teknisi: input.teknisi.trim() || "UNKNOWN",
            text_laporan: input.text_laporan.trim(),
          }),
        },
      );
      setResult(next);
      setPage(1);
      history.reload();
      await refresh();
      setSuccess("Prediksi dibuat dan dicatat pada history append-only.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }
  function openDecision(item: PredictionHistoryItem) {
    setPending(item);
    setDecision(item.actual_decision ?? item.prediction);
    setReason("");
    setError(null);
  }
  const reasonRequired = requiresActualReason(
    pending?.actual_decision ?? null,
    decision,
  );
  async function saveDecision(event: FormEvent) {
    event.preventDefault();
    if (!pending || (reasonRequired && !reason.trim())) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await request<PredictionHistoryItem>(
        jobPath(
          job.job_id,
          `predictions/${pending.prediction_id}/actual-decision`,
        ),
        {
          method: "PATCH",
          body: JSON.stringify({
            actual_decision: decision,
            reason: reason.trim() || null,
          }),
        },
      );
      if (result?.prediction_id === updated.prediction_id) setResult(updated);
      history.reload();
      setPending(null);
      setSuccess(
        "Keputusan aktual tercatat sebagai event baru. Event lama tetap utuh.",
      );
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }
  const updateInput = (key: keyof PredictionInput, value: string) =>
    setInput((current) => ({ ...current, [key]: value }));
  return (
    <>
      <PageHeader
        index="07"
        title="Rekomendasi, bukan keputusan final."
        description="Inference memakai pipeline model tersimpan tanpa training ulang. Keputusan aktual admin dicatat terpisah sebagai event append-only."
        action={
          job.artifacts.predictions && (
            <DownloadLink jobId={job.job_id} artifact="predictions">
              History JSONL
            </DownloadLink>
          )
        }
      />
      {error && <Notice tone="error">{error}</Notice>}
      {success && <Notice tone="success">{success}</Notice>}
      {schema.error && <Notice tone="error">{schema.error}</Notice>}
      {!available ? (
        <Empty title="Model aktif belum tersedia">
          Selesaikan training dan evaluation, lalu pilih “Gunakan untuk prediksi” pada menu Evaluation.
        </Empty>
      ) : (
        <>
          <Notice>{generic ? 'Model menggunakan target dataset yang dipilih. Tinjau evaluasi per kelas dan kondisi sebenarnya sebelum keputusan final.' : 'Model ini berbasis weak supervision. Tinjau kondisi sebenarnya sebelum keputusan final, terutama kasus tindak lanjut.'}</Notice>
          <div className="two-columns prediction-columns">
            <Panel title="Laporan baru" note="INPUT INFERENCE">
              {schema.loading && <Loading label="Memuat kontrak input model…"/>}
              <form className="prediction-form" onSubmit={predict}>
                {generic ? schema.data?.features.map(feature => <label key={feature.name}>{feature.name} <small>({feature.kind})</small>{feature.kind === 'text' ? <textarea name={feature.name} rows={4} value={features[feature.name] ?? ''} disabled={busy} onChange={e => setFeatures(current => ({...current, [feature.name]: e.target.value}))}/> : feature.kind === 'date' ? <input name={feature.name} type="date" defaultValue="" disabled={busy}/> : <input name={feature.name} type={feature.kind === 'numeric' ? 'number' : 'text'} step={feature.kind === 'numeric' ? 'any' : undefined} value={features[feature.name] ?? ''} disabled={busy} onChange={e => setFeatures(current => ({...current, [feature.name]: e.target.value}))}/>}</label>) : <>
                <div className="form-row">
                  <label>
                    Tanggal
                    <input
                      type="date"
                      required
                      value={input.tanggal}
                      onChange={(event) =>
                        updateInput("tanggal", event.target.value)
                      }
                      disabled={busy}
                    />
                  </label>
                  <label>
                    Customer
                    <input
                      required
                      maxLength={200}
                      value={input.customer}
                      onChange={(event) =>
                        updateInput("customer", event.target.value)
                      }
                      placeholder="Nama customer"
                      disabled={busy}
                    />
                  </label>
                </div>
                <label>
                  Teknisi
                  <input
                    maxLength={500}
                    value={input.teknisi}
                    onChange={(event) =>
                      updateInput("teknisi", event.target.value)
                    }
                    placeholder="UNKNOWN jika belum diketahui"
                    disabled={busy}
                  />
                </label>
                <label>
                  Keluhan & solusi
                  <textarea
                    required
                    minLength={3}
                    maxLength={10000}
                    rows={6}
                    value={input.text_laporan}
                    onChange={(event) =>
                      updateInput("text_laporan", event.target.value)
                    }
                    placeholder="Tuliskan kondisi, pekerjaan yang dilakukan, hasil, dan kebutuhan tindak lanjut…"
                    disabled={busy}
                  />
                </label>
                </>}
                <div className="form-bottom">
                  <small>
                    {generic ? 'Kosong: imputasi sesuai model tersimpan' : `${input.text_laporan.length.toLocaleString('id-ID')} / 10.000 karakter`}
                  </small>
                  <button className="primary-button" disabled={busy || !schema.data}>
                    {busy ? (
                      <LoaderCircle className="spin" size={17} />
                    ) : (
                      <Sparkles size={17} />
                    )}
                    {busy
                      ? "Memuat pipeline & memprediksi…"
                      : "Buat rekomendasi"}
                  </button>
                </div>
              </form>
            </Panel>
            <Panel
              title="Hasil rekomendasi"
              note={result?.prediction_id ?? "MENUNGGU INPUT"}
            >
              {result ? (
                <div className="prediction-result">
                  <span
                    className={`decision-badge ${generic ? 'generic' : result.prediction.toLowerCase()}`}
                  >
                    {result.prediction.replaceAll("_", " ")}
                  </span>
                  <strong className="confidence-value">
                    {percent(result.confidence)}
                  </strong>
                  <span className="confidence-label">
                    MODEL CONFIDENCE · BUKAN JAMINAN
                  </span>
                  <BarChart
                    percentage
                    items={Object.entries(result.probabilities).map(
                      ([label, value]) => ({ label, value }),
                    )}
                  />
                  <Notice>{result.warning}</Notice>
                  <small>
                    Model {result.model_id}
                    <br />
                    {formatDate(result.created_at)}
                  </small>
                  {result.actual_decision && (
                    <div className="actual-summary">
                      <CheckCircle2 size={16} />
                      Actual: {result.actual_decision.replaceAll("_", " ")}
                    </div>
                  )}
                </div>
              ) : (
                <Empty title="Belum ada rekomendasi">
                  Isi laporan baru. Tidak ada data contoh yang otomatis dikirim
                  atau disimpan.
                </Empty>
              )}
            </Panel>
          </div>
          <Panel
            title="Prediction history"
            note={`${history.data?.event_count ?? 0} APPEND-ONLY EVENTS`}
          >
            {history.loading ? (
              <Loading />
            ) : history.error ? (
              <Notice tone="error">{history.error}</Notice>
            ) : (
              history.data && (
                <>
                  {history.data.items.length ? (
                    <div className="prediction-history">
                      {history.data.items.map((item) => (
                        <article key={item.prediction_id}>
                          <div className="history-content">
                            <div className="record-meta">
                              <code>{item.prediction_id}</code>
                              <span>{formatDate(item.created_at)}</span>
                            </div>
                            <h3>{generic ? 'Input fitur' : item.input.customer}</h3>
                            <p>{generic ? Object.entries(item.input.features ?? {}).map(([name, value]) => `${name}: ${value ?? '(kosong)'}`).join(' · ') : item.input.text_laporan}</p>
                            <small>
                              {item.input.tanggal} · {item.input.teknisi} ·{" "}
                              {item.model_id}
                            </small>
                            {item.actual_decision_reason && (
                              <blockquote>
                                Alasan actual: {item.actual_decision_reason}
                              </blockquote>
                            )}
                          </div>
                          <div className="history-decision">
                            <span
                              className={`decision-badge ${generic ? 'generic' : item.prediction.toLowerCase()}`}
                            >
                              {item.prediction.replaceAll("_", " ")}
                            </span>
                            <strong>
                              {percent(item.confidence)} confidence
                            </strong>
                            <div className="actual-summary">
                              Actual:{" "}
                              {item.actual_decision?.replaceAll("_", " ") ??
                                "Belum dicatat"}
                            </div>
                            <button
                              className="secondary-button"
                              onClick={() => openDecision(item)}
                            >
                              <ClipboardCheck size={16} />
                              {item.actual_decision
                                ? "Koreksi actual"
                                : "Catat keputusan"}
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <Empty title="History masih kosong">
                      Prediksi bisnis yang Anda buat akan muncul di sini; tidak
                      ada event dummy.
                    </Empty>
                  )}
                  <Pagination
                    page={page}
                    totalPages={history.data.total_pages}
                    total={history.data.total_items}
                    onChange={setPage}
                  />
                </>
              )
            )}
          </Panel>
        </>
      )}
      {pending && (
        <Modal
          titleId="actual-title"
          busy={saving}
          error={error}
          onClose={() => setPending(null)}
        >
          <p className="eyebrow">ADMIN_VALIDATOR · APPEND ONLY</p>
          <h2 id="actual-title">Keputusan aktual laporan</h2>
          <p>
            {pending.prediction_id}
            <br />
            Rekomendasi model: {pending.prediction.replaceAll("_", " ")}
          </p>
          <form onSubmit={saveDecision}>
            <label htmlFor="actual-decision">Keputusan aktual</label>
            <select
              id="actual-decision"
              value={decision}
              disabled={saving}
              onChange={(event) =>
                setDecision(event.target.value)
              }
            >
              {Object.keys(pending?.probabilities ?? {}).map(label => <option key={label} value={label}>{label.replaceAll('_', ' ')}</option>)}
            </select>
            <label htmlFor="actual-reason">
              Alasan {reasonRequired ? "(wajib untuk perubahan)" : "(opsional)"}
            </label>
            <textarea
              id="actual-reason"
              value={reason}
              required={reasonRequired}
              maxLength={500}
              onChange={(event) => setReason(event.target.value)}
              disabled={saving}
            />
            {reasonRequired && (
              <small>
                Koreksi keputusan lama wajib disertai alasan. Histori lama tidak
                ditimpa.
              </small>
            )}
            <button
              className="primary-button"
              disabled={
                saving ||
                pending.actual_decision === decision ||
                (reasonRequired && !reason.trim())
              }
            >
              {saving ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <CheckCircle2 size={17} />
              )}
              Catat event keputusan
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}
