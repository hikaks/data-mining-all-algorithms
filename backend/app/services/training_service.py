from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import platform
from threading import Lock
from time import perf_counter
from typing import Any

import joblib
import pandas as pd

from app.core.config import Settings
from app.core.exceptions import (
    ArtifactNotFoundError,
    InvalidDatasetError,
    InvalidJobStateError,
)
from app.core.job_status import JobStatus, parse_job_status
from app.schemas.training import ModelMetadata, TrainingResult
from app.services.preprocessing_pipeline import MODEL_FEATURES, TARGET_COLUMN
from app.services.training_pipeline import (
    POSITIVE_CLASS,
    TARGET_CLASSES,
    TRAINING_VERSION,
    build_model_pipeline,
    training_configuration,
    transformed_feature_manifest,
    validate_training_frame,
)
from app.storage.file_manager import read_json, write_joblib_atomic, write_json_atomic
from app.storage.job_manager import JobManager
from app.services.dataset_configuration import DatasetConfigurationService, CONFIGURATION_LOCK
from app.services.generic_pipeline import build_pipeline, coerce_frame, model_columns, contract
from app.utils.tabular import object_hash
from app.services.classifiers import PARAMETER_VERSION, NAMES, parameters_for


class TrainingService:
    def __init__(self, settings: Settings) -> None:
        self.jobs = JobManager(settings.storage_root)
        self.configuration = DatasetConfigurationService(settings)
        self._lock = CONFIGURATION_LOCK

    def train(self, job_id: str, algorithm: str = 'random_forest', experiment_id: str | None = None,
              parameter_version: int = PARAMETER_VERSION) -> TrainingResult:
        with self._lock:
            config = self.configuration.get(job_id)
            generic = config['profile'] == 'generic'
            columns = model_columns(config) if generic else list(MODEL_FEATURES)
            model_path = self.jobs.model_pipeline_path(job_id)
            metadata_path = self.jobs.model_metadata_path(job_id)
            if model_path.is_file() or metadata_path.is_file():
                if not model_path.is_file() or not metadata_path.is_file():
                    raise InvalidDatasetError(
                        "Artifact training tidak lengkap; model dan metadata harus tersedia bersama."
                    )
                metadata = read_json(metadata_path)
                self._verify_model_integrity(model_path, metadata)
                return self._result_from_metadata(metadata)

            job_metadata = self.jobs.read_metadata(job_id)
            current_status = parse_job_status(job_metadata.get("status"))
            if current_status != JobStatus.PREPROCESSED:
                raise InvalidJobStateError(
                    "Training hanya dapat dimulai saat status job PREPROCESSED."
                )

            source_path = self.jobs.preprocessed_dataset_path(job_id)
            manifest_path = self.jobs.report_path(job_id, "split_manifest.json")
            if not source_path.is_file():
                raise ArtifactNotFoundError("dataset_preprocessed.xlsx")
            if not manifest_path.is_file():
                raise ArtifactNotFoundError("split_manifest.json")

            manifest = read_json(manifest_path)
            dataframe = self._read_preprocessed(source_path, columns)
            if generic:
                dataframe = coerce_frame(dataframe, config)
            if not config.get('legacy') and manifest['configuration'].get('dataset_configuration_sha256') != object_hash(config):
                raise InvalidDatasetError('Checksum konfigurasi split berubah.')
            source_sha256 = self._sha256(source_path)
            manifest_sha256 = self._sha256(manifest_path)
            train, test = self._select_manifest_rows(
                job_id, dataframe, manifest, source_sha256
            )
            train_distribution = {str(k): int(v) for k, v in train[TARGET_COLUMN].value_counts().items()} if generic else validate_training_frame(train)
            if len(train_distribution) < 2 or any(count < 2 for count in train_distribution.values()):
                raise InvalidDatasetError('Setiap kelas membutuhkan dua record train.')

            parameters = parameters_for(algorithm, parameter_version)
            pipeline = build_pipeline(config, train, algorithm, parameter_version) if generic else build_model_pipeline()
            if not generic and algorithm != 'random_forest':
                from app.services.classifiers import StringClassifier
                from sklearn.pipeline import Pipeline
                from sklearn.preprocessing import StandardScaler
                pipeline.set_params(classifier=StringClassifier(algorithm, parameter_version))
                if algorithm in ('svm_linear', 'knn'):
                    preprocessor = pipeline.named_steps['preprocessor']
                    preprocessor.transformers = [
                        (name, Pipeline([('original', transformer), ('scaler', StandardScaler())]) if name == 'numeric' else transformer, selector)
                        for name, transformer, selector in preprocessor.transformers
                    ]
            started_at = perf_counter()
            try:
                pipeline.fit(
                    train.loc[:, columns],
                    train[TARGET_COLUMN].to_numpy(dtype=str) if generic else train[TARGET_COLUMN].astype(str),
                )
            except (TypeError, ValueError) as error:
                raise InvalidDatasetError(
                    f"Training {NAMES[algorithm]} gagal: {error}"
                ) from error
            training_seconds = round(perf_counter() - started_at, 6)

            fitted_classes = [
                str(value) for value in pipeline.named_steps["classifier"].classes_
            ]
            if set(fitted_classes) != (set(dataframe[TARGET_COLUMN].astype(str)) if generic else set(TARGET_CLASSES)):
                raise InvalidDatasetError(
                    "Model terlatih tidak memiliki dua kelas target yang diwajibkan."
                )

            feature_manifest = transformed_feature_manifest(pipeline)
            feature_manifest['input_columns'] = columns
            if generic:
                feature_manifest['selected_features'] = contract(config)
            created_at = self._now()
            configuration = training_configuration()
            if algorithm != 'random_forest':
                configuration['algorithm'] = NAMES[algorithm]
                configuration['parameters'] = parameters
            if experiment_id:
                configuration['experiment_id'] = experiment_id
                configuration['algorithm_id'] = algorithm
                configuration['parameter_version'] = parameter_version
            if not config.get('legacy'):
                configuration['dataset_configuration'] = config
                configuration['dataset_configuration_sha256'] = object_hash(config)
            model_id = self._model_id(
                job_id,
                source_sha256,
                manifest_sha256,
                configuration,
                manifest["train"]["record_ids"],
            )
            write_joblib_atomic(model_path, pipeline)
            reloaded = self._load_trusted_local_model(model_path)
            sample_size = min(5, len(train))
            sample_features = train.loc[:, columns].head(sample_size)
            original_predictions = pipeline.predict(sample_features).tolist()
            reloaded_predictions = reloaded.predict(sample_features).tolist()
            if original_predictions != reloaded_predictions:
                model_path.unlink(missing_ok=True)
                raise InvalidDatasetError(
                    "Verifikasi load ulang model menghasilkan prediksi berbeda."
                )

            model_sha256 = self._sha256(model_path)
            metadata: dict[str, Any] = {
                "job_id": job_id,
                "model_id": model_id,
                "created_at": created_at,
                "training_version": TRAINING_VERSION,
                "algorithm": configuration['algorithm'],
                "target": {
                    "column": config['target_column'],
                    "classes": fitted_classes,
                    "positive_class": None if generic else POSITIVE_CLASS,
                },
                "configuration": configuration,
                "feature_contract": feature_manifest,
                "training_data": {
                    "row_count": len(train),
                    "class_distribution": train_distribution,
                    "record_ids_sha256": self._list_sha256(
                        manifest["train"]["record_ids"]
                    ),
                    "test_row_count_reserved": len(test),
                    "test_record_ids_sha256": self._list_sha256(
                        manifest["test"]["record_ids"]
                    ),
                    "test_set_used_for_fit": False,
                },
                "artifacts": {
                    "model_pipeline": {
                        "path": "model/model_pipeline.joblib",
                        "sha256": model_sha256,
                        "size_bytes": model_path.stat().st_size,
                        "format": "joblib",
                        "trusted_local_artifact_only": True,
                    },
                    "preprocessed_dataset": {
                        "path": "preprocessed/dataset_preprocessed.xlsx",
                        "sha256": source_sha256,
                    },
                    "split_manifest": {
                        "path": "reports/split_manifest.json",
                        "sha256": manifest_sha256,
                        "split_version": manifest["split_version"],
                    },
                },
                "dependencies": self._dependency_versions(),
                "verification": {
                    "model_reload_passed": True,
                    "prediction_match_after_reload": True,
                    "prediction_sample_size": sample_size,
                    "training_seconds": training_seconds,
                    "split_validation_passed": True,
                    "source_hash_match": True,
                },
            }
            if algorithm == 'svm_linear':
                solver = pipeline.named_steps['classifier'].estimator_
                metadata['verification']['svm_solver'] = {
                    'converged': solver.fit_status_ == 0,
                    'fit_status': int(solver.fit_status_),
                    'iterations': solver.n_iter_.tolist(),
                    'max_iter': parameters['max_iter'],
                }
            if experiment_id:
                root = self.jobs.require_job_path(job_id)
                metadata['artifacts']['model_pipeline']['path'] = str(model_path.relative_to(root)).replace('\\', '/')
                metadata['artifacts']['split_manifest']['path'] = str(manifest_path.relative_to(root)).replace('\\', '/')
            write_json_atomic(metadata_path, metadata)
            self.jobs.update_metadata(
                job_id,
                {
                    "status": JobStatus.TRAINED.value,
                    "model_id": model_id,
                    "training_version": TRAINING_VERSION,
                    "trained_at": created_at,
                    "trained_rows": len(train),
                    "model_pipeline_sha256": model_sha256,
                    "training_seconds": training_seconds,
                },
            )
            return self._result_from_metadata(metadata)

    def metadata(self, job_id: str) -> ModelMetadata:
        model_path = self.jobs.model_pipeline_path(job_id)
        metadata_path = self.jobs.model_metadata_path(job_id)
        if not metadata_path.is_file():
            raise ArtifactNotFoundError("model_metadata.json")
        if not model_path.is_file():
            raise ArtifactNotFoundError("model_pipeline.joblib")
        metadata = read_json(metadata_path)
        self._verify_model_integrity(model_path, metadata)
        return ModelMetadata.model_validate(metadata)

    def model_path(self, job_id: str) -> Path:
        model_path = self.jobs.model_pipeline_path(job_id)
        metadata_path = self.jobs.model_metadata_path(job_id)
        if not model_path.is_file():
            raise ArtifactNotFoundError("model_pipeline.joblib")
        if not metadata_path.is_file():
            raise ArtifactNotFoundError("model_metadata.json")
        self._verify_model_integrity(model_path, read_json(metadata_path))
        return model_path

    @staticmethod
    def _read_preprocessed(path: Path, columns=None) -> pd.DataFrame:
        try:
            dataframe = pd.read_excel(
                path, sheet_name="DATA_PREPROCESSED", dtype=object, keep_default_na=False
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise InvalidDatasetError(
                "Dataset preprocessed tidak dapat dibaca untuk training."
            ) from error
        required = {"record_id", "near_duplicate_group_id", *(columns if columns is not None else MODEL_FEATURES), TARGET_COLUMN}
        missing = sorted(required.difference(dataframe.columns))
        if missing:
            raise InvalidDatasetError(
                "Dataset preprocessed tidak memenuhi kontrak training; kolom hilang: "
                + ", ".join(missing)
                + "."
            )
        if dataframe["record_id"].duplicated().any():
            raise InvalidDatasetError("record_id pada dataset training harus unik.")
        dataframe["record_id"] = dataframe["record_id"].astype(str)
        return dataframe

    @staticmethod
    def _select_manifest_rows(
        job_id: str,
        dataframe: pd.DataFrame,
        manifest: dict[str, Any],
        source_sha256: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if manifest.get("job_id") != job_id:
            raise InvalidDatasetError("Split manifest tidak berasal dari job yang sama.")
        if not manifest.get("validation", {}).get("passed"):
            raise InvalidDatasetError("Split manifest belum lolos validasi isolasi.")
        if manifest.get("source_artifact", {}).get("sha256") != source_sha256:
            raise InvalidDatasetError(
                "Hash dataset preprocessing berbeda dari split manifest."
            )

        train_ids = [str(value) for value in manifest.get("train", {}).get("record_ids", [])]
        test_ids = [str(value) for value in manifest.get("test", {}).get("record_ids", [])]
        if not train_ids or not test_ids:
            raise InvalidDatasetError("Split manifest tidak memiliki train/test record ID.")
        if len(train_ids) != len(set(train_ids)) or len(test_ids) != len(set(test_ids)):
            raise InvalidDatasetError("Split manifest memiliki record ID duplikat.")
        if set(train_ids).intersection(test_ids):
            raise InvalidDatasetError("Train dan test record ID saling tumpang tindih.")

        source_ids = set(dataframe["record_id"])
        assigned_ids = set(train_ids).union(test_ids)
        if assigned_ids != source_ids:
            raise InvalidDatasetError(
                "Coverage record ID split manifest tidak sama dengan dataset preprocessing."
            )
        indexed = dataframe.set_index("record_id", drop=False)
        train = indexed.loc[train_ids].reset_index(drop=True)
        test = indexed.loc[test_ids].reset_index(drop=True)
        if set(train['near_duplicate_group_id']).intersection(test['near_duplicate_group_id']):
            raise InvalidDatasetError('Group train dan test saling tumpang tindih.')
        classes = set(dataframe[TARGET_COLUMN].astype(str))
        for partition in (train, test):
            counts = partition[TARGET_COLUMN].astype(str).value_counts()
            if any(counts.get(label, 0) < 2 for label in classes):
                raise InvalidDatasetError('Setiap kelas membutuhkan minimal dua record train dan test.')
        if len(train) != manifest["train"].get("row_count") or len(test) != manifest[
            "test"
        ].get("row_count"):
            raise InvalidDatasetError("Jumlah baris split manifest tidak konsisten.")
        return train, test

    def _verify_model_integrity(
        self, model_path: Path, metadata: dict[str, Any]
    ) -> None:
        self.configuration.verify_snapshot(metadata['job_id'], metadata.get('configuration', {}))
        expected = (
            metadata.get("artifacts", {})
            .get("model_pipeline", {})
            .get("sha256")
        )
        if not expected or self._sha256(model_path) != expected:
            raise InvalidDatasetError("Checksum model pipeline tidak valid.")

    @staticmethod
    def _load_trusted_local_model(path: Path) -> Any:
        try:
            return joblib.load(path)
        except (OSError, ValueError, TypeError, EOFError) as error:
            raise InvalidDatasetError(
                "Model pipeline lokal tidak dapat dimuat ulang."
            ) from error

    @staticmethod
    def _dependency_versions() -> dict[str, str]:
        return {
            "python": platform.python_version(),
            "scikit-learn": version("scikit-learn"),
            "pandas": version("pandas"),
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "joblib": version("joblib"),
        }

    @staticmethod
    def _model_id(
        job_id: str,
        source_sha256: str,
        manifest_sha256: str,
        configuration: dict[str, Any],
        train_ids: list[str],
    ) -> str:
        payload = json.dumps(
            {
                "job_id": job_id,
                "source_sha256": source_sha256,
                "manifest_sha256": manifest_sha256,
                "configuration": configuration,
                "train_ids": train_ids,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        prefix = {'RandomForestClassifier': 'RF', 'DecisionTreeClassifier': 'DT', 'SVC': 'SVM', 'KNeighborsClassifier': 'KNN'}[configuration['algorithm']]
        return prefix + "-" + sha256(payload).hexdigest()[:16].upper()

    @staticmethod
    def _list_sha256(values: list[str]) -> str:
        encoded = json.dumps(values, separators=(",", ":")).encode("utf-8")
        return sha256(encoded).hexdigest()

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _result_from_metadata(metadata: dict[str, Any]) -> TrainingResult:
        return TrainingResult(
            job_id=metadata["job_id"],
            status=JobStatus.TRAINED.value,
            model_id=metadata["model_id"],
            algorithm=metadata["algorithm"],
            training_version=metadata["training_version"],
            trained_rows=metadata["training_data"]["row_count"],
            train_distribution=metadata["training_data"]["class_distribution"],
            classes=metadata["target"]["classes"],
            transformed_feature_count=metadata["feature_contract"][
                "transformed_feature_count"
            ],
            training_seconds=metadata["verification"]["training_seconds"],
            created_at=datetime.fromisoformat(metadata["created_at"]),
        )
