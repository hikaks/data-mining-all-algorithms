# Frontend Workflow dan UAT Lokal

Revisi 17 September 2026: menu Training kini membuat eksperimen dengan rasio/algoritma pilihan, lalu split dan training secara eksplisit. Evaluation menampilkan eksperimen yang dipilih; **Gunakan untuk prediksi** memerlukan konfirmasi dan tidak terjadi otomatis. Model sebelumnya tetap aktif sampai pilihan itu diubah. Tutorial dan kontrak terkini: [model-experiments.md](model-experiments.md). Tujuh menu dan gaya tampilan dipertahankan.

Diperiksa: **16 September 2026**. Implementasi Tahap 12 selesai; **UAT operator belum disahkan**. Aplikasi tetap local-only untuk satu operator dan tidak memiliki authentication/session.

## Menjalankan dan membuka workspace

Backend harus tersedia pada `127.0.0.1:8000`, lalu jalankan `npm run dev` dari folder `frontend`. Buka `http://127.0.0.1:5173/`.

Menu Dataset menerima `.xlsx`/`.csv` maksimal 25 MB. Upload membuat job UPLOADED dengan preview raw; tahap lain terkunci. Pada panel Target & fitur, pilih sheet Excel atau koreksi pemisah CSV, profil Umum/PT, target dan fitur/jenis, lalu Simpan konfigurasi. Umum memakai label yang tersedia dan nama kolom/kelas bebas. Preset PT hanya menerima kontrak resmi DATA_MENTAH (12 atau 19 kolom), mempertahankan identifikasi/impor otomatis. Setelah konfigurasi tersimpan, lanjut understanding → cleaning → preprocessing → split/training → evaluation → prediction. Tidak ada labeling manual. Kontrak terbaru dan kasus negatif ada pada [dataset-configuration.md](dataset-configuration.md).

Konfigurasi terkunci setelah cleaning. Untuk target/fitur/label berbeda, upload job baru. Job lama memakai adapter preset read-only tanpa menulis config/mengubah model. Generic evaluation menonjolkan recall kelas terendah dan macro/weighted F1; prediksi Umum memuat form fitur/kelas aktual dari schema model tersimpan, termasuk opsi keputusan aktual dinamis. Penjelasan domain/Needs Review/angka PT di bawah tidak berlaku pada target Umum.

Untuk melanjutkan artifact yang sudah ada, masukkan job ID pada **Buka job lokal**. Job terakhir disimpan di localStorage hanya sebagai pilihan workspace, bukan session autentikasi. Koneksi memakai GET `/api/jobs/{job_id}`, sehingga job `EVALUATED` tidak mencoba menginisialisasi labeling atau menurunkan status.

Baseline lama: job `aNvdsL7wjhr7Lqb7TAxd6g`, model `RF-46320A252D2C7AC4`. Job operator berikutnya: `qXWnZIzpXCsSNlGMxGU1jA`, model `RF-6FD18E1CA248CA67`. Keduanya EVALUATED. Raw, label, model, evaluation, dan history yang dibuat operator tidak ditimpa oleh pengujian.

## Urutan penggunaan

| Menu | Hasil dan aksi utama |
|---|---|
| Dataset | Upload Excel/CSV; pilih sheet/pemisah, profil, target dan fitur/jenis; simpan konfigurasi; buka job dan preview/export |
| Data Understanding | Distribusi target Umum atau distribusi domain PT, missing/unique, tanpa cutoff PT untuk Umum |
| Cleaning & Audit | Cleaning dan transfer label otomatis, ringkasan normalisasi/penghapusan, audit per bagian, download cleaned |
| Preprocessing | Langsung setelah cleaning; feature contract, pengecualian, leakage audit, target distribution, near-duplicate group/pair/conflict, download features |
| Split & Training | Manifest group-aware, distribusi train/test, validasi overlap, fitting baseline, parameter/provenance model |
| Evaluation | Recall minoritas, precision/F1, balanced accuracy/accuracy, confusion matrix, feature importance, keterbatasan |
| Prediction | Input laporan baru, rekomendasi/probabilities, history, catat/koreksi actual decision, export JSONL |

Ikuti tombol lanjutan pada halaman. Processing backend bersifat sinkron: tunggu respons selesai sebelum melanjutkan. UI menampilkan loading indeterminate, bukan estimasi persentase progress yang tidak tersedia dari backend. Jika request gagal, error domain ditampilkan dan artifact hanya dianggap tersedia setelah metadata dibaca kembali.

Identifikasi memakai kebijakan business-rule versioned `ai-assisted-id-v1`, bukan panggilan LLM/cloud baru. Label otomatis mempunyai alasan, confidence, role validator, dan provenance. Label workbook diimpor apa adanya setelah validasi. Needs Review bukan kelas Random Forest, dikecualikan dari training, dan tidak memblokir kelanjutan karena tugas labeling manual. Gate tetap memerlukan dua kelas dengan minimal dua sampel per kelas. Kelanjutan job lama hanya melengkapi UNLABELED; keputusan final/review dan audit lama dipertahankan. Job yang sudah dipreprocess/dilatih tidak dimigrasikan. Koreksi label memakai workbook/job baru, bukan fitur labeling interaktif.

