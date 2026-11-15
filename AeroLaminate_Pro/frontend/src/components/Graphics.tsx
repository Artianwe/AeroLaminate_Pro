"use client";
// AeroLaminate Pro - custom SVG graphics: matrix heatmap, field contour, ply-stack cross-section.
// Author: Anwesh Ajitabh Dash.
import { useState } from "react";
import { fmt } from "@/lib/project";

// Diverging scale: blue (negative) - neutral grey - orange (positive); reference palette slots 1 and 2.
function diverging(t: number): string {
  const c = Math.max(-1, Math.min(1, t));
  const mid = [236, 233, 224];
  const pos = [235, 104, 52];
  const neg = [42, 120, 214];
  const e = c >= 0 ? pos : neg;
  const a = Math.abs(c) ** 0.7;
  const rgb = mid.map((m, i) => Math.round(m + (e[i] - m) * a));
  return `rgb(${rgb.join(",")})`;
}

export function MatrixHeatmap({ M, labels, units }: { M: number[][]; labels: string[]; units: (i: number, j: number) => string }) {
  const [hover, setHover] = useState<[number, number] | null>(null);
  const n = M.length;
  const cell = 46, pad = 40;
  const norm = (i: number, j: number) => {
    const d = Math.sqrt(Math.abs(M[i][i] * M[j][j]));
    return d > 0 ? M[i][j] / d : 0;
  };
  const W = pad + n * cell + 4, H = pad + n * cell + 4;
  return (
    <div className="flex items-start gap-3">
      <svg width={W} height={H} className="shrink-0 font-mono">
        {labels.map((l, i) => (
          <g key={l}>
            <text x={pad + i * cell + cell / 2} y={pad - 8} textAnchor="middle" fontSize={10.5} fill="#52514e">{l}</text>
            <text x={pad - 6} y={pad + i * cell + cell / 2 + 3} textAnchor="end" fontSize={10.5} fill="#52514e">{l}</text>
          </g>
        ))}
        {M.map((row, i) => row.map((v, j) => {
          const t = norm(i, j);
          return (
            <g key={`${i}-${j}`} onMouseEnter={() => setHover([i, j])} onMouseLeave={() => setHover(null)}>
              <rect x={pad + j * cell + 1} y={pad + i * cell + 1} width={cell - 2} height={cell - 2} fill={diverging(t)}
                stroke={hover && hover[0] === i && hover[1] === j ? "#1a1a19" : "none"} strokeWidth={1.5} />
              <text x={pad + j * cell + cell / 2} y={pad + i * cell + cell / 2 + 3} textAnchor="middle" fontSize={9.5}
                fill={Math.abs(t) > 0.65 ? "#fcfbf7" : "#262624"}>{Math.abs(t) < 5e-13 ? "0" : t.toFixed(2)}</text>
            </g>
          );
        }))}
        <line x1={pad + 3 * cell} x2={pad + 3 * cell} y1={pad} y2={pad + n * cell} stroke="#1a1a19" strokeWidth={1} />
        <line y1={pad + 3 * cell} y2={pad + 3 * cell} x1={pad} x2={pad + n * cell} stroke="#1a1a19" strokeWidth={1} />
      </svg>
      <div className="min-w-[170px] text-[11px] leading-5 text-graphite-600">
        <p className="mb-1">Cell value: normalised coupling K<sub>ij</sub>/√(K<sub>ii</sub>K<sub>jj</sub>) — scale-free, so A, B and D blocks are comparable.</p>
        {hover ? (
          <div className="border border-rule bg-ivory-50 p-1.5 font-mono text-[10.5px]">
            <div className="font-sans font-semibold">{labels[hover[0]]}–{labels[hover[1]]}</div>
            <div>value: {fmt(M[hover[0]][hover[1]], 6)} {units(hover[0], hover[1])}</div>
            <div>normalised: {norm(hover[0], hover[1]).toFixed(4)}</div>
          </div>
        ) : <p className="text-graphite-400">Hover a cell for the raw value and units.</p>}
        <div className="mt-2 flex items-center gap-1 font-mono text-[10px]">
          <span>−1</span>
          <span className="h-2 w-24" style={{ background: `linear-gradient(90deg, ${diverging(-1)}, ${diverging(0)}, ${diverging(1)})` }} />
          <span>+1</span>
        </div>
      </div>
    </div>
  );
}

