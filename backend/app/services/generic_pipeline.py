"""Pure, deterministic feature preparation. Learned transforms live in the model."""
from datetime import date
import json
from hashlib import sha256

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier

from app.core.exceptions import InvalidDatasetError
from app.services.training_pipeline import RANDOM_FOREST_PARAMETERS
from app.utils.tabular import feature_value


class StringLabelRandomForest(RandomForestClassifier):
    """Encode train labels before RF balancing; preserve exact public string classes.

    Numeric-looking codes (e.g. '01' versus '1') must not be coerced by
    class-weight validation. RF trees already predict encoded class indices;
    its public classes_ supplies the inverse mapping for predict/probabilities.
    """
    def fit(self, X, y, sample_weight=None):
        self.label_encoder_ = LabelEncoder()
        encoded = self.label_encoder_.fit_transform(np.asarray(y, dtype=str))
        super().fit(X, encoded, sample_weight=sample_weight)
        self.classes_ = self.label_encoder_.classes_.copy()
        return self


def contract(config):
    mapping = []
    for index, feature in enumerate(config['features']):
        alias = f'feature_{index:04d}'
        columns = [alias + '_' + part for part in ('year', 'month', 'weekday')] if feature['kind'] == 'date' else [alias]
        mapping.append({**feature, 'columns': columns})
    return mapping


def prepare_features(values, config, location='input'):
    result, normalized = {}, {}
    for feature in contract(config):
        name, kind = feature['name'], feature['kind']
        value = feature_value(values.get(name), kind, f'{location}, kolom {name}')
        normalized[name] = value
        if kind == 'date':
            parsed = date.fromisoformat(value) if value else None
            parts = [parsed.year, parsed.month, parsed.weekday()] if parsed else [np.nan] * 3
            result.update(zip(feature['columns'], parts))
        else:
            result[feature['columns'][0]] = value if value is not None else (np.nan if kind == 'numeric' else '' if kind == 'text' else '__MISSING_CATEGORY__')
    return result, normalized


def fingerprint(values):
    return sha256(json.dumps(values, sort_keys=True, ensure_ascii=False, default=str, allow_nan=False).encode()).hexdigest()


def model_columns(config):
    return [column for feature in contract(config) for column in feature['columns']]


def coerce_frame(frame, config):
    frame = frame.copy()
    for feature in contract(config):
        for column in feature['columns']:
            if feature['kind'] in ('numeric', 'date'):
                frame[column] = pd.to_numeric(frame[column].replace('', np.nan), errors='raise')
            else:
                frame[column] = frame[column].fillna('').astype(str)
    return frame


def build_pipeline(config, train, algorithm='random_forest', parameter_version=2):
    transformers = []
    for index, feature in enumerate(contract(config)):
        kind, columns = feature['kind'], feature['columns']
        if kind in ('numeric', 'date'):
            if train[columns].isna().all().any():
                raise InvalidDatasetError(f"Fitur {feature['name']} seluruhnya kosong pada train set; median tidak dapat dipelajari.")
            transformer = SimpleImputer(strategy='median')
            if algorithm in ('svm_linear', 'knn'):
                transformer = Pipeline([('imputer', transformer), ('scaler', StandardScaler())])
            selector = columns
        elif kind == 'categorical':
            transformer = OneHotEncoder(handle_unknown='ignore')
            selector = columns
        else:
            transformer = TfidfVectorizer(max_features=5000, sublinear_tf=True, token_pattern=r'(?u)\b\w+\b')
            selector = columns[0]  # scalar selector: vectorizer receives a 1-D series
        transformers.append((f'{kind}_{index}', transformer, selector))
    from app.services.classifiers import StringClassifier
    classifier = StringLabelRandomForest(**RANDOM_FOREST_PARAMETERS) if algorithm == 'random_forest' else StringClassifier(algorithm, parameter_version)
    return Pipeline([('preprocessor', ColumnTransformer(transformers, remainder='drop')), ('classifier', classifier)])
