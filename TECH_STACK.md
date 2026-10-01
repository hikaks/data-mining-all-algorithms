# TECH STACK & PROJECT STRUCTURE
## Sistem Data Mining Random Forest PT Maxkomp

---

# 1. Prinsip Utama

Project harus:

- berbasis web,
- ringan,
- dapat berjalan pada device dengan resource rendah,
- tidak menggunakan database,
- tidak menggunakan microservices,
- tidak menggunakan Redis,
- tidak menggunakan message broker,
- tidak menggunakan worker terpisah jika belum diperlukan,
- mudah dijalankan secara lokal,
- mudah dipahami saat sidang,
- memprioritaskan kejelasan alur data mining.

Arsitektur yang digunakan:

```text
React + Vite + TypeScript
          ↓
      HTTP / REST
          ↓
FastAPI + Python
          ↓
Pandas + Scikit-learn
          ↓
Filesystem
```

Model arsitektur:

> **Modular Monolith**

---

# 2. Tech Stack Final

## Frontend

```text
React
Vite
TypeScript
Tailwind CSS
shadcn/ui
Recharts
Axios
React Router
```

### Fungsi

| Teknologi | Fungsi |
|---|---|
| React | UI utama |
| Vite | Dev server dan build |
| TypeScript | Type safety |
| Tailwind CSS | Styling ringan |
| shadcn/ui | Komponen UI |
| Recharts | Grafik |
| Axios | HTTP client |
| React Router | Routing halaman |

---

# 3. Backend

```text
Python
FastAPI
Pydantic
Uvicorn
```

### Fungsi

| Teknologi | Fungsi |
|---|---|
| Python | Bahasa backend dan ML |
| FastAPI | REST API |
| Pydantic | Validasi request/response |
| Uvicorn | ASGI server |

Tidak menggunakan Node.js sebagai backend kedua.

---

# 4. Data Processing

```text
Pandas
NumPy
OpenPyXL
```

### Fungsi

- membaca Excel,
- profiling data,
- missing value analysis,
- duplicate detection,
- cleaning,
- transformasi,
- ekspor Excel,
- feature engineering sederhana.

Untuk ukuran dataset PT Maxkomp saat ini, Pandas sudah lebih dari cukup.

---

# 5. Machine Learning

```text
Scikit-learn
Joblib
```

Komponen utama:

```text
RandomForestClassifier
train_test_split
Pipeline
ColumnTransformer
OneHotEncoder
TfidfVectorizer (jika diperlukan)
classification_report
confusion_matrix
accuracy_score
precision_score
recall_score
f1_score
```

---

# 6. Storage

Tidak menggunakan database.

Gunakan:

```text
Excel
JSON
JSONL
Joblib
Filesystem
```

Struktur:

```text
storage/
└── jobs/
    └── <job_id>/
        ├── raw/
        ├── cleaned/
        ├── labeled/
        ├── model/
        ├── reports/
        ├── predictions/
        └── config/
```

---

# 7. Struktur Project

