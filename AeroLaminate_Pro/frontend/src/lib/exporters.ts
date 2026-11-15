// AeroLaminate Pro - chart and data export (PNG, SVG, CSV, JSON). Author: Anwesh Ajitabh Dash.

export function download(name: string, data: BlobPart, type: string) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function slug(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 60) || "chart";
}

export type Row = Record<string, string | number | boolean | null | undefined>;

export function toCSV(rows: Row[], header?: string[]): string {
  if (!rows.length) return "";
  const cols = header ?? Array.from(rows.reduce((s, r) => { Object.keys(r).forEach((k) => s.add(k)); return s; }, new Set<string>()));
  const esc = (v: unknown) => {
    if (v === null || v === undefined) return "";
    const s = typeof v === "number" ? (Number.isFinite(v) ? String(v) : "") : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
}

export function exportCSV(name: string, rows: Row[], provenance = "Calculated by AeroLaminate Pro (author: Anwesh Ajitabh Dash)") {
  const body = `# ${provenance}\n# Exported ${new Date().toISOString()}\n` + toCSV(rows);
  download(`${slug(name)}.csv`, body, "text/csv;charset=utf-8");
}

const STYLE_PROPS = ["fill", "stroke", "stroke-width", "stroke-dasharray", "font-family", "font-size", "font-weight", "opacity", "fill-opacity", "stroke-opacity", "text-anchor", "dominant-baseline"];

function serializeSVG(svg: SVGSVGElement, title: string): string {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const src = svg.querySelectorAll("*");
  const dst = clone.querySelectorAll("*");
  src.forEach((el, i) => {
    const cs = getComputedStyle(el);
    const target = dst[i] as SVGElement;
    STYLE_PROPS.forEach((p) => { const v = cs.getPropertyValue(p); if (v) target.style.setProperty(p, v); });
  });
  const w = svg.clientWidth || Number(svg.getAttribute("width")) || 600;
  const h = svg.clientHeight || Number(svg.getAttribute("height")) || 400;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(w)); clone.setAttribute("height", String(h));
  clone.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  bg.setAttribute("width", "100%"); bg.setAttribute("height", "100%"); bg.setAttribute("fill", "#fcfbf7");
  clone.insertBefore(bg, clone.firstChild);
  const t = document.createElementNS("http://www.w3.org/2000/svg", "title");
  t.textContent = `${title} - AeroLaminate Pro (Anwesh Ajitabh Dash)`;
  clone.insertBefore(t, clone.firstChild);
  return new XMLSerializer().serializeToString(clone);
}

function findSVG(root: HTMLElement): SVGSVGElement | null {
  const svgs = Array.from(root.querySelectorAll("svg")).filter((s) => !s.closest("button") && s.clientWidth > 60);
  return (svgs.sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0] as SVGSVGElement) ?? null;
}

export function exportSVG(root: HTMLElement, title: string) {
  const svg = findSVG(root);
  if (!svg) return alert("No vector graphic found in this panel");
  download(`${slug(title)}.svg`, serializeSVG(svg, title), "image/svg+xml");
}

export function exportPNG(root: HTMLElement, title: string, scale = 2) {
  const svg = findSVG(root);
  if (!svg) return alert("No vector graphic found in this panel");
  const xml = serializeSVG(svg, title);
  const img = new Image();
  const w = svg.clientWidth, h = svg.clientHeight;
  img.onload = () => {
    const c = document.createElement("canvas");
    c.width = w * scale; c.height = h * scale;
    const ctx = c.getContext("2d")!;
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0, w, h);
    c.toBlob((b) => b && download(`${slug(title)}.png`, b, "image/png"), "image/png");
  };
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
}
