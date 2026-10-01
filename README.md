# PT Maxkomp Random Forest Data Mining System

Aplikasi modular-monolith klasifikasi dataset Excel/CSV umum dan laporan teknisi PT Maxkomp. Backend menggunakan FastAPI, Pandas, dan filesystem. Frontend menggunakan React, Vite, dan TypeScript.

Kontrak terbaru: [pemilihan target dan fitur](docs/dataset-configuration.md). Profil Umum memakai label yang sudah tersedia; preset PT mempertahankan identifikasi otomatis. Tidak ada labeling manual. Job baru tetap UPLOADED sampai konfigurasi valid disimpan, lalu ANALYZED; pengubahan konfigurasi dikunci setelah cleaning. Penjelasan metodologi/angka PT di bawah hanya berlaku untuk preset PT atau job lama, bukan aturan dataset Umum.

Pilihan split 20/80, 25/75, 30/70 dan algoritma RF/DT/SVM linear/KNN tersedia melalui [eksperimen model](docs/model-experiments.md). Satu job dapat memiliki beberapa eksperimen; setelah evaluasi, model untuk prediksi dipilih manual. Artifact/model lama tidak dimigrasikan.

## Status Pengembangan

Alur yang sudah tersedia:

```text
Upload Excel/CSV (UPLOADED)
→ Pilih sheet/pemisah, profil, target dan fitur; simpan konfigurasi (ANALYZED)
→ Understanding
→ Cleaning dan transfer label (alasan dan confidence diaudit)
→ Preprocessing (stateless, leakage guard, near-duplicate grouping)
→ Train/Test Split (stratified, group-aware, reproducible)
→ Random Forest Training (pipeline tunggal, persistensi terverifikasi)
→ Evaluation (fixed test set, metrik per kelas, traceability checksum)
→ Prediction dan History (model tersimpan, JSONL append-only)
```

Frontend workflow tersedia melalui tujuh menu yang memuat dataset/report aktual, aksi processing, export, dan prediction history. Tidak ada menu/tugas labeling manual. Job terakhir dipulihkan melalui GET metadata tanpa mengubah label atau model. Seluruh halaman dipecah sebagai lazy-loaded page chunks.

Pekerjaan berikutnya:

```text
Uji penerimaan operator (UAT) pada workflow lokal dan data operasional nyata
```

Target historical labeling telah dibuat oleh kebijakan `ai-assisted-id-v1` dan dicatat sebagai `AI_VALIDATOR`. Sistem tidak membuat label dummy: setiap keputusan memiliki rule, alasan, confidence, dan audit provenance. Record `NEEDS_REVIEW` tidak digunakan untuk training.

File preset siap upload: `dataset/Data_Berlabel_Gabungan_PT_MAXKOMP.xlsx`. Semua 1.541 baris dan 12 kolom sumber dipertahankan, lalu ditambahkan tujuh kolom target/audit (19 kolom). Raw tidak diubah. Identifikasi/impor PT dilakukan saat konfigurasi preset disimpan, bukan sebelum pemilihan profil. Dataset umum dapat memakai nama sheet/kolom dan kelas lain; lihat [kontrak terbaru](docs/dataset-configuration.md).

Lihat [task.md](task.md) untuk status milestone, [panduan frontend](docs/frontend-workflow.md) untuk penggunaan/UAT, dan [rekonsiliasi cleaning](docs/cleaning-reconciliation.md) untuk penjelasan hasil 1.028 record.

## Alur Data

```text
UPLOAD BERLABEL / AUTO-IDENTIFIED
↓
UNDERSTANDING
↓
CLEANING
↓
CLEANED + LABELED (otomatis)
↓
PREPROCESSING
↓
TRAIN / TEST
↓
RANDOM FOREST
↓
EVALUATION
↓
PREDICTION
```

Status job bergerak melalui state berikut:

```text
UPLOADED → ANALYZED → CLEANED → LABELED
         → PREPROCESSED → TRAINED → EVALUATED
```

Untuk preset PT, `CLEANED` merupakan state internal sebelum transfer label dan respons akhirnya `LABELED`; untuk Umum, respons cleaning adalah `CLEANED`. `LABELING` dipertahankan untuk job PT lama. Job/model lama tidak dimigrasikan atau dilatih ulang. Konfigurasi/label yang berbeda sesudah cleaning memerlukan workbook/job baru.

## Menjalankan Backend

Gunakan Python versi yang didukung dependency proyek. Dari direktori root:

```powershell
python -m venv .venv311
.venv311\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Dokumentasi API tersedia di `http://127.0.0.1:8000/docs`.

Jika Windows Application Control memblokir DLL NumPy/Pandas, gunakan container untuk test dan jalankan backend di lingkungan yang mengizinkan dependency tersebut.

Alternatif backend lokal melalui Docker dari root proyek (jangan menjalankan instance kedua jika port 8000 sudah digunakan):

