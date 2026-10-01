# AGENT.md
## AI Development Rules — PT Maxkomp Random Forest Project

Dokumen ini adalah **aturan kerja wajib** untuk AI coding agent yang mengerjakan repository ini.

AI **harus mengikuti dokumen ini** sebelum membuat, mengubah, menghapus, atau memindahkan file.

---

# 1. Project Context

Nama project:

```text
PT Maxkomp Random Forest Data Mining System
```

Judul penelitian:

> **IMPLEMENTASI METODE RANDOM FOREST UNTUK PENGAMBILAN KEPUTUSAN LAPORAN TEKNISI DAN ADMINISTRASI BERBASIS WEB DI PT MAXKOMP**

Arsitektur:

```text
React + Vite + TypeScript
          ↓
        REST API
          ↓
FastAPI + Python
          ↓
Pandas + Scikit-learn
          ↓
Filesystem
```

Database:

```text
TIDAK DIGUNAKAN
```

---

# 2. Tujuan Agent

Agent harus membantu membangun aplikasi yang:

1. menerima dataset Excel,
2. melakukan data understanding,
3. melakukan data cleaning,
4. menghasilkan dataset bersih,
5. melakukan preprocessing,
6. membagi train/test,
7. melatih Random Forest,
8. mengevaluasi model,
9. melakukan prediction,
10. menyimpan artifact ke filesystem.

---

# 3. Rule Paling Penting

## JANGAN HALUSINASI

Agent tidak boleh:

- mengarang nama file,
- mengarang nama kolom,
- mengarang endpoint,
- mengarang nilai statistik,
- mengarang jumlah row,
- mengarang nilai accuracy,
- mengarang konfigurasi yang belum ada,
- mengarang business rule,
- mengarang target classification,
- mengarang requirement user,
- menganggap file ada tanpa mengecek,
- menganggap dependency sudah terpasang tanpa mengecek.

Jika informasi tidak tersedia:

```text
CHECK FIRST
```

Jika tetap tidak tersedia:

```text
STATE THE ASSUMPTION
```

atau:

```text
ASK / LEAVE TODO
```

Jangan membuat fakta palsu agar task terlihat selesai.

---

# 4. Source of Truth Priority

Jika terjadi konflik, gunakan prioritas:

```text
1. Instruksi user terbaru
2. AGENT.md
3. ERD.md
4. TECH_STACK.md
5. Existing codebase
6. Assumption agent
```

Instruksi user eksplisit selalu lebih tinggi daripada asumsi agent.

---

# 5. Wajib Membaca Sebelum Coding

Sebelum melakukan perubahan besar:

```text
1. Baca AGENT.md
2. Baca ERD.md
3. Baca TECH_STACK.md
4. Inspect struktur repository
5. Inspect file terkait
6. Baru lakukan perubahan
```

Jangan langsung membuat file jika file serupa sudah ada.

---

# 6. Jangan Mengubah Arsitektur Tanpa Izin

Arsitektur default:

```text
Frontend: React + Vite + TypeScript
Backend: FastAPI + Python
ML: Scikit-learn
Data: Pandas
Storage: Filesystem
Database: None
```

Agent dilarang menambahkan secara sepihak:

```text
PostgreSQL
MySQL
SQLite
MongoDB
Supabase
Firebase
Redis
Celery
RabbitMQ
Kafka
Node.js backend
NestJS backend
Laravel backend
Django
microservices
```

Jika agent merasa teknologi tersebut diperlukan, agent harus:

```text
1. jelaskan alasannya,
2. jelaskan alternatif tanpa teknologi tersebut,
3. tunggu izin user.
```

---

# 7. Jangan Over-Engineering

Prioritas:

```text
simple
readable
testable
maintainable
```

Bukan:

```text
most complex
most abstract
most enterprise
```

Untuk dataset kecil/ribuan row, jangan memperkenalkan big-data framework.

Dilarang menambahkan Spark, Dask, Kafka, atau distributed compute tanpa requirement eksplisit.

---

# 8. Data Mentah Tidak Boleh Dimodifikasi

Raw dataset harus immutable.

Flow:

```text
raw.xlsx
↓
cleaning
↓
cleaned.xlsx
```

Jangan overwrite:

```text
raw.xlsx
```

dengan hasil cleaning.

---

# 9. Cleaning dan Preprocessing Harus Dipisah

