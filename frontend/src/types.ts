export type LabelValue = "SELESAI" | "TINDAK_LANJUT" | "NEEDS_REVIEW";
export type LabelFilter = "ALL" | "UNLABELED" | LabelValue;

export type PageId =
  | "dataset"
  | "understanding"
  | "cleaning"
  | "preprocessing"
  | "training"
  | "evaluation"
  | "prediction";
export type JsonMap = Record<string, unknown>;
export interface JobOverview {
  active_experiment_id?: string | null;
  experiment_count?: number;
  prediction_ready?: boolean;
  job_id: string;
  original_filename: string;
  status: string;
  created_at: string;
  sheet_name: string | null;
  raw_rows: number;
  raw_columns: number;
  cleaned_rows: number;
  labeled_rows: number;
  needs_review_rows: number;
  preprocessed_rows: number;
  split_train_rows: number;
  split_test_rows: number;
  model_id: string | null;
  input_label_source: string | null;
  input_label_counts: Record<string, number>;
  training_ready: boolean;
  file_format: 'xlsx' | 'csv';
  sheets: string[];
  configuration_ready: boolean;
  profile: 'generic' | 'maxkomp' | null;
  target_column: string | null;
  artifacts: Record<string, boolean>;
}
export interface WorkspaceProps {
  selectedExperiment?: string | null;
  selectExperiment?: (id: string) => void;
  job: JobOverview;
  refresh: () => Promise<void>;
  navigate: (page: PageId) => void;
}
export interface DatasetUploadResult {
  job_id: string;
  original_filename: string;
  status: string;
  row_count: number;
  column_count: number;
}
export type FeatureKind = 'numeric' | 'categorical' | 'text' | 'date';
export interface DatasetConfiguration {
  schema_version?: number;
  legacy?: boolean;
  profile: 'generic' | 'maxkomp';
  sheet_name: string | null;
  delimiter: ',' | ';' | '\t' | null;
  target_column: string;
  features: Array<{name: string; kind: FeatureKind}>;
}
export interface DatasetSchema {
  sheet_name: string | null;
  sheets: string[];
  delimiter: DatasetConfiguration['delimiter'];
  delimiter_ambiguous: boolean;
  maxkomp_available: boolean;
  locked: boolean;
  row_count: number;
  columns: Array<{name: string; dtype: FeatureKind; missing_count: number; unique_count: number}>;
  target_distribution: Array<{value: string; count: number}>;
  target_missing: number;
  warnings: string[];
  preview: JsonMap[];
}
export interface PredictionSchema {
  profile: 'generic' | 'maxkomp';
  target_column: string;
  classes: string[];
  features: DatasetConfiguration['features'];
}
export interface DatasetPreview {
  page: number;
  page_size: number;
  total_rows: number;
  total_pages: number;
  columns: string[];
  items: JsonMap[];
}
export interface DatasetSummary {
  row_count: number;
  column_count: number;
  duplicate_rows: number;
  operationally_empty_rows: number;
  date_range: JsonMap;
  distributions: Record<string, Array<{ value: string; count: number }>>;
  columns: Array<{
    name: string;
    dtype: string;
    missing_count: number;
    missing_percentage: number;
    unique_count: number;
  }>;
}
export interface CleaningReport {
  rows_before: number;
  rows_after: number;
  removed: Record<string, number>;
  normalization: Record<string, number | Record<string, string>>;
  missing_values: Record<string, number>;
  decisions: Record<string, string>;
  near_duplicate_evaluation: JsonMap;
}
export interface AuditPage {
  page: number;
  total_items: number;
  total_pages: number;
  items: JsonMap[];
}
export interface PreprocessingReport {
  preprocessing_version: string;
  source_rows: number;
  output_rows: number;
  excluded_rows: number;
  excluded_counts: Record<string, number>;
  target_distribution: Record<string, number>;
  feature_contract: JsonMap;
  leakage_audit: JsonMap;
  transformer_spec: JsonMap;
  near_duplicate_evaluation: {
    method: string;
    threshold: number;
    pair_count: number;
    group_count: number;
    automatic_removal: boolean;
    conflicting_label_groups: string[];
  };
}
export interface ModelMetadata {
  model_id: string;
  created_at: string;
  algorithm: string;
  configuration: JsonMap;
  feature_contract: JsonMap;
  training_data: JsonMap;
  verification: JsonMap;
  dependencies: Record<string, string>;
}
export interface EvaluationReport {
  model_id: string;
  evaluation_id: string;
  metrics: {
    accuracy: number;
    balanced_accuracy: number;
    positive_precision: number | null;
    positive_recall: number | null;
    positive_f1: number | null;
    highlighted_class?: string;
    highlighted_recall?: number;
    macro_average: {f1: number};
    weighted_average?: {f1: number};
    total_count: number;
    correct_count: number;
    per_class: Record<
      string,
      { precision: number; recall: number; f1: number; support: number }
    >;
  };
  confusion_matrix: { label_order: string[]; values: number[][] };
  feature_importance: {
    available?: boolean;
    top_features: Array<{ feature: string; importance: number }>;
    limitations: string[];
  };
  limitations: string[];
}
export interface PredictionInput {
  tanggal: string;
  customer: string;
  teknisi: string;
  text_laporan: string;
}
export interface PredictionResult {
  experiment_id?: string;
  prediction_id: string;
  model_id: string;
  created_at: string;
  prediction: string;
  confidence: number;
  probabilities: Record<string, number>;
  recommendation_only: boolean;
  warning: string;
  actual_decision: string | null;
}
export interface PredictionHistoryItem extends PredictionResult {
  input: Partial<PredictionInput> & {features?: JsonMap};
  actual_decision_reason: string | null;
  actual_decision_recorded_at: string | null;
}
export interface PredictionHistoryPage {
  page: number;
  total_items: number;
  total_pages: number;
  event_count: number;
  items: PredictionHistoryItem[];
}

export type AlgorithmId = 'random_forest' | 'decision_tree' | 'svm_linear' | 'knn';
export interface Experiment {
  experiment_id: string;
  created_at: string;
  algorithm: AlgorithmId;
  parameters: JsonMap;
  status: 'CREATED' | 'SPLIT_READY' | 'TRAINED' | 'EVALUATED';
  active: boolean;
  test_ratio: number;
  actual_test_ratio?: number;
  test_set_id?: string;
  model_id: string | null;
  training_seconds: number | null;
  operation: string | null;
  error: {stage: string; message: string} | null;
  metrics: EvaluationReport['metrics'] | null;
}
export interface ExperimentList {
  items: Experiment[];
  active_experiment_id: string | null;
}