Preprocessing memisahkan identifier/metadata/target dari fitur. Learned TF-IDF, encoding, dan imputasi hanya di-fit pada train set. Split manifest menjadi sumber record ID train/test. Record ID bersifat job-specific, sehingga upload workbook yang sama sebagai job baru tidak menjanjikan holdout/metrik yang identik; reproduksi baseline memakai manifest dan dependency baseline yang sama.

## Batas model yang wajib dipahami

Baseline lama `aNvdsL7wjhr7Lqb7TAxd6g` mempunyai accuracy **98,04%**, tetapi recall TINDAK_LANJUT **40%**: 2 dari 5 kasus test ditemukan. Job operator `qXWnZIzpXCsSNlGMxGU1jA` mempunyai recall minoritas **20%**. UI membaca report masing-masing job dan menonjolkan recall minoritas/confusion matrix, bukan hanya accuracy. Upload/job baru tidak menjamin metrik baseline yang sama.

Target historical berasal dari weak supervision, bukan ground-truth manusia independen. Test set minoritas kecil, dan confidence bukan jaminan ketepatan atau probabilitas terkalibrasi. Hasil inference adalah **rekomendasi**, bukan keputusan final.

Prediction memuat pipeline tersimpan tanpa fitting ulang. Admin dapat mencatat actual decision pertama tanpa alasan; perubahan keputusan lama wajib beralasan. Event baru ditambahkan ke JSONL, sedangkan rekomendasi dan event lama tetap utuh. Jangan memakai job aktual untuk prediksi contoh/dummy.

## Struktur dan perilaku frontend

- App shell menangani job, navigasi, dan status artifact; tujuh page module dimuat melalui React.lazy/Suspense di module scope. Modul Historical Labeling dihapus.
- Backend tetap source of truth. Angka report berasal dari API, bukan nilai dummy atau hardcode baseline.
- Preview raw/cleaned, audit cleaning, dan prediction history memakai server-side pagination 25 record.
- Cleaning report ringkas tidak mengirim seluruh detail operasi; audit dibaca per bagian. GET audit label lama dipertahankan read-only, tanpa halaman atau aksi mutasi labeling.
- Chart memakai agregat HTML/CSS ringan tanpa menambahkan chart library. Tabel lebar mempunyai scroll internal.
- Navigasi viewport kecil dapat dibuka/ditutup; sidebar tertutup tidak dapat difokuskan. Dialog memiliki focus trap, Escape, restoration of focus, dan error di dalam dialog.
- Export menggunakan download endpoint backend; raw tidak diubah oleh halaman.

## Verifikasi terbaru — target dan fitur Umum

81 test backend, 14 test frontend, build, QA browser lengkap Umum dan preset PT lulus. Server utama telah dimuat ulang, seluruh checksum 30 file job operator tetap identik. QA sementara/volume disposable dibersihkan dan port 5174/8001 tertutup; loopback 5173/8000 berjalan. Bukti, job QA, checksum model/history dan batas UAT ada di [dataset-configuration-qa.md](dataset-configuration-qa.md).

## Verifikasi historis tanpa labeling manual

Revisi tanpa labeling manual diverifikasi pada job QA disposable `NGfell4CzPg-_o6ZLtAxRQ`:
upload workbook berlabel lewat HTTP (201, 19 kolom), lalu browser menampilkan label input
1.424/36/81 dan tujuh menu tanpa Historical Labeling. Cleaning lewat UI merespons LABELED
dan tombol langsung ke preprocessing. Preprocessing lewat UI menghasilkan 1.018 kandidat
(995 SELESAI, 23 TINDAK_LANJUT), mengecualikan dua review/delapan tanggal, serta leakage
audit PASS. Tidak ada request labeling manual. Backend utama telah dimuat ulang dan seluruh
30 file artifact dua job operator tetap identik checksum setelah restart. Pengujian QA
tidak mengubah model atau history aktual.

QA revisi telah dihentikan/dihapus setelah selesai (artifact disposable tanpa backup,
dapat dibuat ulang). Port 5174/8001 tertutup; server utama 5173/8000 tetap berjalan di
loopback. Workspace lama EVALUATED berhasil dibuka read-only dengan ringkasan/export label.
Audit dependency frontend produksi (`npm audit --omit=dev`) menemukan 0 vulnerability;
`compileall` backend lulus. Penerimaan operator/model tetap belum disahkan.

Frontend diverifikasi memakai Node.js **24.14.0**:

```powershell
cd frontend
npm test
npm run build
```

