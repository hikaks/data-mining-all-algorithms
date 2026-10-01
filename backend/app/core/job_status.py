from enum import StrEnum

from app.core.exceptions import InvalidJobStateError


class JobStatus(StrEnum):
    UPLOADED = "UPLOADED"
    ANALYZED = "ANALYZED"
    CLEANED = "CLEANED"
    LABELING = "LABELING"
    LABELED = "LABELED"
    PREPROCESSED = "PREPROCESSED"
    TRAINED = "TRAINED"
    EVALUATED = "EVALUATED"


JOB_STATUS_ORDER = {status: index for index, status in enumerate(JobStatus)}
LEGACY_STATUS_ALIASES = {
    "uploaded": JobStatus.UPLOADED,
    "understood": JobStatus.ANALYZED,
    "analyzed": JobStatus.ANALYZED,
    "cleaned": JobStatus.CLEANED,
    "labeling": JobStatus.LABELING,
    "labeled": JobStatus.LABELED,
    "preprocessed": JobStatus.PREPROCESSED,
    "trained": JobStatus.TRAINED,
    "evaluated": JobStatus.EVALUATED,
}


def parse_job_status(value: object) -> JobStatus:
    if isinstance(value, JobStatus):
        return value
    text = str(value)
    try:
        return JobStatus(text.upper())
    except ValueError:
        alias = LEGACY_STATUS_ALIASES.get(text.lower())
        if alias is None:
            raise InvalidJobStateError(f"Status job '{text}' tidak dikenal.")
        return alias


def advance_job_status(current: object, target: JobStatus) -> JobStatus:
    current_status = parse_job_status(current)
    if JOB_STATUS_ORDER[current_status] >= JOB_STATUS_ORDER[target]:
        return current_status
    return target


def require_status_at_most(
    current: object, maximum: JobStatus, operation: str
) -> JobStatus:
    current_status = parse_job_status(current)
    if JOB_STATUS_ORDER[current_status] > JOB_STATUS_ORDER[maximum]:
        raise InvalidJobStateError(
            f"Operasi '{operation}' tidak tersedia saat status job "
            f"sudah {current_status.value}."
        )
    return current_status
