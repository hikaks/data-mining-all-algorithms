# TASK CONTROL — PT Maxkomp Random Forest Data Mining System

Dokumen ini adalah papan kendali pengembangan proyek. Perbarui checkbox hanya setelah source, artifact, dan pengujian terkait tersedia.

## Status Saat Ini

- Terakhir diperiksa: **17 September 2026**
- Posisi pengembangan: **Tahap 1–12, dataset Umum, Tahap 13 eksperimen model dan perbaikan SVM versi 2 teruji; penerimaan akhir tetap UAT operator**
- Kemajuan milestone: **12 tahap baseline + konfigurasi dataset Umum + eksperimen model; final acceptance proyek belum disahkan**
- Status produk: **seluruh workflow sudah terhubung ke UI lokal; bukan berarti model sudah andal atau UAT telah selesai**
- Scope final: **local-only, satu operator, tidak untuk deployment atau akses melalui LAN/internet**.
- Gate berikutnya setelah QA: UAT upload Excel/CSV → simpan target/fitur → processing → prediksi. Recall mengikuti report model aktif, bukan angka baseline; keluaran tetap rekomendasi.
- Version control: folder proyek **belum menjadi repository Git**.

## Perbaikan SVM — kebijakan parameter versi 2

- [x] Eksperimen SVM baru memakai max_iter=-1; konvergensi tetap wajib sebelum publikasi.
- [x] Parameter berversi: eksperimen/joblib lama kompatibel, tanpa migrasi/penimpaan artifact.
- [x] Metadata mencatat fit_status, iterasi dan batas solver; pesan kegagalan menyebut algoritma yang benar.
- [x] Tindakan UI membuat pengganti SVM gagal dengan rasio/split sama, tanpa mengganti model aktif atau redesign.
- [x] 136 test backend, 20 test frontend, production build lulus.
- [x] Empat algoritma × tiga rasio berhasil dievaluasi pada salinan terisolasi dataset 3.000 baris operator; 14 file asal job QA identik.
- [x] Browser pengganti SVM EVALUATED; server utama dimuat ulang; checksum 96 file operator identik, changed=[], extra=[].
- [ ] UAT operator mencoba SVM baru dan aktivasi manual bila diinginkan.

Bukti: `docs/svm-convergence-qa.md`. Berhasil diproses tidak menjamin akurasi sama; validasi dataset tetap dipertahankan.

### Legenda

- `[x]` selesai dan sudah diverifikasi.
- `[ ]` belum selesai atau belum diverifikasi.
- `BLOCKED` tidak boleh dilanjutkan sebelum keputusan/data prasyarat tersedia.
- `DEFERRED` sengaja ditunda dan alasannya harus tetap terdokumentasi.

## Tahap 13 — Pilihan Split, Algoritma, dan Eksperimen Model

Kontrak: `docs/model-experiments.md`. Bukti verifikasi: `docs/model-experiments-qa.md`.

- [x] Rasio test/train 20/80, 25/75, 30/70; seed 42; tanpa sampling; min dua record/kelas/bagian; group isolation.
- [x] Strategi default kompatibel, SGKF empat fold untuk 25%, GSS 256 kandidat untuk 30%/fallback; rasio aktual ditampilkan.
- [x] RF tetap, DT, SVM linear, KNN; parameter tetap; scaler numerik/kalender SVM/KNN fit train-only; kelas string dan reload terjaga.
- [x] Guard KNN <5 train, SVM belum konvergen, source/config/model/shared-split checksum berubah.
- [x] Storage eksperimen immutable per pilihan, manifest bersama/referensi legacy, status/error terpisah, processing idempotent, pemulihan operasi terputus baca-saja.
- [x] Endpoint create/list/detail/split/train/evaluate/report/download/active; request invalid tidak membuat artifact.
- [x] Dropdown rasio/algoritma, tabel metrik/status/durasi/model aktif, pemilih eksperimen dibedakan dari aktivasi; tujuh menu/gaya lama dipertahankan.
- [x] Evaluation eksplisit dan aktivasi manual dengan konfirmasi; test set berbeda ditandai; SVM/KNN importance tidak tersedia.
- [x] Prediction mengikuti model aktif, confidence sesuai kelas predict() meskipun bukan probabilitas terbesar; history/model/eksperimen asal dan koreksi append-only.
- [x] Adapter Model sebelumnya read-only; endpoint/payload PT lama kompatibel; kegagalan eksperimen baru tidak mengganti model aktif atau menurunkan job.
- [x] Regression backend: 131 test; frontend: 19 test; production build lulus. Seluruh 36 kombinasi profil × rasio × algoritma diuji.
- [x] Browser QA terisolasi Umum/PT/legacy/error, restart loopback 5173/8000, GET kompatibilitas lima job aktual; seluruh 82 file storage identik, QA runtime dihentikan.
- [ ] UAT operator pada pilihan split/algoritma/aktivasi model disahkan.

## Revisi Target dan Fitur Dataset Umum

Kontrak aktif: `docs/dataset-configuration.md`. Revisi historis di bawah berlaku untuk preset/legacy PT; identifikasi/impor label PT kini dilakukan saat konfigurasi preset disimpan, bukan langsung sebelum pilihan profil.

