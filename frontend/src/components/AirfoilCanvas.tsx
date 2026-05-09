import { useMemo } from "react";

interface Props {
  x: number[];
  y: number[];
  name?: string;
  color?: string;
  height?: number;
}

export function AirfoilCanvas({ x, y, name, color = "#38bdf8", height = 200 }: Props) {
  const path = useMemo(() => {
    if (!x?.length || !y?.length) return "";
    const W = 560, H = height;
    const pad = 32;

    const xMin = Math.min(...x), xMax = Math.max(...x);
    const yMin = Math.min(...y), yMax = Math.max(...y);

    const scaleX = (W - 2 * pad) / (xMax - xMin || 1);
    const scaleY = (H - 2 * pad) / (yMax - yMin || 1);
    const scale  = Math.min(scaleX, scaleY);

    const ox = pad - xMin * scale + ((W - 2*pad) - (xMax - xMin) * scale) / 2;
    const oy = H/2 + (yMax + yMin) * scale / 2;

    const tx = (v: number) => ox + v * scale;
    const ty = (v: number) => oy - v * scale;

    return x.map((xi, i) =>
      `${i === 0 ? "M" : "L"} ${tx(xi).toFixed(2)} ${ty(y[i]).toFixed(2)}`
    ).join(" ") + " Z";
  }, [x, y, height]);

  if (!path) return (
    <div className="airfoil-empty">
      <span>Generate an airfoil to see it here</span>
    </div>
  );

  return (
    <div className="airfoil-canvas-wrap">
      <svg viewBox={`0 0 560 ${height}`} width="100%" height={height}>
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1.0].map(v => {
          const px = 32 + v * (560 - 64);
          return <line key={v} x1={px} y1={0} x2={px} y2={height}
            stroke="#1e293b" strokeWidth="1" strokeDasharray="3,3" />;
        })}
        {/* Chord line */}
        <line x1="32" y1={height/2} x2="528" y2={height/2}
          stroke="#1e293b" strokeWidth="1" strokeDasharray="4,4" />
        {/* Airfoil fill */}
        <path d={path} fill={color} fillOpacity="0.12" />
        {/* Airfoil outline */}
        <path d={path} fill="none" stroke={color} strokeWidth="2.5"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {name && <div className="airfoil-name">{name}</div>}
    </div>
  );
}
