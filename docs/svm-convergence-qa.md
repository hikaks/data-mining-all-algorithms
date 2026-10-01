# Perbaikan konvergensi SVM — 17 September 2026

Engineering QA; UAT pengguna tetap terpisah. Tidak ada perubahan tampilan/CSS, algoritma lain, label, split, atau dependency.

## Penyebab dan perbaikan

Job `RAHib9nFcP5jfOY5Ihp08A`, dataset `Data_Label_Augmentasi_PT_MAXKOMP_3000.xlsx`, profil Umum, mempunyai SVM 25/75 yang berhenti pada batas 10.000 iterasi. SVM baru memakai kebijakan parameter versi 2 dengan `max_iter=-1`; model masih wajib `fit_status_=0` sebelum disimpan. Versi 1 tetap dibaca dengan parameter asli, tanpa migrasi. UI membuat pengganti, bukan mengubah konfigurasi eksperimen lama.

## Regression dan real-data QA

- 136 test backend lulus, termasuk 36 kombinasi profil binary/multiclass/PT × empat algoritma × tiga rasio.
- Lima test tambahan: adapter eksperimen/joblib SVM lama tanpa migrasi dan empat versi parameter invalid. Nonkonvergensi tetap tidak menerbitkan model.
- 20 test frontend lulus, termasuk pemulihan SVM tanpa mengubah rasio/eksperimen. Production build lulus; stylesheet dan dependency sama.
- Warning dependency Starlette/TestClient dan SVC(probability=True) tetap ada; tidak menaikkan dependency.

Container QA `maxkomp-svm-qa-20260917` memakai storage internal `/tmp/svm-convergence-qa`. Backend source dan storage operator dipasang **read-only**; hanya job di atas disalin ke storage QA internal. Script `backend/tests/qa_svm_convergence.py` menolak storage lain dan menolak menimpa salinan yang sudah ada. Tidak ada POST training/evaluasi/prediksi ke job operator.

Raw 3.000, cleaned 2.929, kandidat model 2.917. Seluruh 12 kombinasi berhasil EVALUATED dan reload model. Record/group overlap nol; algoritma dengan rasio sama memakai test set identik. Semua 14 file asal salinan job tetap identik, termasuk RF terlatih dan descriptor SVM lama yang gagal. Model aktif tidak berubah.

| Test/train diminta | RF accuracy | DT accuracy | SVM accuracy | KNN accuracy |
|---|---|---|---|---|
| 20/80 | 98,80% | 98,63% | 99,49% | 73,24% |
| 25/75 | 99,18% | 98,49% | 99,32% | 73,84% |
| 30/70 | 98,97% | 98,28% | 98,86% | 74,03% |

Rasio aktual: 19,986287%, 25,025711%, 29,962290%. SVM konvergen pada 31.726, 28.153, dan 21.940 iterasi untuk test 20%, 25%, dan 30%; fit_status=0 semuanya. Durasi fitting SVM sekitar 2,4–2,9 detik, bukan durasi total request. Berhasil dievaluasi bukan jaminan akurasi tinggi; KNN menampilkan hasil nyata lebih rendah. Ini holdout dataset berlabel augmentasi, bukan bukti kinerja operasional independen.

## Browser, storage, dan runtime

Frontend QA 5174 memproxy backend QA 8001, terpisah dari origin browser operator 5173. Browser memverifikasi pemilihan eksperimen gagal, tindakan pengganti mempertahankan rasio 25/75, parameter -1, reuse split, training, dan evaluasi eksplisit. Pemeriksaan akhir storage/restart dicatat setelah smoke test.

Snapshot operator sebelum pekerjaan: 96 file. Sesudah automated/real-data QA, sebelum restart: 96 identik, changed=[], extra=[]. Bukti per-file disimpan pada `svm-convergence-storage-checksums.json` setelah pemeriksaan akhir.

Browser pengganti `EXP-5636E7EBFD681615` mencapai EVALUATED, model `SVM-79DCF08EDB35D674`, accuracy 99,32%, macro F1 99,19%. Tombol Gunakan untuk prediksi tersedia, model aktif tetap belum dipilih. Split_reference sama dengan SVM lama; 14 file asal clone tetap identik sesudah browser QA. SVM/KNN menampilkan feature importance tidak tersedia, tanpa menggagalkan evaluasi.

Server utama menggunakan image `maxkomp-backend-local-svm-convergence`, source overlay tanpa install dependency. Container sebelumnya disimpan stopped sebagai `maxkomp-local-config-before-svm-fix-20260917`. Frontend dimuat ulang (PID 19300). Health backend, frontend root, dan proxy utama semuanya 200. Runtime mengonfirmasi parameter_version=2, max_iter=-1, scikit-learn tetap 1.9.1.

Sesudah restart dan GET smoke eksperimen/evaluasi/model-metadata/schema prediksi/history job lama: **96 file operator identik**, changed=[], extra=[]. Adapter RF terlatih dan SVM lama gagal tetap terbaca tanpa migrasi; tidak ada POST pada job aktual. Hash sebelum, sebelum restart, dan sesudah tercatat pada [snapshot checksum](svm-convergence-storage-checksums.json). Hasil 12 eksperimen QA terisolasi disimpan di [hasil real-data QA](svm-convergence-results.json). UAT pengguna tetap belum selesai.

Reproduksi: gunakan container baru dengan internal STORAGE_ROOT di atas, mount backend `/app/backend:ro`, mount storage `/input-storage:ro`, jalankan uvicorn pada port QA8001, lalu `rtk docker exec -e PYTHONPATH=/app/backend maxkomp-svm-qa-20260917 python backend/tests/qa_svm_convergence.py`. Script hanya dapat dijalankan sekali pada root QA baru. Runtime utama tetap loopback, bukan LAN/cloud.

Container/frontend/tab QA sudah dihentikan/ditutup. Container QA stopped dipertahankan dengan salinan internal read-only-input untuk reproduksi; storage operator tidak dihapus atau dimigrasi. Server utama tetap berjalan di 127.0.0.1:8000/5173 untuk UAT.