Cleaning meliputi:

```text
empty rows
duplicates
missing values
whitespace
date normalization
customer normalization
technician normalization
basic validity
```

Preprocessing ML meliputi:

```text
feature selection
feature engineering
encoding
vectorization
train-test preparation
```

Jangan mencampur dua proses ini hanya untuk menghemat file.

---

# 10. Kebijakan Label AI-Assisted

Target Random Forest harus berasal dari:

```text
business rule yang telah disetujui
atau
manual labeling yang valid
```

Pemilik aplikasi telah menyetujui identifikasi otomatis menggunakan kebijakan versioned `ai-assisted-id-v1`. Agent boleh menetapkan `SELESAI`, `TINDAK_LANJUT`, atau `NEEDS_REVIEW` hanya melalui rule eksplisit pada `services/auto_labeling.py`. `Eskalasi` bukan kelas target pada scope final.

Revisi final 16 September 2026: tidak ada fitur/tugas labeling manual. Dataset siap pakai
disimpan terpisah di `dataset/Data_Berlabel_Gabungan_PT_MAXKOMP.xlsx`, dengan 12 kolom sumber
utuh + 7 kolom label/audit. Upload mengimpor label; workbook mentah diidentifikasi otomatis.
Cleaning mentransfer label, lalu langsung preprocessing. Pertahankan Needs Review sebagai
status pengecualian, jangan paksa kelas final. Endpoint mutasi labeling dihapus; GET audit
lama tetap read-only. Kelanjutan job lama hanya melengkapi UNLABELED, tidak menimpa keputusan,
audit, model, atau job yang sudah dipreprocess. Koreksi lewat workbook/job baru. Label impor
bukan ground-truth independen yang telah diverifikasi aplikasi.

Target final project telah dikunci sebagai:

```text
keputusan_laporan
├── SELESAI
└── TINDAK_LANJUT
```

- `SELESAI`: laporan dapat ditutup karena tidak ada tindakan teknis atau administratif lanjutan.
- `TINDAK_LANJUT`: laporan belum dapat ditutup karena masih ada tindakan teknis atau administratif yang harus diselesaikan.

Keputusan otomatis wajib mencatat role `AI_VALIDATOR`, alasan, confidence, dan versi kebijakan. Jangan mencatat keputusan otomatis sebagai `ADMIN_VALIDATOR`. Record `NEEDS_REVIEW` tidak boleh masuk training. Status sumber boleh menjadi evidence labeling, tetapi tidak boleh menjadi fitur model. Evaluasi wajib menyatakan bahwa target bersifat weakly-supervised dan bukan ground-truth manusia independen.

---

# 11. Cegah Data Leakage

Sebelum training, agent wajib memeriksa potensi leakage.

Contoh:

Jika target adalah hasil akhir pekerjaan:

```text
keluhan + solusi
```

tidak boleh langsung digunakan jika bagian solusi sudah membocorkan hasil.

Contoh teks leakage:

```text
"printer sudah normal"
"masalah selesai"
"berhasil diperbaiki"
```

Waktu prediksi final project adalah setelah teknisi mengisi keluhan dan solusi/tindakan, tetapi sebelum admin menetapkan keputusan akhir. Karena itu, isi `Keluhan_Solusi_Asli` boleh digunakan sebagai fitur. Keputusan akhir admin adalah target dan tidak boleh masuk ke fitur.

Jika waktu prediksi diubah pada masa depan menjadi sebelum solusi diketahui, fitur solusi wajib dikeluarkan dan metodologi harus ditinjau ulang.

---

# 12. Duplicate Handling Sebelum Split

Urutan wajib:

```text
clean duplicate
↓
preprocessing
↓
train-test split
```

Jangan:

```text
split
↓
remove duplicate
```

karena record sama dapat masuk train dan test.

Exact duplicate ditentukan dari fingerprint SHA-256 atas nilai yang sudah dinormalisasi:

```text
customer
+ tanggal
+ teknisi
+ nama_user
+ keluhan_solusi
```

Aturan fingerprint:

- metadata sumber seperti `No_Asli`, `Sumber_File`, `Sumber_Sheet`, dan `Baris_Sumber` tidak digunakan,
- daftar teknisi dinormalisasi sebagai set yang diurutkan agar urutan nama tidak memengaruhi fingerprint,
- exact duplicate otomatis dikeluarkan dari cleaned dataset dan dicatat dalam audit,
- near duplicate menggunakan character n-gram cosine similarity threshold `0.92` pada customer yang sama. Record hanya diberi `near_duplicate_group_id`, tidak boleh otomatis dihapus, dan seluruh anggota group wajib berada pada split yang sama.

