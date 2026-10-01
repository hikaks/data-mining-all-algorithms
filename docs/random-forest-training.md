# Random Forest Training

Baseline RF di bawah dipertahankan. Pilihan DT, SVM linear dan KNN kini tersedia sebagai eksperimen terpisah; scaler hanya ditambahkan pada numerik/kalender SVM/KNN. Aktivasi model memerlukan evaluasi dan konfirmasi manual. Lihat [kontrak eksperimen](model-experiments.md).

## Status

Tahap 9 selesai dan telah dijalankan pada job `aNvdsL7wjhr7Lqb7TAxd6g`.

Model aktual:

```text
model_id: RF-46320A252D2C7AC4
training_version: random-forest-baseline-v1
train rows: 814
SELESAI: 796
TINDAK_LANJUT: 18
transformed features: 6378
test rows reserved: 204
test set used for fit: false
```

## Pipeline

Satu artifact Scikit-learn Pipeline memuat:

```text
ColumnTransformer
├── TfidfVectorizer untuk text_laporan
├── SimpleImputer + OneHotEncoder untuk customer dan teknisi
└── SimpleImputer untuk fitur kalender dan jumlah teknisi
↓
RandomForestClassifier
```

Seluruh transformer dan classifier hanya di-fit pada record train yang tercantum dalam `split_manifest.json`. Record test tidak digunakan untuk fitting, pemilihan fitur, atau pemilihan parameter.

## Parameter Baseline

```json
{
  "n_estimators": 100,
  "criterion": "gini",
  "max_depth": 20,
  "min_samples_split": 2,
  "min_samples_leaf": 2,
  "max_features": "sqrt",
  "class_weight": "balanced",
  "bootstrap": true,
  "random_state": 42,
  "n_jobs": 1
}
```

Konfigurasi ini ditujukan untuk komputer lokal 2 core/4 GB RAM. Tidak ada grid search, randomized search, oversampling, atau undersampling pada baseline.

## Artifact

```text
storage/jobs/<job_id>/model/model_pipeline.joblib
storage/jobs/<job_id>/model/model_metadata.json
```

`model_metadata.json` menyimpan parameter, kontrak fitur, distribusi train, hash daftar train/test ID, checksum sumber dan model, durasi training, hasil reload verification, serta versi dependency.

Joblib menggunakan mekanisme pickle. Aplikasi hanya boleh memuat artifact lokal tepercaya dari direktori job. Jangan memuat file Joblib dari upload atau sumber eksternal. Kompatibilitas model lintas versi scikit-learn tidak dijamin; cocokkan versi dependency pada metadata atau lakukan retraining.

## Endpoint

```text
POST /api/jobs/{job_id}/train
GET  /api/jobs/{job_id}/model-metadata
GET  /api/jobs/{job_id}/download/model
```

`POST /train` bersifat idempotent: jika pasangan model dan metadata yang valid sudah ada, endpoint mengembalikan hasil training yang sama dan tidak melatih ulang.

## Gate Tahap 10

Keberhasilan training bukan bukti kualitas model. Evaluasi berikutnya wajib memakai tepat 204 record test pada split manifest dan melaporkan metrik kelas minoritas `TINDAK_LANJUT`, bukan hanya accuracy.
