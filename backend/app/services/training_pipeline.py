from hashlib import sha256
import json
from typing import Any

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline

from app.services.preprocessing_pipeline import (
    MODEL_FEATURES,
    TARGET_COLUMN,
    assert_feature_contract,
    build_model_preprocessor,
)


TRAINING_VERSION = "random-forest-baseline-v1"
RANDOM_STATE = 42
TARGET_CLASSES = ("SELESAI", "TINDAK_LANJUT")
POSITIVE_CLASS = "TINDAK_LANJUT"
RANDOM_FOREST_PARAMETERS: dict[str, Any] = {
    "n_estimators": 100,
    "criterion": "gini",
    "max_depth": 20,
    "min_samples_split": 2,
    "min_samples_leaf": 2,
    "max_features": "sqrt",
    "class_weight": "balanced",
    "bootstrap": True,
    "random_state": RANDOM_STATE,
    "n_jobs": 1,
}


def build_model_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", build_model_preprocessor()),
            ("classifier", RandomForestClassifier(**RANDOM_FOREST_PARAMETERS)),
        ]
    )


def validate_training_frame(dataframe: pd.DataFrame) -> dict[str, int]:
    required = {*MODEL_FEATURES, TARGET_COLUMN}
    missing = sorted(required.difference(dataframe.columns))
    if missing:
        raise ValueError("Kolom training hilang: " + ", ".join(missing))
    if dataframe.empty:
        raise ValueError("Dataset training kosong.")

    assert_feature_contract(list(dataframe.loc[:, list(MODEL_FEATURES)].columns))
    target = dataframe[TARGET_COLUMN]
    if target.isna().any():
        raise ValueError("Target training tidak boleh kosong.")

    observed = set(target.astype(str).unique())
    expected = set(TARGET_CLASSES)
    if observed != expected:
        raise ValueError(
            "Target training harus tepat berisi kelas SELESAI dan TINDAK_LANJUT."
        )
    counts = {
        label: int((target.astype(str) == label).sum()) for label in TARGET_CLASSES
    }
    if any(count < 2 for count in counts.values()):
        raise ValueError("Setiap kelas training membutuhkan minimal dua record.")
    return counts


def transformed_feature_manifest(pipeline: Pipeline) -> dict[str, Any]:
    names = pipeline.named_steps["preprocessor"].get_feature_names_out().tolist()
    encoded = json.dumps(names, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return {
        "input_columns": list(MODEL_FEATURES),
        "transformed_feature_count": len(names),
        "transformed_feature_names_sha256": sha256(encoded).hexdigest(),
    }


def training_configuration() -> dict[str, Any]:
    return {
        "training_version": TRAINING_VERSION,
        "algorithm": "RandomForestClassifier",
        "pipeline": ["ColumnTransformer", "RandomForestClassifier"],
        "parameters": dict(RANDOM_FOREST_PARAMETERS),
        "fit_scope": "TRAIN_RECORD_IDS_FROM_SPLIT_MANIFEST_ONLY",
        "hyperparameter_search": "NONE",
        "resource_profile": "LOCAL_2_CORE_4GB",
    }
