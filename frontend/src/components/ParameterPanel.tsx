import type { ManualParams } from "../types/airfoil";

interface Props {
  params: ManualParams;
  onChange: (p: ManualParams) => void;
  onGenerate: () => void;
  onSimulate: () => void;
  loading: boolean;
  hasAirfoil: boolean;
}

interface SliderDef {
  key: keyof ManualParams;
  label: string;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  description: string;
}

const SLIDERS: SliderDef[] = [
  {
    key: "max_camber",
    label: "Max Camber (m)",
    min: 0, max: 0.10, step: 0.005,
    format: v => `${(v * 100).toFixed(1)}%`,
    description: "Controls lift — higher camber = more lift",
  },
  {
    key: "camber_pos",
    label: "Camber Position (p)",
    min: 0.1, max: 0.9, step: 0.05,
    format: v => `${(v * 10).toFixed(0)}0% chord`,
    description: "Where max camber occurs along chord",
  },
  {
    key: "max_thickness",
    label: "Max Thickness (t)",
    min: 0.06, max: 0.20, step: 0.005,
    format: v => `${(v * 100).toFixed(1)}%`,
    description: "Controls drag and structural strength",
  },
  {
    key: "reynolds",
    label: "Reynolds Number",
    min: 50000, max: 3000000, step: 50000,
    format: v => v >= 1e6 ? `${(v/1e6).toFixed(2)}M` : `${(v/1e3).toFixed(0)}k`,
    description: "Flight speed × chord / kinematic viscosity",
  },
];

export function ParameterPanel({ params, onChange, onGenerate, onSimulate, loading, hasAirfoil }: Props) {
  const set = (key: keyof ManualParams, value: number) =>
    onChange({ ...params, [key]: value });

  return (
    <div className="param-panel">
      <div className="panel-title">
        <span className="panel-icon">⚙</span>
        NACA 4-Digit Parameters
      </div>

      <div className="naca-preview">
        NACA {Math.round(params.max_camber * 100)}{Math.round(params.camber_pos * 10)}{String(Math.round(params.max_thickness * 100)).padStart(2, "0")}
      </div>

      <div className="sliders">
        {SLIDERS.map(s => (
          <div className="slider-row" key={s.key}>
            <div className="slider-header">
              <span className="slider-label">{s.label}</span>
              <span className="slider-value">{s.format(params[s.key] as number)}</span>
            </div>
            <input
              type="range"
              min={s.min}
              max={s.max}
              step={s.step}
              value={params[s.key] as number}
              onChange={e => set(s.key, parseFloat(e.target.value))}
              className="slider"
            />
            <div className="slider-desc">{s.description}</div>
          </div>
        ))}
      </div>

      <div className="action-buttons">
        <button className="btn-primary" onClick={onGenerate} disabled={loading}>
          {loading ? <span className="spinner" /> : "⬡"}
          Generate Airfoil
        </button>
        <button
          className="btn-secondary"
          onClick={onSimulate}
          disabled={loading || !hasAirfoil}
        >
          {loading ? <span className="spinner" /> : "▶"}
          Run Simulation
        </button>
      </div>
    </div>
  );
}
