import { lazy, Suspense, useEffect, useState, useRef } from "react";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  BrainCircuit,
  Check,
  ChevronRight,
  Database,
  FlaskConical,
  Layers3,
  Menu,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { getJob } from "./api";
import { errorMessage, Loading, Notice } from "./components/ui";
import type { JobOverview, PageId } from "./types";

const DatasetPage = lazy(() => import("./pages/DatasetPage"));
const UnderstandingPage = lazy(() => import("./pages/UnderstandingPage"));
const CleaningPage = lazy(() => import("./pages/CleaningPage"));
const PreprocessingPage = lazy(() => import("./pages/PreprocessingPage"));
const TrainingPage = lazy(() => import("./pages/TrainingPage"));
const EvaluationPage = lazy(() => import("./pages/EvaluationPage"));
const PredictionPage = lazy(() => import("./pages/PredictionPage"));
const pages = [
  {
    id: "dataset",
    label: "Dataset",
    icon: Database,
    artifact: "raw",
    index: "01",
  },
  {
    id: "understanding",
    label: "Data Understanding",
    icon: BarChart3,
    artifact: "understanding",
    index: "02",
  },
  {
    id: "cleaning",
    label: "Cleaning & Audit",
    icon: FlaskConical,
    artifact: "cleaned",
    index: "03",
  },
  {
    id: "preprocessing",
    label: "Preprocessing",
    icon: Layers3,
    artifact: "preprocessed",
    index: "04",
  },
  {
    id: "training",
    label: "Split & Training",
    icon: BrainCircuit,
    artifact: "model",
    index: "05",
  },
  {
    id: "evaluation",
    label: "Evaluation",
    icon: Activity,
    artifact: "evaluation",
    index: "06",
  },
  {
    id: "prediction",
    label: "Prediction",
    icon: Sparkles,
    artifact: "predictions",
    index: "07",
  },
] as const;
const components = {
  understanding: UnderstandingPage,
  cleaning: CleaningPage,
  preprocessing: PreprocessingPage,
  training: TrainingPage,
  evaluation: EvaluationPage,
  prediction: PredictionPage,
};

