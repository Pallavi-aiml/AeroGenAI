import { useState } from "react";
import { AirfoilCanvas } from "./AirfoilCanvas";
import { ComparePolarChart } from "./PolarChart";
import { compareAirfoils, computeMetrics } from "../services/api";
import type { AirfoilResult, CompareResult } from "../types/airfoil";

interface Props {
  airfoilA: AirfoilResult | null;
  airfoilB: AirfoilResult | null;
  reynolds: number;
}

export function ComparePanel({ airfoilA, airfoilB, reynolds }: Props) {
  const [result, setResult]   = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const run = async () => {
    if (!airfoilA || !airfoilB) return;
    setLoading(true);
    setError(null);
    try {
      const r = await compareAirfoils(airfoilA, airfoilB, reynolds);
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  };

  if (!airfoilA || !airfoilB) {
    return (
      <div className="compare-empty">
        <div className="empty-icon">⬡⬡</div>
        <div className="empty-title">Two airfoils needed for comparison</div>
        <div className="empty-sub">Generate or load a second airfoil, then come back here.</div>
      </div>
    );
  }

  return (
    <div className="compare-panel">
      {/* Shape side-by-side */}
      <div className="compare-shapes">
        <div className="compare-shape-card">
          <div className="card-title compare-label-a">{airfoilA.name}</div>
          <AirfoilCanvas x={airfoilA.x} y={airfoilA.y} color="#38bdf8" height={140} />
        </div>
        <div className="compare-shape-card">
          <div className="card-title compare-label-b">{airfoilB.name}</div>
          <AirfoilCanvas x={airfoilB.x} y={airfoilB.y} color="#fbbf24" height={140} />
        </div>
      </div>

      <button className="btn-primary wide" onClick={run} disabled={loading}>
        {loading ? <span className="spinner" /> : "⬡"}
        Compare Both Airfoils
      </button>

      {error && <div className="status-bar error">⚠ {error}</div>}

      {result && (
        <>
          {/* Metrics table */}
          <div className="compare-table-wrap card">
            <div className="card-title">Results Table</div>
            <table className="compare-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th style={{ color: "#38bdf8" }}>{result.a.name}</th>
                  <th style={{ color: "#fbbf24" }}>{result.b.name}</th>
                </tr>
              </thead>
              <tbody>
                {(["best_ld", "best_ld_alpha", "max_cl", "stall_alpha",
                   "cl_at_target", "cd_at_target", "ld_at_target"] as const).map(k => {
                  const ma = computeMetrics(result.a.polar);
                  const mb = computeMetrics(result.b.polar);
                  if (!ma || !mb) return null;
                  const va = ma[k] as number;
                  const vb = mb[k] as number;
                  const labels: Record<string, string> = {
                    best_ld: "Best L/D", best_ld_alpha: "Best L/D α (°)",
                    max_cl: "Max Cl", stall_alpha: "Stall α (°)",
                    cl_at_target: "Cl @ 5°", cd_at_target: "Cd @ 5°",
                    ld_at_target: "L/D @ 5°",
                  };
                  const higherBetter = !["cd_at_target"].includes(k);
                  const better = higherBetter ? va > vb : va < vb;
                  return (
                    <tr key={k}>
                      <td>{labels[k]}</td>
                      <td className={better ? "better" : ""}>{va}</td>
                      <td className={!better ? "better" : ""}>{vb}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Overlaid polar charts */}
          <div className="card">
            <div className="card-title">Overlaid Polar Charts</div>
            <ComparePolarChart
              polarA={result.a.polar} nameA={result.a.name}
              polarB={result.b.polar} nameB={result.b.name}
            />
          </div>
        </>
      )}
    </div>
  );
}