export function FieldContour({ x, y, w, xLabel, yLabel, unit, symmetric = true }: {
  x: number[]; y: number[]; w: number[][]; xLabel: string; yLabel: string; unit: string; symmetric?: boolean;
}) {
  const [hover, setHover] = useState<{ i: number; j: number } | null>(null);
  const nx = x.length, ny = y.length;
  const ax = x[nx - 1] - x[0], ay = y[ny - 1] - y[0];
  const maxW = 360, maxH = 230;
  const s = Math.min(maxW / ax, maxH / ay);
  const pw = ax * s, ph = ay * s;
  const cw = pw / nx, ch = ph / ny;
  const m = Math.max(...w.flat().map(Math.abs)) || 1;
  const L = 44;
  return (
    <div className="flex items-start gap-3">
      <svg width={pw + L + 8} height={ph + 34} className="shrink-0 font-mono">
        {w.map((row, j) => row.map((v, i) => (
          <rect key={`${i}-${j}`} x={L + i * cw} y={ph - (j + 1) * ch} width={cw + 0.4} height={ch + 0.4}
            fill={diverging(symmetric ? v / m : (2 * v) / m - 1)} onMouseEnter={() => setHover({ i, j })} onMouseLeave={() => setHover(null)} />
        )))}
        <rect x={L} y={0} width={pw} height={ph} fill="none" stroke="#3a3a38" />
        <text x={L + pw / 2} y={ph + 26} textAnchor="middle" fontSize={10.5} fill="#3a3a38">{xLabel}</text>
        <text x={L} y={ph + 12} fontSize={10} fill="#52514e">{fmt(x[0], 3)}</text>
        <text x={L + pw} y={ph + 12} textAnchor="end" fontSize={10} fill="#52514e">{fmt(x[nx - 1], 3)}</text>
        <text x={L - 4} y={ph} textAnchor="end" fontSize={10} fill="#52514e">{fmt(y[0], 3)}</text>
        <text x={L - 4} y={10} textAnchor="end" fontSize={10} fill="#52514e">{fmt(y[ny - 1], 3)}</text>
        <text transform={`translate(12 ${ph / 2}) rotate(-90)`} textAnchor="middle" fontSize={10.5} fill="#3a3a38">{yLabel}</text>
      </svg>
      <div className="min-w-[140px] font-mono text-[10.5px] text-graphite-600">
        {hover ? <div className="border border-rule bg-ivory-50 p-1.5">
          <div>x = {fmt(x[hover.i], 4)}</div><div>y = {fmt(y[hover.j], 4)}</div><div>w = {fmt(w[hover.j][hover.i], 4)} {unit}</div>
        </div> : <span className="font-sans text-graphite-400">Hover for values</span>}
        <div className="mt-2 flex items-center gap-1 text-[10px]">
          <span>{fmt(symmetric ? -m : 0, 2)}</span>
          <span className="h-2 w-20" style={{ background: `linear-gradient(90deg, ${diverging(-1)}, ${diverging(0)}, ${diverging(1)})` }} />
          <span>{fmt(m, 2)}</span>
        </div>
      </div>
    </div>
  );
}

function plyFill(a: number): string {
  const n = ((a % 180) + 180) % 180;
  if (Math.abs(n) < 1e-9) return "#3a3a38";
  if (Math.abs(n - 90) < 1e-9) return "#e2dccb";
  if (Math.abs(n - 45) < 1e-9 || Math.abs(n - 135) < 1e-9) return "#c9a35a";
  return "#8a8780";
}