---

# 13. Train-Test Split

Konfigurasi split final:

```text
80% train
20% test
random_state = 42
```

Gunakan `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` dan pilih kandidat holdout terbaik. `near_duplicate_group_id` tidak boleh muncul di train dan test sekaligus. Jangan melakukan oversampling/undersampling pada tahap split. Jika exact stratification tidak dapat dicapai karena constraint group atau jumlah kelas, agent harus mencatat deviasi dan penyebabnya pada manifest.

---

# 14. Random Forest

Model utama project:

```text
RandomForestClassifier
```

Jangan mengganti algoritma utama menjadi:

```text
XGBoost
LightGBM
SVM
Neural Network
Decision Tree
```

kecuali hanya sebagai metode pembanding atau user meminta.

---

# 15. Baseline Model

Default awal:

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
    n_jobs=1,
)
```

Konfigurasi di atas adalah baseline final `random-forest-baseline-v1` untuk perangkat lokal 2 core/4 GB RAM. Pipeline hanya boleh di-fit pada record train yang tercantum di split manifest. Test set dilarang digunakan untuk fit atau pemilihan parameter.

Jangan melakukan tuning ekstrem tanpa alasan.

Model disimpan bersama preprocessing dalam `model_pipeline.joblib`. Selalu simpan `model_metadata.json`, checksum seluruh input/artifact, versi dependency, dan hasil verifikasi load ulang. Karena Joblib berbasis pickle, hanya muat artifact lokal tepercaya dari path job yang dikendalikan aplikasi.

---

# 16. Evaluation Minimum

Untuk classification, wajib menyediakan:

```text
Accuracy
Balanced Accuracy
Precision
Recall
F1-Score
Confusion Matrix
Classification Report
```

Jangan menyimpulkan model bagus hanya berdasarkan accuracy.

Evaluation final hanya menggunakan record test dari `split_manifest.json`. Tetapkan `TINDAK_LANJUT` sebagai positive class, simpan urutan label confusion matrix, dan catat prediction audit per record. Setelah test set dibuka untuk evaluation, jangan mengubah parameter model berdasarkan hasil tersebut; tuning berikutnya harus dilakukan dengan cross-validation pada train set dan menghasilkan versi model baru.

---

# 17. Class Imbalance

Agent wajib memeriksa distribusi target sebelum training.

Jika satu kelas sangat dominan:

```text
report it
```

Jangan menyembunyikan imbalance.

Jangan otomatis menggunakan SMOTE tanpa izin dan tanpa alasan metodologis.

---

# 18. Feature Importance

Jika menampilkan feature importance:

- gunakan nama fitur setelah transformasi,
- jangan memalsukan mapping,
- jangan menampilkan nama fitur yang tidak dapat dilacak kembali.

Jika TF-IDF/OneHot menghasilkan banyak fitur, agent harus menyajikannya dengan hati-hati.

---

# 19. File Storage Contract

Setiap job:

```text
storage/jobs/<job_id>/
```

Isi:

```text
raw/
cleaned/
labeled/
model/
reports/
config/
predictions/
```

Jangan menyimpan file job ke lokasi acak.

---

# 20. Job ID

Agent harus menggunakan identifier unik.

Jangan menggunakan nama customer sebagai directory utama.

Contoh:

```text
storage/jobs/01JQ7M4QABWZ8F6H/
```

---

# 21. Tidak Ada Database

Metadata disimpan sebagai JSON.

Contoh:

```text
config/job.json
reports/cleaning_report.json
reports/labeling_report.json
reports/evaluation.json
```

Jangan diam-diam membuat SQLite hanya karena lebih mudah.

---

# 22. Backend Responsibility

Backend adalah source of truth untuk:

```text
validation
cleaning
preprocessing
training
evaluation
prediction
file storage
```

Frontend tidak boleh melakukan cleaning utama agar logic tidak terduplikasi.

---

# 23. Frontend Responsibility

Frontend hanya:

```text
input
display
navigation
interaction
chart
progress
download
```

Jangan memindahkan Random Forest ke browser.

---

# 24. Route Layer Harus Tipis

Route:

```text
parse request
validate
call service
return response
```

Jangan menaruh 300 baris Pandas logic di route.

---

# 25. Service Layer

Gunakan service untuk orchestration.

Contoh:

```text
route
↓
cleaning service
↓
cleaner modules
↓
storage
```

---

# 26. Cleaning Modules

Simpan cleaning terpisah:

```text
empty_row_cleaner.py
duplicate_cleaner.py
missing_value_cleaner.py
whitespace_cleaner.py
customer_cleaner.py
technician_cleaner.py
date_cleaner.py
```

Jika sebuah rule belum diketahui:

```text
DO NOT INVENT IT
```

Baris dianggap `operationally_empty` jika seluruh field operasional utama kosong:

```text
tanggal
teknisi
nama_user
keluhan_solusi
status
yang_mengetahui
```

Baris tersebut dikeluarkan dari cleaned dataset, tetapi dipertahankan di raw dataset dan dicatat dalam cleaning report. Baris yang masih memiliki informasi operasional tidak boleh dibuang hanya karena sebagian field kosong; tandai sebagai incomplete dan terapkan strategi missing value per field.

---

# 27. Normalization Mapping

Mapping seperti:

```text
PT. ASPAC -> PT ASPAC
```

harus:

- berasal dari data nyata,
- atau rule eksplisit,
- atau config yang dapat dilihat user.

Jangan membuat mapping tersembunyi di banyak file.

Disarankan menyimpan mapping di satu config.

Mapping resmi disimpan terpusat di:

```text
backend/config/customer_mapping.json
backend/config/technician_mapping.json
```

Canonical customer yang disetujui:

```text
PT. ASPAC            -> PT ASPAC
PT. Auto Sukses      -> PT Auto Sukses
PT. Geotech Efathama -> PT Geotech Efathama
PT. KAIROS           -> PT KAIROS
PT.Bina Flora        -> PT Bina Flora
PT.Equator           -> PT Equator
PT.Kelly             -> PT Kelly
PT.Polypackindo      -> PT Polypackindo
PT.SST               -> PT SST
PT.Selera            -> PT Selera
Wellon                -> Wellon
```

Canonical teknisi yang disetujui:

```text
Harrry     -> Harry
Pak Victor -> Victor
```

Whitespace, newline, dan pemisah daftar teknisi dinormalisasi sebelum mapping. Multi-teknisi disimpan sebagai set nama canonical yang diurutkan dengan separator ` | `, misalnya `Eman/Arya` menjadi `Arya | Eman`. Nilai seperti `Abdull` tidak boleh dikoreksi tanpa konfirmasi identitas.

---

# 28. Tidak Boleh Silent Correction

Jika aplikasi memperbaiki:

```text
tanggal
customer
teknisi
status
```

perubahan harus dapat diaudit.

Minimal cleaning report harus menyimpan:

```text
field
old_value
new_value
reason
```

jika correction bersifat non-trivial.

Periode dataset penelitian dikunci pada:

```text
2023-05-03 sampai 2026-03-31
```

Gunakan konfigurasi:

```text
DATA_START_DATE=2023-05-03
DATA_CUTOFF_DATE=2026-03-31
```

Tanggal di luar periode tersebut ditandai invalid untuk korpus penelitian. Jangan mengubah tahun atau tanggal secara otomatis. Koreksi hanya boleh dilakukan jika ada bukti sumber atau keputusan pengguna, serta wajib menyimpan nilai lama, nilai baru, dan alasan.

---

# 29. Missing Value

Jangan selalu menghapus row dengan missing value.

Agent harus menentukan strategi berdasarkan field.

Contoh:

```text
missing target -> biasanya tidak dapat dipakai training
missing optional feature -> bisa diimputasi / kategori Unknown
```

Tetapi keputusan final harus terdokumentasi.

---

# 30. Excel Handling

Gunakan:

```text
Pandas
OpenPyXL
```

Jangan bergantung pada LibreOffice.

Saat membaca file:

- validasi extension,
- validasi sheet,
- validasi header,
- tangani empty file,
- tangani corrupted workbook.

---

# 31. API Response

Response harus konsisten.

Contoh sukses:

```json
{
  "success": true,
  "data": {},
  "message": "Dataset berhasil diproses."
}
```

Contoh gagal:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_DATASET",
    "message": "Kolom wajib tidak ditemukan."
  }
}
```

