import test from "node:test";
import assert from "node:assert/strict";
import {svmReplacementOptions} from '../src/experimentPolicy.ts';
import {
  runStage,
  downloadUrl,
  getJob,
  jobPath,
  request,
  uploadDataset,
  experimentPath,
  createExperiment,
  runExperiment,
  activateExperiment,
} from "../src/api.ts";
import {
  requiresActualReason,
  validateDatasetFile,
  validatePrediction,
} from "../src/validation.ts";

function mockFetch(t, implementation) {
  const original = globalThis.fetch;
  globalThis.fetch = implementation;
  t.after(() => {
    globalThis.fetch = original;
  });
}
function success(data) {
  return new Response(JSON.stringify({ success: true, data, message: "OK" }), {
    status: 200,
  });
}

test('failed legacy SVM replacement retains ratio without modifying the experiment', () => {
  const experiment = {algorithm: 'svm_linear', test_ratio: 0.25, parameters: {max_iter: 10000},
    error: {stage: 'train', message: 'Not converged'}, model_id: null};
  const before = structuredClone(experiment);
  assert.deepEqual(svmReplacementOptions(experiment), {test_ratio: 0.25, algorithm: 'svm_linear'});
  assert.deepEqual(experiment, before);
  assert.equal(svmReplacementOptions(null), null);
  assert.equal(svmReplacementOptions({...experiment, algorithm: 'knn'}), null);
  assert.equal(svmReplacementOptions({...experiment, model_id: 'SVM-valid'}), null);
  assert.equal(svmReplacementOptions({...experiment, error: null}), null);
  assert.equal(svmReplacementOptions({...experiment, error: {stage: 'split'}}), null);
  assert.equal(svmReplacementOptions({...experiment, parameters: {max_iter: -1}}), null);
});

test('experiment creation sends explicit ratio/algorithm without processing automatically', async t => {
  const calls = [];
  mockFetch(t, async (path, init) => {
    calls.push(path); assert.equal(path, '/api/jobs/job-id/experiments');
    assert.equal(init.method, 'POST');
    assert.deepEqual(JSON.parse(init.body), {test_ratio: 0.25, algorithm: 'svm_linear'});
    return success({experiment_id: 'EXP-1234'});
  });
  assert.equal((await createExperiment('job-id', 0.25, 'svm_linear')).experiment_id, 'EXP-1234');
  assert.equal(calls.length, 1);
});
test('experiment processing addresses only selected experiment and never repeats a failed POST', async t => {
  let calls = 0;
  mockFetch(t, async (path, init) => {
    calls++; assert.equal(path, '/api/jobs/job-id/experiments/EXP-1234/train');
    assert.equal(init.method, 'POST'); throw new TypeError('connection lost');
  });
  await assert.rejects(runExperiment('job-id', 'EXP-1234', 'train'), /Backend lokal/);
  assert.equal(calls, 1);
});
test('activating a model is explicit PUT, separate from selecting or evaluating it', async t => {
  mockFetch(t, async (path, init) => {
    assert.equal(path, '/api/jobs/job-id/active-experiment'); assert.equal(init.method, 'PUT');
    assert.deepEqual(JSON.parse(init.body), {experiment_id: 'EXP-1234'}); return success({active: true});
  });
  assert.equal((await activateExperiment('job-id', 'EXP-1234')).active, true);
});
test('experiment report/download paths keep legacy identity explicit and encode identifiers', () => {
  assert.equal(experimentPath('job id', 'legacy', 'evaluation'), '/api/jobs/job%20id/experiments/legacy/evaluation');
  assert.equal(experimentPath('job-id', 'EXP-1234', 'download/model'), '/api/jobs/job-id/experiments/EXP-1234/download/model');
});

