"use client";
// AeroLaminate Pro - XY and bar plots on Recharts, with zoom/pan, reference lines and data inspection.
// Author: Anwesh Ajitabh Dash.
import { useMemo, useRef, useState, type ReactNode } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ReferenceDot, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { fmt } from "@/lib/project";

const AX = { stroke: "#b9b3a3", tick: { fill: "#52514e", fontSize: 10.5, fontFamily: "var(--font-mono)" } };
const GRID = "#e9e4d6";

export interface Series {
  name: string; color: string; data: { x: number; y: number; [k: string]: unknown }[];
  dashed?: boolean; line?: boolean; points?: boolean; width?: number; hideLegend?: boolean;
}
export interface RefLine { value: number; label?: string; color?: string; dashed?: boolean }
export interface RefPt { x: number; y: number; label?: string; color?: string }

type Dom = [number, number];

function extent(series: Series[], key: "x" | "y", refs: RefLine[] = [], pts: RefPt[] = []): Dom {
  let lo = Infinity, hi = -Infinity;
  for (const s of series) for (const d of s.data) { const v = d[key]; if (Number.isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }
  for (const r of refs) if (Number.isFinite(r.value)) { lo = Math.min(lo, r.value); hi = Math.max(hi, r.value); }
  for (const p of pts) { const v = p[key]; if (Number.isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }
  if (!Number.isFinite(lo)) return [0, 1];
  if (lo === hi) { const d = Math.abs(lo) * 0.1 || 1; return [lo - d, hi + d]; }
  const pad = (hi - lo) * 0.05;
  return [lo - pad, hi + pad];
}

function niceTicks([a, b]: Dom, n = 6): number[] {
  const span = b - a;
  const step0 = span / n;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) ?? step0;
  const out: number[] = [];
  for (let v = Math.ceil(a / step) * step; v <= b + 1e-9 * span; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  return out;
}

export function XYPlot({ series, xLabel, yLabel, height = 260, refX = [], refY = [], points = [], equal = false, xDomain, yDomain,
  tooltipExtra, legend = true }: {
  series: Series[]; xLabel: string; yLabel: string; height?: number; refX?: RefLine[]; refY?: RefLine[]; points?: RefPt[];
  equal?: boolean; xDomain?: Dom; yDomain?: Dom; tooltipExtra?: (p: Record<string, unknown>) => ReactNode; legend?: boolean;
}) {
  const baseX = useMemo(() => xDomain ?? extent(series, "x", refX, points), [series, refX, points, xDomain]);
  const baseY = useMemo(() => yDomain ?? extent(series, "y", refY, points), [series, refY, points, yDomain]);
  const [view, setView] = useState<{ x: Dom; y: Dom } | null>(null);
  const drag = useRef<{ cx: number; cy: number; v: { x: Dom; y: Dom } } | null>(null);
  const box = useRef<HTMLDivElement>(null);
  let x = view?.x ?? baseX, y = view?.y ?? baseY;
  if (equal && !view) {
    const span = Math.max(x[1] - x[0], y[1] - y[0]);
    const cx = (x[0] + x[1]) / 2, cy = (y[0] + y[1]) / 2;
    x = [cx - span / 2, cx + span / 2]; y = [cy - span / 2, cy + span / 2];
  }
  const zoom = (f: number) => {
    const cx = (x[0] + x[1]) / 2, cy = (y[0] + y[1]) / 2;
    setView({ x: [cx - (cx - x[0]) * f, cx + (x[1] - cx) * f], y: [cy - (cy - y[0]) * f, cy + (y[1] - cy) * f] });
  };
  const onDown = (e: React.MouseEvent) => { drag.current = { cx: e.clientX, cy: e.clientY, v: { x, y } }; };
  const onMove = (e: React.MouseEvent) => {
    const d = drag.current; const el = box.current;
    if (!d || !el || e.buttons !== 1) return;
    const w = el.clientWidth - 80, h = el.clientHeight - 60;
    const dx = ((e.clientX - d.cx) / w) * (d.v.x[1] - d.v.x[0]);
    const dy = ((e.clientY - d.cy) / h) * (d.v.y[1] - d.v.y[0]);
    if (Math.abs(e.clientX - d.cx) + Math.abs(e.clientY - d.cy) > 3)
      setView({ x: [d.v.x[0] - dx, d.v.x[1] - dx], y: [d.v.y[0] + dy, d.v.y[1] + dy] });
  };
  const onWheel = (e: React.WheelEvent) => { if (e.ctrlKey || e.metaKey) { e.preventDefault(); zoom(e.deltaY > 0 ? 1.15 : 1 / 1.15); } };
  const b = "h-5 w-5 border border-rule bg-ivory-50/90 font-mono text-[11px] leading-none text-graphite-600 hover:bg-ivory-200";
  const shown = series.filter((s) => s.data.length);
  return (
    <div ref={box} className="relative select-none" style={{ height }} onMouseDown={onDown} onMouseMove={onMove}
      onMouseUp={() => (drag.current = null)} onMouseLeave={() => (drag.current = null)} onDoubleClick={() => setView(null)} onWheel={onWheel}>
      <div className="absolute right-1 top-0 z-10 flex gap-0.5 opacity-60 hover:opacity-100" onMouseDown={(e) => e.stopPropagation()}>
        <button className={b} title="Zoom in (Ctrl+wheel)" onClick={() => zoom(0.7)}>+</button>
        <button className={b} title="Zoom out" onClick={() => zoom(1 / 0.7)}>−</button>
        <button className={b} title="Reset view (double-click)" onClick={() => setView(null)}>⟲</button>
      </div>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 14, bottom: 26, left: 8 }}>
          <CartesianGrid stroke={GRID} />
          <XAxis type="number" dataKey="x" domain={x} ticks={niceTicks(x)} allowDataOverflow {...AX} tickFormatter={(v) => fmt(v, 3)}
            label={{ value: xLabel, position: "insideBottom", offset: -14, fill: "#3a3a38", fontSize: 11 }} />
          <YAxis type="number" dataKey="y" domain={y} ticks={niceTicks(y, 5)} allowDataOverflow {...AX} width={58} tickFormatter={(v) => fmt(v, 3)}
            label={{ value: yLabel, angle: -90, position: "insideLeft", offset: 10, fill: "#3a3a38", fontSize: 11, style: { textAnchor: "middle" } }} />
          <Tooltip cursor={{ stroke: "#8a8780", strokeWidth: 1 }} isAnimationActive={false}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as Record<string, unknown>;
              const s = (payload[0] as unknown as { name?: string }).name;
              return (
                <div className="border border-rule bg-ivory-50 px-2 py-1 font-mono text-[10.5px] shadow-sm">
                  <div className="font-sans text-[11px] font-semibold text-graphite-900">{(p.series as string) ?? s}</div>
                  <div>{xLabel}: {fmt(p.x as number, 5)}</div>
                  <div>{yLabel}: {fmt(p.y as number, 5)}</div>
                  {tooltipExtra?.(p)}
                </div>
              );
            }} />
          {legend && shown.length > 1 && <Legend verticalAlign="top" height={20} iconSize={10}
            wrapperStyle={{ fontSize: 10.5, color: "#3a3a38" }} payload={shown.filter((s) => !s.hideLegend).map((s) => ({ value: s.name, type: "plainline", color: s.color, id: s.name,
              payload: { strokeDasharray: s.dashed ? "5 3" : "0" } as never }))} />}
          {refX.map((r, i) => <ReferenceLine key={`rx${i}`} x={r.value} stroke={r.color ?? "#6b6963"} strokeDasharray={r.dashed === false ? undefined : "4 3"} ifOverflow="hidden"
            label={r.label ? { value: r.label, position: "insideTopRight", fontSize: 10, fill: r.color ?? "#52514e" } : undefined} />)}
          {refY.map((r, i) => <ReferenceLine key={`ry${i}`} y={r.value} stroke={r.color ?? "#6b6963"} strokeDasharray={r.dashed === false ? undefined : "4 3"} ifOverflow="hidden"
            label={r.label ? { value: r.label, position: "insideTopLeft", fontSize: 10, fill: r.color ?? "#52514e" } : undefined} />)}
          {shown.map((s) => (
            <Scatter key={s.name} name={s.name} data={s.data.map((d) => ({ ...d, series: s.name }))} fill={s.color} isAnimationActive={false}
              line={s.line === false ? false : { stroke: s.color, strokeWidth: s.width ?? 2, strokeDasharray: s.dashed ? "5 3" : undefined }}
              lineType="joint" shape={s.points ? "circle" : (props: { cx?: number; cy?: number }) => <circle cx={props.cx} cy={props.cy} r={s.line === false ? 4 : 2.5} fill={s.color} fillOpacity={s.line === false ? 0.85 : 0.001} />} />
          ))}
          {points.map((p, i) => <ReferenceDot key={`p${i}`} x={p.x} y={p.y} r={5} fill={p.color ?? "#1a1a19"} stroke="#fcfbf7" strokeWidth={2} ifOverflow="hidden"
            label={p.label ? { value: p.label, position: "top", fontSize: 10, fill: "#1a1a19" } : undefined} />)}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface BarDef { key: string; name: string; color: string }