Jangan expose stack trace ke user.

---

# 32. Jangan Hardcode Statistik

Dilarang:

```python
duplicates = 430
accuracy = 0.92
rows_after = 1034
```

kecuali angka tersebut digunakan sebagai fixture test eksplisit.

Semua nilai produksi harus dihitung dari data.

---

# 33. Jangan Hardcode Prediction

Dilarang:

```python
return "Tindak Lanjut"
```

sebagai hasil dummy pada endpoint production.

Mock hanya boleh berada dalam test/dev fixture yang jelas.

---

# 34. Performance

Target aplikasi harus ringan.

Agent harus menghindari:

```text
loading full dataset to frontend
rendering thousands of rows
training model repeatedly
large grid search
duplicate DataFrame copies
unnecessary background processes
```

---

# 35. Pagination

Preview dataset harus paginated.

Default:

```text
50 row/page
```

Jangan return seluruh dataset jika hanya diminta preview.

---

# 36. Model Loading

Prediction:

```text
load model_pipeline.joblib
predict
```

Jangan retrain model setiap prediction.

Artifact ML final adalah satu Scikit-learn `Pipeline` yang mencakup preprocessing dan `RandomForestClassifier`. Simpan bersama `model_metadata.json`.

---

# 37. Concurrency

Jangan menambahkan Celery/Redis.

