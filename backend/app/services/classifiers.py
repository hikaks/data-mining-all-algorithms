"""Fixed local baselines; public labels always retain their original strings."""
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import LabelEncoder
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier

from app.core.exceptions import InvalidDatasetError
from app.services.training_pipeline import RANDOM_FOREST_PARAMETERS

PARAMETER_VERSION = 2
LEGACY_PARAMETERS = {
    'random_forest': dict(RANDOM_FOREST_PARAMETERS),
    'decision_tree': dict(criterion='gini', max_depth=20, min_samples_split=2,
                          min_samples_leaf=2, class_weight='balanced', random_state=42),
    'svm_linear': dict(kernel='linear', C=1.0, probability=True, class_weight='balanced',
                       cache_size=200, max_iter=10000, random_state=42),
    'knn': dict(n_neighbors=5, weights='distance', algorithm='brute', metric='euclidean', n_jobs=1),
}
PARAMETERS = {algorithm: dict(parameters) for algorithm, parameters in LEGACY_PARAMETERS.items()}
# The libsvm solver must finish, rather than publish an iteration-limited fit.
PARAMETERS['svm_linear']['max_iter'] = -1


def parameters_for(algorithm, parameter_version=PARAMETER_VERSION):
    policies = {1: LEGACY_PARAMETERS, 2: PARAMETERS}
    if type(parameter_version) is not int or parameter_version not in policies or algorithm not in PARAMETERS:
        raise InvalidDatasetError('Versi parameter atau algoritma eksperimen tidak valid.')
    return dict(policies[parameter_version][algorithm])

NAMES = {'random_forest': 'RandomForestClassifier', 'decision_tree': 'DecisionTreeClassifier',
         'svm_linear': 'SVC', 'knn': 'KNeighborsClassifier'}


class StringClassifier(ClassifierMixin, BaseEstimator):
    def __init__(self, algorithm='decision_tree', parameter_version=PARAMETER_VERSION):
        self.algorithm = algorithm
        self.parameter_version = parameter_version

    def __setstate__(self, state):
        # Old joblib models retain their original parameter policy in memory.
        state.setdefault('parameter_version', 1)
        super().__setstate__(state)

    def fit(self, X, y):
        if self.algorithm == 'knn' and len(y) < 5:
            raise InvalidDatasetError('KNN dengan K=5 membutuhkan minimal lima record train.')
        self.encoder_ = LabelEncoder().fit(np.asarray(y, dtype=str))
        self.classes_ = self.encoder_.classes_.copy()
        constructor = {'decision_tree': DecisionTreeClassifier, 'svm_linear': SVC,
                       'knn': KNeighborsClassifier}[self.algorithm]
        parameters = parameters_for(self.algorithm, self.parameter_version)
        self.estimator_ = constructor(**parameters)
        self.estimator_.fit(X, self.encoder_.transform(np.asarray(y, dtype=str)))
        if self.algorithm == 'svm_linear' and self.estimator_.fit_status_ != 0:
            limit = parameters['max_iter']
            message = f'SVM belum konvergen dalam {limit} iterasi.' if limit != -1 else 'Solver SVM belum berhasil konvergen.'
            raise InvalidDatasetError(message + ' Model tidak dipublikasikan.')
        return self

    def predict(self, X):
        return self.encoder_.inverse_transform(self.estimator_.predict(X).astype(int))

    def predict_proba(self, X):
        return self.estimator_.predict_proba(X)

    @property
    def feature_importances_(self):
        return self.estimator_.feature_importances_
