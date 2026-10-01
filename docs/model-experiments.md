# Pilihan split dan eksperimen model

Kontrak 17 September 2026. Aplikasi tetap local-only, tujuh menu dan tampilan lama dipertahankan. Tidak ada dependency baru, tuning otomatis, sampling, atau labeling manual.

## Penggunaan

1. Upload dan simpan target/fitur, lalu selesaikan cleaning dan preprocessing seperti sebelumnya. Job yang sudah dipreprocess tidak perlu diupload ulang.
2. Pada **Split & Training**, pilih test/train 20/80, 25/75, atau 30/70 dan algoritma, kemudian **Buat eksperimen**.
3. Jalankan **Buat split manifest**, kemudian **Latih**. Rasio aktual ditampilkan karena group tidak boleh dipisahkan.
4. Buka **Evaluation** dan jalankan **Evaluasi model** secara eksplisit.
5. Tekan **Gunakan untuk prediksi** dan konfirmasi. Eksperimen yang hanya dilihat bukan model aktif. Job baru belum dapat memprediksi sampai model pertama diaktifkan.
6. Untuk mencoba pilihan lain, buat eksperimen baru pada job yang sama. Tidak ada perubahan konfigurasi eksperimen setelah dibuat.

Model lama tampil sebagai **Model sebelumnya** (`legacy`), aktif awal jika sudah dievaluasi. Adapter hanya membaca artifact asli: tidak menyalin, mengubah, atau melatihnya ulang. Berpindah eksperimen/navigasi tidak menjalankan processing.

## Split dan pembandingan

Seed 42; tanpa sampling; group isolation; minimal dua record setiap kelas pada train dan test. Kandidat dipilih berdasarkan kedekatan rasio dan distribusi kelas, bukan hasil model. Test 20% mempertahankan strategi lima fold; 25% mencoba empat fold; 30% dan fallback group kecil memakai 256 kandidat GroupShuffleSplit. Ketidakcukupan record/group menghasilkan error jelas.

Sumber, checksum konfigurasi, rasio, dan seed yang sama menghasilkan referensi manifest bersama. Manifest lama dapat direferensikan tanpa ditulis ulang. `test_set_id` mengidentifikasi checksum sumber dan record test; tabel menandai test set berbeda sebagai tidak langsung sebanding. Rasio diminta bukan jaminan rasio aktual persis. Pemakaian holdout berulang untuk memilih algoritma juga bukan validasi independen.

## Algoritma dan pipeline

| ID | Algoritma | Parameter tetap |
|---|---|---|
| `random_forest` | Random Forest | Seluruh parameter/pipeline baseline dipertahankan |
| `decision_tree` | Decision Tree | max_depth=20, min_samples_leaf=2, class_weight=balanced, random_state=42 |
| `svm_linear` | SVC linear | kernel=linear, C=1, probability=True, class_weight=balanced, cache_size=200, max_iter=-1, random_state=42 |
| `knn` | KNN | n_neighbors=5, weights=distance, algorithm=brute, metric=euclidean, n_jobs=1 |

Parameter lengkap dapat dibaca pada detail eksperimen dan metadata. SVM/KNN menstandardisasi numerik/kalender setelah imputasi, dengan fit hanya pada train. OneHot dan TF-IDF tetap mengikuti kontrak fitur. RF tidak memperoleh scaler baru. Adapter classifier mempertahankan kelas string, termasuk `"01"` dan `"1"`, setelah persistensi/reload.

KNN menolak train kurang dari lima record. SVM yang belum konvergen tidak mempublikasikan model siap. SVM dapat lebih lama saat fitting/probability estimation; KNN dapat lebih lama saat evaluasi/prediksi. Durasi fitting bukan total durasi request.

### Kebijakan parameter SVM versi 2

Eksperimen baru menyimpan `parameter_version=2`. `max_iter=-1` berarti tanpa batas iterasi solver; training menunggu konvergensi, bukan berhenti pada 10.000 iterasi. Algoritma tetap SVC linear dengan parameter lain sama, tanpa tuning atau perubahan dependency. `fit_status_` tetap harus nol sebelum publikasi. Metadata `verification.svm_solver` mencatat status, jumlah iterasi per pasangan kelas, dan batas solver. Lihat [kontrak resmi SVC](https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVC.html).

Eksperimen tanpa `parameter_version` dibaca sebagai versi 1 dan memakai parameter asli, termasuk batas SVM 10.000. Artifact, descriptor, dan joblib lama tidak dimigrasi atau ditulis ulang. Versi/parameter invalid ditolak. Untuk SVM lama yang gagal, pilih eksperimennya di Training, tekan **Buat ulang SVM tanpa batas iterasi**, lalu **Buat split manifest → Latih SVM linear → Evaluasi**. Pengganti memakai rasio dan split bersama yang sama, tanpa mengganti model aktif otomatis. `max_iter=-1` dijelaskan pada detail parameter.