Untuk versi awal, proses synchronous cukup selama dataset kecil.

Jika suatu hari training benar-benar berat, baru evaluasi worker terpisah.

---

# 38. Error Handling

Agent harus menangani:

```text
file not found
job not found
missing cleaned dataset
missing model
invalid target
single-class target
insufficient class samples
NaN after transform
model load failure
```

Jangan membiarkan error teknis menjadi HTTP 500 generik jika dapat diberi pesan yang jelas.

---

# 39. Single-Class Guard

Sebelum training:

```python
if y.nunique() < 2:
    reject_training()
```

Pesan harus jelas:

> Target hanya memiliki satu kelas sehingga Random Forest classification tidak dapat dilatih secara valid.

---

# 40. Metrics Guard

Jangan menghitung precision/recall/F1 dengan parameter sembarang tanpa memahami binary vs multiclass.

Untuk multiclass, nyatakan:

```text
macro
weighted
```

secara eksplisit.

---

# 41. Random State

Untuk reproducibility:

```text
random_state = 42
```

sebagai default.

User boleh mengubah jika UI menyediakan parameter.

---

# 42. Testing

Setiap logic penting harus dapat dites.

Minimum:

```text
test_empty_row_cleaning
test_duplicate_cleaning
test_missing_value_handling
test_date_cleaning
test_customer_normalization
test_technician_normalization
test_split
test_training
test_evaluation
test_prediction
```

---

# 43. Jangan Mengubah Test Agar Bug Terlihat Lulus

Jika test gagal karena implementasi salah:

```text
fix code
```

bukan:

```text
weaken test
```

Test hanya boleh diubah jika requirement memang berubah.

---

# 44. Dependency Rule

Sebelum menambah package:

1. cek apakah dependency existing sudah bisa,
2. cek apakah standard library cukup,
3. baru tambahkan dependency.

Jangan install library hanya untuk satu fungsi sederhana.

---

# 45. Security

Minimal:

- sanitize filename,
- batasi ukuran upload,
- jangan execute file user,
- jangan deserialize Joblib dari sumber user,
- Joblib hanya boleh memuat model yang dibuat aplikasi sendiri,
- jangan expose absolute server path ke client.

---

# 46. CORS

Pada development, batasi origin ke frontend development server.

Jangan gunakan:

```text
allow_origins=["*"]
```

untuk runtime lokal; origin harus tetap dibatasi ke frontend lokal yang digunakan.

---

# 47. Secrets

Jangan hardcode:

```text
secret key
API key
password
token
```

Gunakan environment variable.

Project saat ini seharusnya hampir tidak membutuhkan secret eksternal.

Scope final aplikasi adalah local-only untuk satu operator dan tidak untuk deployment atau akses LAN/internet. Authentication dan session tidak perlu diimplementasikan pada scope ini. `ADMIN_VALIDATOR` dan `AI_VALIDATOR` merupakan role domain untuk audit historical labeling, bukan akun login.

