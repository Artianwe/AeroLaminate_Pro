"use client";
// AeroLaminate Pro - plot container with export controls and result classification. Author: Anwesh Ajitabh Dash.
import { Component, useRef, type ReactNode } from "react";
import { exportCSV, exportPNG, exportSVG, type Row } from "@/lib/exporters";

export type Classification = "calculated" | "screening" | "estimate" | "reference" | "illustrative" | "unavailable";
const CLS: Record<Classification, { label: string; cls: string; title: string }> = {
  calculated: { label: "CALCULATED", cls: "border-graphite-600 text-graphite-700", title: "Direct solver output (CLT / closed form), verified analytically" },
  screening: { label: "SCREENING", cls: "border-amber-600 text-amber-700", title: "Established approximation with stated assumptions; not a high-fidelity prediction" },
  estimate: { label: "ESTIMATE", cls: "border-amber-600 text-amber-700 bg-amber-400/10", title: "Empirical relation or estimated data: trends only" },
  reference: { label: "REFERENCE", cls: "border-graphite-400 text-graphite-500", title: "Reference/closed-form data shown for comparison" },
  illustrative: { label: "ILLUSTRATIVE DATA", cls: "border-bad text-bad", title: "Uses illustrative material properties: not for engineering decisions" },
  unavailable: { label: "UNAVAILABLE", cls: "border-graphite-400 text-graphite-400", title: "Missing inputs or unsupported configuration" },
};

export function Badge({ c }: { c: Classification }) {
  const s = CLS[c];
  return <span title={s.title} className={`inline-block border px-1 font-mono text-[9.5px] leading-[14px] tracking-wider ${s.cls}`}>{s.label}</span>;
}

export default function ChartFrame({ title, subtitle, classification = "calculated", csv, children, actions, className = "", note, illustrative }: {
  title: string; subtitle?: ReactNode; classification?: Classification; csv?: () => Row[]; children: ReactNode;
  actions?: ReactNode; className?: string; note?: ReactNode; illustrative?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const btn = "px-1.5 py-[1px] font-mono text-[10px] text-graphite-500 hover:text-graphite-900 hover:bg-ivory-200 border border-transparent hover:border-rule";
  return (
    <section className={`panel flex flex-col ${className}`}>
      <header className="flex items-center gap-2 border-b border-rule px-2.5 py-1.5">
        <h3 className="text-[12px] font-semibold text-graphite-900">{title}</h3>
        <Badge c={classification} />
        {illustrative && <Badge c="illustrative" />}
        {subtitle && <span className="truncate text-xxs text-graphite-500">{subtitle}</span>}
        <div className="ml-auto flex items-center gap-0.5">
          {actions}
          <button className={btn} title="Export PNG (2x)" onClick={() => ref.current && exportPNG(ref.current, title)}>PNG</button>
          <button className={btn} title="Export SVG" onClick={() => ref.current && exportSVG(ref.current, title)}>SVG</button>
          {csv && <button className={btn} title="Export the plotted numerical data" onClick={() => exportCSV(title, csv())}>CSV</button>}
        </div>
      </header>
      <div ref={ref} className="relative min-h-0 flex-1 px-1.5 pb-1.5 pt-1"><PlotBoundary>{children}</PlotBoundary></div>
      {note && <footer className="border-t border-rule px-2.5 py-1 text-xxs text-graphite-500">{note}</footer>}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="flex h-full min-h-[120px] items-center justify-center px-6 text-center text-[11.5px] text-graphite-500">{children}</div>;
}

/** Contains a rendering failure to one panel instead of the whole workspace. */
class PlotBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(e: Error) { return { error: e.message }; }
  componentDidUpdate(prev: { children: ReactNode }) { if (prev.children !== this.props.children && this.state.error) this.setState({ error: null }); }
  render() {
    return this.state.error ? <Empty>This view could not be rendered: {this.state.error}</Empty> : this.props.children;
  }
}
