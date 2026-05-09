import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
  ScatterChart, Scatter,
} from "recharts";
import type { PolarResult } from "../types/airfoil";

const CHART_STYLE = { fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" };
const TOOLTIP_STYLE = { background: "#0f172a", border: "1px solid #1e293b", borderRadius: 6 };

interface SingleProps { polar: PolarResult; color?: string; label?: string }
interface CompareProps {
  polarA: PolarResult; nameA: string;
  polarB: PolarResult; nameB: string;
}

// ── Single airfoil polar charts ──────────────────────────────────────────────

export function PolarChart({ polar, color = "#38bdf8", label }: SingleProps) {
  const data = polar.alpha.map((a, i) => ({
    alpha: a, Cl: polar.cl[i], Cd: polar.cd[i], LD: polar.ld[i],
  }));
  // Drag bucket: Cd vs Cl
  const bucket = polar.cl.map((cl, i) => ({ Cl: cl, Cd: polar.cd[i] }));

  return (
    <div className="polar-charts">
      {label && <div className="polar-label">{label}</div>}

      <div className="chart-block">
        <div className="chart-title">Lift Curve — Cl vs α</div>
        <ResponsiveContainer width="100%" height={170}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: -8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="alpha" tick={CHART_STYLE} stroke="#334155"
              label={{ value: "α (deg)", position: "insideBottom", offset: -2, style: CHART_STYLE }} />
            <YAxis tick={CHART_STYLE} stroke="#334155" />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#94a3b8" }}
              itemStyle={{ color }} formatter={(v: number) => v.toFixed(4)}
              labelFormatter={(l) => `α = ${l}°`} />
            <ReferenceLine x={0} stroke="#334155" strokeDasharray="3 3" />
            <ReferenceLine y={0} stroke="#334155" strokeDasharray="3 3" />
            <Line type="monotone" dataKey="Cl" stroke={color} strokeWidth={2}
              dot={false} activeDot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-block">
        <div className="chart-title">Drag Polar — Cd vs α</div>
        <ResponsiveContainer width="100%" height={170}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: -8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="alpha" tick={CHART_STYLE} stroke="#334155"
              label={{ value: "α (deg)", position: "insideBottom", offset: -2, style: CHART_STYLE }} />
            <YAxis tick={CHART_STYLE} stroke="#334155" />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#94a3b8" }}
              itemStyle={{ color: "#f472b6" }} formatter={(v: number) => v.toFixed(5)}
              labelFormatter={(l) => `α = ${l}°`} />
            <Line type="monotone" dataKey="Cd" stroke="#f472b6" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-block">
        <div className="chart-title">Efficiency — L/D vs α</div>
        <ResponsiveContainer width="100%" height={170}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: -8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="alpha" tick={CHART_STYLE} stroke="#334155"
              label={{ value: "α (deg)", position: "insideBottom", offset: -2, style: CHART_STYLE }} />
            <YAxis tick={CHART_STYLE} stroke="#334155" />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#94a3b8" }}
              itemStyle={{ color: "#34d399" }} formatter={(v: number) => v.toFixed(1)}
              labelFormatter={(l) => `α = ${l}°`} />
            <ReferenceLine x={0} stroke="#334155" strokeDasharray="3 3" />
            <Line type="monotone" dataKey="LD" stroke="#34d399" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-block">
        <div className="chart-title">Drag Bucket — Cd vs Cl</div>
        <ResponsiveContainer width="100%" height={160}>
          <ScatterChart margin={{ top: 8, right: 16, left: -8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="Cl" name="Cl" tick={CHART_STYLE} stroke="#334155"
              label={{ value: "Cl", position: "insideBottom", offset: -2, style: CHART_STYLE }} />
            <YAxis dataKey="Cd" name="Cd" tick={CHART_STYLE} stroke="#334155" />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ strokeDasharray: "3 3" }}
              formatter={(v: number) => v.toFixed(5)} />
            <Scatter data={bucket} fill={color} fillOpacity={0.8} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ── Side-by-side compare chart ────────────────────────────────────────────────

export function ComparePolarChart({ polarA, nameA, polarB, nameB }: CompareProps) {
  const dataA = polarA.alpha.map((a, i) => ({ alpha: a, ClA: polarA.cl[i], CdA: polarA.cd[i], LDA: polarA.ld[i] }));
  const dataB = polarB.alpha.map((a, i) => ({ alpha: a, ClB: polarB.cl[i], CdB: polarB.cd[i], LDB: polarB.ld[i] }));

  // Merge on alpha
  const merged: Record<number, Record<string, number>> = {};
  dataA.forEach(d => { merged[d.alpha] = { ...merged[d.alpha], alpha: d.alpha, ClA: d.ClA, CdA: d.CdA, LDA: d.LDA }; });
  dataB.forEach(d => { merged[d.alpha] = { ...merged[d.alpha], alpha: d.alpha, ClB: d.ClB, CdB: d.CdB, LDB: d.LDB }; });
  const data = Object.values(merged).sort((a, b) => a.alpha - b.alpha);

  return (
    <div className="polar-charts">
      <div className="chart-block">
        <div className="chart-title">Lift Curve — Cl vs α</div>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: -8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="alpha" tick={CHART_STYLE} stroke="#334155" />
            <YAxis tick={CHART_STYLE} stroke="#334155" />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelFormatter={l => `α = ${l}°`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <ReferenceLine y={0} stroke="#334155" strokeDasharray="3 3" />
            <Line type="monotone" dataKey="ClA" name={nameA} stroke="#38bdf8" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="ClB" name={nameB} stroke="#fbbf24" strokeWidth={2} dot={false} strokeDasharray="5 3" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-block">
        <div className="chart-title">Drag — Cd vs α</div>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: -8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="alpha" tick={CHART_STYLE} stroke="#334155" />
            <YAxis tick={CHART_STYLE} stroke="#334155" />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelFormatter={l => `α = ${l}°`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="CdA" name={nameA} stroke="#38bdf8" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="CdB" name={nameB} stroke="#fbbf24" strokeWidth={2} dot={false} strokeDasharray="5 3" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-block">
        <div className="chart-title">Efficiency — L/D vs α</div>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: -8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="alpha" tick={CHART_STYLE} stroke="#334155" />
            <YAxis tick={CHART_STYLE} stroke="#334155" />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelFormatter={l => `α = ${l}°`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="LDA" name={nameA} stroke="#38bdf8" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="LDB" name={nameB} stroke="#fbbf24" strokeWidth={2} dot={false} strokeDasharray="5 3" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