test("connecting a job is GET only and never initializes labeling", async (t) => {
  mockFetch(t, async (path, init) => {
    assert.equal(path, "/api/jobs/existing-job-id");
    assert.equal(init.method, undefined);
    assert.equal(init.body, undefined);
    return success({ job_id: "existing-job-id", status: "EVALUATED" });
  });
  assert.equal((await getJob("existing-job-id")).status, "EVALUATED");
});
test("multipart upload lets the browser create its boundary", async (t) => {
  const file = new File(["test-only workbook bytes"], "test.xlsx");
  mockFetch(t, async (path, init) => {
    assert.equal(path, "/api/dataset/upload");
    assert.equal(init.method, "POST");
    assert.equal(init.headers.has("Content-Type"), false);
    assert.equal(init.body.get("file").name, "test.xlsx");
    return success({ job_id: "uploaded-job-id" });
  });
  assert.equal((await uploadDataset(file)).job_id, "uploaded-job-id");
});
test("cleaning proceeds directly without an interactive labeling request", async (t) => {
  mockFetch(t, async (path, init) => {
    assert.equal(path, "/api/jobs/job-id/clean");
    assert.equal(init.method, "POST");
    assert.equal(init.body, undefined);
    return success({ status: "LABELED" });
  });
  assert.equal((await runStage("job-id", "clean")).status, "LABELED");
});
test("generic cleaning report keeps counters and source column mappings through a read-only GET", async (t) => {
  const report = {
    rows_before: 3000,
    rows_after: 2494,
    normalization: {
      operation_count: 4370,
      source_column_map: {
        Customer_Asli: "Customer_Asli",
        keputusan_laporan: "source__keputusan_laporan",
      },
    },
  };
  mockFetch(t, async (path, init) => {
    assert.equal(path, "/api/jobs/job-id/cleaning-report?include_details=false");
    assert.equal(init.method, undefined);
    assert.equal(init.body, undefined);
    return success(report);
  });
  assert.deepEqual(
    await request(jobPath("job-id", "cleaning-report?include_details=false")),
    report,
  );
});
test("API errors preserve the domain error code and message", async (t) => {
  mockFetch(
    t,
    async () =>
      new Response(
        JSON.stringify({
          success: false,
          error: { code: "INVALID_JOB_STATE", message: "Job dikunci." },
        }),
        { status: 409 },
      ),
  );
  await assert.rejects(request("/test"), /INVALID_JOB_STATE: Job dikunci/);
});
test("non-JSON and unknown response envelopes are explained", async (t) => {
  mockFetch(t, async () => new Response("Bad gateway", { status: 502 }));
  await assert.rejects(
    request("/test"),
    /tidak memberikan response JSON \(502\)/,
  );
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 });
  await assert.rejects(request("/test"), /tidak sesuai kontrak/);
});
test("network failures are actionable and abort cancellation is preserved", async (t) => {
  mockFetch(t, async () => {
    throw new TypeError("Failed to fetch");
  });
  await assert.rejects(request("/test"), /Backend lokal tidak dapat dihubungi/);
  globalThis.fetch = async () => {
    throw new DOMException("Cancelled", "AbortError");
  };
  await assert.rejects(request("/test"), { name: "AbortError" });
});
test("custom headers and encoded job paths are preserved", async (t) => {
  mockFetch(t, async (_path, init) => {
    assert.equal(init.headers.get("X-Test"), "present");
    return success(1);
  });
  assert.equal(
    await request("/test", { headers: new Headers({ "X-Test": "present" }) }),
    1,
  );
  assert.equal(
    jobPath("unsafe/id", "dataset/preview"),
    "/api/jobs/unsafe%2Fid/dataset/preview",
  );
  assert.equal(
    downloadUrl("job-id", "predictions"),
    "/api/jobs/job-id/download/predictions",
  );
});

test("workbook validation accepts the size boundary and rejects oversized/wrong extensions", () => {
  assert.equal(
    validateDatasetFile({ name: "DATA.XLSX", size: 25 * 1024 * 1024 }),
    null,
  );
  assert.match(
    validateDatasetFile({ name: "data.xlsx", size: 25 * 1024 * 1024 + 1 }),
    /25 MB/,
  );
  assert.match(
    validateDatasetFile({ name: "data.txt", size: 1 }),
    /Hanya dataset/,
  );
});
test("missing or empty workbook cannot be uploaded", () => {
  assert.match(validateDatasetFile(null), /Pilih dataset/);
  assert.match(
    validateDatasetFile({ name: "data.xlsx", size: 0 }),
    /Workbook kosong/,
  );
});
test("prediction validates non-whitespace input without touching the API", () => {
  const valid = {
    tanggal: "2026-09-16",
    customer: "TEST ONLY",
    teknisi: "UNKNOWN",
    text_laporan: "Laporan pengujian",
  };
  assert.equal(validatePrediction(valid), null);
  assert.match(
    validatePrediction({ ...valid, text_laporan: "   " }),
    /non-whitespace/,
  );
  assert.match(validatePrediction({ ...valid, tanggal: "" }), /Tanggal/);
});
test("first actual decision is optional-reason, while a changed final decision requires reason", () => {
  assert.equal(requiresActualReason(null, "SELESAI"), false);
  assert.equal(requiresActualReason("SELESAI", "SELESAI"), false);
  assert.equal(requiresActualReason("SELESAI", "TINDAK_LANJUT"), true);
});

test('CSV/BOM upload uses multipart without a forced content type', async t => {
  assert.equal(validateDatasetFile({name: 'free.CSV', size: 20}), null);
  mockFetch(t, async (path, init) => {
    assert.equal(path, '/api/dataset/upload');
    assert.equal(init.body.get('file').name, 'free.csv');
    assert.equal(init.headers.has('Content-Type'), false);
    return success({status: 'UPLOADED', configuration_ready: false});
  });
  assert.equal((await uploadDataset(new File(['\ufeffx;y\n1;A'], 'free.csv'))).configuration_ready, false);
});
test('configuration is PUT and preserves arbitrary selected names and kinds', async t => {
  const configuration = {profile: 'generic', target_column: 'kelas bebas', features: [{name: 'jumlah', kind: 'numeric'}]};
  mockFetch(t, async (path, init) => {
    assert.equal(path, '/api/jobs/free/dataset/configuration');
    assert.equal(init.method, 'PUT');
    assert.equal(init.headers.get('Content-Type'), 'application/json');
    assert.deepEqual(JSON.parse(init.body), configuration);
    return success(configuration);
  });
  assert.deepEqual(await request(jobPath('free', 'dataset/configuration'), {method: 'PUT', body: JSON.stringify(configuration)}), configuration);
});
test('general predictions and actual decisions retain dynamic classes', async t => {
  mockFetch(t, async (_path, init) => {
    assert.deepEqual(JSON.parse(init.body), {features: {'jumlah bebas': 12}});
    return success({prediction: 'kelas ketiga', probabilities: {A: 0.1, B: 0.2, 'kelas ketiga': 0.7}});
  });
  assert.equal((await request('/predict', {method: 'POST', body: JSON.stringify({features: {'jumlah bebas': 12}})})).prediction, 'kelas ketiga');
  assert.equal(requiresActualReason('A', 'kelas ketiga'), true);
});
