import { useState } from "react";
import { searchDatabase, getAirfoilByIndex } from "../services/api";
import type { DBResult, AirfoilResult } from "../types/airfoil";

interface Props {
  onSelect: (airfoil: AirfoilResult) => void;
}

export function DatabasePanel({ onSelect }: Props) {
  const [thickMin, setThickMin] = useState(0.08);
  const [thickMax, setThickMax] = useState(0.16);
  const [results, setResults]   = useState<DBResult[]>([]);
  const [loading, setLoading]   = useState(false);
  const [searched, setSearched] = useState(false);

  const search = async () => {
    setLoading(true);
    try {
      const res = await searchDatabase({ thickness_min: thickMin, thickness_max: thickMax, limit: 12 });
      setResults(res.results as unknown as DBResult[]);
      setSearched(true);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const load = async (r: DBResult) => {
    try {
      const airfoil = await getAirfoilByIndex(r.index);
      onSelect(airfoil);
    } catch (e) { console.error(e); }
  };

  return (
    <div className="db-panel">
      <div className="panel-title">
        <span className="panel-icon">🗄</span>
        UIUC Database — 1,606 Airfoils
      </div>
      <div className="db-filters">
        <div className="filter-row">
          <label>Thickness min</label>
          <input type="range" min={0.04} max={0.18} step={0.01}
            value={thickMin} onChange={e => setThickMin(+e.target.value)} className="slider" />
          <span className="filter-val">{(thickMin * 100).toFixed(0)}%</span>
        </div>
        <div className="filter-row">
          <label>Thickness max</label>
          <input type="range" min={0.06} max={0.25} step={0.01}
            value={thickMax} onChange={e => setThickMax(+e.target.value)} className="slider" />
          <span className="filter-val">{(thickMax * 100).toFixed(0)}%</span>
        </div>
        <button className="btn-primary" onClick={search} disabled={loading}>
          {loading ? <span className="spinner" /> : "🔍"} Search
        </button>
      </div>
      {searched && results.length === 0 && (
        <div className="db-empty">No airfoils match these filters.</div>
      )}
      <div className="db-results">
        {results.map(r => (
          <div className="db-card" key={r.index} onClick={() => load(r)}>
            <div className="db-card-name">{r.name}</div>
            <div className="db-card-meta">
              <span>t/c = {(r.max_thickness * 100).toFixed(1)}%</span>
              <span>f/c = {(r.max_camber * 100).toFixed(1)}%</span>
              <span>{r.is_symmetric ? "Symmetric" : "Cambered"}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
