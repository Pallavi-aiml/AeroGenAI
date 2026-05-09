import { useState, useCallback } from "react";
import { generateNACA4, simulate } from "./services/api";
import { AirfoilCanvas }  from "./components/AirfoilCanvas";
import { ParameterPanel } from "./components/ParameterPanel";
import { PolarChart }     from "./components/PolarChart";
import { MetricsPanel }   from "./components/MetricsPanel";
import { DatabasePanel }  from "./components/DatabasePanel";
import { ComparePanel }   from "./components/ComparePanel";
import { VaePanel }       from "./components/VaePanel";
import type { AirfoilResult, PolarResult, ManualParams } from "./types/airfoil";
import "./App.css";

type Tab = "manual" | "database" | "compare" | "vae";

const DEFAULT_PARAMS: ManualParams = {
  max_camber:    0.02,
  camber_pos:    0.40,
  max_thickness: 0.12,
  reynolds:      500000,
};

export default function App() {
  const [tab, setTab]           = useState<Tab>("manual");
  const [params, setParams]     = useState<ManualParams>(DEFAULT_PARAMS);
  const [airfoil, setAirfoil]   = useState<AirfoilResult | null>(null);
  const [airfoilB, setAirfoilB] = useState<AirfoilResult | null>(null);  // P4: second slot
  const [polar, setPolar]       = useState<PolarResult | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [status, setStatus]     = useState("");

  const handleGenerate = useCallback(async () => {
    setLoading(true); setError(null); setPolar(null); setStatus("Generating airfoil…");
    try {
      const r = await generateNACA4({
        max_camber: params.max_camber, camber_pos: params.camber_pos,
        max_thickness: params.max_thickness,
      });
      setAirfoil(r);
      setStatus(`Generated ${r.name}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed"); setStatus("");
    } finally { setLoading(false); }
  }, [params]);

  const handleSimulate = useCallback(async () => {
    if (!airfoil) return;
    setLoading(true); setError(null); setStatus("Running simulation…");
    try {
      const r = await simulate({ x: airfoil.x, y: airfoil.y, reynolds: params.reynolds });
      setPolar(r);
      setStatus(r.source === "xfoil" ? "XFoil simulation complete" : "Simulation complete (physics approximation)");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Simulation failed"); setStatus("");
    } finally { setLoading(false); }
  }, [airfoil, params.reynolds]);

  const handleDBSelect = useCallback((selected: AirfoilResult) => {
    setAirfoil(selected); setPolar(null);
    setStatus(`Loaded ${selected.name} from UIUC database`);
  }, []);

  // P4: load airfoil into compare slot B
  const handleLoadB = useCallback((af: AirfoilResult) => {
    setAirfoilB(af);
    setStatus(`Loaded ${af.name} as comparison airfoil B`);
  }, []);

  // P5: VAE loads into primary slot
  const handleVaeLoad = useCallback((af: AirfoilResult) => {
    setAirfoil(af); setPolar(null);
    setStatus(`Loaded ${af.name} from VAE`);
    setTab("manual");
  }, []);

  const TABS: { id: Tab; label: string }[] = [
    { id: "manual",   label: "Manual Design" },
    { id: "database", label: "UIUC Database" },
    { id: "compare",  label: "Compare" },
    { id: "vae",      label: "β-VAE" },
  ];

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <div className="logo">⬡ AeroGenAI</div>
          <div className="tagline">AI-Driven Airfoil Design &amp; Optimization</div>
        </div>
        <div className="header-right">
          <div className="tab-bar">
            {TABS.map(t => (
              <button key={t.id}
                className={`tab ${tab === t.id ? "active" : ""}`}
                onClick={() => setTab(t.id)}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      {(status || error) && (
        <div className={`status-bar ${error ? "error" : ""}`}>
          {error ? `⚠ ${error}` : `✓ ${status}`}
        </div>
      )}

      <main className="app-main">
        {/* Left panel */}
        <aside className="left-panel">
          {tab === "manual" && (
            <ParameterPanel
              params={params} onChange={setParams}
              onGenerate={handleGenerate} onSimulate={handleSimulate}
              loading={loading} hasAirfoil={!!airfoil}
            />
          )}
          {tab === "database" && <DatabasePanel onSelect={handleDBSelect} />}
          {tab === "compare" && (
            <div className="db-panel">
              <div className="panel-title">
                <span className="panel-icon">⬡</span>
                Airfoil Slots
              </div>
              <div style={{ marginBottom: 12 }}>
                <div className="slot-label" style={{ color: "#38bdf8" }}>Slot A (primary)</div>
                <div className="slot-name">{airfoil?.name ?? "— none —"}</div>
                {airfoil && <AirfoilCanvas x={airfoil.x} y={airfoil.y} height={80} color="#38bdf8" />}
              </div>
              <div>
                <div className="slot-label" style={{ color: "#fbbf24" }}>Slot B (comparison)</div>
                <div className="slot-name">{airfoilB?.name ?? "— none —"}</div>
                {airfoilB && <AirfoilCanvas x={airfoilB.x} y={airfoilB.y} height={80} color="#fbbf24" />}
              </div>
              <div style={{ marginTop: 12, fontSize: 11, color: "#475569" }}>
                Load airfoils via Manual or Database tab, then compare here.
              </div>
              {airfoil && !airfoilB && (
                <button className="btn-secondary" style={{ marginTop: 8 }}
                  onClick={() => setAirfoilB(airfoil)}>
                  Copy A → B
                </button>
              )}
            </div>
          )}
          {tab === "vae" && (
            <div style={{ fontSize: 11, color: "#475569", padding: 16 }}>
              Use the sliders on the right to explore the latent space.<br />
              Click "Use This Airfoil" to send it to the main workspace.
            </div>
          )}
        </aside>

        {/* Right content */}
        <section className="right-content">
          {tab === "compare" ? (
            <ComparePanel
              airfoilA={airfoil}
              airfoilB={airfoilB}
              reynolds={params.reynolds}
            />
          ) : tab === "vae" ? (
            <VaePanel onLoad={handleVaeLoad} reynolds={params.reynolds} />
          ) : (
            <>
              {/* Airfoil Shape */}
              <div className="card">
                <div className="card-title">Airfoil Shape</div>
                <AirfoilCanvas x={airfoil?.x ?? []} y={airfoil?.y ?? []} name={airfoil?.name} />
                {airfoil && (
                  <>
                    <div className="feature-badges">
                      <span className="badge">t/c = {(airfoil.features.max_thickness * 100).toFixed(1)}%</span>
                      <span className="badge">f/c = {(airfoil.features.max_camber * 100).toFixed(1)}%</span>
                      <span className="badge">{airfoil.features.is_symmetric ? "Symmetric" : "Cambered"}</span>
                      {airfoil.source === "pca" && <span className="badge" style={{ color: "#a78bfa", borderColor: "rgba(167,139,250,0.3)" }}>PCA VAE</span>}
                      {airfoil.source === "vae" && <span className="badge" style={{ color: "#a78bfa", borderColor: "rgba(167,139,250,0.3)" }}>β-VAE</span>}
                      {tab === "database" && <span className="badge badge-blue">UIUC Real Data</span>}
                    </div>
                    {/* Set as B for compare */}
                    <div style={{ marginTop: 10 }}>
                      <button className="btn-secondary" onClick={() => { setAirfoilB(airfoil); setStatus(`${airfoil.name} set as comparison B`); }}
                        style={{ fontSize: 11, padding: "5px 12px" }}>
                        Set as Compare B
                      </button>
                    </div>
                  </>
                )}
              </div>

              {/* Simulate button for DB tab */}
              {airfoil && tab === "database" && !polar && (
                <div className="card simulate-prompt">
                  <button className="btn-primary wide" onClick={handleSimulate} disabled={loading}>
                    {loading ? <span className="spinner" /> : "▶"} Run XFoil Simulation
                  </button>
                </div>
              )}

              {/* Polar charts */}
              {polar && (
                <div className="card">
                  <div className="card-title">Aerodynamic Polars</div>
                  <PolarChart polar={polar} />
                </div>
              )}

              {/* Metrics */}
              {polar && <MetricsPanel polar={polar} />}

              {/* Empty state */}
              {!airfoil && (
                <div className="empty-state">
                  <div className="empty-icon">⬡</div>
                  <div className="empty-title">No airfoil generated yet</div>
                  <div className="empty-sub">
                    Use the parameter panel to generate a NACA airfoil,<br />
                    browse the UIUC database of 1,606 real airfoils,<br />
                    or explore the β-VAE latent space.
                  </div>
                </div>
              )}
            </>
          )}
        </section>
      </main>
    </div>
  );
}
