# Label Dataset Otomatis dan Audit Historis

Revisi final 16 September 2026: **fitur/tugas labeling manual dihapus**. Gunakan workbook
`dataset/Data_Berlabel_Gabungan_PT_MAXKOMP.xlsx`, upload → cleaning → langsung preprocessing.
Workbook mentah tetap didukung dengan identifikasi otomatis. Dokumentasi ini menjelaskan
kebijakan dan provenance, bukan langkah labeling yang harus dikerjakan operator.

## Tujuan

Historical labeling menghasilkan target weakly-supervised untuk `keputusan_laporan` melalui kebijakan identifikasi yang disetujui pemilik aplikasi. Random Forest belajar dari hasil identifikasi tersebut; hasil evaluasi mengukur konsistensi terhadap kebijakan, bukan validitas ground-truth manusia independen.

## Validator

Identifikasi otomatis menggunakan role:

```text
AI_VALIDATOR
```

Keputusan manual historis atau label workbook manual memakai `ADMIN_VALIDATOR`; tidak ada UI
koreksi label saat ini. Kedua role dicatat apa adanya, tanpa menyamarkan rule sebagai keputusan
manusia. Label impor divalidasi kontraknya, bukan diverifikasi sebagai ground-truth independen.

## Nilai Label

Target training `keputusan_laporan` hanya boleh berisi:

```text
SELESAI
TINDAK_LANJUT
```

Definisi:

- `SELESAI`: laporan dapat ditutup dan tidak membutuhkan tindakan teknis atau administratif lanjutan berdasarkan bukti yang tersedia.
- `TINDAK_LANJUT`: laporan belum dapat ditutup karena masih terdapat tindakan teknis dan/atau administratif.

Jika keputusan belum dapat ditentukan, gunakan:

```text
labeling_status = NEEDS_REVIEW
keputusan_laporan = null
```

`NEEDS_REVIEW` bukan kelas Random Forest.

## Kebijakan Identifikasi AI-Assisted

Versi kebijakan aktif: `ai-assisted-id-v1`.

- Isi laporan kosong menghasilkan `NEEDS_REVIEW`.
- Indikasi kuat seperti belum selesai, menunggu, harus diservis/diganti, atau perangkat dibawa untuk tindak lanjut menghasilkan `TINDAK_LANJUT`.
- Status sumber `OK` menghasilkan `SELESAI` hanya jika tidak ditemukan indikasi kuat tindak lanjut.
- Tanpa status `OK`, bukti eksplisit seperti `OK`, `selesai`, `beres`, `sudah`, atau `jadi` dapat menghasilkan `SELESAI`.
- Bukti yang tidak cukup menghasilkan `NEEDS_REVIEW`.

Kebijakan bersifat deterministik dan dapat diuji ulang. `Status_Asli` tidak boleh dimasukkan sebagai fitur model. Karena target diturunkan dari teks laporan dan status sumber, distribusi kelas serta potensi bias weak supervision wajib dilaporkan pada evaluasi.

## Record Incomplete

`yang_mengetahui` bersifat opsional untuk kelayakan training. Nilai kosong tidak menyebabkan record dibuang dan nama orang tidak boleh diimputasi.

Record dikeluarkan dari kandidat training apabila:

- `keputusan_laporan` kosong;
- `labeling_status = NEEDS_REVIEW`;
- record operationally-empty;
- data inti tidak cukup untuk membentuk feature input yang valid.

Strategi missing-value fitur final harus ditetapkan pada tahap preprocessing.

## Artifact

```text
storage/jobs/<job_id>/labeled/dataset_labeled.xlsx
storage/jobs/<job_id>/reports/input_labels.json
storage/jobs/<job_id>/reports/labeling_report.json
```

`dataset_labeled.xlsx` memakai sheet `DATA_LABELED` dan menambahkan:

- `labeling_status`;
- `label_validator_role`;
- `label_updated_at`;
- `label_confidence`;
- `label_decision_reason`;
- `label_policy_version`.

Workbook upload memiliki 12 kolom sumber + tujuh kolom target/audit berurutan; sheet tetap
`DATA_MENTAH`. Label/audit tidak boleh parsial. Snapshot input mencatat checksum raw dan
source IMPORTED/AUTO_IDENTIFIED. Cleaning mentransfer label ke cleaned/labeled, bukan
menentukan ulang label impor. Exact duplicate dengan label bertentangan ditolak. Cleaning
artifact tidak ditimpa tahap berikutnya; sumber mentah tetap utuh.

## Audit

Setiap perubahan label menyimpan event dengan:

- jenis operasi IMPORT_LABEL/UPLOAD_AUTO_IDENTIFY (single/bulk/auto hanya audit historis);
- `record_id`;
- status dan target sebelumnya;
- status dan target baru;
- role validator;
- alasan jika ada;
- confidence dan versi kebijakan untuk identifikasi otomatis;
- waktu UTC.

Audit lama tidak diubah. Kelanjutan job lama sebelum preprocessing melengkapi hanya
UNLABELED, tanpa menimpa label final/review. Job yang sudah dipreprocess/dilatih tidak
dimigrasikan. Koreksi label sekarang dilakukan melalui workbook baru dan upload job baru.

## Endpoint

```text
GET   /api/jobs/{job_id}/labeling/summary
GET   /api/jobs/{job_id}/labeling/records
GET   /api/jobs/{job_id}/labeling/report
GET   /api/jobs/{job_id}/download/labeled
```

Endpoint GET hanya audit/export read-only dan kompatibilitas artifact. Initialize, single
PATCH, bulk, dan auto POST sudah dihapus (404); tidak ada fitur labeling interaktif.

## Progress dan Status Job

- Upload langsung mencatat label input, dengan status job ANALYZED.
- Cleaning yang berhasil merespons LABELED: semua record sudah diidentifikasi, meskipun ada Needs Review.
- LABELING/UNLABELED dipertahankan hanya untuk kompatibilitas job lama.
- Hanya record dengan target final yang dihitung sebagai training-eligible.

## Training Gate

Backend melaporkan readiness untuk preprocessing/training. Gate menolak apabila:

- belum ada keputusan final;
- hanya tersedia satu kelas;
- salah satu kelas memiliki kurang dari dua sample.

Record `UNLABELED` dan `NEEDS_REVIEW` tidak ikut training. Preprocessing/training belum boleh menggunakan dummy label, dummy model, dummy metric, atau dummy prediction.
