# Prediction dan Prediction History

Revisi eksperimen: prediction mengikuti model yang diaktifkan manual setelah evaluasi; history mencatat eksperimen/model asal. Koreksi divalidasi terhadap kelas model asal meskipun model aktif berubah. Confidence adalah probabilitas kelas hasil predict(), bukan selalu probabilitas terbesar, terutama pada SVM. Lihat [kontrak eksperimen](model-experiments.md).

## Status

Tahap 11 selesai. Endpoint inference dan histori tersedia untuk setiap job yang sudah berstatus `EVALUATED`.

Job aktual `aNvdsL7wjhr7Lqb7TAxd6g` belum memiliki prediction event. Tidak ada data dummy yang ditambahkan ke histori bisnis.

## Kontrak Input

```json
{
  "tanggal": "2026-04-01",
  "customer": "SST",
  "teknisi": "Eman | Harry",
  "text_laporan": "Laptop harus dibawa ke kantor untuk service lanjutan"
}
```

Field tambahan ditolak. Backend menormalisasi teks dan menghitung `tahun`, `bulan`, `hari_dalam_minggu`, serta `jumlah_teknisi` menggunakan kontrak yang sama dengan preprocessing.

## Inference

Pipeline yang sudah tersimpan dimuat dari `model/model_pipeline.joblib` setelah checksum, `model_id`, evaluation artifact, dan versi scikit-learn diverifikasi. Endpoint hanya memanggil `predict` dan `predict_proba`; tidak ada training ulang.

Probabilities dipetakan mengikuti `model.classes_`. Confidence adalah probability untuk kelas hasil prediksi. Response selalu menyatakan bahwa hasil merupakan rekomendasi dan memuat recall `TINDAK_LANJUT` dari evaluation artifact aktif.

## Histori Append-Only

Artifact:

```text
storage/jobs/<job_id>/predictions/predictions.jsonl
```

Event `prediction_created` menyimpan:

- `event_id` dan `prediction_id` unik;
- model ID serta checksum model;
- input bisnis yang telah dinormalisasi;
- kelas, confidence, probabilities, dan peringatan rekomendasi.

Event `actual_decision_recorded` menyimpan keputusan admin tanpa mengubah event prediction. Keputusan pertama tidak memerlukan alasan. Perubahan keputusan yang sudah tercatat wajib memiliki alasan dan menyimpan `previous_actual_decision`.

GET history membaca seluruh event lalu merekonstruksi state terbaru per `prediction_id`. File dengan JSON tidak valid, baris terpotong, event ID duplikat, actual decision tanpa prediction, atau rantai previous decision yang tidak konsisten akan ditolak.

## Endpoint

```text
POST  /api/jobs/{job_id}/predict
GET   /api/jobs/{job_id}/predictions?page=1&page_size=25
PATCH /api/jobs/{job_id}/predictions/{prediction_id}/actual-decision
GET   /api/jobs/{job_id}/download/predictions
```

Model evaluasi saat ini memiliki recall `TINDAK_LANJUT` 40%. Prediction tidak boleh dijadikan keputusan final otomatis; admin tetap menentukan `actual_decision`.