function App() {
  const [job, setJob] = useState<JobOverview | null>(null);
  const jobGeneration = useRef(0);
  const [selectedExperiment, setSelectedExperiment] = useState<string | null>(null);
  const [activePage, setActivePage] = useState<PageId>("dataset");
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mobileMenu, setMobileMenu] = useState(false);
  async function connect(id: string) {
    const generation = ++jobGeneration.current;
    setConnecting(true);
    setError(null);
    try {
      const next = await getJob(id.trim());
      if (generation !== jobGeneration.current) return;
      setJob(next);
      setSelectedExperiment(next.active_experiment_id ?? null);
      localStorage.setItem("maxkomp-job-id", next.job_id);
      setActivePage("dataset");
    } catch (caught) {
      if (generation !== jobGeneration.current) return;
      setError(errorMessage(caught));
      throw caught;
    } finally {
      if (generation === jobGeneration.current) setConnecting(false);
    }
  }
  useEffect(() => {
    const saved = localStorage.getItem("maxkomp-job-id");
    if (saved) void connect(saved).catch(() => {});
  }, []);
  useEffect(() => {
    if (!mobileMenu) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileMenu(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [mobileMenu]);
  async function refresh() {
    const generation = jobGeneration.current;
    if (job) {
      const next = await getJob(job.job_id);
      if (generation === jobGeneration.current) setJob(next);
    }
  }
  function navigate(page: PageId) {
    if (page !== 'dataset' && (!job || job.configuration_ready === false)) return;
    setActivePage(page);
    setMobileMenu(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  const completed = pages
    .slice(0, 6)
    .filter((page) => job?.artifacts[page.artifact]).length;
  const ActiveComponent =
    activePage === "dataset" ? null : components[activePage];
  return (
    <div className="console-shell">
      <aside className={`sidebar ${mobileMenu ? "open" : ""}`}>
        <a
          className="console-brand"
          href="#"
          onClick={(event) => {
            event.preventDefault();
            navigate("dataset");
          }}
        >
          <span className="brand-symbol">
            M<span>.</span>
          </span>
          <div>
            <strong>MAXKOMP</strong>
            <small>DATA MINING CONSOLE</small>
          </div>
        </a>
        <div className="sidebar-section-label">
          RESEARCH WORKFLOW <span>7 MODULES</span>
        </div>
        <nav aria-label="Navigasi workflow">
          {pages.map((page) => (
            <button
              key={page.id}
              className={`nav-item ${activePage === page.id ? "active" : ""}`}
              disabled={page.id !== "dataset" && (!job || job.configuration_ready === false)}
              onClick={() => navigate(page.id)}
            >
              <page.icon size={18} />
              <span>{page.label}</span>
              {job?.artifacts[page.artifact] ? (
                <Check className="nav-check" size={14} />
              ) : (
                <small>{page.index}</small>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-indicator">
            <span />
            LOCAL WORKSPACE
          </div>
          <p>
            Satu operator. Artifact tersimpan di komputer ini, tanpa deployment
            publik.
          </p>
          <div>
            <ShieldCheck size={16} />
            <span>Backend sebagai source of truth</span>
          </div>
        </div>
      </aside>
      {mobileMenu && (
        <button
          className="sidebar-backdrop"
          aria-label="Tutup navigasi"
          onClick={() => setMobileMenu(false)}
        />
      )}
      <div className="console-main">
        <header className="console-topbar">
          <div className="breadcrumb">
            <button
              className="mobile-toggle"
              aria-label={mobileMenu ? "Tutup navigasi" : "Buka navigasi"}
              onClick={() => setMobileMenu(!mobileMenu)}
            >
              {mobileMenu ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>
              {pages.find((page) => page.id === activePage)?.label}
            </strong>
          </div>
          <div className="header-meta">
            <span className="status-chip">
              <span />
              {job?.status ?? "BELUM ADA JOB"}
            </span>
            {job && (
              <button
                className="icon-button"
                aria-label="Refresh status job"
                onClick={() =>
                  void refresh().catch((caught) =>
                    setError(errorMessage(caught)),
                  )
                }
              >
                <RefreshCw size={16} />
              </button>
            )}
          </div>
        </header>
        <main className="console-content">
          {job && (
            <div className="job-context">
              <div>
                <span>ACTIVE JOB</span>
                <code>{job.job_id}</code>
                <small title={job.original_filename}>
                  {job.original_filename}
                </small>
              </div>
              <div>
                <strong>
                  {completed}
                  <span>/6</span>
                </strong>
                <small>artifact tahap tersedia</small>
              </div>
            </div>
          )}
          {error && (
            <Notice tone="error">
              <div className="notice-dismiss">
                <span>{error}</span>
                <button aria-label="Tutup error" onClick={() => setError(null)}>
                  <X size={16} />
                </button>
              </div>
            </Notice>
          )}
          {connecting && (
            <Notice>Menghubungkan job tanpa mengubah data…</Notice>
          )}
          <Suspense fallback={<Loading label="Menyiapkan halaman…" />}>
            {activePage === "dataset" ? (
              <DatasetPage
                key={job?.job_id ?? "empty"}
                job={job}
                connect={connect}
                refresh={refresh}
                navigate={navigate}
              />
            ) : job && ActiveComponent ? (
              <ActiveComponent
                key={`${job.job_id}:${activePage === 'prediction' ? job.active_experiment_id ?? 'none' : ''}`}
                job={job}
                refresh={refresh}
                navigate={navigate}
                selectedExperiment={selectedExperiment}
                selectExperiment={setSelectedExperiment}
              />
            ) : null}
          </Suspense>
          <footer className="console-footer">
            <span>PT MAXKOMP · RESEARCH DESK</span>
            <span>
              Local-only <ArrowUpRight size={12} /> 127.0.0.1
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
export default App;
