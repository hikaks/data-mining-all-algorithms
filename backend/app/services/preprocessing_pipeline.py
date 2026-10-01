from dataclasses import dataclass
from hashlib import sha256
import math
import unicodedata
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PREPROCESSING_VERSION = "stateless-features-v1"
NEAR_DUPLICATE_THRESHOLD = 0.92
TARGET_COLUMN = "keputusan_laporan"
TEXT_FEATURES = ("text_laporan",)
CATEGORICAL_FEATURES = ("customer", "teknisi")
NUMERIC_FEATURES = ("tahun", "bulan", "hari_dalam_minggu", "jumlah_teknisi")
MODEL_FEATURES = (*TEXT_FEATURES, *CATEGORICAL_FEATURES, *NUMERIC_FEATURES)
IDENTIFIER_COLUMNS = ("record_id", "near_duplicate_group_id")
FORBIDDEN_MODEL_COLUMNS = {
    "record_id",
    "near_duplicate_group_id",
    "keputusan_laporan",
    "status",
    "tahun_sumber",
    "sumber_file",
    "sumber_sheet",
    "baris_sumber",
    "no_asli",
    "duplicate_fingerprint",
    "labeling_status",
    "label_validator_role",
    "label_updated_at",
    "label_confidence",
    "label_decision_reason",
    "label_policy_version",
    "nama_user",
    "yang_mengetahui",
}


@dataclass(frozen=True)
class NearDuplicateResult:
    group_ids: list[str]
    pair_count: int
    groups: list[dict[str, Any]]
    sample_pairs: list[dict[str, Any]]
    conflicting_label_groups: list[str]


def build_model_preprocessor() -> ColumnTransformer:
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    numeric_pipeline = Pipeline(
        steps=[("imputer", SimpleImputer(strategy="median"))]
    )
    return ColumnTransformer(
        transformers=[
            (
                "text",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                ),
                "text_laporan",
            ),
            ("categorical", categorical_pipeline, list(CATEGORICAL_FEATURES)),
            ("numeric", numeric_pipeline, list(NUMERIC_FEATURES)),
        ],
        remainder="drop",
    )


def transformer_spec() -> dict[str, Any]:
    return {
        "version": PREPROCESSING_VERSION,
        "fit_policy": "FIT_ON_TRAIN_ONLY",
        "learned_transformations_fitted": False,
        "text": {
            "columns": list(TEXT_FEATURES),
            "transformer": "TfidfVectorizer",
            "params": {
                "lowercase": True,
                "ngram_range": [1, 2],
                "min_df": 1,
                "sublinear_tf": True,
            },
        },
        "categorical": {
            "columns": list(CATEGORICAL_FEATURES),
            "imputer": "most_frequent",
            "encoder": "OneHotEncoder(handle_unknown='ignore')",
        },
        "numeric": {
            "columns": list(NUMERIC_FEATURES),
            "imputer": "median",
            "scaling": "not_required_for_random_forest",
        },
        "remainder": "drop",
    }


def assert_feature_contract(columns: list[str] | tuple[str, ...]) -> None:
    unexpected = sorted(set(columns).intersection(FORBIDDEN_MODEL_COLUMNS))
    if unexpected:
        raise ValueError(
            "Kolom leakage/identifier masuk ke fitur model: " + ", ".join(unexpected)
        )
    missing = sorted(set(MODEL_FEATURES).difference(columns))
    if missing:
        raise ValueError("Kolom fitur wajib hilang: " + ", ".join(missing))


def assert_finite_matrix(matrix: Any) -> None:
    values = matrix.data if sparse.issparse(matrix) else np.asarray(matrix)
    if not np.isfinite(values).all():
        raise ValueError("Hasil transformasi mengandung NaN atau infinite value.")


def normalize_report_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    normalized = unicodedata.normalize("NFKC", str(value))
    return " ".join(normalized.split())


def technician_count(value: Any) -> int:
    text = normalize_report_text(value)
    if not text:
        return 0
    return len({part.strip().casefold() for part in text.split("|") if part.strip()})


def detect_near_duplicates(
    dataframe: pd.DataFrame,
    threshold: float = NEAR_DUPLICATE_THRESHOLD,
    sample_limit: int = 200,
) -> NearDuplicateResult:
    total = len(dataframe)
    if total == 0:
        return NearDuplicateResult([], 0, [], [], [])

    record_ids = dataframe["record_id"].astype(str).tolist()
    texts = dataframe["text_laporan"].fillna("").astype(str).tolist()
    customers = dataframe["customer"].fillna("UNKNOWN").astype(str).str.casefold().tolist()
    labels = dataframe[TARGET_COLUMN].astype(str).tolist()
    parents = list(range(total))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        lowercase=True,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(texts)
    similarities = cosine_similarity(matrix, dense_output=False).tocoo()
    pairs: list[dict[str, Any]] = []
    pair_count = 0
    for left, right, score in zip(
        similarities.row, similarities.col, similarities.data, strict=True
    ):
        if left >= right or score < threshold or customers[left] != customers[right]:
            continue
        pair_count += 1
        union(int(left), int(right))
        if len(pairs) < sample_limit:
            pairs.append(
                {
                    "left_record_id": record_ids[left],
                    "right_record_id": record_ids[right],
                    "similarity": round(float(score), 6),
                    "customer": dataframe.iloc[left]["customer"],
                }
            )

    members_by_root: dict[int, list[int]] = {}
    for index in range(total):
        members_by_root.setdefault(find(index), []).append(index)

    group_id_by_index: dict[int, str] = {}
    groups: list[dict[str, Any]] = []
    conflicting: list[str] = []
    for members in members_by_root.values():
        if len(members) == 1:
            index = members[0]
            group_id_by_index[index] = f"UNIQUE-{record_ids[index]}"
            continue
        member_ids = sorted(record_ids[index] for index in members)
        digest = sha256("|".join(member_ids).encode("utf-8")).hexdigest()[:12].upper()
        group_id = f"NDG-{digest}"
        group_labels = sorted({labels[index] for index in members})
        for index in members:
            group_id_by_index[index] = group_id
        group = {
            "group_id": group_id,
            "size": len(members),
            "record_ids": member_ids,
            "labels": group_labels,
            "has_label_conflict": len(group_labels) > 1,
        }
        groups.append(group)
        if group["has_label_conflict"]:
            conflicting.append(group_id)

    groups.sort(key=lambda item: (-item["size"], item["group_id"]))
    pairs.sort(key=lambda item: -item["similarity"])
    return NearDuplicateResult(
        group_ids=[group_id_by_index[index] for index in range(total)],
        pair_count=pair_count,
        groups=groups,
        sample_pairs=pairs,
        conflicting_label_groups=conflicting,
    )


def finite_numeric_features(dataframe: pd.DataFrame) -> bool:
    values = dataframe.loc[:, list(NUMERIC_FEATURES)].to_numpy(dtype=float)
    return bool(np.isfinite(values).all())


def class_ratio(counts: dict[str, int]) -> float | None:
    values = [value for value in counts.values() if value > 0]
    if len(values) < 2:
        return None
    return round(max(values) / min(values), 4)