```text
maxkomp-random-forest/
│
├── README.md
├── ERD.md
├── TECH_STACK.md
├── AGENT.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   │
│   ├── public/
│   │   ├── logo.png
│   │   └── favicon.ico
│   │
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css
│       │
│       ├── api/
│       │   ├── client.ts
│       │   ├── dataset.api.ts
│       │   ├── cleaning.api.ts
│       │   ├── preprocessing.api.ts
│       │   ├── model.api.ts
│       │   └── prediction.api.ts
│       │
│       ├── components/
│       │   ├── layout/
│       │   ├── common/
│       │   ├── dataset/
│       │   ├── cleaning/
│       │   ├── preprocessing/
│       │   ├── model/
│       │   └── prediction/
│       │
│       ├── pages/
│       │   ├── DashboardPage.tsx
│       │   ├── DatasetPage.tsx
│       │   ├── DataUnderstandingPage.tsx
│       │   ├── CleaningPage.tsx
│       │   ├── PreprocessingPage.tsx
│       │   ├── TrainingPage.tsx
│       │   ├── EvaluationPage.tsx
│       │   └── PredictionPage.tsx
│       │
│       ├── hooks/
│       ├── types/
│       └── utils/
│
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   │
│   ├── config/
│   │   ├── customer_mapping.json
│   │   └── technician_mapping.json
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── constants.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   └── routes/
│   │   │       ├── dataset.py
│   │   │       ├── cleaning.py
│   │   │       ├── preprocessing.py
│   │   │       ├── training.py
│   │   │       ├── evaluation.py
│   │   │       ├── prediction.py
│   │   │       └── auth.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── dataset.py
│   │   │   ├── cleaning.py
│   │   │   ├── preprocessing.py
│   │   │   ├── training.py
│   │   │   ├── evaluation.py
│   │   │   └── prediction.py
│   │   │
│   │   ├── services/
│   │   │   ├── dataset_service.py
│   │   │   ├── data_understanding_service.py
│   │   │   ├── export_service.py
│   │   │   │
│   │   │   └── cleaning/
│   │   │       ├── pipeline.py
│   │   │       ├── empty_row_cleaner.py
│   │   │       ├── duplicate_cleaner.py
│   │   │       ├── missing_value_cleaner.py
│   │   │       ├── whitespace_cleaner.py
│   │   │       ├── customer_cleaner.py
│   │   │       ├── technician_cleaner.py
│   │   │       └── date_cleaner.py
│   │   │
│   │   ├── ml/
│   │   │   ├── preprocessing/
│   │   │   │   ├── feature_selector.py
│   │   │   │   ├── feature_engineering.py
│   │   │   │   ├── categorical_encoder.py
│   │   │   │   ├── text_vectorizer.py
│   │   │   │   └── pipeline.py
│   │   │   │
│   │   │   ├── models/
│   │   │   │   └── random_forest.py
│   │   │   │
│   │   │   ├── training/
│   │   │   │   ├── splitter.py
│   │   │   │   ├── trainer.py
│   │   │   │   └── tuning.py
│   │   │   │
│   │   │   └── evaluation/
│   │   │       ├── metrics.py
│   │   │       ├── confusion_matrix.py
│   │   │       └── feature_importance.py
│   │   │
│   │   ├── storage/
│   │   │   ├── file_manager.py
│   │   │   ├── job_manager.py
│   │   │   └── model_manager.py
│   │   │
│   │   └── utils/
│   │       ├── dataframe.py
│   │       ├── excel.py
│   │       ├── validation.py
│   │       └── helpers.py
│   │
│   └── tests/
│       ├── test_cleaning.py
│       ├── test_preprocessing.py
│       ├── test_training.py
│       └── test_prediction.py
│
└── storage/
    └── jobs/
        └── <job_id>/
            ├── raw/
            ├── cleaned/
            ├── model/
            ├── reports/
            ├── predictions/
            └── config/
```

---

# 8. Halaman Utama

Sidebar:

```text
Dashboard

DATA
├── Dataset
├── Data Understanding
├── Data Cleaning
└── Preprocessing

RANDOM FOREST
├── Training
├── Evaluation
└── Prediction
```

Jangan membuat menu yang tidak dibutuhkan.

---

# 9. Endpoint Utama

## Dataset

```text
POST /api/dataset/upload
GET  /api/jobs/{job_id}/dataset/preview
GET  /api/jobs/{job_id}/dataset/summary
```

## Authentication

Tidak ada endpoint authentication pada scope final. Aplikasi berjalan local-only untuk satu operator. Jika scope berubah menjadi multi-user atau akses jaringan, desain authentication harus dibuka kembali sebelum endpoint data diekspos.

## Cleaning

```text
POST /api/jobs/{job_id}/clean
GET  /api/jobs/{job_id}/cleaning-report
```

## Label Dataset Otomatis dan Audit Read-only

```text
GET   /api/jobs/{job_id}/labeling/summary
GET   /api/jobs/{job_id}/labeling/records
GET   /api/jobs/{job_id}/labeling/report
GET   /api/jobs/{job_id}/download/labeled
```

`keputusan_laporan` hanya menerima `SELESAI` atau `TINDAK_LANJUT`.
`NEEDS_REVIEW` disimpan sebagai `labeling_status` dan tidak menjadi target model.
Auto-labeling menggunakan kebijakan deterministik `ai-assisted-id-v1`. Status sumber dan isi laporan menjadi evidence; setiap keputusan mencatat `AI_VALIDATOR`, alasan, confidence, dan versi kebijakan. `Status_Asli` dilarang menjadi fitur model.

