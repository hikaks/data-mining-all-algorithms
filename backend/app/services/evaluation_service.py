from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from threading import Lock
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

from app.core.config import Settings
from app.core.exceptions import (
    ArtifactNotFoundError,
    InvalidDatasetError,
    InvalidJobStateError,
)
from app.core.job_status import JobStatus, parse_job_status
from app.schemas.evaluation import (
    EvaluationReport,
    EvaluationResult,
    FeatureImportanceReport,
)
from app.services.preprocessing_pipeline import MODEL_FEATURES, TARGET_COLUMN
from app.services.training_pipeline import POSITIVE_CLASS, TARGET_CLASSES
from app.storage.file_manager import read_json, write_json_atomic
from app.storage.job_manager import JobManager
from app.services.dataset_configuration import DatasetConfigurationService, CONFIGURATION_LOCK
from app.services.generic_pipeline import coerce_frame


EVALUATION_VERSION = "fixed-test-evaluation-v1"
FEATURE_IMPORTANCE_METHOD = "mean_decrease_in_impurity"
FEATURE_IMPORTANCE_LIMITATIONS = [
    "Impurity-based importance dapat bias terhadap fitur berkardinalitas tinggi.",
    "Fitur teks atau kategori yang berkorelasi dapat membagi importance sehingga ranking individual mengecil.",
    "Feature importance bersifat deskriptif terhadap model dan bukan bukti hubungan kausal.",
]


