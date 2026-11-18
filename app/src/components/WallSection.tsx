// A drawn section of an assembly, inside face on the left, outside on the right, as if cut through and
// seen from above (a wall) or from the side (a roof, ceiling or floor). Not to scale: thin layers get a
// minimum width and thick ones are compressed. Framed layers show their members at the entered spacing.
// Nothing is calculated here: thicknesses come from the house file, R-values and framing from the core.
import type { AssemblyResult } from "../engine";
import { fmt, num } from "../schemaUtil";
import type { Library, Obj } from "../types";

type Props = { assembly: Obj; lib: Library; result: AssemblyResult | null };

const H = 150;            // drawing height (px): two framing bays
const TOP = 26;           // room for layer numbers
const SIDE = 46;          // room for the inside / outside labels

/** Distorted width: grows with the square root of thickness, never thinner than 9 px. */
export function layerWidthPx(thicknessIn: number): number {
  return Math.max(9, 10 + 24 * Math.sqrt(Math.max(thicknessIn, 0)));
}

const FILL: Record<string, string> = {
  gypsum_plaster: "url(#hatch-plaster)", wood: "url(#hatch-wood)", batts: "url(#hatch-batt)", loose_fill: "url(#hatch-loose)",
  spray_foam: "url(#hatch-foam)", rigid_boards: "url(#hatch-board)", natural_fiber: "url(#hatch-straw)", masonry: "url(#hatch-brick)",
  cladding: "url(#hatch-clad)", roofing: "url(#hatch-clad)", flooring: "url(#hatch-wood)", air_space: "var(--sec-air)", custom: "url(#hatch-custom)",
};