- [x] XLSX/CSV ≤25 MB, UTF-8/BOM, tiga pemisah dan koreksi, sheet/nama kolom bebas.
- [x] Tolak header kosong/duplikat sebelum Pandas mangling; raw byte-identik.
- [x] Gate UPLOADED sampai config valid disimpan; preview raw tetap tersedia.
- [x] Panel target/fitur/jenis, distribusi target kosong, peringatan ID/potensi leakage, tujuh menu/gaya lama tetap dipertahankan.
- [x] Konfigurasi schema-version/revision per job, checksum raw/config, terkunci setelah cleaning.
- [x] Profil Umum terpisah dari kontrak resmi PT, tanpa mapping/cutoff/labeling PT.
- [x] Binary/multiclass, numeric class codes sebagai string, target kosong dikecualikan dengan audit.
- [x] Cleaning terpisah, audit normalisasi, duplicate X+Y, konflik X-identik/Y-berbeda dipertahankan.
- [x] Group-aware 80/20 seed 42, tanpa sampling/overlap, min dua record tiap kelas pada train/test dan error sampel/group kurang.
- [x] Numeric median, kategori kosong eksplisit/OneHot unknown-ignore, TF-IDF per teks, kalender tanggal; learned fit hanya train.
- [x] Random Forest lokal tetap ringan; snapshot/hash config masuk manifest/model metadata; reload diverifikasi.
- [x] Evaluasi kelas dinamis, confusion matrix/per-class/macro/weighted F1/accuracy/balanced accuracy; Umum menyoroti recall terendah, PT TINDAK_LANJUT.
- [x] Schema/form prediksi tersimpan dinamis, target/extra ditolak, classes_/actual/history dinamis, koreksi wajib alasan.
- [x] Adapter PT legacy read-only, payload flat lama didukung, tidak retrain model lama atau upgrade dependency.
- [x] Seluruh 83 test backend (regression PT + Umum), 15 test frontend dan build lulus; dua warning dependency lama masih terbuka.
- [x] QA browser Umum: upload CSV → pilih empat jenis fitur → semua processing → kategori baru/tanggal/missing → actual/koreksi/reload/lock config.
- [x] QA browser preset PT selesai sampai prediction/history; 1.541 raw → 1.028 cleaned → 1.018 kandidat → 814/204 split, tujuh fitur resmi dipertahankan.
- [x] Muat ulang frontend 5173/backend 8000 pada loopback; seluruh checksum 30 artifact/model/history aktual identik sebelum QA dan sesudah restart/GET legacy.
- [x] Bersihkan frontend/container/tab/volume QA disposable; port 5174/8001 tertutup. Container runtime lama disimpan stopped untuk rollback, storage tidak dihapus.
- [ ] UAT operator disahkan (penerimaan akhir, tidak diwakili hasil engineering).

## Perbaikan UAT — Laporan Cleaning Profil Umum

- [x] Reproduksi kegagalan `normalization.source_column_map` pada GET laporan cleaning Excel/CSV setelah POST cleaning berhasil.
- [x] Sesuaikan schema backend dan tipe frontend untuk counter angka serta mapping string-ke-string; counter preset PT tetap kompatibel.
- [x] Test laporan lengkap/ringkas mempertahankan mapping, tidak mengubah artifact/status, dan tetap dapat dilanjutkan preprocessing pada fixture terisolasi.
- [x] Verifikasi runtime GET laporan lengkap/ringkas mengembalikan JSON 200 untuk job Umum dan dua job PT lama; halaman Cleaning & Audit tampil normal.
- [x] Backend lokal dimuat ulang menggunakan image `maxkomp-backend-local-cleaning-report`; versi dependency tidak berubah. Container sebelumnya disimpan stopped sebagai `maxkomp-local-config-before-cleaning-fix` untuk rollback.
- [x] Seluruh 37 path/checksum file storage aktual identik sebelum dan sesudah perbaikan, restart, serta browser QA read-only.
- Job operator `E6dKqqOAEAUlu8FPEuV5Jg` tetap **CLEANED**, 3.000 raw → 2.494 cleaned, 506 duplicate dibuang. Tidak upload/reclean/preprocess/train/evaluate/predict ulang pada job aktual. Tahap berikutnya: preprocessing oleh operator. Bukti: `docs/dataset-configuration-qa.md`.

## Revisi Workflow — Dataset Berlabel, Tanpa Labeling Manual (Historis)

Keputusan pengguna: agent mengidentifikasi data; operator tidak mengerjakan labeling.
File siap upload: `dataset/Data_Berlabel_Gabungan_PT_MAXKOMP.xlsx`.