Runtime native backend dan frontend harus bind ke loopback (`127.0.0.1`). Bind internal container ke `0.0.0.0` hanya boleh dipakai bila port host dipublikasikan ke `127.0.0.1`. Jangan mempublikasikan port ke LAN/internet atau menambahkan deployment configuration tanpa perubahan requirement. Jika scope berubah menjadi multi-user atau akses jaringan, authentication dan authorization menjadi gate wajib sebelum aplikasi diekspos.

---

# 48. Logging

Log:

```text
job_id
operation
status
duration
error summary
```

Jangan log seluruh isi data customer.

---

# 49. Documentation

Jika membuat endpoint baru, update dokumentasi terkait.

Jika mengubah struktur storage, update:

```text
ERD.md
TECH_STACK.md
AGENT.md jika diperlukan
```

---

# 50. Jangan Mengubah Nama Domain Tanpa Alasan

Gunakan istilah konsisten:

```text
dataset
cleaning
preprocessing
training
evaluation
prediction
job
model
```

Jangan berganti-ganti:

```text
project
session
task
experiment
```

untuk entity yang sama tanpa alasan.

---

# 51. Bahasa

Kode:

```text
English
```

UI dapat menggunakan:

```text
Bahasa Indonesia
```

Contoh:

```python
def remove_duplicates():
    ...
```

UI:

```text
Hapus Data Duplikat
```

Jangan membuat nama function campuran seperti:

```python
hapus_duplicates_data()
```

---

# 52. Type Hints

Backend Python harus menggunakan type hints pada public function sebisa mungkin.

Contoh:

```python
def load_dataset(path: Path) -> pd.DataFrame:
    ...
```

---

# 53. Pydantic

Request/response schema gunakan Pydantic.

Jangan mengirim dictionary acak tanpa kontrak untuk endpoint utama.

---

# 54. Frontend Type Safety

Response API harus memiliki TypeScript type/interface.

Hindari:

```typescript
any
```

jika struktur sudah diketahui.

---

# 55. UI Low-End Rule

Jangan menggunakan:

- heavy animation,
- WebGL,
- 3D background,
- massive shadow effects,
- autoplay video,
- chart terlalu banyak.

UI harus sederhana dan responsif.

---

# 56. Dashboard

Dashboard hanya menampilkan data aktual.

Jika belum ada job:

```text
Empty State
```

bukan dummy metric.

---

# 57. Progress

Untuk proses sinkron kecil:

```text
loading state
```

cukup.

Jangan membuat fake progress 1–100% yang tidak mencerminkan proses aktual.

---

# 58. User Confirmation

Agent tidak perlu bertanya untuk detail kecil yang dapat mengikuti dokumen project.

Namun agent harus berhenti dan meminta arahan jika keputusan akan:

- mengubah algoritma utama,
- menambahkan database,
- mengubah target penelitian,
- menghapus data,
- mengubah business rule,
- melakukan migrasi arsitektur besar.

---

# 59. Preserve Existing Work

Sebelum refactor:

```text
inspect
understand
change minimally
test
```

Jangan rewrite seluruh repository jika hanya satu modul yang bermasalah.

---

# 60. No Fake Completion

Agent tidak boleh mengatakan:

```text
"selesai"
```

jika:

- test belum dijalankan,
- code belum dibuat,
- endpoint masih dummy,
- model masih mock,
- file tidak ada,
- requirement utama belum terpenuhi.

Nyatakan secara spesifik apa yang selesai dan apa yang belum.

---

# 61. Completion Checklist

Sebelum menutup task coding:

```text
[ ] Requirement dipahami
[ ] File terkait sudah dibaca
[ ] Tidak ada arsitektur baru tanpa izin
[ ] Tidak ada dummy production data
[ ] Tidak ada hardcoded metrics
[ ] Error handling ditambahkan
[ ] Test relevan dijalankan
[ ] Lint/type check jika tersedia
[ ] Dokumentasi diupdate bila diperlukan
[ ] Perubahan diringkas dengan jelas
```

---

# 62. Data Science Checklist

Sebelum training:

```text
[ ] Dataset bersih tersedia
[ ] Target tersedia
[ ] Target memiliki >= 2 kelas
[ ] Distribusi kelas diperiksa
[ ] Duplikat ditangani
[ ] Leakage diperiksa
[ ] Feature ditentukan
[ ] Metadata tidak masuk feature
[ ] Preprocessing pipeline fit hanya pada training data
[ ] Train-test split reproducible
```

