import { jobPath } from '../api';
import { Panel, Notice, Loading, percent, useResource } from './ui';
import type { AlgorithmId, ExperimentList, WorkspaceProps } from '../types';

export const algorithmNames: Record<AlgorithmId, string> = {
  random_forest: 'Random Forest', decision_tree: 'Decision Tree', svm_linear: 'SVM linear', knn: 'KNN',
};
export function useExperiments(props: WorkspaceProps) {
  const resource = useResource<ExperimentList>(jobPath(props.job.job_id, 'experiments'));
  const id = props.selectedExperiment ?? resource.data?.active_experiment_id ?? resource.data?.items[0]?.experiment_id ?? null;
  const selected = resource.data?.items.find(item => item.experiment_id === id) ?? null;
  return {...resource, id, selected};
}
export function ExperimentPicker({props, experiments, disabled = false}: {props: WorkspaceProps; experiments: ReturnType<typeof useExperiments>; disabled?: boolean}) {
  return <Panel title="Eksperimen yang ditampilkan" note="Tidak mengubah model aktif untuk prediksi">
    <div className="panel-body config-controls">
      {experiments.loading && <Loading label="Membaca daftar eksperimen…" />}
      {experiments.error && <Notice tone="error">{experiments.error}</Notice>}
      <label>Eksperimen
        <select aria-label="Eksperimen yang ditampilkan" value={experiments.id ?? ''} disabled={disabled || !experiments.data?.items.length}
          onChange={event => props.selectExperiment?.(event.target.value)}>
          {!experiments.data?.items.length && <option value="">Belum ada eksperimen</option>}
          {experiments.data?.items.map(item => <option key={item.experiment_id} value={item.experiment_id}>
            {item.experiment_id === 'legacy' ? 'Model sebelumnya' : item.experiment_id} · {algorithmNames[item.algorithm]} · Test {percent(item.test_ratio)} · {item.status}{item.active ? ' · Aktif' : ''}
          </option>)}
        </select>
      </label>
      {experiments.selected?.error && <Notice tone="error">{experiments.selected.error.stage}: {experiments.selected.error.message}</Notice>}
    </div>
  </Panel>;
}
