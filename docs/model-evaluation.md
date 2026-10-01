# Model Evaluation

Revisi eksperimen: evaluasi diakses per eksperimen dan tidak mengaktifkan model otomatis. RF/DT menyediakan impurity importance (simpangan antarpohon hanya RF); SVM/KNN menampilkan tidak tersedia. Aktivasi manual memeriksa evaluasi/checksum; GET lama mengikuti model aktif. Lihat [model-experiments.md](model-experiments.md).

## Status

Tahap 10 selesai dan telah dijalankan untuk model `RF-46320A252D2C7AC4` pada job `aNvdsL7wjhr7Lqb7TAxd6g`.

```text
evaluation_id: EVAL-0048A5E730529AA6
evaluation_version: fixed-test-evaluation-v1
test rows: 204
SELESAI: 199
TINDAK_LANJUT: 5
```

## Hasil

| Metrik | Nilai |
|---|---:|
| Accuracy | 0,98039216 |
| Balanced accuracy | 0,69748744 |
| Precision `TINDAK_LANJUT` | 0,66666667 |
| Recall `TINDAK_LANJUT` | 0,4 |
| F1 `TINDAK_LANJUT` | 0,5 |
| Macro precision | 0,82587065 |
| Macro recall | 0,69748744 |
| Macro F1 | 0,745 |

Confusion matrix memakai baris aktual, kolom prediksi, dan urutan label `[SELESAI, TINDAK_LANJUT]`:

```text
[[198, 1],
 [  3, 2]]
```

Dari lima kasus aktual `TINDAK_LANJUT`, model hanya mendeteksi dua dan melewatkan tiga. Accuracy tinggi terutama dipengaruhi dominasi kelas `SELESAI`; balanced accuracy dan recall kelas minoritas harus menjadi dasar interpretasi.

## Artifact

```text
storage/jobs/<job_id>/reports/evaluation.json
storage/jobs/<job_id>/reports/feature_importance.json
```

`evaluation.json` menyimpan classification report, confusion matrix, prediction audit untuk seluruh 204 record test, serta checksum model, metadata, split manifest, dataset preprocessing, dan feature importance.

`feature_importance.json` menyimpan 6.378 nama fitur hasil transformer beserta Mean Decrease in Impurity dan deviasi antar-pohon. Fitur teratas mencakup token `harus`, `cek laptop`, `kantor`, `ke kantor`, dan `cek`.

## Keterbatasan

- Test set hanya memiliki lima record `TINDAK_LANJUT`; perubahan satu prediksi sangat memengaruhi recall.
- Target berasal dari kebijakan historical labeling AI-assisted, bukan ground-truth manusia independen.
- Impurity-based importance dapat bias terhadap fitur berkardinalitas tinggi dan tidak menunjukkan hubungan kausal.
- Hasil satu fixed holdout belum membuktikan performa pada data operasional baru.

Model adalah rekomendasi untuk admin. Model tidak boleh menetapkan keputusan final secara otomatis, terutama karena recall kelas tindak lanjut baru 40%.

## Endpoint

```text
POST /api/jobs/{job_id}/evaluate
GET  /api/jobs/{job_id}/evaluation
GET  /api/jobs/{job_id}/feature-importance
GET  /api/jobs/{job_id}/download/evaluation
GET  /api/jobs/{job_id}/download/feature-importance
```

`POST /evaluate` idempotent. Jika evaluation artifact yang checksum-nya valid sudah tersedia, endpoint mengembalikan hasil yang sama tanpa menjalankan evaluation ulang.
