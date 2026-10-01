from dataclasses import dataclass
import re
from typing import Any, Mapping

import pandas as pd


POLICY_VERSION = "ai-assisted-id-v1"
AI_VALIDATOR_ROLE = "AI_VALIDATOR"


@dataclass(frozen=True)
class AutoLabelDecision:
    label: str
    confidence: float
    reason: str
    matched_rule: str


FOLLOW_UP_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "belum_selesai",
        re.compile(r"\b(?:belum|belom)\b(?:\s+\w+){0,4}\s+\b(?:beres|selesai|bisa|diperbaiki|dikerjakan)\b"),
    ),
    (
        "masih_diproses",
        re.compile(r"\b(?:masih|lagi)\s+(?:tetap\s+)?(?:proses|diproses|dikerjakan|ditanya|dicek|dibantu|urus|menunggu|tunggu)\b"),
    ),
    (
        "menunggu",
        re.compile(
            r"\b(?:pending|tertunda|menunggu)\b|"
            r"\btunggu\s+(?:kabar|barang|part|sparepart|vendor|persetujuan|konfirmasi)\b"
        ),
    ),
    (
        "dilanjutkan",
        re.compile(r"\b(?:lanjut|dilanjutkan)\s+(?:besok|lagi|hari\s+\w+)\b"),
    ),
    (
        "tindakan_lanjutan_wajib",
        re.compile(
            r"\b(?:harus|perlu|butuh)\s+(?:di\s*)?"
            r"(?:service|servis|ganti|diganti|tambah|ditambah|beli|dibeli|order|pesan|"
            r"diperbaiki|claim|klaim|perbaikan)\b"
        ),
    ),
    (
        "tindakan_lanjutan_direncanakan",
        re.compile(
            r"\b(?:mau|akan)\s+(?:di\s*)?"
            r"(?:service|servis|claim|klaim|ganti|diganti|bawa|dibawa)\b"
        ),
    ),
    (
        "dibawa_untuk_tindak_lanjut",
        re.compile(
            r"\b(?:bawa|dibawa)\s+(?:ke\s+)?"
            r"(?:kantor|service|servis|teknisi|harco|geotech)\b"
        ),
    ),
    (
        "gagal_diselesaikan",
        re.compile(r"\b(?:tidak|nggak|ga|gak)\s+(?:bisa\s+)?(?:selesai|beres)\b"),
    ),
)

COMPLETION_PATTERN = re.compile(r"\b(?:ok|selesai|beres|sudah|jadi|done)\b")


def classify_record(record: Mapping[str, Any]) -> AutoLabelDecision:
    text = _text(record.get("keluhan_solusi"))
    source_status = _text(record.get("status"))

    if not text:
        return AutoLabelDecision(
            label="NEEDS_REVIEW",
            confidence=0.1,
            reason="Isi laporan kosong sehingga tidak ada bukti yang cukup untuk keputusan final.",
            matched_rule="empty_report",
        )

    for rule_name, pattern in FOLLOW_UP_RULES:
        match = pattern.search(text)
        if match:
            evidence = match.group(0)
            confidence = 0.84 if source_status == "ok" else 0.92
            return AutoLabelDecision(
                label="TINDAK_LANJUT",
                confidence=confidence,
                reason=(
                    f"Ditemukan indikasi pekerjaan belum ditutup: '{evidence}' "
                    f"(aturan {rule_name})."
                ),
                matched_rule=rule_name,
            )

    if source_status == "ok":
        return AutoLabelDecision(
            label="SELESAI",
            confidence=0.97,
            reason=(
                "Status sumber menyatakan OK dan tidak ditemukan indikasi kuat "
                "tindakan lanjutan."
            ),
            matched_rule="source_status_ok",
        )

    completion = COMPLETION_PATTERN.search(text)
    if completion:
        return AutoLabelDecision(
            label="SELESAI",
            confidence=0.86,
            reason=(
                f"Tidak ada status sumber, tetapi ditemukan bukti penyelesaian "
                f"'{completion.group(0)}' tanpa indikasi tindak lanjut."
            ),
            matched_rule="completion_evidence",
        )

    return AutoLabelDecision(
        label="NEEDS_REVIEW",
        confidence=0.4,
        reason=(
            "Laporan tidak memiliki status sumber maupun bukti penyelesaian atau "
            "tindak lanjut yang cukup kuat."
        ),
        matched_rule="insufficient_evidence",
    )


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).lower().split())