- [x] Identifikasi seluruh 1.541 baris memakai kebijakan approved `ai-assisted-id-v1`.
- [x] Simpan workbook berlabel dengan 12 kolom sumber + 7 kolom target/audit.
- [x] Verifikasi semua nilai sumber tetap sama; workbook mentah tidak ditimpa.
- [x] Catat alasan, confidence, role AI_VALIDATOR, waktu, dan versi kebijakan.
- [x] Bukti tidak cukup ditandai Needs Review, bukan dipaksakan menjadi kelas model.
- [x] Upload berlabel mengimpor label; upload mentah mengidentifikasi otomatis.
- [x] Simpan snapshot `reports/input_labels.json` beserta checksum sumber.
- [x] Cleaning mentransfer label dan langsung menghasilkan status LABELED.
- [x] Tolak metadata label invalid/parsial dan exact duplicate dengan label bertentangan.
- [x] Hapus menu/halaman/action labeling manual dan endpoint initialize/single/bulk/auto.
- [x] Pertahankan GET audit/export untuk provenance dan job lama (read-only).
- [x] Langsung preprocessing setelah cleaning, tanpa tugas labeling.
- [x] Kelanjutan job lama hanya melengkapi UNLABELED; label final/review dan audit lama tetap utuh.
- [x] Test kompatibilitas job CLEANED lama dan penolakan artifact label parsial.
- [x] Verifikasi workbook nyata lewat upload → cleaning → preprocessing di storage sementara.
- [x] 58 test backend, 11 test frontend, dan production build tujuh page chunk lulus.
- [x] QA browser: label input langsung muncul, tujuh menu tanpa labeling, cleaning → preprocessing berhasil (1.018 kandidat).
- [x] Backend utama dimuat ulang pada loopback 8000; seluruh 30 file artifact dua job operator tetap identik checksum.
- [x] Workspace lama EVALUATED dibuka melalui browser tanpa mutasi; ringkasan label/export tetap tersedia.
- [x] QA sementara dibersihkan; port 5174/8001 tertutup, server utama 5173/8000 tetap berjalan.
- [x] Audit dependency frontend produksi menemukan 0 vulnerability; compileall backend lulus.
- [ ] UAT operator disahkan; ini tetap gate penerimaan, bukan tugas labeling.

Distribusi workbook upload: **1.424 SELESAI, 36 TINDAK_LANJUT, 81 NEEDS_REVIEW**.
Setelah cleaning: **1.003 SELESAI, 23 TINDAK_LANJUT, 2 NEEDS_REVIEW** (1.028 total).
Preprocessing: **995 SELESAI + 23 TINDAK_LANJUT = 1.018 kandidat**; dua review
dan delapan tanggal invalid dikecualikan dengan audit. Tidak ada langkah manual tambahan.
Panduan file: `dataset/README.md`. Label tetap weak supervision, bukan ground-truth manusia independen.

## Baseline Implementasi Tahap 1–12 (Historis)

Dataset: `dataset/Data_Mentah_Gabungan_PT_MAXKOMP.xlsx`

| Pemeriksaan | Hasil |
|---|---:|
| Sheet | `DATA_MENTAH` |
| Baris mentah | 1.541 |
| Kolom | 12 |
| Baris setelah cleaning | 1.028 |
| Operationally-empty dihapus | 77 |
| Exact duplicate dihapus | 436 |
| Tanggal invalid | 8 |
| Record incomplete | 641 |
| `yang_mengetahui` kosong | 638 |
| Label final `keputusan_laporan` tersedia | 1.026 |
| `NEEDS_REVIEW` | 2 |
| Near duplicate | 24 group / 50 pasangan, 0 konflik label |

Verifikasi teknis terakhir:

- `[x]` Docker test image berhasil dibangun.
- `[x]` Seluruh **58 test** backend lulus setelah revisi workflow, di Python 3.11 container (dua warning dependency masih tercatat).
- `[x]` Seluruh **11 test** frontend lulus di Node.js 24.14.0.
- `[x]` Python `compileall` lulus.
- `[x]` Upload dataset asli melalui API berhasil: HTTP 201.
- `[x]` Cleaning dataset asli melalui API berhasil: HTTP 200.
- `[x]` Preview cleaned dan cleaning report dataset asli berhasil dibaca.
- `[x]` Inisialisasi historical labeling dahulu berhasil; langkah ini sekarang dihapus/diganti label saat upload dan cleaning.
- `[x]` AI-assisted identification memproses 1.028 record dengan 1.026 target final dan 2 `NEEDS_REVIEW`.
- `[x]` Preprocessing dataset aktual menghasilkan 1.018 record tanpa null pada kontrak output.
- `[x]` Split manifest aktual mencakup 1.018 record dengan record/group overlap 0.
- `[x]` Frontend production build berhasil dan audit npm menemukan 0 vulnerability.
- `[x]` UI diverifikasi di browser dengan dataset aktual: progress, pagination, filter, evidence, dan empty state tampil dengan benar.
- `[x]` QA historis Tahap 12: upload HTTP → cleaning → labeling/auto → preprocessing → split → training → evaluation → prediction → actual decision/koreksi. Revisi workflow terbaru tidak memakai labeling/auto.
- `[x]` Guard UI: prediksi sebelum evaluation terkunci, input whitespace ditolak, koreksi actual tanpa alasan tidak dapat disimpan, focus dialog tetap terperangkap dan Escape menutup dialog.
- `[x]` Layout desktop dan viewport kecil diperiksa; pagination raw memuat 25 record, dan tidak ada horizontal overflow halaman pada viewport kecil.
- `[x]` Job aktual tetap `EVALUATED`, model `RF-46320A252D2C7AC4` tidak ditimpa, dan prediction history aktual tetap kosong.
- `[x]` Lingkungan QA sementara dibersihkan; port 5174/8001 tertutup dan aplikasi utama tetap tersedia pada loopback 5173/8000.
- `[ ]` Test native Windows belum dapat dijalankan karena Application Control memblokir DLL Pandas/NumPy. Gunakan container sampai kebijakan/runtime tersebut diselesaikan.

