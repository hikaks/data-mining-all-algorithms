# QA eksperimen model — 17 September 2026

Engineering QA terpisah dari UAT operator. Dataset/model/evaluation/history aktual tidak digunakan untuk POST pengujian.

## Automated regression

- Backend: 131 test (83 regression sebelumnya + 48 test eksperimen).
- Seluruh 36 kombinasi: tiga rasio × empat algoritma × profil Umum binary, Umum multiclass, preset PT.
- Group/record overlap nol, min dua record/kelas/bagian, train-only imputasi/scaling, unknown category, kelas string `01`/`1`, reload proses/model, idempotensi, reuse split dan referensi manifest legacy.
- Request invalid tanpa artifact, aktivasi sebelum evaluasi ditolak, checksum sumber/config/model/shared split dan konfigurasi eksperimen berubah ditolak.
- KNN train kurang dari lima, SVM nonkonvergen/model tidak dipublikasikan, split sampel/group kurang, operasi proses terputus dengan GET read-only/retry manual.
- Pergantian model aktif, history lintas eksperimen/koreksi model asal, probabilitas confidence kelas predict() bukan argmax.
- Frontend: 19 test; production build menghasilkan tujuh page chunks; tidak ada perubahan dependency/stylesheet/framework.
- Warning dependency TestClient/Starlette sebelumnya tetap ada. scikit-learn 1.9.1 juga memberi FutureWarning untuk SVC(probability=True); parameter sengaja tetap sesuai kontrak pengguna, bukan diubah/diupgrade.

Perintah backend source terbaru tanpa menginstal dependency:

```powershell
rtk docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v C:/dev/Data-Mining/backend:/app/backend:ro maxkomp-backend-test python -m pytest backend/tests -q
```

Frontend: `rtk proxy npm test` dan `rtk proxy npm run build` dari `frontend/`.

## Browser QA terisolasi

Frontend QA 5174 memproxy backend 8001. Container `maxkomp-experiments-qa-20260917` hanya memakai storage internal `/tmp/experiments-qa`, source backend read-only; tidak memasang storage aktual. Fixtures dibuat oleh `backend/tests/seed_experiments_qa.py` yang menolak lokasi storage lain. Semua job berikut hanya fixture QA.

| Job QA | Bukti browser |
|---|---|
| `6k9vOfgy7ijYLuVVdC_JDg` | Umum binary empat jenis fitur, kode 01/1; SVM 25/75 dan KNN 30/70 dibuat/split/train/evaluate melalui UI |
| `NBDnCIHbVTmvse0F4y6lCA` | RF multiclass root terbaca sebagai Model sebelumnya; confusion matrix A/B/C, aktif awal, laporan/download memakai adapter legacy |
| `toAMs6ULjXPUYB_BMmCW5g` | Preset PT, Decision Tree 20/80, split 16/4, evaluation eksplisit, prioritas TINDAK_LANJUT, importance DT, konfirmasi aktivasi dan payload form PT lama/prediksi berhasil |
| `I2oWFo6RoJbesBkx44mCwg` | Split gagal karena dua record tidak cukup; CREATED/Gagal tetap terlihat, training tidak diaktifkan, alasan domain ditampilkan |

SVM `EXP-7E1133BB59D8CB3E`/`SVM-8C8D1EECEF7D0DE0` menghasilkan prediksi nyata kelas **01**, confidence **33,87%**, sedangkan kelas **1** mempunyai **66,13%**. UI tidak memaksa kelas probabilitas terbesar. Unknown category diterima melalui pipeline tersimpan.

KNN `EXP-5B52A54BE0197DE2`/`KNN-1753E556F43F4510` awalnya hanya ditampilkan dan dievaluasi: SVM tetap aktif. Setelah konfirmasi eksplisit, KNN menjadi aktif. Prediksi SVM `PRED-69259D7E2F9646A3` tetap berada dalam history; keputusan pertama dan koreksi dengan alasan menambah event dari 1 → 2 → 3, tanpa menulis ulang rekomendasi/model asal. Tabel menandai test set 25%/30% sebagai tidak langsung sebanding.

Restart QA sempat menyebabkan GET laporan 502; UI menampilkan error tanpa mengulang processing. Pembacaan ulang/navigasi memulihkan laporan saat backend tersedia. Kendali browser tab pertama sempat terganggu pada dialog konfirmasi; pengujian dilanjutkan pada tab QA baru dan aktivasi diverifikasi lewat UI/backend. Ini bukan kegagalan training/aktivasi aplikasi.

Screenshot dan pemeriksaan DOM pada viewport browser normal 1265 px menunjukkan tujuh menu tetap ada, identitas tampilan lama dipertahankan, dan scrollWidth halaman sama dengan clientWidth (tanpa overflow horizontal halaman). Pengujian ini tidak menggantikan audit aksesibilitas atau UAT lengkap.

## Storage aktual dan runtime

Snapshot awal: **82 file** di `storage/`, termasuk lima job dengan evaluasi. Sesudah seluruh QA, sebelum restart utama: **82 identik**, tidak ada tambahan/pengubahan file. Snapshot awal dan akhir disimpan di `model-experiments-storage-checksums.json` setelah restart/GET smoke selesai.

Image lokal menggunakan `backend/Dockerfile.experiments`, overlay source pada runtime yang sudah terverifikasi. Tidak menjalankan pip/npm install. Versi tetap: scikit-learn 1.9.1, pandas 3.0.5, numpy 2.4.6, scipy 1.17.1, joblib 1.6.0, FastAPI 0.141.1.

Verifikasi akhir lulus: 131 test backend, 19 test frontend, production build. Server utama `maxkomp-local-config` memakai image `maxkomp-backend-local-experiments`; container sebelumnya disimpan stopped sebagai `maxkomp-local-config-before-experiments-20260917`. Frontend dimuat ulang (PID 6872), backend/frontend hanya dipublish pada loopback 8000/5173; `/health`, frontend root dan proxy API menghasilkan 200.

GET eksperimen/schema prediction/history seluruh lima job aktual menghasilkan 200. Job `ZhTquvcEwlcSxz2owWpGkA` tampil sebagai legacy aktif, model `RF-15C9BFF0C11F9530`, accuracy 98,799314% dan recall TINDAK_LANJUT 96,089385%, sama dengan artifact sebelumnya. Tidak ada POST prediksi/training/evaluasi pada job aktual.

Sesudah restart dan seluruh GET smoke: **82 file tetap identik**, changed=[], extra=[]. Hash per file sebelum/sesudah tercatat di [snapshot checksum](model-experiments-storage-checksums.json). Server/container/tab QA dihentikan/ditutup; container QA stopped dipertahankan dengan fixture internal untuk reproduksi, tidak memuat data operator. Storage aktual tidak dihapus. Penerimaan akhir tetap UAT pengguna.
