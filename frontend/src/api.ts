import type { JobOverview, DatasetUploadResult, AlgorithmId, Experiment } from "./types";

interface SuccessEnvelope<T> {
  success: true;
  data: T;
  message: string;
}

interface ErrorEnvelope {
  success: false;
  error: { code: string; message: string };
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (typeof init?.body === "string" && !headers.has("Content-Type"))
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === "AbortError")
      throw caught;
    throw new Error(
      "Backend lokal tidak dapat dihubungi. Pastikan server pada 127.0.0.1:8000 berjalan.",
    );
  }
  let payload: SuccessEnvelope<T> | ErrorEnvelope;
  try {
    payload = await response.json();
  } catch {
    throw new Error(
      `Backend tidak memberikan response JSON (${response.status}). Pastikan backend lokal berjalan.`,
    );
  }
  if (!response.ok || payload.success !== true) {
    const detail = (payload as ErrorEnvelope).error;
    const message = detail
      ? `${detail.code}: ${detail.message}`
      : `Request gagal (${response.status}). Response backend tidak sesuai kontrak.`;
    throw new Error(message);
  }
  return payload.data;
}

export function jobPath(jobId: string, suffix = "") {
  return `/api/jobs/${encodeURIComponent(jobId)}${suffix ? `/${suffix}` : ""}`;
}
export function getJob(jobId: string) {
  return request<JobOverview>(jobPath(jobId));
}
export function uploadDataset(file: File) {
  const body = new FormData();
  body.append("file", file);
  return request<DatasetUploadResult>("/api/dataset/upload", {
    method: "POST",
    body,
  });
}
export function runStage(jobId: string, stage: string) {
  return request<Record<string, unknown>>(jobPath(jobId, stage), {
    method: "POST",
  });
}
export function downloadUrl(jobId: string, artifact: string) {
  return jobPath(jobId, `download/${artifact}`);
}

export function experimentPath(jobId: string, experimentId: string, suffix = '') {
  return jobPath(jobId, `experiments/${encodeURIComponent(experimentId)}${suffix ? `/${suffix}` : ''}`);
}
export function createExperiment(jobId: string, testRatio: number, algorithm: AlgorithmId) {
  return request<Experiment>(jobPath(jobId, 'experiments'), {
    method: 'POST', body: JSON.stringify({test_ratio: testRatio, algorithm}),
  });
}
export function runExperiment(jobId: string, experimentId: string, stage: 'split' | 'train' | 'evaluate') {
  return request(experimentPath(jobId, experimentId, stage), {method: 'POST'});
}
export function activateExperiment(jobId: string, experimentId: string) {
  return request<Experiment>(jobPath(jobId, 'active-experiment'), {
    method: 'PUT', body: JSON.stringify({experiment_id: experimentId}),
  });
}
