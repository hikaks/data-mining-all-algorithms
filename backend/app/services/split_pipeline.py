from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold


SPLIT_VERSION = "stratified-group-holdout-v1"
RANDOM_STATE = 42
TARGET_TEST_RATIO = 0.2
PREFERRED_FOLDS = 5
TARGET_COLUMN = "keputusan_laporan"
GROUP_COLUMN = "near_duplicate_group_id"


@dataclass(frozen=True)
class SplitSelection:
    train_indices: list[int]
    test_indices: list[int]
    strategy: str
    selected_candidate: int
    candidate_summaries: list[dict[str, Any]]


def select_group_stratified_holdout(dataframe: pd.DataFrame, test_ratio: float = TARGET_TEST_RATIO) -> SplitSelection:
    if test_ratio not in (0.2, 0.25, 0.3):
        raise ValueError("Rasio test harus 20%, 25%, atau 30%.")
    requested_ratio = test_ratio
    _validate_input(dataframe)
    labels = dataframe[TARGET_COLUMN].astype(str)
    groups = dataframe[GROUP_COLUMN].astype(str)
    class_counts = labels.value_counts()
    unique_groups = groups.nunique()

    folds = 5 if test_ratio == 0.2 else 4 if test_ratio == 0.25 else None
    if folds and int(class_counts.min()) >= folds and unique_groups >= folds:
        splitter = StratifiedGroupKFold(
            n_splits=folds,
            shuffle=True,
            random_state=RANDOM_STATE,
        )
        candidates: Iterable[tuple[Any, Any]] = splitter.split(
            dataframe[["record_id"]], labels, groups
        )
        strategy = "StratifiedGroupKFold"
    else:
        splitter = GroupShuffleSplit(
            n_splits=256,
            test_size=test_ratio,
            random_state=RANDOM_STATE,
        )
        candidates = splitter.split(dataframe[["record_id"]], labels, groups)
        strategy = "GroupShuffleSplitBestCandidate"

    all_classes = sorted(labels.unique().tolist())
    overall_proportions = labels.value_counts(normalize=True).to_dict()
    summaries: list[dict[str, Any]] = []
    valid_candidates: list[tuple[float, int, list[int], list[int]]] = []
    for candidate_index, (train_index, test_index) in enumerate(candidates):
        train_indices = [int(index) for index in train_index]
        test_indices = [int(index) for index in test_index]
        train_labels = labels.iloc[train_indices]
        test_labels = labels.iloc[test_indices]
        train_counts = _counts(train_labels, all_classes)
        test_counts = _counts(test_labels, all_classes)
        group_overlap = sorted(
            set(groups.iloc[train_indices]).intersection(groups.iloc[test_indices])
        )
        test_ratio = len(test_indices) / len(dataframe)
        distribution_error = sum(
            abs(
                test_counts[label] / len(test_indices)
                - float(overall_proportions[label])
            )
            for label in all_classes
        )
        score = abs(test_ratio - requested_ratio) + distribution_error
        valid = (
            not group_overlap
            and all(train_counts[label] >= 2 for label in all_classes)
            and all(test_counts[label] >= 2 for label in all_classes)
        )
        summaries.append(
            {
                "candidate": candidate_index,
                "train_rows": len(train_indices),
                "test_rows": len(test_indices),
                "test_ratio": round(test_ratio, 8),
                "train_distribution": train_counts,
                "test_distribution": test_counts,
                "group_overlap_count": len(group_overlap),
                "selection_score": round(score, 12),
                "valid": valid,
            }
        )
        if valid:
            valid_candidates.append(
                (score, candidate_index, train_indices, test_indices)
            )

    if not valid_candidates:
        raise ValueError(
            "Tidak ada split group-aware yang mempertahankan minimal dua record "
            "setiap kelas pada train dan test."
        )
    _, selected_candidate, train_indices, test_indices = min(
        valid_candidates, key=lambda item: (item[0], item[1])
    )
    return SplitSelection(
        train_indices=train_indices,
        test_indices=test_indices,
        strategy=strategy,
        selected_candidate=selected_candidate,
        candidate_summaries=summaries,
    )


def validate_selection(
    dataframe: pd.DataFrame, selection: SplitSelection
) -> dict[str, Any]:
    train = dataframe.iloc[selection.train_indices]
    test = dataframe.iloc[selection.test_indices]
    train_ids = set(train["record_id"].astype(str))
    test_ids = set(test["record_id"].astype(str))
    train_groups = set(train[GROUP_COLUMN].astype(str))
    test_groups = set(test[GROUP_COLUMN].astype(str))
    record_overlap = sorted(train_ids.intersection(test_ids))
    group_overlap = sorted(train_groups.intersection(test_groups))
    coverage = train_ids.union(test_ids)
    source_ids = set(dataframe["record_id"].astype(str))
    return {
        "record_overlap_count": len(record_overlap),
        "group_overlap_count": len(group_overlap),
        "complete_coverage": coverage == source_ids,
        "missing_record_count": len(source_ids.difference(coverage)),
        "duplicate_assignment_count": len(record_overlap),
        "passed": not record_overlap
        and not group_overlap
        and coverage == source_ids,
    }


def _validate_input(dataframe: pd.DataFrame) -> None:
    required = {"record_id", TARGET_COLUMN, GROUP_COLUMN}
    missing = sorted(required.difference(dataframe.columns))
    if missing:
        raise ValueError("Kolom split hilang: " + ", ".join(missing))
    if dataframe.empty:
        raise ValueError("Dataset preprocessing kosong.")
    if dataframe["record_id"].duplicated().any():
        raise ValueError("record_id harus unik sebelum split.")
    if dataframe[["record_id", TARGET_COLUMN, GROUP_COLUMN]].isna().any().any():
        raise ValueError("Identifier, target, dan group split tidak boleh kosong.")
    class_counts = dataframe[TARGET_COLUMN].value_counts()
    if len(class_counts) < 2 or int(class_counts.min()) < 2:
        raise ValueError("Setiap kelas memerlukan minimal dua record untuk split.")
    if dataframe[GROUP_COLUMN].nunique() < 2:
        raise ValueError("Split membutuhkan minimal dua group independen.")


def _counts(values: pd.Series, classes: list[str]) -> dict[str, int]:
    counts = values.value_counts().to_dict()
    return {label: int(counts.get(label, 0)) for label in classes}
