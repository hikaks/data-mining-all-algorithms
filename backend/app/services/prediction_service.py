from datetime import datetime, timezone
from importlib.metadata import version
import math
from pathlib import Path
import re
import secrets
from threading import Lock
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.core.config import Settings
from app.core.exceptions import (
    ArtifactNotFoundError,
    InvalidDatasetError,
    InvalidJobStateError,
    PredictionNotFoundError,
)
from app.core.job_status import JOB_STATUS_ORDER, JobStatus, parse_job_status
from app.schemas.prediction import (
    ActualDecisionRequest,
    PredictionHistoryItem,
    PredictionHistoryPage,
    PredictionRequest,
    PredictionResult,
    GenericPredictionRequest,
)
from app.services.preprocessing_pipeline import (
    MODEL_FEATURES,
    normalize_report_text,
    technician_count,
)
from app.services.training_pipeline import TARGET_CLASSES
from app.storage.file_manager import (
    append_json_line,
    read_json,
    read_json_lines,
)
from app.storage.job_manager import JobManager
from app.services.dataset_configuration import DatasetConfigurationService, CONFIGURATION_LOCK
from app.services.generic_pipeline import prepare_features, model_columns
from app.storage.experiments import artifact_jobs, active_id, metadata_for_model


PREDICTION_VERSION = "model-pipeline-inference-v1"
PREDICTION_ID_PATTERN = re.compile(r"^PRED-[A-F0-9]{16}$")
EVENT_ID_PATTERN = re.compile(r"^EVENT-[A-F0-9]{16}$")
ADMIN_VALIDATOR_ROLE = "ADMIN_VALIDATOR"