## Aturan Wajib Pengembangan

- Dataset mentah tidak boleh dimodifikasi atau ditimpa.
- Cleaning dan preprocessing harus tetap menjadi dua tahap terpisah.
- Jangan membuat label `SELESAI` atau `TINDAK_LANJUT` tanpa rule yang dapat diuji dan diaudit.
- Target berasal dari business rule AI-assisted `ai-assisted-id-v1` yang telah disetujui pemilik aplikasi atau koreksi manual tervalidasi.
- Status sumber boleh menjadi evidence labeling, tetapi tidak boleh menjadi fitur model.
- `NEEDS_REVIEW` disimpan sebagai status review, bukan kelas target Random Forest.
- `yang_mengetahui` bersifat opsional untuk kelayakan training dan nama orang tidak boleh diimputasi.
- Jangan menggunakan target atau metadata sumber sebagai fitur model.
- Exact duplicate harus dibuang sebelum train/test split.
- Split harus berdasarkan `record_id` dan disimpan dalam `split_manifest.json`.
- Preprocessing dan model harus disimpan sebagai satu Scikit-learn Pipeline.
- Prediction history harus append-only; event lama tidak boleh diubah.
- Backend tetap menjadi source of truth untuk validasi dan data processing.
- Jangan menambahkan database, Redis, message broker, atau microservice tanpa perubahan requirement yang disetujui.

---

## Tahap 1 — Upload Dataset

Status: **SELESAI**

- [x] Endpoint `POST /api/dataset/upload` tersedia.
- [x] Hanya menerima extension `.xlsx`.
- [x] Batas upload 25 MB diterapkan.
- [x] Sheet `DATA_MENTAH` divalidasi.
- [x] Dua belas header wajib dan urutannya divalidasi.
- [x] Empty/corrupt workbook ditangani dengan error API.
- [x] Nama file pengguna tidak dipakai sebagai path penyimpanan.
- [x] File mentah disimpan sebagai `storage/jobs/<job_id>/raw/dataset.xlsx`.
- [x] Upload gagal tidak meninggalkan job setengah jadi.
- [x] Dataset asli 1.541 baris berhasil di-upload.

Acceptance criteria: **terpenuhi**.

## Tahap 2 — Preview Dataset

Status: **SELESAI**

- [x] Endpoint preview raw tersedia.
- [x] Server-side pagination tersedia.
- [x] Default page size 50 dan maksimum 100.
- [x] Nilai tanggal dan null aman untuk response JSON.
- [x] Dataset penuh tidak dikirim sekaligus ke client.

Acceptance criteria: **terpenuhi**.

## Tahap 3 — Data Understanding

Status: **SELESAI**

- [x] Jumlah baris dan kolom dihitung dari dataset aktual.
- [x] Missing value per kolom dihitung.
- [x] Unique value per kolom dihitung.
- [x] Raw duplicate dihitung.
- [x] Operationally-empty record dihitung.
- [x] Distribusi tahun, customer, teknisi, dan status tersedia.
- [x] Minimum/maksimum dan validitas periode tanggal tersedia.
- [x] Report disimpan sebagai `data_understanding.json`.
- [x] Tidak ada statistik produksi yang di-hardcode.

Acceptance criteria: **terpenuhi**.

## Tahap 4 — Data Cleaning

Status: **SELESAI UNTUK CORE CLEANING**

- [x] Raw dataset tetap utuh.
- [x] Operationally-empty record dihapus dari cleaned dataset dan dicatat dalam audit.
- [x] Whitespace dan newline dinormalisasi.
- [x] Customer dinormalisasi melalui file mapping.
- [x] Teknisi dinormalisasi, dideduplikasi, dan diurutkan.
- [x] Tanggal dinormalisasi dan diperiksa terhadap periode penelitian.
- [x] Tanggal invalid dipertahankan dengan flag/reason, bukan dikoreksi diam-diam.
- [x] Exact duplicate menggunakan fingerprint canonical SHA-256.
- [x] Metadata sumber tidak masuk fingerprint duplicate.
- [x] Incomplete record dipertahankan dan ditandai.
- [x] Cleaning report menyimpan operasi dan keputusan cleaning.
- [x] Re-cleaning bersifat deterministik dalam test.
- [x] Cleaning dataset asli menghasilkan 1.028 baris.
- [x] Metode near duplicate ditetapkan: character n-gram cosine similarity threshold `0.92`, customer sama.
- [x] Evaluasi near duplicate menghasilkan 24 group/50 pasangan; tidak ada penghapusan otomatis atau konflik label.
- [x] `yang_mengetahui` diputuskan opsional untuk kelayakan training; 638 hasil cleaning kosong pada field ini dan tidak dibuang otomatis.

