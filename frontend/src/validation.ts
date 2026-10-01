import type { PredictionInput, PredictionResult } from "./types";

export function validateDatasetFile(
  file: Pick<File, "name" | "size"> | null,
): string | null {
  if (!file) return "Pilih dataset .xlsx atau .csv terlebih dahulu.";
  if (!/\.(xlsx|csv)$/i.test(file.name))
    return "Hanya dataset .xlsx atau .csv yang diterima.";
  if (file.size === 0) return "Workbook kosong tidak dapat diunggah.";
  if (file.size > 25 * 1024 * 1024)
    return "Ukuran workbook melebihi batas 25 MB.";
  return null;
}

export function validatePrediction(input: PredictionInput): string | null {
  if (!input.tanggal) return "Tanggal laporan wajib diisi.";
  if (!input.customer.trim() || input.text_laporan.trim().length < 3)
    return "Customer wajib diisi dan laporan minimal 3 karakter non-whitespace.";
  return null;
}

export function requiresActualReason(
  previous: PredictionResult["actual_decision"],
  next: PredictionResult["prediction"],
) {
  return previous != null && previous !== next;
}