Revisi final: tidak ada fitur labeling manual. Workbook siap pakai memiliki 12 kolom sumber
+ 7 kolom target/audit. Upload mengimpor label atau mengidentifikasi workbook mentah otomatis,
menyimpan `reports/input_labels.json` dengan checksum. Cleaning mentransfer label dan merespons
LABELED; berikutnya langsung preprocessing. Mutasi initialize/PATCH/bulk/auto dihapus (404).
GET di atas hanya provenance/backward compatibility. Job lama belum dipreprocess hanya
dilengkapi pada UNLABELED, tanpa overwrite label final/review dan audit. Model/job yang telah
dipreprocess tidak dimigrasikan. Label weak supervision bukan ground-truth manusia independen.

## Preprocessing

```text
POST /api/jobs/{job_id}/preprocess
GET  /api/jobs/{job_id}/preprocessing-report
GET  /api/jobs/{job_id}/download/preprocessed
```

Tahap ini hanya menghasilkan feature frame stateless. `ColumnTransformer` berisi TF-IDF, categorical imputer/one-hot encoder, dan numeric imputer, tetapi learned transformation wajib di-fit pada train set setelah split. Near duplicate menggunakan character n-gram cosine threshold `0.92` untuk customer yang sama dan disimpan sebagai group, bukan dihapus.

## Train/Test Split

```text
POST /api/jobs/{job_id}/split
GET  /api/jobs/{job_id}/split-manifest
GET  /api/jobs/{job_id}/download/split-manifest
```

Split menggunakan `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`. Kandidat holdout dipilih berdasarkan kedekatan rasio 80/20 dan distribusi kelas. `near_duplicate_group_id` wajib terisolasi pada satu sisi dan tidak menjadi fitur model. Tidak ada sampling pada tahap split.

## Training

```text
POST /api/jobs/{job_id}/train
GET  /api/jobs/{job_id}/model-metadata
GET  /api/jobs/{job_id}/download/model
```

Training versi `random-forest-baseline-v1` memakai satu Pipeline berisi `ColumnTransformer` dan `RandomForestClassifier`. Fit hanya menggunakan record train dari `split_manifest.json`; checksum dataset dan manifest diverifikasi sebelum fit. Model dan metadata ditulis atomik, lalu model di-load ulang untuk memastikan hasil prediction konsisten.

## Evaluation

```text
POST /api/jobs/{job_id}/evaluate
GET  /api/jobs/{job_id}/evaluation
GET  /api/jobs/{job_id}/feature-importance
GET  /api/jobs/{job_id}/download/evaluation
GET  /api/jobs/{job_id}/download/feature-importance
```

Evaluation versi `fixed-test-evaluation-v1` memuat model tersimpan tanpa retraining dan hanya menggunakan record test dari split manifest. Artifact memuat accuracy, balanced accuracy, metrik per kelas, classification report, confusion matrix, prediction audit per record, serta checksum model/metadata/split/dataset. MDI feature importance disimpan penuh dengan nama fitur hasil `get_feature_names_out()` dan peringatan bias impurity-based importance.

## Prediction

```text
POST  /api/jobs/{job_id}/predict
GET   /api/jobs/{job_id}/predictions
PATCH /api/jobs/{job_id}/predictions/{prediction_id}/actual-decision
GET   /api/jobs/{job_id}/download/predictions
```

Endpoint `POST .../predict` hanya menerima tanggal, customer, teknisi, dan teks laporan. Fitur turunan dihitung backend lalu Pipeline yang sudah fit menjalankan `predict` dan `predict_proba`; probabilitas dipetakan menggunakan `classes_`. Endpoint tidak pernah memanggil `fit`.

Endpoint `PATCH .../actual-decision` tidak mengubah baris JSONL lama. Endpoint memvalidasi keputusan admin lalu menambahkan event `actual_decision_recorded` baru. Keputusan pertama tidak memerlukan alasan; perubahan keputusan yang sudah tercatat wajib beralasan. GET history merekonstruksi state terbaru dari seluruh event dan menyediakan pagination server-side.

## Download