---

# 63. Preprocessing Leakage Rule

Encoder/vectorizer harus di-`fit` menggunakan training data.

Jangan:

```text
fit preprocessing ke seluruh dataset
↓
split
```

Gunakan:

```text
split
↓
fit preprocessing pada X_train
↓
transform X_train dan X_test
```

Cara terbaik adalah menggunakan Scikit-learn `Pipeline` dan `ColumnTransformer`.

---

# 64. Test Set Rule

Test set hanya untuk evaluasi akhir.

Jangan menggunakan test set berkali-kali untuk memilih parameter sampai overfit terhadap test set.

Jika tuning diperlukan:

```text
train
↓
cross-validation pada train
↓
final test
```

---

# 65. Artifact Compatibility

Model dan preprocessing harus berada dalam satu artifact `model_pipeline.joblib` dari training run yang sama.

Metadata model minimal:

```json
{
  "algorithm": "RandomForestClassifier",
  "random_state": 42,
  "target": "keputusan_laporan",
  "classes": ["SELESAI", "TINDAK_LANJUT"],
  "positive_class": "TINDAK_LANJUT",
  "features": [],
  "created_at": ""
}
```

Selain artifact model, simpan `split_manifest.json` yang sekurang-kurangnya memuat `random_state`, rasio aktual, strategi, hash artifact sumber, seluruh train/test record ID dan group ID, distribusi kelas, serta hasil validasi coverage/overlap.

`dataset_preprocessed.xlsx` hanya menyimpan feature frame stateless, target, dan group ID. Representasi matrix hasil OneHot/TF-IDF tidak boleh diekspor sebagai dataset produksi; dokumentasikan learned transformation melalui preprocessing report, split manifest, metadata model, dan pipeline.

---

# 66. Prediction History

Setiap hasil prediksi disimpan append-only sebagai JSONL:

```text
storage/jobs/<job_id>/predictions/predictions.jsonl
```

Event prediksi minimal:

```json
{
  "event_type": "prediction_created",
  "prediction_id": "",
  "created_at": "",
  "model_id": "",
  "prediction": "SELESAI",
  "confidence": 0.0,
  "actual_decision": null
}
```

Keputusan final admin ditulis sebagai event baru, bukan dengan mengubah baris prediksi lama:

```json
{
  "event_type": "actual_decision_recorded",
  "prediction_id": "",
  "created_at": "",
  "actual_decision": "SELESAI"
}
```

`actual_decision` hanya berasal dari keputusan final admin dan dapat digunakan untuk evaluasi lanjutan. Penulisan JSONL harus aman terhadap concurrent append dan record tidak boleh memuat credential atau data yang tidak diperlukan.

Input prediction hanya menerima `tanggal`, `customer`, `teknisi`, dan `text_laporan`. Fitur `tahun`, `bulan`, `hari_dalam_minggu`, dan `jumlah_teknisi` dihitung backend dengan fungsi yang sama seperti preprocessing. Tolak field tambahan agar target/status sumber tidak dapat masuk ke inference contract.

Map `predict_proba` wajib mengikuti urutan `model.classes_`. Confidence adalah probabilitas untuk kelas yang diprediksi. Peringatan rekomendasi harus mengambil recall kelas positif dari evaluation artifact aktif dan tidak boleh di-hardcode.

Keputusan aktual pertama dapat dicatat tanpa alasan. Jika keputusan aktual diubah, alasan wajib tersedia dan perubahan ditulis sebagai event baru dengan `previous_actual_decision`; jangan pernah menimpa event lama.

---

# 67. Reproducibility

Training config harus disimpan.

Contoh:

```json
{
  "test_size": 0.2,
  "random_state": 42,
  "n_estimators": 100,
  "max_depth": null
}
```

---

# 68. Project Philosophy

Keputusan teknis harus mengikuti urutan:

```text
Correctness
↓
Research validity
↓
Simplicity
↓
Maintainability
↓
Performance
↓
Visual polish
```

Jangan mengorbankan validitas penelitian demi UI yang terlihat canggih.

---

# 69. Final Rule

Jika agent tidak yakin terhadap data, aturan bisnis, atau metodologi:

> **Jangan menebak. Periksa sumber yang tersedia, dokumentasikan ketidakpastian, dan hanya gunakan fakta yang dapat dibuktikan.**