Tanpa batas iterasi bukan jaminan semua input valid atau durasi singkat. Guard dataset/split/checksum dan KNN minimal lima train tetap berlaku. SVC dapat memerlukan waktu/memori tinggi pada data sangat besar; kegagalan nyata tetap dilaporkan, bukan diubah menjadi sukses. Bukti tambahan tersedia di [QA konvergensi SVM](svm-convergence-qa.md).

Semua algoritma memakai `predict()` untuk rekomendasi dan `predict_proba()` sesuai urutan `classes_`. Confidence diambil dari probabilitas kelas rekomendasi, **bukan selalu probabilitas terbesar**; SVM dapat menghasilkan perbedaan kedua hasil ini. Lihat [dokumentasi resmi SVM](https://scikit-learn.org/stable/modules/svm.html#scores-and-probabilities). Confidence bukan jaminan ketepatan atau probabilitas terkalibrasi.

RF memiliki impurity importance/simpangan antarpohon. DT memiliki impurity importance tanpa simpangan antarpohon. SVM/KNN memberikan artifact eksplisit `available=false`, bukan importance palsu atau error evaluasi. Prioritas PT tetap TINDAK_LANJUT; Umum menonjolkan recall terendah.

## Storage dan integritas

```text
storage/jobs/<job_id>/
  raw/, cleaned/, preprocessed/, config/   # bersama, tidak ditimpa eksperimen
  experiments/
    splits/<split_key>/split_manifest.json
    EXP-<id>/experiment.json
    EXP-<id>/model/{model_pipeline.joblib,model_metadata.json}
    EXP-<id>/reports/{evaluation.json,feature_importance.json}
    active.json                           # pilihan model aktif, bukan model baru
  predictions/predictions.jsonl           # history bersama append-only
```

Nama file model mengikuti kontrak artifact backend. Descriptor memuat waktu, ID, algoritma/parameter, rasio/seed, snapshot/hash konfigurasi, hash sumber, referensi dan hash split. Aktivasi memverifikasi evaluasi, konfigurasi/sumber/model serta traceability. Perubahan checksum ditolak. Status CREATED → SPLIT_READY → TRAINED → EVALUATED terpisah dari job; kegagalan menyimpan tahap/alasan dan tidak menurunkan tahap berhasil atau mengganti model aktif.

Request processing sinkron/idempotent per eksperimen. Frontend tidak mengulang POST/PUT otomatis. Jika hasil tidak pasti, baca ulang status dengan GET sebelum mencoba manual. Operasi dari proses server yang terputus ditampilkan sebagai terputus melalui adapter baca-saja; retry eksplisit memeriksa artifact terlebih dahulu.

History mencatat model dan eksperimen asal. Koreksi memakai kelas model asal, bukan model yang sekarang aktif; alasan perubahan keputusan wajib. Event dan rekomendasi lama tidak ditulis ulang.

## API

Semua respons memakai envelope `success/data/message` sekarang; request extra-field dan nilai invalid ditolak sebelum direktori eksperimen dibuat.

| Method/path relatif `/api/jobs/{job_id}` | Kontrak |
|---|---|
| GET `/experiments` | items, active_experiment_id |
| POST `/experiments` | `{test_ratio:0.20\|0.25\|0.30, algorithm:"random_forest"\|"decision_tree"\|"svm_linear"\|"knn"}`; default 0.20/RF |
| GET `/experiments/{experiment_id}` | Konfigurasi, status, operasi/error, metrik, model_id, test_set_id |
| POST `/experiments/{experiment_id}/split` | Buat/reuse manifest |
| POST `/experiments/{experiment_id}/train` | Fit/persist model |
| POST `/experiments/{experiment_id}/evaluate` | Evaluasi eksplisit |
| GET `/experiments/{experiment_id}/{report}` | `split-manifest`, `model-metadata`, `evaluation`, `feature-importance` |
| GET `/experiments/{experiment_id}/download/{artifact}` | Report di atas atau `model` |
| PUT `/active-experiment` | `{experiment_id:"EXP-..."}`; hanya model EVALUATED/integritas valid |

ID `legacy` didukung pada endpoint eksperimen sebagai adapter artifact sebelumnya. GET laporan lama mengikuti model aktif, atau artifact root bila belum ada model aktif baru. Endpoint processing lama tetap menjalankan alur default root. Payload prediksi `{features:{...}}` dan payload PT lama kompatibel; schema/form, probabilitas, warning, dan unduhan mengikuti model aktif. Overview memproyeksikan ketersediaan eksperimen tanpa menulis status job lama.

Engineering QA dicatat pada [model-experiments-qa.md](model-experiments-qa.md). Penerimaan akhir tetap UAT operator.
