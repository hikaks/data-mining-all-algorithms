# Preprocessing

## Tujuan

Tahap preprocessing menghasilkan dataset stateless yang siap dibagi menjadi train dan test tanpa melakukan fit terhadap vocabulary, kategori, atau statistik imputasi pada seluruh data. Learned transformer hanya boleh di-fit pada train set setelah split.

Prasyarat penggunaan saat ini: upload workbook berlabel → cleaning → langsung preprocessing.
Tidak ada inisialisasi atau tugas labeling manual. Cleaning mentransfer label ke artifact
`DATA_LABELED`; Needs Review dikecualikan otomatis. Untuk job lama yang belum dipreprocess,
backend mengidentifikasi hanya record yang belum berlabel dan mempertahankan keputusan/audit
yang sudah ada. Artifact label parsial ditolak, bukan ditimpa. Job/model yang sudah diproses
tidak diubah oleh mekanisme kompatibilitas ini. Gate dua kelas dengan minimal dua sampel
per kelas dan seluruh leakage guard tetap berlaku.

## Artifact

```text
storage/jobs/<job_id>/preprocessed/dataset_preprocessed.xlsx
storage/jobs/<job_id>/reports/preprocessing_report.json
```

Dataset memakai sheet `DATA_PREPROCESSED`.

## Hasil Dataset Aktual

```text
Input labeled            1.028
NEEDS_REVIEW dikeluarkan     2
Tanggal di luar periode      8
Output preprocessing     1.018

SELESAI                   995
TINDAK_LANJUT              23
Imbalance ratio       43,2609
```

Record yang dikeluarkan tetap tersedia pada artifact labeled dan tercatat beserta alasan pada preprocessing report.

## Kontrak Fitur

Identifier, bukan fitur:

- `record_id`;
- `near_duplicate_group_id`.

Fitur model:

- teks: `text_laporan`;
- kategori: `customer`, `teknisi`;
- numerik: `tahun`, `bulan`, `hari_dalam_minggu`, `jumlah_teknisi`.

Target:

- `keputusan_laporan`.

Kolom berikut dilarang menjadi fitur:

- target dan seluruh metadata labeling;
- status sumber;
- file, sheet, nomor baris, dan nomor sumber;
- fingerprint cleaning;
- nama user dan pihak yang mengetahui;
- identifier/group ID.

## Pipeline Train-Only

Factory `build_model_preprocessor()` menghasilkan satu `ColumnTransformer`:

- `TfidfVectorizer` untuk teks;
- `SimpleImputer` dan `OneHotEncoder(handle_unknown='ignore')` untuk kategori;
- `SimpleImputer(strategy='median')` untuk numerik;
- seluruh kolom lain di-drop.

Artifact Tahap 7 tidak menyimpan transformer yang sudah di-fit. Pada tahap training, pipeline harus di-fit hanya menggunakan train set dan dipakai dengan `transform()` pada test/prediction. Hal ini mencegah vocabulary, kategori, dan statistik test masuk ke model.

## Near Duplicate

Near duplicate dideteksi menggunakan cosine similarity dari TF-IDF character n-gram pada teks, dibatasi pada customer yang sama.

```text
threshold = 0.92
automatic_removal = false
```

Dataset aktual menghasilkan 24 group dari 50 pasangan dan tidak memiliki group dengan konflik label. Record tidak dihapus; `near_duplicate_group_id` dipakai pada tahap split agar seluruh anggota group berada pada sisi yang sama.

## Leakage dan Weak Supervision

Status sumber dilarang menjadi fitur karena digunakan sebagai salah satu evidence pada `ai-assisted-id-v1`. Teks laporan tetap menjadi fitur karena prediksi ditujukan setelah teknisi menulis laporan. Karena label juga diturunkan dari teks, evaluasi mengukur konsistensi terhadap kebijakan weak supervision dan bukan ground-truth manusia independen.

## Endpoint

```text
POST /api/jobs/{job_id}/preprocess
GET  /api/jobs/{job_id}/preprocessing-report
GET  /api/jobs/{job_id}/download/preprocessed
```

`POST .../preprocess` idempotent setelah kedua artifact tersedia. Setelah berhasil, status job menjadi `PREPROCESSED` dan perubahan label dikunci.
