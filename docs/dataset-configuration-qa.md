# Bukti QA revisi target dan fitur

Tanggal: 16 September 2026. Engineering QA bukan UAT pengguna.

- Backend regression PT dan Umum: 81 test lulus, dua warning TestClient/Starlette lama; versi dependency tidak diubah. Termasuk group kalender identik, kode target 01/1 berbeda, dan numeric target sebagai string classification.
- Frontend: 14 test lulus dan build TypeScript/Vite berhasil.
- Browser QA berjalan di frontend 5174/backend 8001 dengan storage disposable, bukan storage operator.
- Job Umum QA `imyxXLWAGlOGxF1ps2mpDA`: CSV titik koma, 30 record, target A/B/C; numeric/kategori/teks/tanggal dipilih dan jenis teks dikoreksi. Menu processing terkunci pada UPLOADED. Konfigurasi tersimpan menjadi ANALYZED.
- Understanding menampilkan distribusi target 10/10/10 tanpa customer/teknisi/cutoff PT. Cleaning → preprocessing → split → training → evaluation berhasil lewat UI: 24 train/6 test, setiap kelas dua record test, overlap nol.
- Model QA `RF-BCB8662378613768`: confusion matrix 3×3, macro/weighted F1, kelas C dengan recall terendah ditonjolkan. Angka fixture bukan hasil model penelitian atau jaminan kualitas model.
- Form prediksi dibentuk dari empat fitur model. Kategori baru dan numeric/tanggal kosong diterima sesuai strategi model; tanggal native valid 2041-04-05 terbukti tersimpan pada history. Penanganan tanggal form memakai FormData/defaultValue agar nilai native browser tidak hilang saat render.
- Keputusan aktual C lalu koreksi A beralasan menambah event, tidak menimpa rekomendasi B. Simpan perubahan tanpa alasan disabled. Reload tetap memuat history/config terkunci. Fresh-load tidak menghasilkan console runtime error (warning controlled/uncontrolled sementara saat HMR perubahan source tidak terulang setelah reload).

## Preset PT dan runtime utama

- Job preset QA `ZeFxs4cvBEdhpDTF96W-jQ`: upload XLSX berlabel 1.541×19 → simpan preset → LABELED setelah cleaning 1.028 → preprocessing 1.018 (995/23, dua review/delapan tanggal excluded) → split 814/204 dengan overlap nol → training/reload → evaluation → prediksi flat lama dan actual decision berhasil lewat browser.
- Model preset QA `RF-E2CDFDBE76E7B46B`, evaluasi `EVAL-5B3DB6EFF14CDF4`: PT tetap menyoroti TINDAK_LANJUT. Recall QA 0/5 bukan metrik model aktual. Tidak ada model/artifact QA yang mengganti baseline operator.
- Verifikasi workbook nyata lewat script menggunakan storage sementara: semua 1.541 record/12 kolom sumber identik, SHA workbook berlabel tetap `520ec0eb776b076ffda8a3cc5ebb8f2068e04dc7fd9a570db5ca616b85992e79`.
- Backend utama `maxkomp-local-config`, image `maxkomp-backend-local-config`, storage bind workspace tetap `/app/storage`, publish **127.0.0.1:8000**. Container lama `maxkomp-local-prelabeled` stopped dan disimpan untuk rollback; tidak dihapus.
- Frontend dimuat ulang pada **127.0.0.1:5173**. Browser tetap memuat job lama aNv... EVALUATED/model RF-46320A252D2C7AC4. Health backend healthy.
- GET configuration adapter, model metadata, evaluation, prediction schema dan predictions pada kedua job lama berhasil. Tidak membuat dataset_config.json untuk legacy, tidak fitting model, tidak menambahkan history.
- Semua **30 file job aktual** dibandingkan SHA-256 sebelum QA, sebelum restart dan sesudah restart/GET legacy: **seluruh path/checksum identik**.