Hasil revisi: **11 test frontend lulus**, production build tujuh page chunk berhasil. Audit npm pada pemeriksaan Tahap 12 menemukan **0 vulnerability**. Test meliputi koneksi GET tanpa initialize, multipart boundary, cleaning tanpa request labeling interaktif, error/network/abort, path encoding, ukuran/extension file, whitespace, dan guard alasan.

Backend: **58 test lulus**, termasuk impor/identifikasi label, transfer cleaning, label invalid/parsial, konflik duplicate, endpoint mutasi 404, kelanjutan job CLEANED/pending lama tanpa overwrite, metadata read-only, laporan compact, oversized/corrupt upload, dan append-only history. Dua warning TestClient/Starlette masih terbuka.

QA historis Tahap 12 menggunakan backend disposable 8001 tanpa mount storage aktual. Dataset asli di-upload HTTP, kemudian cleaning → initialize/auto labeling → preprocessing → split → training → evaluation → prediction → actual decision/koreksi diuji lewat UI. Ini bukti sebelum revisi, **bukan alur labeling yang masih harus dijalankan**. Upload form/transport multipart diverifikasi lewat test frontend/API; dialog OS tidak diotomasi.

Hasil browser:

- Dataset QA: 1.541 raw → 1.028 cleaned → 1.026 label final/2 review → 1.018 kandidat → 814 train/204 test.
- Prediksi sebelum evaluation terkunci; input whitespace ditolak tanpa event.
- Satu prediksi QA mempunyai probabilities/confidence dan history; keputusan aktual menambah event kedua, koreksi beralasan menambah event ketiga.
- Simpan koreksi tanpa alasan tidak aktif; fokus dialog tetap di dalam dialog dan Escape menutupnya.
- Job aktual dapat dibuka tanpa mutasi labeling; preview raw memuat 25 record dan halaman kedua tampil.
- Layout desktop dan viewport kecil diperiksa; lebar dokumen tidak melampaui viewport kecil.

Artifact/prediksi QA tidak dipindahkan ke storage aktual. Metrik/model QA bukan pengganti baseline aktual. Raw aktual mempunyai SHA-256 yang sama dengan workbook sumber (`07e734b22a3f2684e27992754d27ab2985088940fcfa0499cea02138050f889a`).

Setelah verifikasi, frontend QA dihentikan dan container disposable beserta artifact QA dihapus (dapat dibuat ulang, tanpa backup). Port 5174/8001 sudah tertutup; frontend utama 5173 dan backend utama 8000 tetap berjalan hanya di loopback.

### Mengulang QA terisolasi

Jalankan backend disposable dari root proyek:

```powershell
docker build --target runtime -f backend/Dockerfile -t maxkomp-backend-local-prelabeled .
docker run --rm --name maxkomp-ui-qa-prelabeled -p 127.0.0.1:8001:8000 -e STORAGE_ROOT=/app/qa-storage maxkomp-backend-local-prelabeled
```

Di terminal lain:

```powershell
cd frontend
npm run dev:qa
```

Buka `http://127.0.0.1:5174/`. Konfigurasi QA hanya mem-proxy API ke port 8001; tidak mengakses backend aktual port 8000. Upload workbook ke QA, lakukan pengujian, lalu hentikan frontend/container QA. Karena tanpa volume, artifact QA bersifat sementara dan dapat dibuat ulang. Jangan memasang volume `storage/` aktual ke container QA.

## Checklist UAT operator berikutnya

- [ ] Buka job aktual dan pastikan report/evidence dapat dipahami serta export dapat dibuka.
- [ ] Pada job QA baru, upload workbook valid dan satu workbook invalid; error harus jelas tanpa artifact setengah jadi.
- [ ] Pastikan UPLOADED mengunci processing; setelah konfigurasi disimpan target/fitur terbaca dan cleaning → preprocessing → split/training/evaluation terbuka tanpa labeling manual.
- [ ] Uji Excel sheet/kolom bebas dan CSV tiga pemisah; koreksi jenis, lihat target kosong/peringatan leakage, dan pastikan config terkunci setelah cleaning.
- [ ] Uji form prediksi Umum, kategori baru, kelas aktual multiclass, macro/weighted F1 dan recall terendah; job PT lama tetap terbaca tanpa perubahan.
- [ ] Pastikan alasan/confidence identifikasi dan pengecualian Needs Review/tanggal dapat dipahami.
- [ ] Pastikan peringatan recall minoritas dan rekomendasi-only cukup jelas untuk penggunaan operasional.
- [ ] Pada job QA, buat prediksi dan catat/koreksi actual decision; prediksi awal tidak berubah.
- [ ] Tinjau kenyamanan tabel, filter, loading/error, keyboard, dan ukuran layar yang biasa dipakai.
- [ ] Catat masalah, lalu sahkan UAT setelah masalah blocking ditutup.

Implementasi selesai tidak menggantikan persetujuan pengguna atau validasi model pada data operasional baru.
