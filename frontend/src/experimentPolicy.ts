import type {Experiment} from './types';

export function svmReplacementOptions(experiment: Experiment | null) {
  if (!experiment || experiment.algorithm !== 'svm_linear' || experiment.error?.stage !== 'train'
      || experiment.model_id || experiment.parameters.max_iter !== 10000) return null;
  return {test_ratio: experiment.test_ratio, algorithm: 'svm_linear' as const};
}