Acceptance criteria cleaning dan near-duplicate grouping: **terpenuhi**.

## Tahap 5 — Export dan Audit Cleaned Dataset

Status: **SELESAI**

- [x] Cleaned dataset disimpan sebagai `cleaned/dataset_cleaned.xlsx`.
- [x] Sheet output menggunakan `DATA_CLEANED`.
- [x] Endpoint download raw tersedia.
- [x] Endpoint download cleaned tersedia.
- [x] Endpoint preview cleaned tersedia dan paginated.
- [x] Endpoint cleaning report tersedia.
- [x] Endpoint audit detail tersedia dan paginated.
- [x] Raw file terverifikasi tidak berubah setelah cleaning.

Acceptance criteria: **terpenuhi**.

---

## Tahap 6 — Historical Labeling

Status: **SELESAI HISTORIS — DIGANTIKAN IMPOR/IDENTIFIKASI LABEL OTOMATIS SAAT UPLOAD**

Checkbox tahap ini mencatat implementasi historis. Fitur interaktif single/bulk/auto dan
UI labeling telah dipensiunkan sesuai revisi workflow di atas; tidak perlu dijalankan lagi.

Seluruh record telah diidentifikasi oleh kebijakan versioned dan diaudit. Pada akhir Tahap 6 state masih `LABELING`, sehingga dua record `NEEDS_REVIEW` tidak dianggap sebagai target final. Record tersebut kemudian dikeluarkan dari kandidat training secara audit pada Tahap 7; state terkini sudah `EVALUATED`.

### Job dataset aktual