export function PlyStack({ plies, z, selected, onSelect, state, rf }: {
  plies: { angle: number; thickness: number; material?: string }[]; z: number[]; selected: number | null; onSelect: (i: number) => void;
  state?: string[]; rf?: number[];
}) {
  const h = z[z.length - 1] - z[0];
  const H = Math.min(320, Math.max(120, plies.length * 14));
  const W = 230;
  const L = 52;
  const sy = H / h;
  return (
    <svg width={W + L + 128} height={H + 24} className="font-mono">
      <defs>
        {plies.map((p, i) => (
          <clipPath key={i} id={`ply-clip-${i}`}><rect x={L} y={12 + (z[z.length - 1] - z[i + 1]) * sy} width={W} height={p.thickness * sy} /></clipPath>
        ))}
      </defs>
      {plies.map((p, i) => {
        const y0 = 12 + (z[z.length - 1] - z[i + 1]) * sy;
        const hh = p.thickness * sy;
        const th = (p.angle * Math.PI) / 180;
        const lines = [];
        // fibre direction drawn in plan view projected on the strip: slope = tan(theta)
        if (hh > 4) {
          for (let k = -20; k <= 40; k++) {
            const xs = L + k * 12;
            const dx = Math.abs(Math.cos(th)) < 1e-6 ? 0 : hh / Math.tan(th);
            lines.push(Math.abs(Math.sin(th)) < 1e-6
              ? <line key={k} x1={L} x2={L + W} y1={y0 + hh / 2} y2={y0 + hh / 2} stroke="#fcfbf7" strokeOpacity={0.5} strokeWidth={0.8} />
              : <line key={k} x1={xs} x2={xs + dx} y1={y0 + hh} y2={y0} stroke={plyFill(p.angle) === "#e2dccb" ? "#8a8780" : "#fcfbf7"} strokeOpacity={0.55} strokeWidth={0.8} />);
            if (Math.abs(Math.sin(th)) < 1e-6) break;
          }
        }
        const st = state?.[i];
        return (
          <g key={i} onClick={() => onSelect(i)} className="cursor-pointer">
            <rect x={L} y={y0} width={W} height={hh} fill={plyFill(p.angle)} stroke="#fcfbf7" strokeWidth={hh > 3 ? 1 : 0.3} />
            <g clipPath={`url(#ply-clip-${i})`}>{lines}</g>
            {st && st !== "-" && <rect x={L} y={y0} width={W} height={hh} fill={st === "F" ? "#b3372f" : "#d69214"} fillOpacity={0.45} />}
            {selected === i && <rect x={L - 1} y={y0} width={W + 2} height={hh} fill="none" stroke="#d69214" strokeWidth={2} />}
            {hh >= 9 && <text x={L + W + 6} y={y0 + hh / 2 + 3.5} fontSize={10} fill="#3a3a38">{i + 1}: {p.angle}°{rf && rf[i] !== undefined ? `  RF ${rf[i] < 0 ? "∞" : fmt(rf[i], 3)}` : ""}</text>}
          </g>
        );
      })}
      <line x1={L - 6} x2={L + W + 4} y1={12 + H / 2} y2={12 + H / 2} stroke="#d69214" strokeDasharray="4 3" />
      <text x={L - 8} y={12 + 4} textAnchor="end" fontSize={9.5} fill="#52514e">+{fmt(h / 2, 3)}</text>
      <text x={L - 8} y={12 + H / 2 + 3} textAnchor="end" fontSize={9.5} fill="#8a5a05">z=0</text>
      <text x={L - 8} y={12 + H} textAnchor="end" fontSize={9.5} fill="#52514e">−{fmt(h / 2, 3)}</text>
      <text x={4} y={12 + H + 10} fontSize={9.5} fill="#8a8780">z [mm]</text>
    </svg>
  );
}
