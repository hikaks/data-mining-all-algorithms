class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class InvalidDatasetError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_DATASET", message, 422)


class JobNotFoundError(AppError):
    def __init__(self, job_id: str) -> None:
        super().__init__("JOB_NOT_FOUND", f"Job '{job_id}' tidak ditemukan.", 404)


class ArtifactNotFoundError(AppError):
    def __init__(self, artifact_name: str) -> None:
        super().__init__(
            "ARTIFACT_NOT_FOUND", f"Artifact '{artifact_name}' belum tersedia.", 404
        )


class InvalidJobStateError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_JOB_STATE", message, 409)


class RecordNotFoundError(AppError):
    def __init__(self, record_id: str) -> None:
        super().__init__(
            "RECORD_NOT_FOUND", f"Record '{record_id}' tidak ditemukan.", 404
        )


class PredictionNotFoundError(AppError):
    def __init__(self, prediction_id: str) -> None:
        super().__init__(
            "PREDICTION_NOT_FOUND",
            f"Prediction '{prediction_id}' tidak ditemukan.",
            404,
        )