- Job ID: `aNvdsL7wjhr7Lqb7TAxd6g`
- Dataset sumber: `dataset/Data_Mentah_Gabungan_PT_MAXKOMP.xlsx`
- Hasil cleaning: **1.028 record** dari 1.541 baris sumber.
- Hasil identifikasi: **1.003 `SELESAI`, 23 `TINDAK_LANJUT`, 2 `NEEDS_REVIEW`**.
- Record training-eligible: **1.026 / 1.028 (99,81%)**.
- Status setelah Tahap 6 sempat `LABELING` karena dua record `NEEDS_REVIEW`; setelah pengecualian preprocessing, training, dan evaluation, status job sekarang `EVALUATED`.
- Runtime lokal: backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:5173`.

### Keputusan yang harus disetujui

- [x] Sumber target ditetapkan sebagai weak supervision dari business rule `ai-assisted-id-v1` yang disetujui pemilik aplikasi.
- [x] Validator otomatis ditetapkan sebagai `AI_VALIDATOR`; koreksi manual tetap `ADMIN_VALIDATOR`.
- [x] Dua kelas final dikunci: `SELESAI` dan `TINDAK_LANJUT`.
- [x] `NEEDS_REVIEW` ditetapkan sebagai status sementara dan bukan kelas model.
- [x] Status sumber ditetapkan sebagai evidence kebijakan labeling dan dilarang menjadi fitur model.
- [x] Record incomplete tetap dapat dilabeli; field administrasi opsional tidak otomatis menggugurkan record.
- [x] Definisi operasional label dan kebijakan audit didokumentasikan di `docs/historical-labeling.md`.

### Implementasi yang harus dibuat

- [x] Buat `labeled/dataset_labeled.xlsx` yang mempertahankan `record_id`.
- [x] Buat `reports/labeling_report.json` dengan event audit.
- [x] Validasi input label hanya menerima `SELESAI`, `TINDAK_LANJUT`, atau `NEEDS_REVIEW`.
- [x] Pastikan `NEEDS_REVIEW` tidak ditulis ke `keputusan_laporan`.
- [x] Simpan role validator dan waktu keputusan untuk audit.
- [x] Wajibkan alasan saat mengubah keputusan final yang sudah ada.
- [x] Raw dan cleaned artifact tidak ditimpa oleh labeling.
- [x] Ringkasan progress, distribusi kelas, dan training gate tersedia.
- [x] Endpoint single/bulk dahulu tersedia; sekarang dihapus (404).
- [x] Endpoint/tombol UI auto dahulu tersedia; sekarang diganti identifikasi saat upload.
- [x] Alasan, confidence, validator role, dan versi kebijakan disimpan per record dan event audit.
- [x] Filter `ALL`, `UNLABELED`, `SELESAI`, `TINDAK_LANJUT`, dan `NEEDS_REVIEW` tersedia.
- [x] Export `dataset_labeled.xlsx` tersedia.
- [x] Tambahkan test initialize, single, bulk, auto, review, invalid label/record, idempotency, relabel reason, state lock, dan download.
- [x] UI historical labeling dahulu diverifikasi; sekarang dihapus, tujuh menu tersisa.

### Acceptance criteria

- [x] Seluruh record training-eligible mempunyai label dari kebijakan tervalidasi.
- [x] Tidak ada label otomatis tanpa rule, alasan, confidence, dan audit provenance.
- [x] Distribusi kelas diketahui: 1.003 `SELESAI` dan 23 `TINDAK_LANJUT`; imbalance wajib ditangani pada split/evaluasi.
- [x] Artifact labeled dataset dan audit dapat direproduksi oleh test dan API aktual.
- [x] Pemilik aplikasi menyetujui AI-assisted identification dan pengecualian `NEEDS_REVIEW` dari training.

## Tahap 7 — Preprocessing

Status: **SELESAI**

- [x] Tentukan fitur final dan alasan pemilihannya.
- [x] Keluarkan `record_id`, nomor/file/sheet/baris sumber, target, status sumber, dan metadata audit dari fitur.
- [x] Audit potensi leakage dari teks dan dokumentasikan batas weak supervision.
- [x] Buat feature engineering tahun, bulan, hari dalam minggu, dan jumlah teknisi.
- [x] Buat factory `ColumnTransformer` untuk fitur kategori, numerik, dan teks.
- [x] Tangani missing value secara eksplisit di pipeline train-only.
- [x] Tambahkan guard NaN/infinite dan test fit-train/transform-test.
- [x] Simpan `preprocessed/dataset_preprocessed.xlsx` dan `preprocessing_report.json`.
- [x] Tambahkan test preprocessing, idempotency, state lock, download, dan leakage guard.

Hasil aktual: 1.018 record output; 2 `NEEDS_REVIEW` dan 8 tanggal di luar periode dikeluarkan. Target menjadi 995 `SELESAI` dan 23 `TINDAK_LANJUT`. Tidak ada nilai null pada kontrak output. Learned transformer belum di-fit agar vocabulary/statistik test tidak bocor sebelum split.

Acceptance criteria: **terpenuhi melalui factory pipeline dan test train-only**. Fitting produksi dilakukan setelah split pada Tahap 8/9.

## Tahap 8 — Train/Test Split dan Split Manifest

Status: **SELESAI**

- [x] Split dilakukan setelah exact duplicate dibuang dan near-duplicate group tersedia.
- [x] Gunakan `random_state=42`.
- [x] Gunakan `StratifiedGroupKFold` untuk stratification dan group isolation.
- [x] Tetapkan requested test size 20%; hasil aktual 204/1.018 atau 20,039293%.
- [x] Pastikan satu `record_id` tidak muncul di train dan test.
- [x] Pastikan satu `near_duplicate_group_id` tidak muncul di kedua sisi.
- [x] Simpan `split_manifest.json` berisi seluruh train/test record ID, group ID, konfigurasi, distribusi, hash, dan validasi.
- [x] Tambahkan test determinisme, idempotency, coverage, group isolation, dan download.

Hasil aktual: train 814 record (796 `SELESAI`, 18 `TINDAK_LANJUT`) dan test 204 record (199 `SELESAI`, 5 `TINDAK_LANJUT`). Record overlap 0, group overlap 0, missing record 0, sampling `NONE`.

Acceptance criteria: **terpenuhi**. Split dapat direproduksi persis dari manifest dengan seed dan kandidat yang sama.

## Tahap 9 — Random Forest Training

Status: **SELESAI**

- [x] Buat satu Scikit-learn Pipeline berisi preprocessing dan `RandomForestClassifier`.
- [x] Gunakan baseline parameter yang ringan untuk device 2 core/4 GB RAM.
- [x] Hindari grid search besar.
- [x] Validasi target tersedia dan memiliki kelas yang cukup.
- [x] Simpan `model_pipeline.joblib`.
- [x] Simpan `model_metadata.json`.
- [x] Simpan parameter, fitur, label, waktu training, dan versi dependency.
- [x] Tambahkan test training pada fixture kecil.

Hasil aktual: model `RF-46320A252D2C7AC4` dilatih pada 814 record train (796 `SELESAI`, 18 `TINDAK_LANJUT`) dengan `class_weight='balanced'`, 100 pohon, `max_depth=20`, `min_samples_leaf=2`, `n_jobs=1`, dan tanpa hyperparameter search. Pipeline menghasilkan 6.378 fitur tertransformasi; test set 204 record tidak digunakan saat fit.

Acceptance criteria: **terpenuhi**. Model dapat di-load ulang, checksum terverifikasi, dan menghasilkan prediction tanpa training ulang.

## Tahap 10 — Evaluation

Status: **SELESAI**

- [x] Hitung accuracy.
- [x] Hitung precision, recall, dan F1.
- [x] Positive class ditetapkan sebagai `TINDAK_LANJUT`.
- [x] Simpan confusion matrix.
- [x] Simpan classification report.
- [x] Simpan feature importance dengan penjelasan keterbatasannya.
- [x] Evaluasi hanya menggunakan test set dari split manifest.
- [x] Simpan `evaluation.json`.
- [x] Tambahkan test perhitungan metric.

Hasil aktual pada 204 record test: accuracy `0,98039216`, balanced accuracy `0,69748744`, precision `TINDAK_LANJUT` `0,66666667`, recall `0,4`, dan F1 `0,5`. Confusion matrix dengan urutan label `[SELESAI, TINDAK_LANJUT]` adalah `[[198, 1], [3, 2]]`. Model melewatkan 3 dari 5 kasus tindak lanjut dan menghasilkan 1 false positive.

Acceptance criteria: **terpenuhi**. Evaluation ditelusuri melalui checksum model, metadata, split manifest, dataset, serta test record ID; laporan menyertakan balanced accuracy dan metrik per kelas.

## Tahap 11 — Prediction dan Prediction History

Status: **SELESAI**

- [x] Endpoint prediction memuat model tersimpan tanpa training ulang.
- [x] Input prediction menggunakan kontrak yang tervalidasi.
- [x] Response berisi kelas, confidence, dan probabilities.
- [x] Simpan event `prediction_created` ke JSONL append-only.
- [x] Implementasikan pencatatan keputusan aktual admin.
- [x] Simpan event `actual_decision_recorded` tanpa mengubah event lama.
- [x] Rekonstruksi current state berdasarkan event history.
- [x] Tambahkan test prediction, invalid input, missing model, dan append-only history.

Hasil aktual: inference versi `model-pipeline-inference-v1` memuat model yang checksum dan versi dependency-nya cocok, memetakan probabilities berdasarkan `classes_`, serta menyimpan histori ke `predictions/predictions.jsonl`. Keputusan aktual pertama dapat dicatat tanpa alasan; perubahan keputusan berikutnya wajib beralasan dan selalu menambah event baru. History job aktual masih kosong karena tidak ada data prediksi bisnis yang dibuat secara dummy.

Acceptance criteria: **terpenuhi melalui test terisolasi**. Prediction berulang tidak mengubah model; setiap event baru mempertahankan seluruh byte histori lama sebagai prefix append-only.

## Tahap 12 — Frontend

Status: **SELESAI — WORKFLOW UI LOKAL TERINTEGRASI**

- [x] Inisialisasi React + Vite + TypeScript.
- [x] Buat layout dan navigasi sesuai menu yang disetujui.
- [x] Buat halaman Dataset dan upload state.
- [x] Buat Data Understanding dan chart agregat.
- [x] Buat Cleaning, report, audit, serta download.
- [x] UI Historical Labeling dahulu dibuat; sekarang dipensiunkan, ringkasan label/export ada di Dataset.
- [x] Buat halaman Preprocessing.
- [x] Buat halaman Training dan progress/error state (indeterminate, tanpa persentase palsu).
- [x] Buat halaman Evaluation dengan recall minoritas, confusion matrix, metrik per kelas, dan batas interpretasi.
- [x] Buat halaman Prediction, probabilities, history, serta actual decision/koreksi beralasan.
- [x] Gunakan server-side pagination; frontend hanya memuat 25 record per halaman.
- [x] Gunakan lazy loading; setelah penghapusan labeling tersisa tujuh halaman React.lazy/Suspense.
- [x] State labeling dahulu tersedia; kini memakai ringkasan impor/identifikasi pada Dataset.
- [x] Aksi identifikasi UI dahulu tersedia; kini berjalan otomatis saat upload.
- [x] Verifikasi production build frontend.
- [x] Hubungkan job melalui GET metadata tanpa menginisialisasi atau membuka kembali labeling.
- [x] Tambahkan 11 test frontend untuk API, multipart upload, error, batas file, whitespace, dan guard alasan.
- [x] Verifikasi workflow browser pada storage QA yang terisolasi dari job aktual.

Acceptance criteria implementasi: **terpenuhi**. Seluruh alur dapat digunakan dari UI; upload multipart diverifikasi oleh test frontend dan API, sedangkan aksi setelah upload hingga koreksi actual diverifikasi di browser QA. Panduan dan batas verifikasi ada di `docs/frontend-workflow.md`. UAT pemilik aplikasi tetap merupakan gate terpisah yang belum selesai.

---

## Pekerjaan Lintas Tahap

### P0 — Harus Diselesaikan Sebelum Melanjutkan ML

- [x] Selesaikan Historical Labeling melalui `AI_VALIDATOR` sesuai delegasi final pemilik aplikasi.
- [x] Pastikan target valid, memiliki dua kelas, dan distribusinya tercatat.
- [x] Putuskan perlakuan record incomplete dan `yang_mengetahui` opsional.

### P1 — Koreksi Backend dan Dokumentasi

- [x] Perbaiki regresi status job dan gunakan state `UPLOADED → ANALYZED → CLEANED → LABELING → LABELED → PREPROCESSED → TRAINED → EVALUATED`.
- [x] Perbarui `README.md` dengan alur penuh, endpoint labeling, artifact, dan batas keamanan.
- [x] Tambahkan endpoint GET `/api/jobs/{job_id}` untuk pembacaan metadata/status dan ketersediaan artifact tanpa mutasi.
- [x] Tambahkan test untuk batas ukuran upload.
- [x] Tambahkan test corrupted workbook.
- [x] Tambahkan test agar membaca summary tidak menurunkan status job dan cleaning terkunci setelah labeling dimulai.

### P1 — Scope Local-Only dan Batas Keamanan

- [x] Tetapkan aplikasi untuk satu operator di komputer lokal.
- [x] Keluarkan authentication/session dari scope saat ini.
- [x] Keluarkan deployment, domain publik, reverse proxy, dan HTTPS dari scope saat ini.
- [x] Dokumentasikan perintah backend dengan bind eksplisit ke `127.0.0.1`.
- [x] Pertahankan `ADMIN_VALIDATOR` sebagai role domain untuk audit labeling, bukan akun login.
- **N/A saat ini:** jika scope berubah menjadi multi-user/LAN/internet, buka kembali pekerjaan authentication sebelum aplikasi diekspos.

### P2 — Engineering Lokal

- [ ] Inisialisasi Git repository setelah struktur awal disetujui.
- [ ] Buat commit baseline sebelum pengembangan tahap berikutnya.
- [x] Dokumentasikan cara menjalankan frontend dan backend saat development.
- [ ] Tambahkan health/readiness verification.
- [ ] Pin dependency lebih ketat untuk reproduksibilitas penelitian lokal.
- [ ] Tinjau dua dependency deprecation warning dari TestClient/Starlette.

Deployment configuration dan persistent volume eksternal berstatus **N/A** karena aplikasi local-only. Artifact tetap disimpan di direktori workspace `storage/`.

## Urutan Kerja Berikutnya

Kerjakan dalam urutan berikut dan jangan melompati gate:

1. Lakukan UAT operator mengikuti checklist `docs/frontend-workflow.md`; jangan mengisi job aktual dengan data dummy.
2. Catat masalah UX atau kontrak input yang ditemukan dan perbaiki secara scoped.
3. Kumpulkan keputusan aktual pada data operasional baru untuk validasi independen, bukan menganggap weak-supervision accuracy sebagai ground-truth.
4. Jika kualitas model hendak ditingkatkan, buat milestone eksperimen terpisah; jangan menimpa baseline model/manifest/evaluation yang telah diaudit.
5. Selesaikan engineering lokal yang masih terbuka (version control, pin dependency, readiness, warning) sesuai prioritas yang disetujui.

## Perintah Verifikasi

### Test backend melalui Docker

```powershell
docker build --target test -f backend/Dockerfile -t maxkomp-backend-test .
docker run --rm maxkomp-backend-test
```

Expected dengan revisi Tahap 13:

```text
136 passed
```

Jumlah test expected harus diperbarui setiap kali test baru ditambahkan.

### Test dan build frontend

```powershell
cd frontend
npm test
npm run build
```

Expected: **20 test frontend lulus** dan tujuh page chunk dihasilkan. Runtime verifikasi: Node.js **24.14.0**.

### Menjalankan backend

```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Dokumentasi API:

