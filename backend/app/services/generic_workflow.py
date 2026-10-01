from datetime import datetime, timezone
from collections import defaultdict

import pandas as pd

from app.core.exceptions import InvalidDatasetError, InvalidJobStateError
from app.schemas.cleaning import CleaningResult
from app.services.dataset_configuration import DatasetConfigurationService
from app.services.generic_pipeline import contract, fingerprint, prepare_features, model_columns
from app.services.preprocessing_pipeline import class_ratio
from app.services.preprocessing_service import PreprocessingService
from app.storage.file_manager import read_json, write_json_atomic, write_excel_atomic
from app.storage.job_manager import JobManager
from app.utils.tabular import read_input, label_value, missing, content_hash, object_hash


class GenericWorkflowService:
    def __init__(self, settings):
        self.jobs = JobManager(settings.storage_root)
        self.configuration = DatasetConfigurationService(settings)

    def clean(self, job_id):
        config = self.configuration.get(job_id)
        metadata = self.jobs.read_metadata(job_id)
        path = self.jobs.report_path(job_id, 'cleaning_report.json')
        if path.is_file():
            report = read_json(path)
            cleaned_path = self.jobs.cleaned_dataset_path(job_id)
            if not cleaned_path.is_file() or report.get('artifact_integrity', {}).get('output_cleaned_sha256') != content_hash(cleaned_path):
                raise InvalidDatasetError('Artifact/checksum cleaning tidak lengkap atau berubah.')
            if report.get('dataset_configuration_sha256') != object_hash(config):
                raise InvalidDatasetError('Checksum konfigurasi cleaning berubah.')
            return self.clean_result(report)
        if metadata['status'] != 'ANALYZED':
            raise InvalidJobStateError('Cleaning memerlukan konfigurasi tersimpan dan status ANALYZED.')
        raw = read_input(self.jobs.raw_dataset_path(job_id), config['sheet_name'], config['delimiter'])
        reserved = {'record_id', 'near_duplicate_group_id', 'keputusan_laporan'}
        mapping, occupied = {}, set(raw.columns)
        for name in raw.columns:
            replacement = name
            if name in reserved:
                replacement = 'source__' + name
                while replacement in occupied:
                    replacement = 'source__' + replacement
                occupied.add(replacement)
            mapping[name] = replacement
        output, duplicates, empty, operations = [], [], [], []
        seen = {}
        for index, row in raw.iterrows():
            record_id = 'REC-' + fingerprint([job_id, int(index) + 2])[:20].upper()
            if all(missing(value) for value in row):
                empty.append({'record_id': record_id, 'source_row': int(index) + 2})
                continue
            _, values = prepare_features(row, config, f'baris {int(index) + 2}')
            target = label_value(row[config['target_column']])
            key = fingerprint([values, target])
            if key in seen:
                duplicates.append({'record_id': record_id, 'duplicate_of': seen[key], 'source_row': int(index) + 2})
                continue
            seen[key] = record_id
            normalized = {mapping[name]: (None if missing(value) else value) for name, value in row.items()}
            for name, value in values.items():
                normalized[mapping[name]] = value
                before = None if missing(row[name]) else str(row[name])
                if before != (None if value is None else str(value)):
                    operations.append({'record_id': record_id, 'column': name, 'before': before, 'after': value, 'operation': 'TYPE_AND_WHITESPACE_NORMALIZATION'})
            normalized[mapping[config['target_column']]] = target
            normalized['record_id'] = record_id
            output.append(normalized)
        if not output:
            raise InvalidDatasetError('Tidak ada baris tersisa setelah cleaning.')
        cleaned = pd.DataFrame(output)
        generated = datetime.now(timezone.utc).isoformat()
        report = {
            'job_id': job_id, 'generated_at': generated, 'rows_before': len(raw), 'rows_after': len(cleaned),
            'removed': {'empty_rows': len(empty), 'duplicates': len(duplicates)},
            'normalization': {'operation_count': len(operations), 'source_column_map': mapping},
            'missing_values': {name: int(cleaned[name].isna().sum()) for name in cleaned.columns},
            'invalid_dates': [], 'incomplete_records': [], 'duplicate_records': duplicates,
            'operations': operations, 'removed_empty_records': empty, 'potential_duplicates': [],
            'near_duplicate_evaluation': {'method': 'EXACT_SELECTED_FEATURES', 'automatic_removal': False},
            'decisions': {'duplicates': 'Hapus fitur-plus-target identik; konflik target dipertahankan.', 'raw': 'Raw tidak diubah.'},
            'dataset_configuration_sha256': object_hash(config),
        }
        write_excel_atomic(self.jobs.cleaned_dataset_path(job_id), cleaned, 'DATA_CLEANED', literal_strings=True)
        report['artifact_integrity'] = {'output_cleaned_sha256': content_hash(self.jobs.cleaned_dataset_path(job_id))}
        write_json_atomic(path, report)
        self.jobs.update_metadata(job_id, {'status': 'CLEANED', 'cleaned_rows': len(cleaned), 'cleaned_at': generated, 'configuration_locked': True})
        return self.clean_result(report)

    @staticmethod
    def clean_result(report):
        return CleaningResult(job_id=report['job_id'], status='CLEANED', rows_before=report['rows_before'], rows_after=report['rows_after'], empty_rows_removed=report['removed']['empty_rows'], duplicates_removed=report['removed']['duplicates'], invalid_dates=0, incomplete_rows=0, cleaned_at=report['generated_at'])

    def preprocess(self, job_id):
        config = self.configuration.get(job_id)
        path = self.jobs.report_path(job_id, 'preprocessing_report.json')
        if path.is_file():
            report = read_json(path)
            output_path = self.jobs.preprocessed_dataset_path(job_id)
            if not output_path.is_file() or report['artifact_integrity'].get('output_preprocessed_sha256') != content_hash(output_path):
                raise InvalidDatasetError('Artifact/checksum preprocessing tidak lengkap atau berubah.')
            if report['artifact_integrity'].get('dataset_configuration_sha256') != object_hash(config):
                raise InvalidDatasetError('Checksum konfigurasi preprocessing berubah.')
            return PreprocessingService._result_from_report(report)
        if self.jobs.read_metadata(job_id)['status'] != 'CLEANED':
            raise InvalidJobStateError('Preprocessing hanya dimulai setelah cleaning.')
        source = self.jobs.cleaned_dataset_path(job_id)
        frame = pd.read_excel(source, sheet_name='DATA_CLEANED', dtype=object, keep_default_na=False)
        cleaning = read_json(self.jobs.report_path(job_id, 'cleaning_report.json'))
        if cleaning.get('artifact_integrity', {}).get('output_cleaned_sha256') != content_hash(source):
            raise InvalidDatasetError('Checksum dataset cleaning tidak valid.')
        if cleaning.get('dataset_configuration_sha256') != object_hash(config):
            raise InvalidDatasetError('Checksum konfigurasi cleaning berubah.')
        mapping = cleaning['normalization']['source_column_map']
        rows, excluded, groups = [], [], defaultdict(list)
        for _, row in frame.iterrows():
            target = label_value(row[mapping[config['target_column']]])
            if target is None:
                excluded.append({'record_id': row['record_id'], 'reason': 'EMPTY_TARGET'})
                continue
            features, normalized = prepare_features({name: row[column] for name, column in mapping.items()}, config, f"record {row['record_id']}")
            # Group the stateless model representation, including calendar aliases.
            # Missing values are canonical nulls, never non-standard JSON NaNs.
            group = 'GROUP-' + fingerprint({key: None if missing(value) else value for key, value in features.items()})[:24]
            rows.append({'record_id': row['record_id'], 'near_duplicate_group_id': group, **features, 'keputusan_laporan': target})
            groups[group].append({'record_id': row['record_id'], 'target': target})
        prepared = pd.DataFrame(rows)
        if prepared.empty or prepared['keputusan_laporan'].nunique() < 2:
            raise InvalidDatasetError('Minimal dua kelas diperlukan setelah target kosong dikecualikan.')
        counts = {str(k): int(v) for k, v in prepared['keputusan_laporan'].value_counts().items()}
        conflicts = [{'group_id': key, 'records': items} for key, items in groups.items() if len({item['target'] for item in items}) > 1]
        grouped = [{'group_id': key, 'record_ids': [item['record_id'] for item in items]} for key, items in groups.items() if len(items) > 1]
        generated = datetime.now(timezone.utc).isoformat()
        output = self.jobs.preprocessed_dataset_path(job_id)
        write_excel_atomic(output, prepared, 'DATA_PREPROCESSED', literal_strings=True)
        report = {
            'job_id': job_id, 'generated_at': generated, 'preprocessing_version': 'generic-feature-contract-v1',
            'source_rows': len(frame), 'output_rows': len(prepared), 'excluded_rows': len(excluded),
            'excluded_counts': {'EMPTY_TARGET': len(excluded)} if excluded else {}, 'excluded_records': excluded,
            'target_distribution': counts, 'class_imbalance_ratio': class_ratio(counts),
            'feature_contract': {'identifier_columns': ['record_id', 'near_duplicate_group_id'], 'model_feature_columns': model_columns(config), 'target_column': config['target_column'], 'internal_target_column': 'keputusan_laporan', 'selected_features': contract(config), **{kind + '_features': [column for feature in contract(config) if feature['kind'] == kind for column in feature['columns']] for kind in ('numeric', 'categorical', 'text', 'date')}},
            'leakage_audit': {'passed': True, 'target_excluded_from_features': True, 'near_duplicate_group_excluded_from_features': True, 'weak_supervision_warning': None},
            'transformer_spec': {'fit_scope': 'TRAIN_ONLY', 'numeric': {'imputation': 'median'}, 'categorical': {'missing': '__MISSING_CATEGORY__', 'handle_unknown': 'ignore'}, 'text': {'method': 'TF-IDF per column'}, 'date': {'method': 'year/month/weekday, median from train'}},
            'near_duplicate_evaluation': {'method': 'EXACT_SELECTED_FEATURE_FINGERPRINT', 'threshold': 1.0, 'automatic_removal': False, 'pair_count': sum(len(items)*(len(items)-1)//2 for items in groups.values()), 'group_count': len(grouped), 'groups': grouped, 'sample_pairs': [], 'sample_pairs_truncated': False, 'conflicting_label_groups': conflicts},
            'artifact_integrity': {'input_cleaned_sha256': content_hash(source), 'output_preprocessed_sha256': content_hash(output), 'dataset_configuration_sha256': object_hash(config)},
        }
        write_json_atomic(path, report)
        self.jobs.update_metadata(job_id, {'status': 'PREPROCESSED', 'preprocessed_rows': len(prepared), 'preprocessing_excluded_rows': len(excluded), 'preprocessing_version': report['preprocessing_version'], 'preprocessing_completed_at': generated, 'near_duplicate_groups': len(grouped)})
        return PreprocessingService._result_from_report(report)
