// AeroLaminate Pro - stacking-sequence notation. Author: Anwesh Ajitabh Dash.
// Grammar (bottom -> top as written):  [a/b/c]  with tokens like 0, 45, -45, ±45 (or +-45), 90_2 (repeat),
// group suffix N (repeat group N times) and s (mirror about mid-plane), e.g. [0/±45/90]s, [±45/0_2]2s, [45/-45]3.
// A trailing "s" with an overbar middle ply is written as "[0/45/90~]s" (the "~" ply is not duplicated).

export interface ParseResult { angles: number[]; error?: string }

export function parseLayup(text: string): ParseResult {
  const t = text.replace(/\s+/g, "").replace(/\+\-|\+\/-|±/g, "±");
  if (!t) return { angles: [], error: "Enter a stacking sequence, e.g. [0/±45/90]s" };
  const mm = t.match(/^\[([^\]]+)\](\d+)?(s)?$/i);
  if (!mm) return { angles: [], error: "Use bracket notation, e.g. [0/±45/90]s or [45/-45/0_2]2s" };
  const body = mm[1];
  const rep = mm[2] ? parseInt(mm[2], 10) : 1;
  const sym = !!mm[3];
  if (rep < 1 || rep > 50) return { angles: [], error: "Group repeat must be 1..50" };
  const out: number[] = [];
  let middle: number | null = null;
  const tokens = body.split("/");
  for (let i = 0; i < tokens.length; i++) {
    let tok = tokens[i];
    if (!tok) return { angles: [], error: "Empty ply entry" };
    let isMiddle = false;
    if (tok.endsWith("~")) {
      if (!sym || i !== tokens.length - 1) return { angles: [], error: "'~' (unpaired middle ply) only on the last ply of a symmetric group" };
      isMiddle = true;
      tok = tok.slice(0, -1);
    }
    let count = 1;
    const sub = tok.match(/^(.*)_(\d+)$/);
    if (sub) { tok = sub[1]; count = parseInt(sub[2], 10); }
    if (count < 1 || count > 100) return { angles: [], error: "Ply repeat must be 1..100" };
    let seq: number[];
    if (tok.startsWith("±") || tok.startsWith("∓")) {
      const v = Number(tok.slice(1));
      if (!Number.isFinite(v)) return { angles: [], error: `Invalid angle '${tokens[i]}'` };
      seq = tok.startsWith("±") ? [v, -v] : [-v, v];
    } else {
      const v = Number(tok);
      if (!Number.isFinite(v)) return { angles: [], error: `Invalid angle '${tokens[i]}'` };
      seq = [v];
    }
    if (seq.some((a) => Math.abs(a) > 180)) return { angles: [], error: "Angles must be within ±180°" };
    if (isMiddle) {
      if (count !== 1 || seq.length !== 1) return { angles: [], error: "Middle ply must be a single ply" };
      middle = seq[0];
      continue;
    }
    for (let c = 0; c < count; c++) out.push(...seq);
  }
  let group: number[] = [];
  for (let r = 0; r < rep; r++) group = group.concat(out);
  const full = sym ? [...group, ...(middle !== null ? [middle] : []), ...[...group].reverse()] : group;
  if (full.length === 0) return { angles: [], error: "No plies" };
  if (full.length > 400) return { angles: [], error: "At most 400 plies" };
  return { angles: full };
}

export function formatLayup(angles: number[]): string {
  const n = angles.length;
  if (n === 0) return "[]";
  const sym = angles.every((a, i) => a === angles[n - 1 - i]);
  const half = sym && n > 1 ? angles.slice(0, Math.floor(n / 2)) : angles;
  const mid = sym && n % 2 === 1 && n > 1 ? angles[Math.floor(n / 2)] : null;
  const toks: string[] = [];
  for (let i = 0; i < half.length; ) {
    const a = half[i];
    if (a !== 0 && a !== 90 && half[i + 1] === -a && a > 0) { toks.push(`±${a}`); i += 2; continue; }
    let j = i;
    while (j + 1 < half.length && half[j + 1] === a) j++;
    const c = j - i + 1;
    toks.push(c > 1 ? `${a}_${c}` : `${a}`);
    i = j + 1;
  }
  if (mid !== null) toks.push(`${mid}~`);
  return `[${toks.join("/")}]${sym && n > 1 ? "s" : ""}`;
}