| Artifact aktual | SHA-256 sebelum = sesudah |
|---|---|
| Model aNvdsL7wjhr7Lqb7TAxd6g | `d6984a048891aa95d98f6622ed3c6b3ff41867586ec8b8aa60004cd3decc2238` |
| Model qXWnZIzpXCsSNlGMxGU1jA | `e818dac0c1110997427b167e6d8521508f97fa1c42507282217d780c2fd1c54f` |
| History qXWnZIzpXCsSNlGMxGU1jA | `f6ed69c362be4cff5a135d4578fc19613147de81239cc9b8cf50dda765ed5710` |

Frontend/container/tab/anonymous volume QA dihentikan/dihapus, port 5174/8001 terbukti tertutup. Artifact QA bersifat disposable tanpa backup, dapat dibuat ulang dari fixture/workbook. Tidak ada data aktual yang dihapus. Server utama 5173/8000 tetap loopback. **UAT operator belum disahkan.**

## Perbaikan UAT: error 500 laporan cleaning Umum

16 September 2026. Bukti di bagian sebelumnya tetap merupakan QA revisi awal; bagian ini mencatat perbaikan berikutnya.

- POST cleaning job `E6dKqqOAEAUlu8FPEuV5Jg` berhasil, tetapi GET `cleaning-report?include_details=false` sebelumnya gagal validasi: schema `normalization: dict[str, int]` menolak mapping `source_column_map` yang dipakai profil Umum. Ini bukan kegagalan cleaning atau backend mati.
- Dua regression case baru (Excel dan CSV titik koma) gagal dengan error yang sama sebelum fix, lalu lulus setelah schema menjadi `dict[str, int | dict[str, str]]`; tipe TypeScript diselaraskan. Format artifact dan logika cleaning/preprocessing tidak diubah.
- Test GET lengkap/ringkas memverifikasi mapping tetap utuh, respons JSON 200, detail ringkas kosong, status CLEANED dan seluruh byte artifact fixture tidak berubah. Preprocessing lanjutan berhasil hanya pada fixture disposable. Regression PT memverifikasi counter normalisasi lama tetap angka.
- Seluruh **83 test backend lulus** (43,51 detik, dua warning dependency lama), **15 test frontend lulus**, serta build TypeScript/Vite berhasil. Package versions hasil `pip freeze` sebelum/sesudah runtime identik; dependency tidak dinaikkan.
- Runtime utama tetap container `maxkomp-local-config`, kini image `maxkomp-backend-local-cleaning-report`, storage workspace yang sama dan publish **127.0.0.1:8000**. Container sebelumnya disimpan stopped sebagai `maxkomp-local-config-before-cleaning-fix` untuk rollback; tidak ada container/data operator yang dihapus.
- GET laporan lengkap dan ringkas mengembalikan JSON 200 pada job Umum `E6dKqqOAEAUlu8FPEuV5Jg` serta dua job PT legacy `aNvdsL7wjhr7Lqb7TAxd6g` dan `qXWnZIzpXCsSNlGMxGU1jA`. Health 200/healthy.
- Browser utama 5173 menghubungkan job Umum secara read-only lalu membuka Cleaning & Audit: 3.000 sebelum, 2.494 sesudah, 506 duplicate, 4.370 operasi normalisasi dan mapping kolom tampil, audit paginated berhasil, tombol Ke preprocessing tersedia, tanpa error 500.
- Seluruh **37 path dan SHA-256 file storage aktual** identik sebelum dan sesudah fix/restart/GET/browser QA, termasuk raw, cleaned, konfigurasi, model lama dan history. Job Umum tetap CLEANED, belum preprocessing/model/prediction. Tidak mengeksekusi upload/clean/preprocess/train/evaluate/predict pada job aktual.
- Halaman Cleaning & Audit dibiarkan terbuka untuk operator. Langkah selanjutnya: Ke preprocessing → Jalankan preprocessing. Penerimaan akhir proyek tetap UAT operator; kualitas model tidak dinyatakan hanya dari fix ini.
