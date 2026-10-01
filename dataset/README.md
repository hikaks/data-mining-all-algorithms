# Dataset siap pakai

> Catatan Git: workbook `.xlsx` pada folder ini berisi data operasional dan sengaja
> tidak disimpan di repository publik. Salin workbook yang diperlukan ke folder
> `dataset/` pada komputer lokal sebelum mengikuti langkah di bawah.

Gunakan `Data_Berlabel_Gabungan_PT_MAXKOMP.xlsx` pada menu Dataset → Upload & validasi.
Tidak ada tahap atau menu labeling manual. Setelah upload, jalankan cleaning, lalu langsung preprocessing.

Workbook berlabel mempertahankan semua **1.541 baris dan 12 kolom sumber** dari
`Data_Mentah_Gabungan_PT_MAXKOMP.xlsx`; file mentah tidak diubah. Sheet tetap `DATA_MENTAH`.
Tujuh kolom tambahan, berurutan:

```text
keputusan_laporan, labeling_status, label_validator_role, label_updated_at,
label_confidence, label_decision_reason, label_policy_version
```

Sheet `Keterangan_Label` menjelaskan definisi, sumber, checksum, kebijakan, dan keterbatasan label.

| Tahap | SELESAI | TINDAK_LANJUT | NEEDS_REVIEW | Total |
|---|---:|---:|---:|---:|
| Workbook upload | 1.424 | 36 | 81 | 1.541 |
| Setelah cleaning | 1.003 | 23 | 2 | 1.028 |
| Kandidat preprocessing | 995 | 23 | 0 | 1.018 |

Cleaning menghapus 77 baris operationally-empty dan 436 exact duplicate. Preprocessing
mengecualikan dua Needs Review dan delapan tanggal invalid. Baris yang dikecualikan
tetap tersedia dalam workbook sumber/artifact dan alasan tercatat dalam report.

Label dibuat dari kebijakan deterministik yang sebelumnya disetujui, `ai-assisted-id-v1`:
indikasi tindak lanjut didahulukan; status `OK` hanya menjadi bukti selesai ketika tidak
ada indikasi tersebut. Bukti tidak cukup menjadi `NEEDS_REVIEW` dengan target kosong,
**bukan kelas model dan tidak perlu dilabeli manual untuk melanjutkan**.
Setiap identifikasi mencatat `AI_VALIDATOR`, alasan, confidence, waktu, dan versi kebijakan.
Ini weak supervision, bukan ground-truth manusia independen; confidence bukan jaminan benar.

Upload berlabel mengimpor keputusan yang ada, tidak menentukannya ulang. Workbook mentah
12 kolom masih didukung untuk kompatibilitas: backend mengidentifikasi otomatis saat upload.
Label/audit parsial atau tidak valid ditolak; label exact duplicate yang bertentangan
tidak dibuang diam-diam. Koreksi dataset dilakukan pada salinan workbook, lalu upload
sebagai job baru; jangan mengubah artifact job yang sudah dipakai model.

SHA-256 sumber mentah: `07e734b22a3f2684e27992754d27ab2985088940fcfa0499cea02138050f889a`.

SHA-256 workbook berlabel: `520ec0eb776b076ffda8a3cc5ebb8f2068e04dc7fd9a570db5ca616b85992e79`.
