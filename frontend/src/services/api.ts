
import type {
  AirfoilResult, PolarResult, PolarMetrics,
  CompareResult, OptimizeRequest, OptimizationCandidate, VaeStatus,
} from "../types/airfoil";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(`${BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ── Generation ─────────────────────────────────────────────────────────────

export function generateNACA4(p: {
  max_camber: number; camber_pos: number; max_thickness: number;
}): Promise<AirfoilResult> {
  return post("/api/generate", { mode: "naca4", ...p });
}

// ── Simulation ─────────────────────────────────────────────────────────────

export function simulate(p: {
  x: number[]; y: number[]; reynolds?: number;
  alpha_start?: number; alpha_end?: number; alpha_step?: number;
}): Promise<PolarResult> {
  return post("/api/simulate", {
    reynolds: 500_000, alpha_start: -5, alpha_end: 15, alpha_step: 1, ...p,
  });
}

// ── Database ───────────────────────────────────────────────────────────────

export function searchDatabase(p: {
  thickness_min?: number; thickness_max?: number;
  camber_min?: number; camber_max?: number; limit?: number;
}): Promise<{ results: AirfoilResult[]; count: number }> {
  return get("/api/database", p as Record<string, number>);
}

export function getAirfoilByIndex(index: number): Promise<AirfoilResult> {
  return get(`/api/database/${index}`);
}

// ── Phase 4: Comparison ────────────────────────────────────────────────────

export function compareAirfoils(
  airfoil_a: AirfoilResult,
  airfoil_b: AirfoilResult,
  reynolds  = 500_000,
): Promise<CompareResult> {
  return post("/api/compare", {
    airfoil_a: { x: airfoil_a.x, y: airfoil_a.y, name: airfoil_a.name },
    airfoil_b: { x: airfoil_b.x, y: airfoil_b.y, name: airfoil_b.name },
    reynolds,
  });
}

// ── Phase 5: VAE ───────────────────────────────────────────────────────────

export function decodeLatent(latent: number[]): Promise<AirfoilResult> {
  return post("/api/vae/decode", { latent });
}

export function getVaeStatus(): Promise<VaeStatus> {
  return get("/api/vae/status");
}

// ── Phase 5: Optimize ──────────────────────────────────────────────────────

export function optimize(req: OptimizeRequest): Promise<{ candidates: OptimizationCandidate[] }> {
  return post("/api/optimize", req);
}

// ── Health ────────────────────────────────────────────────────────────────

export function checkHealth(): Promise<{
  status: string; xfoil: boolean; vae: boolean;
}> {
  return get("/api/health");
}

// ── Utility ────────────────────────────────────────────────────────────────

export function computeMetrics(polar: PolarResult): PolarMetrics | null {
  if (!polar?.alpha?.length) return null;
  const { alpha, cl, cd, ld } = polar;

  const bestLdIdx   = ld.reduce((bi, v, i) => (v > ld[bi] ? i : bi), 0);
  const maxClIdx    = cl.reduce((bi, v, i) => (v > cl[bi] ? i : bi), 0);
  const nearest     = (t: number, arr: number[]) =>
    arr.reduce((bi, v, i) => (Math.abs(v - t) < Math.abs(arr[bi] - t) ? i : bi), 0);
  const idx5        = nearest(5.0, alpha);

  return {
    best_ld:       +ld[bestLdIdx].toFixed(1),
    best_ld_alpha: alpha[bestLdIdx],
    max_cl:        +cl[maxClIdx].toFixed(3),
    stall_alpha:   alpha[maxClIdx],
    cl_at_target:  +cl[idx5].toFixed(4),
    cd_at_target:  +cd[idx5].toFixed(5),
    ld_at_target:  +ld[idx5].toFixed(1),
  };
}

// Named export bundle so DatabasePanel etc. can do `import { api } from ...`
export const api = {
  generate:         generateNACA4,
  simulate,
  searchDatabase,
  getAirfoilByIndex,
  compareAirfoils,
  decodeLatent,
  getVaeStatus,
  optimize,
  checkHealth,
  computeMetrics,
};