class EvaluationService:
    def __init__(self, settings: Settings) -> None:
        self.jobs = JobManager(settings.storage_root)
        self.configuration = DatasetConfigurationService(settings)
        self._lock = CONFIGURATION_LOCK

    def evaluate(self, job_id: str) -> EvaluationResult:
        with self._lock:
            config = self.configuration.get(job_id)
            generic = config['profile'] == 'generic'
            evaluation_path = self._evaluation_path(job_id)
            importance_path = self._importance_path(job_id)
            if evaluation_path.is_file() or importance_path.is_file():
                if not evaluation_path.is_file() or not importance_path.is_file():
                    raise InvalidDatasetError(
                        "Artifact evaluation tidak lengkap; evaluation dan feature importance harus tersedia bersama."
                    )
                report = read_json(evaluation_path)
                self._verify_existing_report(job_id, report, importance_path)
                return self._result_from_report(report)

            job_metadata = self.jobs.read_metadata(job_id)
            current_status = parse_job_status(job_metadata.get("status"))
            if current_status != JobStatus.TRAINED:
                raise InvalidJobStateError(
                    "Evaluation hanya dapat dimulai saat status job TRAINED."
                )

            source_path = self.jobs.preprocessed_dataset_path(job_id)
            manifest_path = self.jobs.report_path(job_id, "split_manifest.json")
            model_path = self.jobs.model_pipeline_path(job_id)
            model_metadata_path = self.jobs.model_metadata_path(job_id)
            self._require_file(source_path, "dataset_preprocessed.xlsx")
            self._require_file(manifest_path, "split_manifest.json")
            self._require_file(model_path, "model_pipeline.joblib")
            self._require_file(model_metadata_path, "model_metadata.json")

            manifest = read_json(manifest_path)
            model_metadata = read_json(model_metadata_path)
            self.configuration.verify_snapshot(job_id, model_metadata['configuration'])
            classes = model_metadata['target']['classes']
            positive_class = model_metadata['target']['positive_class']
            columns = model_metadata['feature_contract']['input_columns']
            source_sha256 = self._sha256(source_path)
            manifest_sha256 = self._sha256(manifest_path)
            model_sha256 = self._sha256(model_path)
            model_metadata_sha256 = self._sha256(model_metadata_path)
            self._verify_traceability(
                job_id,
                manifest,
                model_metadata,
                source_sha256,
                manifest_sha256,
                model_sha256,
            )

            dataframe = self._read_preprocessed(source_path, columns)
            if generic:
                dataframe = coerce_frame(dataframe, config)
            test = self._select_test_rows(dataframe, manifest, classes)
            pipeline = self._load_trusted_local_model(model_path)
            features = test.loc[:, columns]
            actual = test[TARGET_COLUMN].astype(str)
            predicted = pd.Series(pipeline.predict(features), dtype=str)
            probabilities = np.asarray(pipeline.predict_proba(features), dtype=float)
            model_classes = [str(value) for value in pipeline.classes_.tolist()]
            if set(model_classes) != set(classes):
                raise InvalidDatasetError(
                    "Kelas pada model tidak sesuai dengan kontrak evaluation."
                )

            metrics = self._metrics(actual, predicted, classes, positive_class)
            matrix = confusion_matrix(
                actual, predicted, labels=classes
            ).tolist()
            report_dict = classification_report(
                actual,
                predicted,
                labels=classes,
                target_names=classes,
                output_dict=True,
                zero_division=0,
            )
            prediction_audit = self._prediction_audit(
                test, actual, predicted, probabilities, model_classes
            )
            created_at = self._now()
            evaluation_id = self._evaluation_id(
                job_id,
                model_metadata["model_id"],
                manifest_sha256,
                manifest["test"]["record_ids"],
            )
            importance = self._feature_importance(
                job_id,
                evaluation_id,
                model_metadata["model_id"],
                created_at,
                pipeline,
            )
            write_json_atomic(importance_path, importance)
            importance_sha256 = self._sha256(importance_path)

            evaluation: dict[str, Any] = {
                "job_id": job_id,
                "evaluation_id": evaluation_id,
                "model_id": model_metadata["model_id"],
                "created_at": created_at,
                "evaluation_version": EVALUATION_VERSION,
                "evaluation_scope": {
                    "dataset_partition": "TEST_ONLY",
                    "row_count": len(test),
                    "record_ids_sha256": self._list_sha256(
                        manifest["test"]["record_ids"]
                    ),
                    "actual_distribution": self._distribution(actual, classes),
                    "predicted_distribution": self._distribution(predicted, classes),
                    "positive_class": positive_class,
                    "labels": classes,
                    "test_set_used_for_parameter_selection": False,
                },
                "traceability": {
                    "model_pipeline_sha256": model_sha256,
                    "model_metadata_sha256": model_metadata_sha256,
                    "split_manifest_sha256": manifest_sha256,
                    "preprocessed_dataset_sha256": source_sha256,
                    "split_version": manifest["split_version"],
                    "training_version": model_metadata["training_version"],
                    "scikit_learn_version": version("scikit-learn"),
                    "feature_importance_sha256": importance_sha256,
                },
                "metrics": metrics,
                "confusion_matrix": {
                    "label_order": classes,
                    "rows": "actual",
                    "columns": "predicted",
                    "values": matrix,
                },
                "classification_report": self._json_ready(report_dict),
                "prediction_audit": prediction_audit,
                "feature_importance": {
                    "method": importance['method'],
                    "available": importance.get('available', True),
                    "feature_count": importance["feature_count"],
                    "top_features": importance["features"][:20],
                    "artifact_path": str(importance_path.relative_to(self.jobs.require_job_path(job_id))).replace('\\', '/'),
                    "artifact_sha256": importance_sha256,
                    "limitations": importance['limitations'],
                },
                "limitations": [
                    "Target historical berasal dari kebijakan AI-assisted labeling dan bukan ground-truth manusia independen.",
                    f"Test set memiliki {int((actual == POSITIVE_CLASS).sum())} record TINDAK_LANJUT; perhatikan ukuran support saat menafsirkan metrik.",
                    "Hasil satu fixed holdout tidak menggantikan validasi pada data operasional baru.",
                ],
            }
            if generic:
                evaluation['limitations'] = ['Target berasal dari kolom dataset yang dipilih; kualitas ground truth belum diverifikasi.', 'Jumlah test per kelas terbatas; perhatikan recall terendah.', 'Satu fixed holdout tidak menggantikan validasi data baru.']
            if not config.get('legacy'):
                evaluation['traceability']['dataset_configuration_sha256'] = model_metadata['configuration']['dataset_configuration_sha256']
            write_json_atomic(evaluation_path, evaluation)
            evaluation_sha256 = self._sha256(evaluation_path)
            self.jobs.update_metadata(
                job_id,
                {
                    "status": JobStatus.EVALUATED.value,
                    "evaluation_id": evaluation_id,
                    "evaluation_version": EVALUATION_VERSION,
                    "evaluated_at": created_at,
                    "evaluated_rows": len(test),
                    "evaluation_accuracy": metrics["accuracy"],
                    "evaluation_balanced_accuracy": metrics["balanced_accuracy"],
                    "evaluation_sha256": evaluation_sha256,
                    "feature_importance_sha256": importance_sha256,
                },
            )
            return self._result_from_report(evaluation)

    def report(self, job_id: str) -> EvaluationReport:
        path = self._evaluation_path(job_id)
        importance_path = self._importance_path(job_id)
        if not path.is_file():
            raise ArtifactNotFoundError("evaluation.json")
        if not importance_path.is_file():
            raise ArtifactNotFoundError("feature_importance.json")
        report = read_json(path)
        self._verify_existing_report(job_id, report, importance_path)
        return EvaluationReport.model_validate(report)

    def feature_importance(self, job_id: str) -> FeatureImportanceReport:
        path = self._importance_path(job_id)
        evaluation_path = self._evaluation_path(job_id)
        if not path.is_file():
            raise ArtifactNotFoundError("feature_importance.json")
        if not evaluation_path.is_file():
            raise ArtifactNotFoundError("evaluation.json")
        self._verify_existing_report(job_id, read_json(evaluation_path), path)
        return FeatureImportanceReport.model_validate(read_json(path))

    def evaluation_path(self, job_id: str) -> Path:
        path = self._evaluation_path(job_id)
        importance_path = self._importance_path(job_id)
        if not path.is_file():
            raise ArtifactNotFoundError("evaluation.json")
        if not importance_path.is_file():
            raise ArtifactNotFoundError("feature_importance.json")
        self._verify_existing_report(job_id, read_json(path), importance_path)
        return path

    def feature_importance_path(self, job_id: str) -> Path:
        path = self._importance_path(job_id)
        evaluation_path = self._evaluation_path(job_id)
        if not path.is_file():
            raise ArtifactNotFoundError("feature_importance.json")
        if not evaluation_path.is_file():
            raise ArtifactNotFoundError("evaluation.json")
        self._verify_existing_report(job_id, read_json(evaluation_path), path)
        return path

    def _verify_existing_report(
        self, job_id: str, report: dict[str, Any], importance_path: Path
    ) -> None:
        metadata_path = self.jobs.model_metadata_path(job_id)
        if metadata_path.is_file():
            self.configuration.verify_snapshot(job_id, read_json(metadata_path).get('configuration', {}))
        if report.get("job_id") != job_id:
            raise InvalidDatasetError("Evaluation report tidak berasal dari job yang sama.")
        traceability = report.get("traceability", {})
        checks = (
            (self.jobs.model_pipeline_path(job_id), "model_pipeline_sha256"),
            (self.jobs.model_metadata_path(job_id), "model_metadata_sha256"),
            (self.jobs.report_path(job_id, "split_manifest.json"), "split_manifest_sha256"),
            (self.jobs.preprocessed_dataset_path(job_id), "preprocessed_dataset_sha256"),
            (importance_path, "feature_importance_sha256"),
        )
        for path, key in checks:
            if not path.is_file() or self._sha256(path) != traceability.get(key):
                raise InvalidDatasetError(
                    f"Traceability artifact evaluation tidak valid: {key}."
                )

    @staticmethod
    def _verify_traceability(
        job_id: str,
        manifest: dict[str, Any],
        model_metadata: dict[str, Any],
        source_sha256: str,
        manifest_sha256: str,
        model_sha256: str,
    ) -> None:
        if manifest.get("job_id") != job_id or model_metadata.get("job_id") != job_id:
            raise InvalidDatasetError("Artifact evaluation tidak berasal dari job yang sama.")
        if not manifest.get("validation", {}).get("passed"):
            raise InvalidDatasetError("Split manifest belum lolos validasi.")
        if manifest.get("source_artifact", {}).get("sha256") != source_sha256:
            raise InvalidDatasetError("Checksum dataset preprocessing tidak valid.")
        artifacts = model_metadata.get("artifacts", {})
        if artifacts.get("model_pipeline", {}).get("sha256") != model_sha256:
            raise InvalidDatasetError("Checksum model pipeline tidak valid.")
        if artifacts.get("split_manifest", {}).get("sha256") != manifest_sha256:
            raise InvalidDatasetError("Checksum split manifest tidak valid.")
        generic = model_metadata.get('configuration', {}).get('dataset_configuration', {}).get('profile') == 'generic'
        if not generic and model_metadata.get("target", {}).get("positive_class") != POSITIVE_CLASS:
            raise InvalidDatasetError("Positive class metadata model tidak valid.")
        trained_version = model_metadata.get("dependencies", {}).get("scikit-learn")
        if trained_version != version("scikit-learn"):
            raise InvalidDatasetError(
                "Versi scikit-learn evaluation berbeda dari versi saat training."
            )

    @staticmethod
    def _read_preprocessed(path: Path, columns=None) -> pd.DataFrame:
        try:
            dataframe = pd.read_excel(
                path, sheet_name="DATA_PREPROCESSED", dtype=object, keep_default_na=False
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise InvalidDatasetError(
                "Dataset preprocessed tidak dapat dibaca untuk evaluation."
            ) from error
        required = {"record_id", *(columns if columns is not None else MODEL_FEATURES), TARGET_COLUMN}
        missing = sorted(required.difference(dataframe.columns))
        if missing:
            raise InvalidDatasetError(
                "Dataset evaluation kehilangan kolom: " + ", ".join(missing)
            )
        if dataframe["record_id"].duplicated().any():
            raise InvalidDatasetError("record_id dataset evaluation harus unik.")
        dataframe["record_id"] = dataframe["record_id"].astype(str)
        return dataframe

    @staticmethod
    def _select_test_rows(
        dataframe: pd.DataFrame, manifest: dict[str, Any], classes=TARGET_CLASSES
    ) -> pd.DataFrame:
        test_ids = [str(value) for value in manifest.get("test", {}).get("record_ids", [])]
        if not test_ids or len(test_ids) != len(set(test_ids)):
            raise InvalidDatasetError("Test record ID pada split manifest tidak valid.")
        indexed = dataframe.set_index("record_id", drop=False)
        missing = sorted(set(test_ids).difference(indexed.index))
        if missing:
            raise InvalidDatasetError("Test record ID tidak ditemukan pada dataset.")
        test = indexed.loc[test_ids].reset_index(drop=True)
        if len(test) != manifest.get("test", {}).get("row_count"):
            raise InvalidDatasetError("Jumlah test row berbeda dari split manifest.")
        observed = set(test[TARGET_COLUMN].astype(str).unique())
        if observed != set(classes):
            raise InvalidDatasetError("Test set harus memiliki kedua kelas target.")
        return test

    @staticmethod
    def _load_trusted_local_model(path: Path) -> Any:
        try:
            return joblib.load(path)
        except (OSError, ValueError, TypeError, EOFError, ImportError) as error:
            raise InvalidDatasetError("Model lokal tidak dapat dimuat.") from error

    @staticmethod
    def _metrics(actual: pd.Series, predicted: pd.Series, classes=TARGET_CLASSES, positive_class=POSITIVE_CLASS) -> dict[str, Any]:
        precision, recall, f1, support = precision_recall_fscore_support(
            actual,
            predicted,
            labels=list(classes),
            zero_division=0,
        )
        per_class = {
            label: {
                "precision": round(float(precision[index]), 8),
                "recall": round(float(recall[index]), 8),
                "f1": round(float(f1[index]), 8),
                "support": int(support[index]),
            }
            for index, label in enumerate(classes)
        }
        highlighted = positive_class or min(per_class, key=lambda label: per_class[label]['recall'])
        positive = per_class.get(positive_class, {})
        return {
            "accuracy": round(float(accuracy_score(actual, predicted)), 8),
            "balanced_accuracy": round(
                float(balanced_accuracy_score(actual, predicted)), 8
            ),
            "positive_class": positive_class,
            "positive_precision": positive.get('precision'),
            "positive_recall": positive.get('recall'),
            "positive_f1": positive.get('f1'),
            "highlighted_class": highlighted,
            "highlighted_recall": per_class[highlighted]['recall'],
            "weighted_average": {key: round(float(np.average(values, weights=support)), 8) for key, values in [('precision', precision), ('recall', recall), ('f1', f1)]},
            "per_class": per_class,
            "macro_average": {
                "precision": round(float(np.mean(precision)), 8),
                "recall": round(float(np.mean(recall)), 8),
                "f1": round(float(np.mean(f1)), 8),
            },
            "correct_count": int((actual.reset_index(drop=True) == predicted).sum()),
            "total_count": len(actual),
        }

    @staticmethod
    def _prediction_audit(
        test: pd.DataFrame,
        actual: pd.Series,
        predicted: pd.Series,
        probabilities: np.ndarray,
        model_classes: list[str],
    ) -> list[dict[str, Any]]:
        audit: list[dict[str, Any]] = []
        actual_values = actual.tolist()
        predicted_values = predicted.tolist()
        for index, record_id in enumerate(test["record_id"].astype(str)):
            probability_map = {
                label: round(float(probabilities[index][class_index]), 8)
                for class_index, label in enumerate(model_classes)
            }
            audit.append(
                {
                    "record_id": record_id,
                    "actual": actual_values[index],
                    "predicted": predicted_values[index],
                    "correct": actual_values[index] == predicted_values[index],
                    "probabilities": probability_map,
                }
            )
        return audit

    @staticmethod
    def _feature_importance(
        job_id: str,
        evaluation_id: str,
        model_id: str,
        created_at: str,
        pipeline: Any,
    ) -> dict[str, Any]:
        try:
            names = pipeline.named_steps["preprocessor"].get_feature_names_out()
            classifier = pipeline.named_steps["classifier"]
            if not hasattr(classifier, 'feature_importances_'):
                return {'job_id': job_id, 'evaluation_id': evaluation_id, 'model_id': model_id,
                        'created_at': created_at, 'method': 'not_available', 'available': False,
                        'feature_count': len(names), 'features': [],
                        'limitations': ['Tidak tersedia untuk algoritma ini.']}
            importances = np.asarray(classifier.feature_importances_, dtype=float)
            deviations = np.std(
                [tree.feature_importances_ for tree in classifier.estimators_], axis=0
            ) if hasattr(classifier, 'estimators_') else [None] * len(importances)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise InvalidDatasetError(
                "Feature importance tidak dapat ditelusuri dari pipeline."
            ) from error
        if len(names) != len(importances):
            raise InvalidDatasetError("Nama fitur dan nilai importance tidak konsisten.")
        features = [
            {
                "feature": str(name),
                "importance": round(float(importance), 12),
                "tree_std": round(float(deviation), 12) if deviation is not None else None,
            }
            for name, importance, deviation in zip(
                names, importances, deviations, strict=True
            )
        ]
        features.sort(key=lambda item: (-item["importance"], item["feature"]))
        for rank, item in enumerate(features, start=1):
            item["rank"] = rank
        return {
            "job_id": job_id,
            "evaluation_id": evaluation_id,
            "model_id": model_id,
            "created_at": created_at,
            "method": FEATURE_IMPORTANCE_METHOD,
            "feature_count": len(features),
            "features": features,
            "limitations": FEATURE_IMPORTANCE_LIMITATIONS,
        }

    @staticmethod
    def _distribution(values: pd.Series, classes=TARGET_CLASSES) -> dict[str, int]:
        counts = values.value_counts().to_dict()
        return {label: int(counts.get(label, 0)) for label in classes}

    @staticmethod
    def _json_ready(value: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(value))

    @staticmethod
    def _evaluation_id(
        job_id: str, model_id: str, manifest_sha256: str, test_ids: list[str]
    ) -> str:
        payload = json.dumps(
            {
                "job_id": job_id,
                "model_id": model_id,
                "manifest_sha256": manifest_sha256,
                "test_ids": test_ids,
                "evaluation_version": EVALUATION_VERSION,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "EVAL-" + sha256(payload).hexdigest()[:16].upper()

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
    def _require_file(path: Path, name: str) -> None:
        if not path.is_file():
            raise ArtifactNotFoundError(name)

    def _evaluation_path(self, job_id: str) -> Path:
        return self.jobs.report_path(job_id, "evaluation.json")

    def _importance_path(self, job_id: str) -> Path:
        return self.jobs.report_path(job_id, "feature_importance.json")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _result_from_report(report: dict[str, Any]) -> EvaluationResult:
        metrics = report["metrics"]
        scope = report["evaluation_scope"]
        return EvaluationResult(
            job_id=report["job_id"],
            status=JobStatus.EVALUATED.value,
            evaluation_id=report["evaluation_id"],
            model_id=report["model_id"],
            evaluation_version=report["evaluation_version"],
            evaluated_rows=scope["row_count"],
            actual_distribution=scope["actual_distribution"],
            predicted_distribution=scope["predicted_distribution"],
            accuracy=metrics["accuracy"],
            balanced_accuracy=metrics["balanced_accuracy"],
            positive_class=metrics["positive_class"],
            positive_precision=metrics["positive_precision"],
            positive_recall=metrics["positive_recall"],
            positive_f1=metrics["positive_f1"],
            created_at=datetime.fromisoformat(report["created_at"]),
        )
