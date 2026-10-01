# Kontrak Dataset Umum dan Preset PT Maxkomp

Revisi 16 September 2026. Local-only, filesystem, tanpa database/cloud atau labeling manual. Dokumen ini menjadi kontrak upload/configuration terbaru; dokumen metodologi PT sebelumnya tetap berlaku hanya untuk preset PT dan job legacy.

## Alur dan gate

Upload → pilih sheet/pemisah, profil, target dan fitur → simpan konfigurasi → understanding → cleaning → preprocessing → split → training → evaluation → prediction.

Job baru tetap `UPLOADED`, preview raw dapat dibaca, tetapi summary/processing memerlukan konfigurasi tersimpan. PUT konfigurasi berhasil menghasilkan `ANALYZED`. Umum: cleaning menghasilkan `CLEANED`; preset PT: cleaning/transfer label menghasilkan `LABELED`. Sesudahnya kedua profil mengikuti `PREPROCESSED → TRAINED → EVALUATED`. Split mempertahankan status `PREPROCESSED` dan menambahkan manifest.

Konfigurasi disimpan di `storage/jobs/{job_id}/config/dataset_config.json`: `schema_version=1`, revision meningkat, waktu simpan, profil, sheet/pemisah, target, fitur/jenis, SHA-256 raw. Konfigurasi dapat diubah saat UPLOADED/ANALYZED, lalu terkunci setelah cleaning. Simpan dan processing memakai lock yang sama pada proses backend lokal tunggal. Untuk konfigurasi/label berbeda sesudahnya, upload job baru.

## Format input

- `.xlsx` dan `.csv` maksimum 25 MB; raw disimpan byte-identik sebagai `raw/dataset.xlsx` atau `raw/dataset.csv`.
- Excel boleh mempunyai sheet/nama kolom bebas. UI menyediakan pilihan sheet, preview lima record, dan preview raw paginated. Sheet pertama yang valid menjadi default; pengguna memilih dataset yang benar.
- CSV UTF-8/UTF-8 BOM. Deteksi koma/titik koma/tab; jika ambigu ditampilkan peringatan dan pilihan koreksi. Periksa preview sebelum simpan. Encoding lain ditolak dengan pesan ekspor ulang.
- Header di baris pertama, whitespace luar dipangkas untuk nama kolom. Header kosong/duplikat ditolak sebelum Pandas dapat mengganti namanya.
- Jenis disarankan berdasarkan nilai dan dapat dikoreksi: numeric, categorical, text, date. Tanggal menerima ISO (`YYYY-MM-DD`/datetime ISO), DD/MM/YYYY atau DD-MM-YYYY, serta tanggal asli Excel. Tidak menebak format tanggal ambigu MM/DD.
- Fitur seluruhnya kosong ditolak. Nilai numeric/date nonkosong yang salah ditolak dengan kolom dan nomor baris. Fitur tambahan/target pada input prediksi ditolak.

## Profil

**Umum** memakai kolom label yang sudah tersedia. Minimal dua kelas; numeric target adalah kode klasifikasi, bukan regresi. Label dikembalikan sebagai string (kode CSV `01` dan `1` berbeda; literal `NA` bukan null). Hanya target kosong dikecualikan saat preprocessing, dengan record ID/alasan pada report. Nilai `NEEDS_REVIEW`, jika memang label dataset umum, merupakan kelas biasa. Tidak ada pemetaan customer/teknisi, cutoff penelitian, atau kebijakan labeling PT.

**PT Maxkomp** hanya untuk XLSX/sheet `DATA_MENTAH` dengan 12 header sumber resmi, atau 12+7 header target/audit resmi berurutan. Target `keputusan_laporan`, tujuh fitur turunan resmi. Label workbook diimpor setelah validasi; raw 12 kolom diidentifikasi melalui kebijakan `ai-assisted-id-v1` saat konfigurasi preset disimpan. Final target SELESAI/TINDAK_LANJUT, Needs Review bukan target dan dikecualikan. Aturan mapping/tanggal/domain dan provenance lama dipertahankan.

Job/model lama tanpa konfigurasi memakai adapter PT read-only. GET tidak membuat config, mengubah artifact, melatih model, atau memigrasikan history. Konfigurasi legacy tidak dapat disimpan; buat job baru. Payload prediksi PT flat lama tetap diterima. Dependency tidak dinaikkan.

## Cleaning dan isolasi

Umum mempertahankan raw dan semua kolom sumber dalam cleaned. Normalisasi jenis/whitespace fitur serta string target diaudit; baris seluruhnya kosong dan duplicate berdasarkan fitur terpilih-plus-target dihapus. Kolom sumber yang bertabrakan dengan identifier/target internal diberi nama `source__...` secara unik; mapping tercatat pada report, tidak ditimpa diam-diam.

