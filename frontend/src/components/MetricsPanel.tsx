import { computeMetrics } from "../services/api";
import type { PolarResult } from "../types/airfoil";

interface Props { polar: PolarResult }

export function MetricsPanel({ polar }: Props) {
  const m = computeMetrics(polar);
  if (!m) return null;

  const cards = [
    { label: "Best L/D",     value: m.best_ld,         sub: `at α = ${m.best_ld_alpha}°`,   color: "#34d399" },
    { label: "L/D at α=5°",  value: m.ld_at_target,    sub: "cruise efficiency",             color: "#34d399" },
    { label: "Max Cl",       value: m.max_cl,           sub: `stall at α = ${m.stall_alpha}°`, color: "#38bdf8" },
    { label: "Cl at α=5°",   value: m.cl_at_target,    sub: "cruise lift",                   color: "#38bdf8" },
    { label: "Cd at α=5°",   value: m.cd_at_target,    sub: "cruise drag",                   color: "#f472b6" },
    { label: "Stall Angle",  value: `${m.stall_alpha}°`, sub: "max lift angle",              color: "#fbbf24" },
  ];

  return (
    <div className="metrics-panel">
      <div className="metrics-header">
        Performance Metrics
        {polar.source === "approximation" && (
          <span className="approx-badge">⚠ Approximation — install XFoil for real results</span>
        )}
      </div>
      <div className="metrics-grid">
        {cards.map(c => (
          <div className="metric-card" key={c.label}>
            <div className="metric-value" style={{ color: c.color }}>{c.value}</div>
            <div className="metric-label">{c.label}</div>
            <div className="metric-sub">{c.sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
