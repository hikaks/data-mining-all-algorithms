# Rekonsiliasi Hasil Cleaning: 1.034 vs 1.028

Tanggal verifikasi: **16 September 2026**

## Kesimpulan

Jumlah yang menjadi source of truth untuk pipeline dan dataset saat ini adalah **1.028 record**.

Perhitungannya:

```text
1.541 input
-  77 operationally-empty
- 436 exact duplicate semantic
= 1.028 record cleaned
```

Tidak ada record yang diubah atau ditambahkan untuk memaksa hasil sama dengan angka lama.

## Asal Angka 1.034

Angka 1.034 ditemukan pada contoh JSON versi sebelum rekonsiliasi di `ERD.md`.
Contoh tersebut menggunakan:

```text
1.541 - 77 - 430 = 1.034
```

Angka yang sama juga muncul di `AGENT.md` sebagai contoh statistik yang **dilarang di-hardcode**. Tidak ditemukan:

- artifact cleaned lama berisi 1.034 record;
- cleaning report lama dengan 430 duplicate;
- source pipeline lama yang menghasilkan 1.034;
- job tersimpan pada `storage/jobs` yang dapat membuktikan hasil tersebut.

Dengan demikian, berdasarkan bukti workspace saat ini, 1.034 adalah angka ilustratif dokumentasi, bukan hasil eksekusi yang dapat direproduksi.

## Mengapa Pipeline Aktual Menemukan 436 Duplicate

Exact duplicate tidak menggunakan seluruh baris Excel mentah. Fingerprint SHA-256 dibentuk dari nilai canonical:

```text
customer
tanggal
sorted-set teknisi
nama_user
keluhan_solusi
```

Metadata sumber seperti file, sheet, nomor asli, dan nomor baris tidak masuk fingerprint. Karena itu:

- full-row duplicate Pandas pada raw dataset: **0**;
- semantic duplicate yang ditemukan pipeline: **436**.

Audit kelompok fingerprint aktual:

| Pemeriksaan | Hasil |
|---|---:|
| Record non-empty sebelum deduplikasi | 1.464 |
| Record duplicate yang dibuang | 436 |
| Kelompok fingerprint yang memiliki duplicate | 388 |
| Kelompok berukuran 2 | 340 |
| Kelompok berukuran lebih dari 2 | 48 |
| Ukuran kelompok terbesar | 3 |
| Record unik setelah deduplikasi | 1.028 |

Selisih tepat enam record antara 1.034 dan 1.028 berasal dari selisih jumlah duplicate ilustratif dan aktual:

```text
436 aktual - 430 ilustratif = 6 record
```

## Batas Rekonsiliasi

Kesimpulan ini berlaku untuk:

- file `dataset/Data_Mentah_Gabungan_PT_MAXKOMP.xlsx` yang diperiksa pada 16 September 2026;
- mapping customer dan teknisi yang saat ini berada di `backend/config`;
- algoritma fingerprint pada `backend/app/services/cleaning/duplicate_cleaner.py`;
- urutan cleaning pada pipeline saat ini.

Jika dataset, mapping, atau aturan fingerprint berubah, statistik wajib dihitung ulang dan tidak boleh disalin dari dokumen ini.

## Near Duplicate

Near duplicate tidak masuk angka 436. Sesuai keputusan final:

- near duplicate tidak dihapus otomatis;
- kandidat hanya boleh diberi flag `POTENTIAL_DUPLICATE`;
- threshold harus disetujui dan kandidat direview admin;
- fitur ini wajib selesai sebelum final train-test split, tetapi tidak memblokir historical labeling.
