import { useState, useEffect, useCallback } from "react";
import { AirfoilCanvas } from "./AirfoilCanvas";
import { decodeLatent, getVaeStatus, optimize } from "../services/api";
import type { AirfoilResult, VaeStatus, OptimizationCandidate } from "../types/airfoil";

interface Props {
  onLoad: (airfoil: AirfoilResult) => void;
  reynolds: number;
}

const LATENT_DIM = 16;

export function VaePanel({ onLoad, reynolds }: Props) {
  const [status, setStatus]       = useState<VaeStatus | null>(null);
  const [latent, setLatent]       = useState<number[]>(Array(LATENT_DIM).fill(0));
  const [airfoil, setAirfoil]     = useState<AirfoilResult | null>(null);
  const [decoding, setDecoding]   = useState(false);
  const [optimizing, setOpt]      = useState(false);
  const [candidates, setCandidates] = useState<OptimizationCandidate[]>([]);
  const [optTarget, setOptTarget] = useState<"best_ld" | "max_cl" | "min_cd">("best_ld");
  const [nCandidates, setN]       = useState(20);

  useEffect(() => {
    getVaeStatus().then(setStatus).catch(() => {});
  }, []);

  const decode = useCallback(async (z: number[]) => {
    setDecoding(true);
    try {
      const af = await decodeLatent(z);
      setAirfoil(af);
    } catch (e) { console.error(e); }
    finally { setDecoding(false); }
  }, []);

  const setDim = (i: number, v: number) => {
    const z = [...latent];
    z[i] = v;
    setLatent(z);
    decode(z);
  };

  const runOpt = async () => {
    setOpt(true);
    setCandidates([]);
    try {
      const res = await optimize({ n_candidates: nCandidates, target: optTarget, reynolds });
      setCandidates(res.candidates);
    } catch (e) { console.error(e); }
    finally { setOpt(false); }
  };

  const statsAvailable = status?.stats != null;
  const sliderMax = (i: number) =>
    statsAvailable ? (status!.stats!.std[i] * 3) : 3;

  return (
    <div className="vae-panel">
      <div className="panel-title">
        <span className="panel-icon">🧠</span>
        β-VAE Latent Space Explorer
      </div>

      {status && !status.available && (
        <div className="vae-notice">
          Run <code>python ml/train_vae.py</code> to train the model.<br />
          PCA surrogate active — sliders still work.
        </div>
      )}
      {status?.available && (
        <div className="vae-notice ok">
          {status.stats ? "VAE model loaded ✓" : "PCA surrogate active (train for full VAE)"}
        </div>
      )}

      {/* Latent sliders */}
      <div className="latent-sliders">
        {Array.from({ length: LATENT_DIM }, (_, i) => (
          <div className="latent-row" key={i}>
            <span className="latent-idx">z{i}</span>
            <input
              type="range"
              min={-sliderMax(i)}
              max={sliderMax(i)}
              step={sliderMax(i) / 50}
              value={latent[i]}
              onChange={e => setDim(i, +e.target.value)}
              className="slider latent-slider"
            />
            <span className="latent-val">{latent[i].toFixed(2)}</span>
          </div>
        ))}
      </div>

      {/* Preview */}
      {airfoil && (
        <div className="latent-preview">
          {decoding
            ? <div className="latent-decoding">Decoding…</div>
            : <AirfoilCanvas x={airfoil.x} y={airfoil.y} height={120} color="#a78bfa" name={airfoil.name} />
          }
          <button className="btn-primary wide" onClick={() => onLoad(airfoil)} style={{ marginTop: 8 }}>
            Use This Airfoil
          </button>
        </div>
      )}

      {/* Reset */}
      <button className="btn-secondary" style={{ marginTop: 8 }}
        onClick={() => { const z = Array(LATENT_DIM).fill(0); setLatent(z); decode(z); }}>
        ↺ Reset Latent
      </button>

      {/* Optimization */}
      <div className="opt-section">
        <div className="panel-title" style={{ marginTop: 20 }}>
          <span className="panel-icon">🚀</span>
          Auto-Optimization Loop
        </div>
        <div className="opt-controls">
          <div className="slider-row">
            <div className="slider-header">
              <span className="slider-label">Candidates</span>
              <span className="slider-value">{nCandidates}</span>
            </div>
            <input type="range" min={5} max={50} step={5}
              value={nCandidates} onChange={e => setN(+e.target.value)} className="slider" />
          </div>
          <div className="slider-row">
            <div className="slider-header">
              <span className="slider-label">Objective</span>
            </div>
            <div className="opt-target-btns">
              {(["best_ld", "max_cl", "min_cd"] as const).map(t => (
                <button key={t}
                  className={`opt-target-btn ${optTarget === t ? "active" : ""}`}
                  onClick={() => setOptTarget(t)}>
                  {t === "best_ld" ? "Best L/D" : t === "max_cl" ? "Max Cl" : "Min Cd"}
                </button>
              ))}
            </div>
          </div>
        </div>
        <button className="btn-primary wide" onClick={runOpt} disabled={optimizing}>
          {optimizing ? <><span className="spinner" /> Optimizing…</> : "▶ Run Optimization"}
        </button>

        {candidates.length > 0 && (
          <div className="opt-results">
            <div className="card-title" style={{ marginTop: 12 }}>Top {candidates.length} Results</div>
            {candidates.map((c, i) => (
              <div className="opt-card" key={i} onClick={() => onLoad({ name: c.name, x: c.x, y: c.y, features: c.features })}>
                <div className="opt-rank">#{i + 1}</div>
                <div className="opt-info">
                  <div className="opt-name">{c.name}</div>
                  <div className="opt-metrics">
                    <span>L/D = {c.metrics.best_ld}</span>
                    <span>Cl_max = {c.metrics.max_cl}</span>
                    <span>t/c = {(c.features.max_thickness * 100).toFixed(1)}%</span>
                  </div>
                </div>
                <AirfoilCanvas x={c.x} y={c.y} height={50} color="#a78bfa" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