export function WallSection({ assembly, lib, result }: Props) {
  const layers = (Array.isArray(assembly.layers) ? assembly.layers : []) as Obj[];
  if (!layers.length) return null;
  const mats = new Map(lib.materials.map((m) => [m.id, m]));
  const framing = result?.ok ? result.framing : null;
  const spacing = framing?.spacing_in ?? 16;
  const memberW = framing?.width_in ?? 1.5;
  const assumed = !framing;
  const isFramed = (l: Obj) => l.framing_material !== undefined || l.framing_r_per_inch_hr_ft2_f_btu_in !== undefined;
  const items = layers.map((l, i) => {
    const m = mats.get(l.material as string);
    const given = num(l.thickness_in);
    const thick = given ?? m?.typical_thickness_in ?? 0.5;
    return { i, l, m, thick, thicknessKnown: given !== undefined || m?.typical_thickness_in !== undefined, framed: isFramed(l),
      category: m?.category ?? "custom", name: (l.name as string) || m?.name || `Layer ${i + 1}`, r: result?.ok ? result.layers?.[i]?.r_value : undefined };
  });
  let x = SIDE;
  const placed = items.map((it) => { const w = layerWidthPx(it.thick); const at = x; x += w; return { ...it, x: at, w }; });
  const width = x + SIDE;
  // Members: two bays visible, members at 0, spacing and 2 x spacing (to scale vertically)
  const bay = (H - 10) / 2;
  const memberH = Math.max(4, (memberW / spacing) * bay * 1.0);
  const memberY = [5, 5 + bay, 5 + 2 * bay].map((y) => y - memberH / 2);
  const runs: { x: number; w: number }[] = [];
  for (const p of placed) {
    if (!p.framed) continue;
    const last = runs[runs.length - 1];
    if (last && Math.abs(last.x + last.w - p.x) < 0.01) last.w += p.w; else runs.push({ x: p.x, w: p.w });
  }
  const kind = (assembly.type as string) ?? "wall";
  const inLabel = kind === "ceiling" ? "room below" : kind === "floor" ? "room above" : "inside";
  const outLabel = kind === "ceiling" ? "attic" : kind === "floor" ? "below" : "outside";
  return (
    <figure className="wall-section" aria-label="Section drawing of the assembly">
      <svg viewBox={`0 0 ${width} ${H + TOP + 10}`} role="img" aria-labelledby="sec-title" preserveAspectRatio="xMinYMin meet">
        <title id="sec-title">{`Section, inside to outside: ${items.map((it) => it.name).join(", ")}`}</title>
        <defs>
          <pattern id="hatch-plaster" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="var(--sec-plaster)" /><circle cx="2" cy="2" r=".8" fill="var(--sec-ink)" /><circle cx="5" cy="5" r=".6" fill="var(--sec-ink)" /></pattern>
          <pattern id="hatch-wood" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="8" fill="var(--sec-wood)" /><line x1="0" y1="0" x2="0" y2="8" stroke="var(--sec-ink)" strokeWidth="1" /></pattern>
          <pattern id="hatch-batt" width="12" height="10" patternUnits="userSpaceOnUse"><rect width="12" height="10" fill="var(--sec-batt)" /><path d="M0 5 Q3 0 6 5 T12 5" fill="none" stroke="var(--sec-ink)" strokeWidth=".8" /></pattern>
          <pattern id="hatch-loose" width="7" height="7" patternUnits="userSpaceOnUse"><rect width="7" height="7" fill="var(--sec-batt)" /><circle cx="1.5" cy="2" r=".9" fill="var(--sec-ink)" /><circle cx="5" cy="4.5" r=".7" fill="var(--sec-ink)" /><circle cx="2.5" cy="6" r=".5" fill="var(--sec-ink)" /></pattern>
          <pattern id="hatch-foam" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="var(--sec-foam)" /><circle cx="4" cy="4" r="2.2" fill="none" stroke="var(--sec-ink)" strokeWidth=".6" /></pattern>
          <pattern id="hatch-board" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="var(--sec-board)" /><path d="M0 6 L6 0 M0 0 L6 6" stroke="var(--sec-ink)" strokeWidth=".5" /></pattern>
          <pattern id="hatch-straw" width="10" height="4" patternUnits="userSpaceOnUse"><rect width="10" height="4" fill="var(--sec-batt)" /><line x1="0" y1="2" x2="10" y2="2" stroke="var(--sec-ink)" strokeWidth=".6" /></pattern>
          <pattern id="hatch-brick" width="16" height="10" patternUnits="userSpaceOnUse"><rect width="16" height="10" fill="var(--sec-brick)" /><path d="M0 0 H16 M0 5 H16 M4 0 V5 M12 5 V10" stroke="var(--sec-mortar)" strokeWidth="1" /></pattern>
          <pattern id="hatch-clad" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)"><rect width="5" height="5" fill="var(--sec-clad)" /><line x1="0" y1="0" x2="0" y2="5" stroke="var(--sec-ink)" strokeWidth=".8" /></pattern>
          <pattern id="hatch-custom" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="var(--sec-air)" /><path d="M0 3 H6" stroke="var(--sec-ink)" strokeWidth=".5" /></pattern>
          <pattern id="hatch-member" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="var(--sec-wood)" /><line x1="0" y1="0" x2="0" y2="5" stroke="var(--sec-ink)" strokeWidth="1.2" /></pattern>
        </defs>
        <g transform={`translate(0 ${TOP})`}>
          {placed.map((p) => (
            <g key={p.i}>
              <rect x={p.x} y={0} width={p.w} height={H} fill={FILL[p.category] ?? FILL.custom} stroke="var(--sec-line)" strokeWidth=".8" />
              <text x={p.x + p.w / 2} y={-8} textAnchor="middle" className="sec-n">{p.i + 1}</text>
            </g>
          ))}
          {runs.map((r, k) => memberY.map((y, j) => (
            <rect key={`${k}-${j}`} className="sec-member" x={r.x} y={Math.max(0, y)} width={r.w} height={Math.min(memberH, H - Math.max(0, y))} fill="url(#hatch-member)" stroke="var(--sec-line)" strokeWidth=".8" />
          )))}
          <text x={SIDE - 6} y={H / 2} textAnchor="end" className="sec-side">{inLabel}</text>
          <text x={width - SIDE + 6} y={H / 2} className="sec-side">{outLabel}</text>
        </g>
      </svg>
      <figcaption>
        <ol className="sec-legend">
          {items.map((it) => (
            <li key={it.i}><span className="sec-swatch" data-cat={it.category} />
              <span>{it.name}</span>
              <span className="muted"> · {it.thicknessKnown ? `${Number(it.thick.toFixed(3))} in` : "thickness not given"}{it.r !== undefined ? ` · R\u2011${fmt(it.r, 2)}` : ""}{it.framed ? " · framed" : ""}</span></li>
          ))}
        </ol>
        <p className="help">Not to scale: thin layers are drawn wider and thick ones narrower so every layer shows.{runs.length ? ` Framing drawn ${memberW} in wide every ${spacing} in${assumed ? " (assumed; give lumber and spacing under Framing)" : ""}.` : ""}</p>
      </figcaption>
    </figure>
  );
}