```text
GET /api/jobs/{job_id}/download/raw
GET /api/jobs/{job_id}/download/cleaned
GET /api/jobs/{job_id}/download/labeled
```

---

# 10. Optimasi untuk Device Low-End

Target utama:

```text
2 CPU core
4 GB RAM
```

Aplikasi sebaiknya masih nyaman digunakan untuk dataset seukuran project ini.

---

## 10.1 Jangan Memuat Seluruh Dataset ke Frontend

Salah:

```text
1541+ row → JSON penuh → React render semuanya
```

Benar:

```text
Backend
  ↓
pagination
  ↓
50 row/page
  ↓
Frontend
```

Gunakan parameter:

```text
?page=1&page_size=50
```

Maksimal default:

```text
50 atau 100 row
```

---

# 11. Pagination Wajib

DataTable tidak boleh render ribuan row sekaligus.

Gunakan server-side pagination.

Contoh response:

```json
{
  "page": 1,
  "page_size": 50,
  "total_rows": 1541,
  "total_pages": 31,
  "items": []
}
```

---

# 12. Hindari State Berlebihan di React

Jangan menyimpan seluruh Excel dalam global state.

Simpan hanya:

```text
job_id
summary
current_page
filter
selected_options
```

Data aktual tetap berada di backend/filesystem.

---

# 13. Hindari Redux Jika Tidak Perlu

Default:

```text
React local state
Context seperlunya
custom hooks
```

Jangan menambahkan Redux/Zustand hanya karena tersedia.

Tambahkan hanya jika state sudah benar-benar kompleks.

---

# 14. Lazy Loading Halaman

Gunakan:

```text
React.lazy
Suspense
```

Halaman seperti Evaluation dan Prediction tidak perlu masuk initial bundle jika belum dibuka.

---

# 15. Chart Ringan

Gunakan Recharts hanya untuk data agregat.

Jangan membuat chart dari setiap row laporan.

Contoh yang benar:

```text
Jumlah laporan per tahun
Jumlah laporan per customer
Distribusi keputusan
Feature importance
Confusion matrix
```

---

# 16. Backend Memory Strategy

Jangan mempertahankan DataFrame besar sebagai global variable.

Pola:

```text
request
↓
load file
↓
process
↓
save result
↓
release object
```

Untuk dataset kecil saat ini pola ini cukup.

---

# 17. Hindari Copy DataFrame Tidak Perlu

Gunakan `.copy()` hanya ketika memang diperlukan.

Hindari membuat banyak salinan DataFrame besar dalam satu pipeline.

---

# 18. Gunakan Chunking Jika Dataset Membesar

Untuk dataset saat ini tidak wajib.

Namun desain utilitas dapat mendukung:

```text
chunksize
```

untuk CSV jika data masa depan jauh lebih besar.

Excel tidak selalu efisien untuk streaming besar.

---

# 19. Random Forest untuk Resource Rendah

Default awal yang aman:

```python
RandomForestClassifier(
    n_estimators=100,
    criterion="gini",
    max_depth=20,
    min_samples_split=2,
    min_samples_leaf=2,
    max_features="sqrt",
    class_weight="balanced",
    bootstrap=True,
    random_state=42,
    n_jobs=1
)
```

Namun pada device rendah:

```text
n_jobs=1 atau 2
```

lebih aman apabila CPU/RAM terbatas.

Jumlah tree tidak perlu ribuan.

Untuk dataset kecil:

```text
100–300 estimators
```

sudah cukup untuk eksplorasi.

---

# 20. Hindari Grid Search Besar

Jangan melakukan:

```text
100 kombinasi × 10 fold
```

pada device rendah.

Gunakan:

```text
manual tuning terbatas
```

atau:

```text
RandomizedSearchCV
```

dengan jumlah iterasi kecil apabila memang diperlukan.

Untuk baseline skripsi:

```text
Random Forest default/baseline
+
beberapa variasi parameter
```

lebih mudah dijelaskan.

---

# 21. Cross Validation

Jika digunakan:

```text
5-fold
```

sudah cukup sebagai default untuk dataset kecil.

Jangan menggunakan nilai fold tinggi tanpa alasan.

---

# 22. Model Persistence

Gunakan Joblib:

```text
model_pipeline.joblib
model_metadata.json
```