class PredictionService:
    def __init__(self, settings: Settings) -> None:
        self.jobs = JobManager(settings.storage_root)
        self.storage_root = settings.storage_root
        self.settings = settings
        self.configuration = DatasetConfigurationService(settings)
        self._lock = CONFIGURATION_LOCK

    def schema(self, job_id):
        self._require_evaluated_job(job_id)
        _, metadata, _, _ = self._load_verified_model(job_id)
        config = metadata.get('configuration', {}).get('dataset_configuration')
        if config and config['profile'] == 'generic':
            return {'profile': 'generic', 'target_column': config['target_column'], 'classes': metadata['target']['classes'], 'features': config['features']}
        return {'profile': 'maxkomp', 'target_column': metadata['target']['column'], 'classes': metadata['target']['classes'], 'features': [{'name': 'tanggal', 'kind': 'date'}, {'name': 'customer', 'kind': 'categorical'}, {'name': 'teknisi', 'kind': 'categorical'}, {'name': 'text_laporan', 'kind': 'text'}]}

    def predict(self, job_id: str, request: PredictionRequest | GenericPredictionRequest) -> PredictionResult:
        with self._lock:
            self._require_evaluated_job(job_id)
            events = self._read_events(job_id)
            states = self._reconstruct(job_id, events)
            model, metadata, model_sha256, evaluation = self._load_verified_model(
                job_id
            )
            config = metadata.get('configuration', {}).get('dataset_configuration', {})
            if config.get('profile') == 'generic':
                if not isinstance(request, GenericPredictionRequest):
                    raise InvalidDatasetError('Profil Umum memerlukan payload features.')
                expected = {feature['name'] for feature in config['features']}
                if set(request.features) != expected:
                    raise InvalidDatasetError('Input features harus tepat sesuai fitur model; target/kolom tambahan ditolak.')
                values, normalized = prepare_features(request.features, config)
                frame = pd.DataFrame([values], columns=model_columns(config))
                normalized_input = {'features': normalized}
            else:
                if not isinstance(request, PredictionRequest):
                    raise InvalidDatasetError('Preset PT memerlukan tanggal/customer/teknisi/text_laporan.')
                frame, normalized_input = self._feature_frame(request)
            try:
                predicted = str(model.predict(frame)[0])
                probability_values = np.asarray(model.predict_proba(frame)[0], dtype=float)
            except (TypeError, ValueError) as error:
                raise InvalidDatasetError(f"Prediction model gagal: {error}") from error

            model_classes = [str(value) for value in model.classes_.tolist()]
            if set(model_classes) != set(metadata['target']['classes']) or predicted not in model_classes:
                raise InvalidDatasetError("Kelas keluaran model tidak valid.")
            if len(probability_values) != len(model_classes) or not np.isfinite(
                probability_values
            ).all():
                raise InvalidDatasetError("Probabilities model tidak valid.")
            probabilities = {
                label: round(float(probability_values[index]), 8)
                for index, label in enumerate(model_classes)
            }
            if not np.isclose(sum(probabilities.values()), 1.0, atol=1e-6):
                raise InvalidDatasetError("Jumlah probabilities model tidak sama dengan satu.")

            prediction_id = self._new_prediction_id(set(states))
            created_at = self._now()
            warning = self._recommendation_warning(evaluation)
            event = {
                "event_type": "prediction_created",
                "event_id": self._new_event_id(),
                "prediction_version": PREDICTION_VERSION,
                "prediction_id": prediction_id,
                "job_id": job_id,
                "model_id": metadata["model_id"],
                "experiment_id": metadata.get('configuration', {}).get('experiment_id', 'legacy'),
                "model_pipeline_sha256": model_sha256,
                "created_at": created_at,
                "input": normalized_input,
                "prediction": predicted,
                "confidence": probabilities[predicted],
                "probabilities": probabilities,
                "recommendation_only": True,
                "warning": warning,
                "actual_decision": None,
            }
            self._append_event(job_id, event)
            return self._prediction_result(event)

    def record_actual_decision(
        self,
        job_id: str,
        prediction_id: str,
        request: ActualDecisionRequest,
    ) -> PredictionHistoryItem:
        with self._lock:
            self._validate_prediction_id(prediction_id)
            events = self._read_events(job_id)
            states = self._reconstruct(job_id, events)
            current = states.get(prediction_id)
            if current is None:
                raise PredictionNotFoundError(prediction_id)
            metadata = metadata_for_model(self.storage_root, job_id, current['model_id'])
            self.configuration.verify_snapshot(job_id, metadata.get('configuration', {}))
            if request.actual_decision not in metadata['target']['classes']:
                raise InvalidDatasetError('Keputusan aktual harus merupakan kelas model asal.')

            previous = current.get("actual_decision")
            if previous == request.actual_decision:
                return PredictionHistoryItem.model_validate(current)
            reason = request.reason.strip() if request.reason else None
            if previous is not None and not reason:
                raise InvalidDatasetError(
                    "Alasan wajib diisi ketika mengubah keputusan aktual yang sudah tercatat."
                )

            event = {
                "event_type": "actual_decision_recorded",
                "event_id": self._new_event_id(),
                "prediction_id": prediction_id,
                "job_id": job_id,
                "model_id": current["model_id"],
                "experiment_id": current.get('experiment_id', 'legacy'),
                "created_at": self._now(),
                "previous_actual_decision": previous,
                "actual_decision": request.actual_decision,
                "reason": reason,
                "validator_role": ADMIN_VALIDATOR_ROLE,
            }
            self._append_event(job_id, event)
            updated = self._reconstruct(job_id, [*events, event])[prediction_id]
            return PredictionHistoryItem.model_validate(updated)

    def history(
        self, job_id: str, page: int, page_size: int
    ) -> PredictionHistoryPage:
        with self._lock:
            self.jobs.require_job_path(job_id)
            events = self._read_events(job_id)
            states = self._reconstruct(job_id, events)
            items = sorted(
                states.values(), key=lambda item: item["created_at"], reverse=True
            )
            total = len(items)
            start = (page - 1) * page_size
            selected = items[start : start + page_size]
            return PredictionHistoryPage(
                page=page,
                page_size=page_size,
                total_items=total,
                total_pages=math.ceil(total / page_size) if total else 0,
                event_count=len(events),
                items=[PredictionHistoryItem.model_validate(item) for item in selected],
            )

    def history_path(self, job_id: str) -> Path:
        with self._lock:
            path = self.jobs.prediction_history_path(job_id)
            if not path.is_file():
                raise ArtifactNotFoundError("predictions.jsonl")
            self._reconstruct(job_id, self._read_events(job_id))
            return path

    def _load_verified_model(
        self, job_id: str
    ) -> tuple[Any, dict[str, Any], str, dict[str, Any]]:
        jobs = artifact_jobs(self.storage_root, job_id)
        model_path = jobs.model_pipeline_path(job_id)
        metadata_path = jobs.model_metadata_path(job_id)
        evaluation_path = jobs.report_path(job_id, "evaluation.json")
        self._require_file(model_path, "model_pipeline.joblib")
        self._require_file(metadata_path, "model_metadata.json")
        self._require_file(evaluation_path, "evaluation.json")
        metadata = read_json(metadata_path)
        self.configuration.verify_snapshot(job_id, metadata.get('configuration', {}))
        evaluation = read_json(evaluation_path)
        from app.services.evaluation_service import EvaluationService
        verifier = EvaluationService(self.settings)
        verifier.jobs = jobs
        verifier._verify_existing_report(job_id, evaluation, jobs.report_path(job_id, 'feature_importance.json'))
        model_sha256 = self._sha256(model_path)
        expected_sha256 = (
            metadata.get("artifacts", {})
            .get("model_pipeline", {})
            .get("sha256")
        )
        if expected_sha256 != model_sha256:
            raise InvalidDatasetError("Checksum model pipeline tidak valid.")
        if evaluation.get("model_id") != metadata.get("model_id"):
            raise InvalidDatasetError("Model evaluation berbeda dari model prediction.")
        if (
            evaluation.get("traceability", {}).get("model_pipeline_sha256")
            != model_sha256
        ):
            raise InvalidDatasetError("Checksum model pada evaluation tidak valid.")
        trained_version = metadata.get("dependencies", {}).get("scikit-learn")
        if trained_version != version("scikit-learn"):
            raise InvalidDatasetError(
                "Versi scikit-learn prediction berbeda dari versi training."
            )
        try:
            model = joblib.load(model_path)
        except (OSError, ValueError, TypeError, EOFError, ImportError) as error:
            raise InvalidDatasetError("Model lokal tidak dapat dimuat.") from error
        return model, metadata, model_sha256, evaluation

    @staticmethod
    def _recommendation_warning(evaluation: dict[str, Any]) -> str:
        metrics = evaluation.get('metrics', {})
        recall = metrics.get('highlighted_recall', metrics.get('positive_recall'))
        label = metrics.get('highlighted_class', metrics.get('positive_class', 'TINDAK_LANJUT'))
        if not isinstance(recall, (int, float)) or not 0 <= float(recall) <= 1:
            raise InvalidDatasetError(
                "Positive recall pada evaluation artifact tidak valid."
            )
        return (
            "Rekomendasi model, bukan keputusan final. Recall evaluasi untuk "
            f"{label} adalah {float(recall) * 100:.2f}%; "
            "admin wajib meninjau hasil."
        )

    @staticmethod
    def _feature_frame(
        request: PredictionRequest,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        text = normalize_report_text(request.text_laporan)
        customer = normalize_report_text(request.customer) or "UNKNOWN"
        teknisi = normalize_report_text(request.teknisi) or "UNKNOWN"
        if not text:
            raise InvalidDatasetError("text_laporan tidak boleh kosong.")
        normalized_input = {
            "tanggal": request.tanggal.isoformat(),
            "customer": customer,
            "teknisi": teknisi,
            "text_laporan": text,
        }
        frame = pd.DataFrame(
            [
                {
                    "text_laporan": text,
                    "customer": customer,
                    "teknisi": teknisi,
                    "tahun": request.tanggal.year,
                    "bulan": request.tanggal.month,
                    "hari_dalam_minggu": request.tanggal.weekday(),
                    "jumlah_teknisi": technician_count(teknisi),
                }
            ],
            columns=list(MODEL_FEATURES),
        )
        return frame, normalized_input

    def _read_events(self, job_id: str) -> list[dict[str, Any]]:
        try:
            return read_json_lines(self.jobs.prediction_history_path(job_id))
        except ValueError as error:
            raise InvalidDatasetError(str(error)) from error

    def _append_event(self, job_id: str, event: dict[str, Any]) -> None:
        try:
            append_json_line(self.jobs.prediction_history_path(job_id), event)
        except ValueError as error:
            raise InvalidDatasetError(str(error)) from error

    def _reconstruct(
        self, job_id: str, events: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        states: dict[str, dict[str, Any]] = {}
        model_classes = {}
        event_ids: set[str] = set()
        for index, event in enumerate(events, start=1):
            if event.get("job_id") != job_id:
                raise InvalidDatasetError(
                    f"Event prediction baris {index} berasal dari job berbeda."
                )
            event_id = event.get("event_id")
            if (
                not isinstance(event_id, str)
                or not EVENT_ID_PATTERN.fullmatch(event_id)
                or event_id in event_ids
            ):
                raise InvalidDatasetError(
                    f"event_id prediction baris {index} tidak valid atau duplikat."
                )
            event_ids.add(event_id)
            event_type = event.get("event_type")
            prediction_id = event.get("prediction_id")
            if not isinstance(prediction_id, str) or not PREDICTION_ID_PATTERN.fullmatch(
                prediction_id
            ):
                raise InvalidDatasetError(
                    f"prediction_id pada event baris {index} tidak valid."
                )
            if event_type == "prediction_created":
                model_id = event.get('model_id')
                if model_id not in model_classes:
                    metadata = metadata_for_model(self.storage_root, job_id, model_id)
                    self.configuration.verify_snapshot(job_id, metadata.get('configuration', {}))
                    model_classes[model_id] = metadata['target']['classes']
                classes = model_classes[model_id]
                if prediction_id in states:
                    raise InvalidDatasetError(
                        f"prediction_created duplikat untuk {prediction_id}."
                    )
                required = {
                    "model_id",
                    "created_at",
                    "input",
                    "prediction",
                    "confidence",
                    "probabilities",
                    "recommendation_only",
                    "warning",
                }
                if not required.issubset(event):
                    raise InvalidDatasetError(
                        f"Event prediction_created baris {index} tidak lengkap."
                    )
                if event.get("prediction") not in classes:
                    raise InvalidDatasetError(
                        f"Prediction pada event baris {index} tidak valid."
                    )
                probabilities = event.get("probabilities")
                if not isinstance(probabilities, dict) or set(probabilities) != set(
                    classes
                ):
                    raise InvalidDatasetError(
                        f"Probabilities pada event baris {index} tidak valid."
                    )
                states[prediction_id] = {
                    "prediction_id": prediction_id,
                    "model_id": event["model_id"],
                    "experiment_id": event.get('experiment_id', 'legacy'),
                    "created_at": event["created_at"],
                    "input": event["input"],
                    "prediction": event["prediction"],
                    "confidence": event["confidence"],
                    "probabilities": event["probabilities"],
                    "recommendation_only": event["recommendation_only"],
                    "warning": event["warning"],
                    "actual_decision": None,
                    "actual_decision_recorded_at": None,
                    "actual_decision_reason": None,
                    "validator_role": None,
                }
            elif event_type == "actual_decision_recorded":
                if prediction_id not in states:
                    raise InvalidDatasetError(
                        f"Actual decision baris {index} tidak memiliki prediction_created."
                    )
                current = states[prediction_id]
                classes = model_classes[current['model_id']]
                if event.get('model_id') != current['model_id']:
                    raise InvalidDatasetError('Model koreksi berbeda dari model asal prediksi.')
                if event.get("previous_actual_decision") != current["actual_decision"]:
                    raise InvalidDatasetError(
                        f"Rantai actual decision {prediction_id} tidak konsisten."
                    )
                if event.get("actual_decision") not in classes:
                    raise InvalidDatasetError(
                        f"Actual decision baris {index} tidak valid."
                    )
                if event.get("validator_role") != ADMIN_VALIDATOR_ROLE:
                    raise InvalidDatasetError(
                        f"Validator role baris {index} tidak valid."
                    )
                current["actual_decision"] = event.get("actual_decision")
                current["actual_decision_recorded_at"] = event.get("created_at")
                current["actual_decision_reason"] = event.get("reason")
                current["validator_role"] = event.get("validator_role")
            else:
                raise InvalidDatasetError(
                    f"event_type prediction baris {index} tidak dikenal."
                )
        return states

    def _require_evaluated_job(self, job_id: str) -> None:
        selected = active_id(self.jobs, job_id)
        if selected is not None:
            return
        metadata = self.jobs.read_metadata(job_id)
        status = parse_job_status(metadata.get("status"))
        if JOB_STATUS_ORDER[status] < JOB_STATUS_ORDER[JobStatus.EVALUATED]:
            raise InvalidJobStateError(
                "Prediction hanya tersedia setelah model berstatus EVALUATED."
            )

    @staticmethod
    def _new_prediction_id(existing: set[str]) -> str:
        while True:
            prediction_id = "PRED-" + secrets.token_hex(8).upper()
            if prediction_id not in existing:
                return prediction_id

    @staticmethod
    def _new_event_id() -> str:
        return "EVENT-" + secrets.token_hex(8).upper()

    @staticmethod
    def _validate_prediction_id(prediction_id: str) -> None:
        if not PREDICTION_ID_PATTERN.fullmatch(prediction_id):
            raise PredictionNotFoundError(prediction_id)

    @staticmethod
    def _prediction_result(event: dict[str, Any]) -> PredictionResult:
        return PredictionResult.model_validate(event)

    @staticmethod
    def _require_file(path: Path, name: str) -> None:
        if not path.is_file():
            raise ArtifactNotFoundError(name)

    @staticmethod
    def _sha256(path: Path) -> str:
        from hashlib import sha256

        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