GET `cleaning-report` mendukung counter angka pada `normalization` untuk preset PT serta `operation_count` dan mapping string-ke-string `source_column_map` untuk Umum. Versi ringkas (`include_details=false`) mengosongkan detail audit saja; ringkasan dan mapping tetap utuh. Membaca laporan tidak menulis ulang artifact atau mengubah status job.

Fitur identik dengan target berbeda tetap disimpan dan dilaporkan. Fingerprint representasi stateless fitur model menghasilkan group yang sama untuk split (bukan cosine similarity PT); tanggal berbeda yang menghasilkan kalender identik juga satu group. Transformasi kalender dilakukan sebelum split; alias internal `feature_0000` dst mencegah tabrakan nama bebas. Mapping alias/nama asli ada di feature contract/model metadata.

Split menargetkan 80/20, seed 42, stratified dan group-aware, tanpa sampling. Semua record dicakup tepat sekali, tidak ada record/group overlap. Minimal dua record setiap kelas pada train DAN test. Jika jumlah/group tidak memungkinkan, error domain menjelaskan ketidakcukupan; tidak memindahkan duplicate ke sisi lain untuk memaksa rasio.

## Model, evaluasi, prediksi

- Numeric: median dari train. Jika numeric/calendar seluruhnya kosong pada train terpilih, training ditolak karena median tidak bisa dipelajari.
- Kategori: nilai kosong eksplisit, OneHot `handle_unknown=ignore`.
- Teks: TF-IDF per kolom, maksimum 5.000 vocabulary per kolom. Vocabulary kosong pada train menghasilkan error jelas.
- Tanggal: year/month/weekday, nilai kosong memakai median train.
- Satu Pipeline/ColumnTransformer dan Random Forest lokal: 100 pohon, max_depth 20, min_samples_leaf 2, balanced, seed 42, n_jobs 1. LabelEncoder train-only melindungi kode string numerik dari coercion saat class balancing; public `classes_`/prediksi tetap label asli.
- Learned transform hanya fit pada train record ID manifest. Snapshot konfigurasi/checksum masuk manifest dan metadata/model identity. Model disimpan lalu reload/prediksi sampel diverifikasi.
- Evaluasi TEST_ONLY: confusion matrix urutan kelas model, metrik per kelas, macro/weighted F1, accuracy, balanced accuracy. Umum menonjolkan recall terendah; PT tetap TINDAK_LANJUT. Field positive metrics bernilai null untuk Umum, bukan kelas positif palsu.
- Form prediksi mengikuti kontrak model tersimpan, bukan konfigurasi input saat ini. General request `{ "features": { "nama fitur": "nilai", "numeric": 12, "boleh kosong": null } }`. Semua fitur wajib hadir sebagai key; null/blank memakai strategi missing model. Target/extra key ditolak. Probabilities mengikuti `classes_` dan jumlahnya satu.
- Keputusan aktual wajib kelas model. History JSONL append-only; koreksi keputusan lama memerlukan alasan. Peringatan rekomendasi berasal dari recall report model aktif, bukan angka hardcoded.
- GET model/evaluasi/history serta inference memverifikasi snapshot konfigurasi dan checksum terkait. Mengubah config di luar aplikasi menimbulkan error, bukan retrain otomatis.

## Endpoint baru

```text
GET /api/jobs/{job_id}/dataset/schema?sheet_name=...&delimiter=...&target_column=...
GET /api/jobs/{job_id}/dataset/configuration
PUT /api/jobs/{job_id}/dataset/configuration
GET /api/jobs/{job_id}/prediction/schema
```

Contoh PUT Umum:

```json
{"profile":"generic","sheet_name":"Data bebas","delimiter":null,"target_column":"hasil","features":[{"name":"jumlah","kind":"numeric"},{"name":"segmen","kind":"categorical"},{"name":"catatan","kind":"text"},{"name":"tanggal","kind":"date"}]}
```

Contoh preset: `{"profile":"maxkomp","sheet_name":"DATA_MENTAH","target_column":"keputusan_laporan","features":[]}`. Tujuh fitur resmi diisi server. Respons upload/overview menyertakan file_format, sheets, configuration_ready; overview juga profile/target_column. Semua POST stage lama tetap dipakai. Endpoint label audit lama hanya untuk preset/legacy, bukan labeling manual atau kontrak target umum.

## Penerimaan

Regression PT, test backend Umum, test frontend/build, dan QA terisolasi merupakan gate engineering. UAT operator tetap penerimaan akhir. Jangan mengirim prediksi dummy atau menjalankan ulang stage pada job aktual untuk QA. Dataset fixture `backend/tests/fixtures/generic.csv` hanya untuk test/QA, bukan data penelitian.