`model_pipeline.joblib` adalah satu Scikit-learn Pipeline yang memuat `ColumnTransformer`, seluruh preprocessing, dan `RandomForestClassifier`. Model tidak perlu dilatih ulang setiap kali prediction. `model_metadata.json` menyimpan parameter, kontrak fitur, distribusi train, hash train/test ID, checksum artefak, durasi, hasil verifikasi reload, serta versi Python/scikit-learn/Pandas/NumPy/SciPy/Joblib.

Joblib menggunakan mekanisme pickle dan hanya boleh memuat artefak lokal tepercaya yang dibuat aplikasi. Model lintas versi scikit-learn tidak dianggap kompatibel; gunakan metadata dependency untuk memutuskan apakah retraining diperlukan.

---

# 23. Prediction Harus Memuat Model yang Sudah Ada

Flow:

```text
load model_pipeline.joblib
predict
return result
```

Histori prediction menggunakan event JSONL append-only dengan `event_id` unik. `prediction_created` menyimpan input ternormalisasi, checksum model, probabilities, confidence, serta peringatan rekomendasi. `actual_decision_recorded` menyimpan keputusan final admin, keputusan sebelumnya, alasan, dan role domain `ADMIN_VALIDATOR` dengan `prediction_id` yang sama. Backend merekonstruksi current state tanpa mengubah event lama dan menolak file JSONL yang terpotong atau rantai keputusan yang tidak konsisten.

Prediksi dijalankan setelah teknisi mengisi keluhan dan solusi/tindakan, tetapi sebelum keputusan akhir admin. Teks gabungan keluhan dan solusi sah menjadi fitur; keputusan admin adalah target dan dilarang menjadi fitur.

Bukan:

```text
predict request
↓
training ulang
↓
predict
```

---

# 24. Runtime Lokal dan Docker

Aplikasi hanya berjalan di komputer lokal dan tidak memiliki target deployment. Backend bind ke `127.0.0.1:8000`, frontend ke `127.0.0.1:5173`, dan artifact disimpan pada direktori workspace `storage/`.

Docker bersifat opsional untuk menjalankan test atau menyediakan lingkungan dependency yang konsisten. Jika port container dipublikasikan, mapping host harus tetap menggunakan loopback, misalnya `127.0.0.1:8000:8000`.

Hindari banyak container.

Ideal:

```text
1 backend container
1 lightweight web/static layer
```

Atau satu container jika React static build diserve oleh backend/reverse proxy sederhana.

---

# 25. Logging

Gunakan logging bawaan Python.

Log minimal:

```text
INFO upload
INFO cleaning
INFO preprocessing
INFO training
INFO evaluation
ERROR exception
```

Jangan menyimpan isi seluruh dataset dalam log.

---

# 26. Validation

Backend harus memvalidasi:

```text
file extension
sheet availability
required columns
file size
empty dataset
target availability
class count
NaN / infinite values
```

Frontend hanya membantu UX.

Backend adalah sumber validasi utama.

---

# 27. Batas Upload

Rekomendasi awal:

```text
25 MB
```

dapat disesuaikan.

Jangan menerima file arbitrarily besar tanpa batas.

---

# 28. File Security

Nama file user tidak boleh langsung digunakan sebagai path.

Gunakan nama internal:

```text
dataset.xlsx
dataset_cleaned.xlsx
```

dan simpan nama asli di metadata.

Periode korpus penelitian dikonfigurasi dengan:

```text
DATA_START_DATE=2023-05-03
DATA_CUTOFF_DATE=2026-03-31
```

Tanggal di luar periode ditandai invalid dan hanya dapat dikoreksi dengan bukti serta audit.

Exact duplicate menggunakan SHA-256 dari gabungan canonical customer, tanggal, sorted-set teknisi, nama user, dan teks keluhan/solusi yang telah dinormalisasi. `No_Asli`, file, sheet, dan nomor baris sumber tidak masuk fingerprint. Near duplicate dievaluasi pada preprocessing report, diberi `near_duplicate_group_id`, dan tidak otomatis dihapus.

Record `operationally_empty` adalah record yang tanggal, teknisi, nama user, keluhan/solusi, status, dan pihak yang mengetahui seluruhnya kosong. Record tersebut dikeluarkan dari cleaned dataset, tetap tersedia di raw dataset, dan dicatat dalam audit.