```powershell
docker build --target runtime -f backend/Dockerfile -t maxkomp-backend-local .
docker run --rm --name maxkomp-backend -p 127.0.0.1:8000:8000 --mount type=bind,source=C:/dev/Data-Mining/storage,target=/app/storage maxkomp-backend-local
```

Bind `0.0.0.0` di dalam container hanya untuk networking container; port pada komputer tetap dipublish secara eksplisit ke loopback. Artifact aktual tetap di folder workspace `storage/`.

## Menjalankan Frontend

Backend harus tersedia pada port `8000`. Di terminal lain:

```powershell
cd frontend
npm install
npm run dev
```

Frontend tersedia di `http://127.0.0.1:5173`. Dev server meneruskan request `/api` ke backend.

Di menu Dataset, upload workbook berlabel baru atau buka job lokal. Dua job aktual sudah `EVALUATED`: `aNvdsL7wjhr7Lqb7TAxd6g` dan `qXWnZIzpXCsSNlGMxGU1jA`. Tombol stage mengikuti gate backend; membuka job tidak mengubah artifact.

## Endpoint Utama

### Dataset dan Cleaning

```text
GET  /health
GET  /api/jobs/{job_id}
POST /api/dataset/upload
GET  /api/jobs/{job_id}/dataset/preview
GET  /api/jobs/{job_id}/dataset/schema
GET  /api/jobs/{job_id}/dataset/configuration
PUT  /api/jobs/{job_id}/dataset/configuration
GET  /api/jobs/{job_id}/dataset/summary
POST /api/jobs/{job_id}/clean
GET  /api/jobs/{job_id}/cleaned/preview
GET  /api/jobs/{job_id}/cleaning-report
GET  /api/jobs/{job_id}/cleaning-report/audit
GET  /api/jobs/{job_id}/download/raw
GET  /api/jobs/{job_id}/download/cleaned
```

`GET /api/jobs/{job_id}` tidak mengubah metadata atau menginisialisasi labeling. Untuk frontend, cleaning report memakai `?include_details=false`, sedangkan detail audit tetap paginated dan audit labeling dapat dibatasi dengan `?limit=25`. Default endpoint lama tetap mempertahankan laporan penuh.

### Audit Label Dataset (read-only)

```text
GET   /api/jobs/{job_id}/labeling/summary
GET   /api/jobs/{job_id}/labeling/records
GET   /api/jobs/{job_id}/labeling/report
GET   /api/jobs/{job_id}/download/labeled
```

Filter record labeling:

```text
ALL | UNLABELED | SELESAI | TINDAK_LANJUT | NEEDS_REVIEW
```

Endpoint initialize, auto, bulk, dan PATCH label sudah dihapus (404). Endpoint GET lama dipertahankan hanya untuk membaca provenance/export, bukan fitur labeling interaktif. Identifikasi workbook mentah menggunakan status sumber dan teks laporan melalui kebijakan `ai-assisted-id-v1`. Status `OK` menjadi bukti kuat `SELESAI` hanya jika tidak ditemukan indikasi tindak lanjut. Frasa kuat seperti pekerjaan belum beres, harus diservis, menunggu, atau dibawa ke teknisi menghasilkan `TINDAK_LANJUT`. Bukti yang tidak cukup menghasilkan `NEEDS_REVIEW`.

Target `keputusan_laporan` hanya boleh berisi:

```text
SELESAI | TINDAK_LANJUT
```

`NEEDS_REVIEW` disimpan pada `labeling_status`, sedangkan `keputusan_laporan` tetap kosong dan record dikeluarkan dari kandidat training. Setiap keputusan otomatis menyimpan role `AI_VALIDATOR`, alasan, confidence, dan versi kebijakan.

Dokumentasi domain dan API lebih rinci tersedia di [historical-labeling.md](docs/historical-labeling.md).

### Preprocessing

```text
POST /api/jobs/{job_id}/preprocess
GET  /api/jobs/{job_id}/preprocessing-report
GET  /api/jobs/{job_id}/download/preprocessed
```

Preprocessing menyimpan fitur stateless dan group ID near-duplicate. TF-IDF, encoder kategori, dan imputer baru di-fit pada train set setelah split. Detailnya tersedia di [preprocessing.md](docs/preprocessing.md).

### Train/Test Split

```text
POST /api/jobs/{job_id}/split
GET  /api/jobs/{job_id}/split-manifest
GET  /api/jobs/{job_id}/download/split-manifest
```

Split memakai `StratifiedGroupKFold`, `random_state=42`, tanpa sampling. Dataset aktual terbagi menjadi 814 train dan 204 test tanpa record/group overlap. Detailnya tersedia di [split-strategy.md](docs/split-strategy.md).

### Random Forest Training

