import { useState, useRef, useEffect } from 'react';
import { ArrowRight, BrainCircuit, GitFork } from 'lucide-react';
import { createExperiment, experimentPath, runExperiment } from '../api';
import { algorithmNames, ExperimentPicker, useExperiments } from '../components/experiments';
import { DownloadLink, Empty, errorMessage, KeyValues, Loading, Notice, number, object, PageHeader, Panel, percent, Stat, useResource } from '../components/ui';
import type { AlgorithmId, JsonMap, ModelMetadata, WorkspaceProps } from '../types';
import {svmReplacementOptions} from '../experimentPolicy';

export default function TrainingPage(props: WorkspaceProps) {
  const {job, refresh, navigate} = props;
  const experiments = useExperiments(props);
  const [ratio, setRatio] = useState(0.2);
  const [algorithm, setAlgorithm] = useState<AlgorithmId>('random_forest');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const mounted = useRef(true);
  useEffect(() => {mounted.current = true; return () => {mounted.current = false;};}, []);
  const selected = experiments.selected;
  const replacement = svmReplacementOptions(selected);
  const manifest = useResource<JsonMap>(selected && selected.status !== 'CREATED' ? experimentPath(job.job_id, selected.experiment_id, 'split-manifest') : null);
  const metadata = useResource<ModelMetadata>(selected?.model_id ? experimentPath(job.job_id, selected.experiment_id, 'model-metadata') : null);
  async function run(stage: 'create' | 'split' | 'train', replacement?: {test_ratio: number; algorithm: AlgorithmId}) {
    setBusy(stage); setError(null); setSuccess(null);
    try {
      if (stage === 'create') {
        const result = await createExperiment(job.job_id, replacement?.test_ratio ?? ratio, replacement?.algorithm ?? algorithm);
        if (!mounted.current) return;
        props.selectExperiment?.(result.experiment_id);
      } else if (selected) {
        await runExperiment(job.job_id, selected.experiment_id, stage);
      }
      if (!mounted.current) return;
      await refresh();
      if (!mounted.current) return;
      experiments.reload(); manifest.reload(); metadata.reload();
      setSuccess(stage === 'create' ? 'Eksperimen dibuat. Buat split lalu latih model; model aktif tidak berubah.' : 'Tahap eksperimen selesai. Artifact sebelumnya tidak ditimpa.');
    } catch (caught) {
      if (mounted.current) {
        setError(`${errorMessage(caught)} Baca ulang status sebelum mencoba kembali.`);
        experiments.reload(); manifest.reload(); metadata.reload();
      }
    } finally {if (mounted.current) setBusy(null);}
  }
  return <>
    <PageHeader index="05" title="Pisahkan data. Latih baseline."
      description="Pilih rasio dan algoritma. Setiap eksperimen menyimpan model terpisah; seluruh transformer dipelajari pada train saja."
      action={selected?.model_id && <button className="primary-button" onClick={() => {props.selectExperiment?.(selected.experiment_id); navigate('evaluation');}}>Evaluasi <ArrowRight size={17} /></button>} />
    {error && <Notice tone="error">{error}</Notice>}
    {success && <Notice tone="success">{success}</Notice>}
    {!job.artifacts.preprocessed && <Empty title="Preprocessing diperlukan">Selesaikan preprocessing sebelum membuat eksperimen.</Empty>}
    <Panel title="Eksperimen baru" note="Tidak perlu upload ulang">
      <div className="panel-body">
        <div className="two-columns config-controls">
          <label>Rasio data test / train<select aria-label="Rasio data test / train" value={ratio} disabled={!!busy} onChange={e => setRatio(Number(e.target.value))}>
            <option value={0.2}>Test 20% / Train 80%</option><option value={0.25}>Test 25% / Train 75%</option><option value={0.3}>Test 30% / Train 70%</option>
          </select></label>
          <label>Algoritma<select aria-label="Algoritma" value={algorithm} disabled={!!busy} onChange={e => setAlgorithm(e.target.value as AlgorithmId)}>
            {Object.entries(algorithmNames).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select></label>
        </div>
        <p>Seed 42. Tidak ada sampling. Rasio aktual dapat berbeda karena group tidak boleh dipecah.</p>
        {algorithm === 'svm_linear' && <Notice>SVM baru tidak dibatasi 10.000 iterasi: solver ditunggu sampai konvergen. Fitting dan estimasi probabilitas dapat lebih lama. Probabilitas tertinggi tidak selalu menjadi kelas hasil predict().</Notice>}
        {algorithm === 'knn' && <Notice>KNN menggunakan K=5 dan bobot jarak, bukan class_weight balanced. Evaluasi dan prediksi dapat lebih lambat meskipun training cepat.</Notice>}
        <button className="primary-button" disabled={!!busy || !job.artifacts.preprocessed} onClick={() => void run('create')}>Buat eksperimen</button>
      </div>
    </Panel>
    <ExperimentPicker props={props} experiments={experiments} disabled={!!busy} />
    {selected && <>
      {replacement && <Notice tone="warning">
        Eksperimen SVM ini masih memakai batas lama 10.000 iterasi. Buat pengganti dengan rasio dan split yang sama, lalu jalankan split dan training. Eksperimen lama dan model aktif tetap dipertahankan.
        <button className="secondary-button" disabled={!!busy || !!selected.operation} onClick={() => void run('create', replacement)}>Buat ulang SVM tanpa batas iterasi</button>
      </Notice>}
      <div className="two-columns training-steps">
        <article className={`stage-card ${selected.status !== 'CREATED' ? 'complete' : ''}`}>
          <div className="stage-card-header"><span>01</span><GitFork size={21} /></div>
          <h2>Train / Test split</h2><p>Test diminta {percent(selected.test_ratio)}. Record dan group terisolasi. {selected.actual_test_ratio != null && `Test aktual ${percent(selected.actual_test_ratio)}.`}</p>
          <button className="secondary-button" disabled={!!busy || !!selected.operation || selected.status !== 'CREATED'} onClick={() => void run('split')}>Buat split manifest</button>
          {selected.status !== 'CREATED' && <DownloadLink jobId={job.job_id} experimentId={selected.experiment_id} artifact="split-manifest">Unduh manifest</DownloadLink>}
        </article>
        <article className={`stage-card ${selected.model_id ? 'complete' : ''}`}>
          <div className="stage-card-header"><span>02</span><BrainCircuit size={21} /></div>
          <h2>{algorithmNames[selected.algorithm]} training</h2><p>Test set tidak digunakan saat fit. Parameter tetap, tanpa pencarian otomatis.</p>
          <button className="primary-button" disabled={!!busy || !!selected.operation || selected.status !== 'SPLIT_READY'} onClick={() => void run('train')}>Latih {algorithmNames[selected.algorithm]}</button>
          {selected.model_id && <DownloadLink jobId={job.job_id} experimentId={selected.experiment_id} artifact="model">Model pipeline</DownloadLink>}
        </article>
      </div>
      <Panel title="Parameter algoritma"><KeyValues values={selected.parameters} /></Panel>
      {selected.algorithm === 'svm_linear' && selected.parameters.max_iter === -1 && <Notice>max_iter = -1 berarti tanpa batas iterasi solver. Model hanya disimpan jika konvergen; tunggu sampai training selesai, terutama untuk data besar.</Notice>}
    </>}
    {busy && <Loading label={`Menjalankan ${busy}… Tidak ada persentase progress dari backend.`} />}
    <Panel title="Daftar eksperimen" note="Model aktif hanya berubah setelah Anda memilihnya di Evaluation">
      <div className="table-scroll"><table className="data-table"><thead><tr><th>Eksperimen</th><th>Algoritma</th><th>Test aktual</th><th>Status</th><th>Fitting</th><th>Accuracy</th><th>Macro F1</th><th>Recall prioritas</th><th>Model</th></tr></thead><tbody>
        {experiments.data?.items.map(item => <tr key={item.experiment_id}>
          <td><button className="secondary-button" disabled={!!busy} onClick={() => props.selectExperiment?.(item.experiment_id)}>{item.experiment_id === 'legacy' ? 'Model sebelumnya' : item.experiment_id}</button></td>
          <td>{algorithmNames[item.algorithm]}</td><td>{item.actual_test_ratio == null ? 'Belum tersedia' : percent(item.actual_test_ratio)}</td><td>{item.status}{item.operation ? ` · ${item.operation} berjalan` : ''}{item.error ? ' · Gagal' : ''}</td>
          <td>{item.training_seconds == null ? 'Belum tersedia' : `${item.training_seconds.toFixed(3)} dtk`}</td>
          <td>{item.metrics ? percent(item.metrics.accuracy) : 'Belum tersedia'}</td><td>{item.metrics ? percent(item.metrics.macro_average.f1) : 'Belum tersedia'}</td><td>{item.metrics ? percent(item.metrics.highlighted_recall ?? item.metrics.positive_recall ?? 0) : 'Belum tersedia'}</td><td>{item.active ? 'Aktif untuk prediksi' : 'Tidak aktif'}</td>
        </tr>)}
      </tbody></table></div>
      <Notice>Bandingkan algoritma pada test set yang sama. {experiments.data && new Set(experiments.data.items.map(item => item.test_set_id).filter(Boolean)).size > 1 ? 'Daftar ini memakai test set berbeda: hasil tidak langsung sebanding.' : 'Eksperimen dengan rasio dan sumber sama berbagi split yang sama.'} Memilih hasil terbaik berulang kali pada test set bukan validasi independen.</Notice>
      <div className="panel-body"><button className="secondary-button" disabled={!!busy} onClick={() => {experiments.reload(); manifest.reload(); metadata.reload();}}>Baca ulang status</button></div>
    </Panel>
    {manifest.error && <Notice tone="error">{manifest.error}</Notice>}{metadata.error && <Notice tone="error">{metadata.error}</Notice>}
    {manifest.data && <Panel title="Ringkasan split"><KeyValues values={{train: object(manifest.data.train).row_count, test: object(manifest.data.test).row_count, strategy: object(manifest.data.selection).strategy, validation: manifest.data.validation}} /></Panel>}
    {metadata.data && <>
      <div className="stats-grid"><Stat label="Train" value={number(metadata.data.training_data.row_count)} /><Stat label="Fitur model" value={number(metadata.data.feature_contract.transformed_feature_count)} /><Stat label="Durasi fitting" value={`${number(metadata.data.verification.training_seconds).toFixed(3)} dtk`} note="Bukan total waktu request, penyimpanan, atau reload." /></div>
      <Panel title="Metadata model"><KeyValues values={{model_id: metadata.data.model_id, algorithm: metadata.data.algorithm, verification: metadata.data.verification}} /><div className="panel-body"><DownloadLink jobId={job.job_id} experimentId={selected?.experiment_id} artifact="model-metadata">Unduh metadata model</DownloadLink></div></Panel>
    </>}
  </>;
}