---

# 29. Authentication

Authentication dan session tidak diperlukan dalam scope final karena aplikasi hanya dipakai oleh satu operator di komputer lokal dan tidak akan di-deploy. `ADMIN_VALIDATOR` dan `AI_VALIDATOR` adalah role domain yang direkam dalam audit historical labeling, bukan identitas hasil login.

Runtime native tidak boleh bind ke `0.0.0.0` atau diekspos ke LAN/internet. Bind internal container hanya boleh digunakan bersama publikasi port host ke `127.0.0.1`. Jika kebutuhan berubah menjadi penggunaan bersama atau akses jaringan, authentication, authorization, session security, dan threat review menjadi gate wajib sebelum perubahan tersebut dilakukan.

---

# 30. Dependency Philosophy

Tambahkan library hanya jika ada kebutuhan nyata.

Jangan menambahkan:

```text
Celery
Redis
RabbitMQ
SQLAlchemy
Alembic
PostgreSQL
MongoDB
Kafka
Dask
Spark
Polars
```

untuk versi awal project.

---

# 31. Dependency Minimum Backend

Contoh:

```text
fastapi
uvicorn
pydantic
python-multipart
pandas
numpy
openpyxl
scikit-learn
joblib
```

Opsional:

```text
pytest
httpx
```

untuk testing.

---

# 32. Dependency Minimum Frontend

Contoh:

```text
react
react-dom
react-router-dom
axios
recharts
```

UI:

```text
tailwindcss
shadcn/ui dependencies yang benar-benar digunakan
```

Jangan install seluruh library icon/chart yang tidak dipakai.

---

# 33. Data Mining Flow

```text
RAW
↓
UNDERSTANDING
↓
CLEANING
↓
CLEANED
↓
HISTORICAL LABELING
↓
PREPROCESSING
↓
FEATURES + TARGET
↓
TRAIN / TEST
↓
RANDOM FOREST
↓
EVALUATION
↓
MODEL
↓
PREDICTION
```

---

# 34. Rekomendasi Development

Mulai dari backend.

Urutan:

```text
1. Upload
2. Preview
3. Data Understanding
4. Cleaning
5. Export cleaned
6. Impor/identifikasi label otomatis saat upload dan transfer cleaning (tanpa fitur labeling manual)
7. Preprocessing
8. Train/Test split + split manifest
9. Random Forest pipeline
10. Evaluation
11. Prediction + history
12. Frontend polishing
```

Jangan mulai dari dashboard penuh.

---

# 35. Prinsip Arsitektur

Gunakan:

```text
route
↓
service
↓
domain/data processing
↓
storage
```

Route tidak boleh berisi algoritma cleaning yang panjang.

Service tidak boleh berisi komponen UI.

ML code tidak boleh mengetahui React.

Storage tidak boleh mengetahui logic Random Forest.

---

# 36. Testing Minimum

Wajib ada test untuk:

```text
duplicate cleaning
empty row cleaning
date parsing
customer normalization
technician normalization
train-test split
model training
evaluation metrics
prediction pipeline
exact duplicate fingerprint
operationally empty detection
date cutoff validation
job state transition
prediction history
```

---

# 37. Target Kinerja

Untuk dataset sekitar ribuan baris:

```text
Upload + profiling: beberapa detik atau kurang
Cleaning: beberapa detik atau kurang
Training RF 100 tree: beberapa detik atau kurang
Prediction: hampir instan
```

Jangan menggunakan angka waktu tersebut sebagai hasil penelitian.
Waktu aktual wajib diukur pada hardware pengujian.

---

# 38. Kesimpulan Stack

Final:

```text
FRONTEND
React + Vite + TypeScript
Tailwind CSS
shadcn/ui
Recharts
Axios

BACKEND
Python
FastAPI
Pydantic
Uvicorn

DATA
Pandas
NumPy
OpenPyXL

MACHINE LEARNING
Scikit-learn
Joblib

STORAGE
Filesystem
Excel
JSON
JSONL
Joblib

ARCHITECTURE
Modular Monolith

DATABASE
None
```

Prioritas utama:

> **Sederhana, ringan, dapat diuji, dapat dijelaskan, dan tidak over-engineered.**