export function BarPlot({ data, xKey, bars, height = 220, yLabel, xLabel, refY = [], horizontal = false, cellColor, yDomain, stacked = false, legend = true }: {
  data: Record<string, unknown>[]; xKey: string; bars: BarDef[]; height?: number; yLabel?: string; xLabel?: string; refY?: RefLine[];
  horizontal?: boolean; cellColor?: (row: Record<string, unknown>, key: string) => string | undefined; yDomain?: [number | string, number | string];
  stacked?: boolean; legend?: boolean;
}) {
  const valueAxis = { type: "number" as const, ...AX, tickFormatter: (v: number) => fmt(v, 3), domain: yDomain ?? ["auto", "auto"] };
  const catAxis = { type: "category" as const, dataKey: xKey, ...AX, interval: 0 as const };
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"} barCategoryGap="18%" barGap={2}
          margin={{ top: 8, right: 14, bottom: xLabel ? 26 : 6, left: horizontal ? 8 : 4 }}>
          <CartesianGrid stroke={GRID} vertical={horizontal} horizontal={!horizontal} />
          {/* Recharts 2 does not discover axes inside fragments: render them as direct children */}
          {horizontal
            ? <XAxis {...valueAxis} label={yLabel ? { value: yLabel, position: "insideBottom", offset: -14, fontSize: 11, fill: "#3a3a38" } : undefined} />
            : <XAxis {...catAxis} label={xLabel ? { value: xLabel, position: "insideBottom", offset: -14, fontSize: 11, fill: "#3a3a38" } : undefined} />}
          {horizontal
            ? <YAxis {...catAxis} width={84} />
            : <YAxis {...valueAxis} width={56} label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", offset: 10, fontSize: 11, fill: "#3a3a38", style: { textAnchor: "middle" } } : undefined} />}
          <Tooltip isAnimationActive={false} cursor={{ fill: "#efeadc", opacity: 0.6 }}
            content={({ active, payload, label }) => active && payload?.length ? (
              <div className="border border-rule bg-ivory-50 px-2 py-1 font-mono text-[10.5px] shadow-sm">
                <div className="font-sans text-[11px] font-semibold">{String(label)}</div>
                {payload.map((p) => <div key={String(p.dataKey)}><span style={{ color: p.color as string }}>■</span> {p.name}: {fmt(p.value as number, 5)}</div>)}
              </div>) : null} />
          {legend && bars.length > 1 && <Legend verticalAlign="top" height={20} iconSize={9} wrapperStyle={{ fontSize: 10.5 }} />}
          {refY.map((r, i) => horizontal
            ? <ReferenceLine key={i} x={r.value} stroke={r.color ?? "#6b6963"} strokeDasharray="4 3" label={r.label ? { value: r.label, position: "top", fontSize: 10, fill: r.color ?? "#52514e" } : undefined} />
            : <ReferenceLine key={i} y={r.value} stroke={r.color ?? "#6b6963"} strokeDasharray="4 3" label={r.label ? { value: r.label, position: "insideTopRight", fontSize: 10, fill: r.color ?? "#52514e" } : undefined} />)}
          {bars.map((b) => (
            <Bar key={b.key} dataKey={b.key} name={b.name} fill={b.color} isAnimationActive={false} stackId={stacked ? "s" : undefined}
              radius={stacked ? 0 : horizontal ? [0, 3, 3, 0] : [3, 3, 0, 0]} maxBarSize={28}>
              {cellColor && data.map((row, i) => <Cell key={i} fill={cellColor(row, b.key) ?? b.color} />)}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