```text
POST /api/jobs/{job_id}/train
GET  /api/jobs/{job_id}/model-metadata
GET  /api/jobs/{job_id}/download/model
```

Training memakai satu Scikit-learn Pipeline yang berisi transformer TF-IDF/OneHot/imputer dan `RandomForestClassifier`. Transformer hanya di-fit pada 814 record train dari split manifest. Baseline aktual memakai 100 pohon, `class_weight='balanced'`, `max_depth=20`, `min_samples_leaf=2`, `n_jobs=1`, dan tanpa grid search. Detail dan batas persistensinya tersedia di [random-forest-training.md](docs/random-forest-training.md).

### Model Evaluation

```text
POST /api/jobs/{job_id}/evaluate
GET  /api/jobs/{job_id}/evaluation
GET  /api/jobs/{job_id}/feature-importance
GET  /api/jobs/{job_id}/download/evaluation
GET  /api/jobs/{job_id}/download/feature-importance
```

Evaluation memakai tepat 204 record test dari split manifest. Baseline job `aNvdsL7wjhr7Lqb7TAxd6g` memperoleh accuracy 98,04%, balanced accuracy 69,75%, dan recall `TINDAK_LANJUT` 40%. Job operator `qXWnZIzpXCsSNlGMxGU1jA` mempunyai recall minoritas 20%; setiap job mengikuti report sendiri. Model belum boleh dianggap andal hanya berdasarkan accuracy dan keluarannya tetap rekomendasi. Detail tersedia di [model-evaluation.md](docs/model-evaluation.md).

### Prediction dan History

```text
POST  /api/jobs/{job_id}/predict
GET   /api/jobs/{job_id}/prediction/schema
GET   /api/jobs/{job_id}/predictions
PATCH /api/jobs/{job_id}/predictions/{prediction_id}/actual-decision
GET   /api/jobs/{job_id}/download/predictions
```

Input prediction Umum berbentuk `{features: {...}}` sesuai schema model. Preset/legacy PT tetap menerima `tanggal`, `customer`, `teknisi`, dan `text_laporan`. Backend memuat model tanpa training ulang dan probabilities mengikuti `classes_`. Keputusan aktual harus kelas model; history JSONL append-only, koreksi wajib beralasan. Lihat [kontrak terbaru](docs/dataset-configuration.md) dan [history PT](docs/prediction-history.md).

## Struktur Artifact Job

```text
storage/jobs/<job_id>/
├── raw/dataset.xlsx
├── cleaned/dataset_cleaned.xlsx
├── labeled/dataset_labeled.xlsx
├── preprocessed/dataset_preprocessed.xlsx
├── reports/data_understanding.json
├── reports/cleaning_report.json
├── reports/input_labels.json
├── reports/labeling_report.json
├── reports/preprocessing_report.json
├── reports/split_manifest.json
├── reports/evaluation.json
├── reports/feature_importance.json
├── model/model_pipeline.joblib
├── model/model_metadata.json
├── predictions/predictions.jsonl
└── config/job.json
    config/dataset_config.json (job baru saja; adapter legacy tidak menulis file)
```

Raw, cleaned, dan labeled dataset tidak pernah ditimpa oleh tahap berikutnya.

## Pengujian

Pengujian yang direkomendasikan:

```powershell
docker build --target test -f backend/Dockerfile -t maxkomp-backend-test .
docker run --rm maxkomp-backend-test
```

Baseline saat dokumen ini diperbarui:

```text
83 passed
```

Test dan build frontend (diverifikasi dengan Node.js 24.14.0):

```powershell
cd frontend
npm test
npm run build
```

Expected: **15 test frontend lulus** dan build berhasil. Backend mencakup regression PT dan dataset Umum: Excel/CSV, binary/multiclass, fitur campuran, train-only, group isolation, konfigurasi/tipe/header invalid, kelas string numerik, history/reload/checksum, serta laporan cleaning lengkap/ringkas dengan mapping kolom. QA memakai storage disposable, tidak mengubah job aktual. Dua warning TestClient/Starlette masih terbuka; dependency tidak dinaikkan.

## Scope Operasional Local-Only

Aplikasi ini diputuskan berjalan **hanya di komputer lokal, untuk satu operator, dan tidak akan di-deploy**. Backend harus tetap bind ke `127.0.0.1:8000` dan frontend ke `127.0.0.1:5173`; jangan mengubah host menjadi `0.0.0.0` atau mengekspos port ke LAN/internet.

Authentication, session, domain publik, reverse proxy, HTTPS, dan konfigurasi deployment tidak termasuk scope saat ini. `ADMIN_VALIDATOR` dan `AI_VALIDATOR` merupakan role domain pada audit historical labeling, bukan akun login. Jika aplikasi kelak akan dipakai bersama atau diakses melalui jaringan, keputusan scope harus dibuka kembali dan authentication wajib diselesaikan terlebih dahulu.
