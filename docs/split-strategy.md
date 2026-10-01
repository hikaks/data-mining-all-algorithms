# Train/Test Split Strategy

Revisi eksperimen 17 September 2026: default 20% di bawah tetap kompatibel; 25% mencoba SGKF empat fold, 30%/fallback memakai 256 GroupShuffleSplit. Manifest dibagikan hanya untuk sumber/config/rasio/seed yang sama; min dua record per kelas per bagian tetap wajib. Rasio aktual dapat berbeda karena group. Lihat [kontrak eksperimen](model-experiments.md).

## Tujuan

Tahap ini membagi feature frame preprocessing menjadi train dan test secara reproducible tanpa memindahkan anggota near-duplicate group ke sisi berbeda.

## Konfigurasi

```text
strategy = StratifiedGroupKFold
n_splits = 5
shuffle = true
random_state = 42
requested_train_ratio = 0.80
requested_test_ratio = 0.20
sampling = NONE
```

`StratifiedGroupKFold` mencoba mempertahankan proporsi kelas sambil memastikan setiap group hanya muncul pada satu fold. Semua kandidat fold dinilai berdasarkan kedekatan rasio test dan distribusi kelas terhadap dataset penuh. Kandidat dengan skor terendah dipilih secara deterministik; jika skor sama, indeks kandidat terendah digunakan.

## Hasil Dataset Aktual

```text
Total                    1.018
Train                      814  (79,960707%)
Test                       204  (20,039293%)

Train SELESAI              796
Train TINDAK_LANJUT         18
Test SELESAI               199
Test TINDAK_LANJUT           5

Selected candidate           1
Record overlap               0
Group overlap                0
Missing record               0
Sampling                     NONE
```

Seluruh 1.018 `record_id` muncul tepat satu kali. Semua anggota dari 24 near-duplicate group tetap berada pada sisi yang sama.

## Artifact

```text
storage/jobs/<job_id>/reports/split_manifest.json
```

Manifest menyimpan:

- hash SHA-256 dataset preprocessing;
- konfigurasi dan versi strategi;
- seluruh train/test record ID dan group ID;
- distribusi kelas;
- ringkasan semua kandidat fold;
- bukti coverage, record overlap, dan group overlap;
- rekomendasi class weighting untuk tahap training.

Tidak ada train/test matrix terpisah yang disimpan. Tahap training membaca dataset preprocessing, memilih baris berdasarkan manifest, lalu melakukan `fit()` pada train dan `transform()` pada test.

## Class Imbalance

Tidak ada oversampling, undersampling, atau data sintetis pada split. Kelas minoritas hanya memiliki 23 record, termasuk 5 pada test. Karena itu metrik kelas minoritas akan memiliki variance tinggi dan tidak boleh dinilai hanya melalui accuracy. Baseline training menggunakan `class_weight='balanced'`, sedangkan evaluasi wajib melaporkan precision, recall, F1, balanced accuracy, dan confusion matrix.

## Endpoint

```text
POST /api/jobs/{job_id}/split
GET  /api/jobs/{job_id}/split-manifest
GET  /api/jobs/{job_id}/download/split-manifest
```

Pembuatan split bersifat idempotent. Request berikutnya mengembalikan manifest yang sama dan tidak mengacak pembagian ulang.