```text
http://127.0.0.1:8000/docs
```

### Pemeriksaan sebelum menandai task selesai

- [x] Source implementation tersedia.
- [x] Test positif dan negatif tersedia.
- [x] Test suite lulus.
- [x] Artifact/output aktual diperiksa.
- [x] Dokumentasi endpoint atau workflow diperbarui.
- [x] Tidak ada dataset mentah yang berubah.
- [x] Tidak ada label, metric, atau prediction dummy di production code/job aktual.
- [x] Status milestone dan tanggal pemeriksaan pada dokumen ini diperbarui.

## Definition of Done Proyek

Proyek baru boleh dinyatakan selesai apabila:

- [x] Tahap 1–12 memenuhi acceptance criteria implementasi yang dicatat pada masing-masing tahap.
- [x] Historical label AI-assisted telah disahkan dengan provenance dan pengecualian review terdokumentasi.
- [x] Guard leakage tersedia dan diuji; batas weak supervision tetap didokumentasikan sebagai keterbatasan metodologi.
- [x] Model, split, dan evaluation dapat ditelusuri/direproduksi menggunakan manifest, record ID, konfigurasi, dan versi dependency yang sama.
- [x] Prediction tidak melakukan training ulang.
- [x] Prediction history append-only terverifikasi pada test dan job QA, tanpa event dummy di job aktual.
- [x] Runtime frontend dan backend tetap local-only pada host loopback (Docker hanya dipublish ke `127.0.0.1`).
- [x] Seluruh test backend dan frontend lulus.
- [x] Build lokal berhasil dan artifact aktual tetap tersedia pada workspace `storage/`.
- [x] Dokumentasi instalasi, penggunaan, metodologi, dan keterbatasan model tersedia untuk scope local-only.
- [ ] Uji penerimaan pengguna/admin selesai.

**Kesimpulan:** Tahap 1–12, dataset Umum, eksperimen model dan perbaikan SVM versi 2 teruji dan berjalan lokal. Empat algoritma × tiga rasio berhasil sampai evaluasi pada salinan dataset operator; SVM baru konvergen tanpa batas 10.000 iterasi. 136 test backend, 20 test frontend, build dan browser QA lulus; 96 file storage aktual identik setelah QA/restart. Model aktif dipilih manual, UAT operator belum selesai. Recall mengikuti evaluasi model aktif, bukan jaminan baseline. Bukti terbaru: `docs/svm-convergence-qa.md`.
