// Assembly layer builder. The R-value shown is calculated by the Python core.
import { useEffect, useState, type ReactNode } from "react";
import { engine, type AssemblyResult } from "../engine";
import { fmt, isWrapped, num } from "../schemaUtil";
import type { Json, Library, Obj } from "../types";
import { WallSection } from "./WallSection";

export function LayerBuilder({ assembly, setAssembly, lib }: { assembly: Obj; setAssembly: (a: Obj) => void; lib: Library }) {
  const layers = (Array.isArray(assembly.layers) ? assembly.layers : []) as Obj[];
  const [computed, setComputed] = useState<{ key: string; result: AssemblyResult } | null>(null);
  const key = JSON.stringify(assembly);
  // Per-layer values are only shown for the layers they were calculated for (never a stale result).
  const result = computed?.result ?? null;
  const fresh = computed?.key === key;
  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => engine.assembly(assembly).then((r) => live && setComputed({ key, result: r })).catch(() => undefined), 150);
    return () => { live = false; clearTimeout(timer); };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const useLayers = Array.isArray(assembly.layers);
  const write = (next: Obj[]) => setAssembly({ ...assembly, layers: next as Json });
  const setLayer = (i: number, patch: Obj) => {
    const next = layers.map((l, j) => {
      if (j !== i) return l;
      const merged: Obj = { ...l, ...patch };
      for (const k of Object.keys(merged)) if (merged[k] === undefined || merged[k] === "") delete merged[k];
      return merged;
    });
    write(next);
  };
  // Split cavities: consecutive framed layers share one framing member, so they form one cavity. The
  // fills are its layers; depth the fills leave unused is a closed air space at the end of the run
  // (the core models it as R-1.0, see rightton.assemblies.split_cavity). Only thicknesses are added
  // up here; all R-values come from the core.
  const isFramed = (l: Obj) => l.framing_material !== undefined || l.framing_r_per_inch_hr_ft2_f_btu_in !== undefined;
  const isAir = (l: Obj) => l.material === "air_space_closed";
  const thick = (l: Obj) => num(l.thickness_in) ?? 0;
  const runs: { start: number; end: number }[] = [];
  for (let i = 0; i < layers.length; i++) {
    if (!isFramed(layers[i])) continue;
    const start = i;
    while (i + 1 < layers.length && isFramed(layers[i + 1])) i++;
    runs.push({ start, end: i });
  }
  const runOf = (i: number) => runs.find((r) => r.start <= i && i <= r.end);
  // An air space at the end of a cavity is its unused depth (an empty cavity is all air space).
  const leftoverIndex = (r: { start: number; end: number }) => (isAir(layers[r.end]) ? r.end : -1);
  const [depthText, setDepthText] = useState<Record<number, string>>({});
  const [depthError, setDepthError] = useState<Record<number, string>>({});
  const round3 = (x: number) => Math.round(x * 1000) / 1000;
  const runWithDepth = (r: { start: number; end: number }, fills: Obj[], depth: number): Obj[] => {
    const used = fills.reduce((a, l) => a + thick(l), 0);
    const framing = { framing_material: layers[r.start].framing_material, framing_r_per_inch_hr_ft2_f_btu_in: layers[r.start].framing_r_per_inch_hr_ft2_f_btu_in };
    for (const k of Object.keys(framing) as (keyof typeof framing)[]) if (framing[k] === undefined) delete framing[k];
    const rest = round3(depth - used);
    return rest > 0.01 ? [...fills, { material: "air_space_closed", thickness_in: rest, ...framing } as Obj] : fills;
  };
  const writeRun = (r: { start: number; end: number }, fills: Obj[], depth: number) =>
    write([...layers.slice(0, r.start), ...runWithDepth(r, fills, depth), ...layers.slice(r.end + 1)]);
  const fillsOf = (r: { start: number; end: number }) => { const li = leftoverIndex(r); return layers.slice(r.start, (li < 0 ? r.end : li - 1) + 1); };
  // Layers with every framed cavity set to a new depth (from the lumber size), where the fills fit.
  const layersAtDepth = (depth: number): Obj[] => {
    let next = [...layers];
    for (const r of [...runs].reverse()) {
      const fills = fillsOf(r);
      if (fills.reduce((a, l) => a + thick(l), 0) <= depth + 0.01) next = [...next.slice(0, r.start), ...runWithDepth(r, fills, depth), ...next.slice(r.end + 1)];
    }
    return next;
  };

  // Framing from lumber size and spacing (format 1.1). The share itself is calculated by the core.
  const fr = (assembly.framing && typeof assembly.framing === "object" && !Array.isArray(assembly.framing) ? assembly.framing : null) as Obj | null;
  const sizes = lib.framing.lumber;
  const setFraming = (next: Obj | null, newDepth?: number) => {
    const a: Obj = { ...assembly };
    if (next) a.framing = next; else delete a.framing;
    if (newDepth !== undefined && runs.length) a.layers = layersAtDepth(newDepth) as Json;
    setAssembly(a);
  };
  const setFramingField = (k: string, v: Json | undefined) => {
    const next: Obj = { ...(fr ?? { lumber: "2x4", spacing_in: 16 }) };
    if (v === undefined) delete next[k]; else next[k] = v;
    const lumber = next.lumber as string;
    const depth = num(next.depth_in) ?? sizes[lumber]?.depth_in;
    const depthChanged = k === "lumber" || k === "depth_in";
    setFraming(next, depthChanged ? depth : undefined);
  };
  const framingPanel = (): ReactNode => {
    const info = fresh && result?.ok ? result.framing : null;
    const lumber = (fr?.lumber as string) ?? "";
    const spacing = num(fr?.spacing_in);
    const preset = lib.framing.spacings_in.includes(spacing as number);
    const pct = (x: number | undefined) => (x === undefined ? "—" : `${fmt(x * 100, 1)}%`);
    const override = num(assembly.framing_frac);
    return (
      <div className="framing-panel">
        <h4>Framing</h4>
        <div className="framing-fields">
          <label>Lumber<select aria-label="Lumber" value={lumber} onChange={(e) => e.target.value === "" ? setFraming(null) : setFramingField("lumber", e.target.value)}>
            <option value="">Not given</option>
            {Object.entries(sizes).map(([k, v]) => <option key={k} value={k}>{k} ({v.width_in} × {v.depth_in} in)</option>)}
            <option value="custom">Custom size</option>
          </select></label>
          {fr && <label>Spacing (in o.c.)<select aria-label="Spacing" value={preset ? String(spacing) : "custom"} onChange={(e) => setFramingField("spacing_in", e.target.value === "custom" ? (spacing ?? 16) + 0.5 : Number(e.target.value))}>
            {lib.framing.spacings_in.map((x) => <option key={x} value={x}>{x} in</option>)}
            <option value="custom">Other</option>
          </select></label>}
          {fr && !preset && <label>Spacing (in)<input type="text" inputMode="decimal" aria-label="Custom spacing (in)" value={spacing ?? ""} onChange={(e) => setFramingField("spacing_in", e.target.value === "" ? undefined : Number(e.target.value))} /></label>}
          {fr && <label>Width (in)<input type="text" inputMode="decimal" aria-label="Member width (in)" value={num(fr.width_in) ?? ""} placeholder={sizes[lumber] ? String(sizes[lumber].width_in) : "required"}
            onChange={(e) => setFramingField("width_in", e.target.value === "" || Number.isNaN(Number(e.target.value)) ? undefined : Number(e.target.value))} /></label>}
          {fr && <label>Depth (in)<input type="text" inputMode="decimal" aria-label="Member depth (in)" value={num(fr.depth_in) ?? ""} placeholder={sizes[lumber] ? String(sizes[lumber].depth_in) : "required"}
            onChange={(e) => setFramingField("depth_in", e.target.value === "" || Number.isNaN(Number(e.target.value)) ? undefined : Number(e.target.value))} /></label>}
        </div>
        {!fr && <p className="help">Pick the stud, joist or rafter size and spacing and the framing share is worked out for you; or type the share below.</p>}
        {fr && <p className="help">Width and depth are the actual size; change them for old full-dimension lumber (a rough-sawn 2x4 is about 2 × 4 in). The depth is the cavity depth.</p>}
        {fr && info && (
          <table className="framing-sum"><tbody>
            <tr><th scope="row">Studs, joists or rafters ({info.width_in} in every {info.spacing_in} in)</th><td>{pct(info.member_frac)}</td></tr>
            <tr><th scope="row">Plates, headers, corners, window framing{info.allowance_overridden ? " (entered)" : " (typical)"}</th>
              <td><input type="text" inputMode="decimal" aria-label="Allowance (%)" className="pct" value={num(fr.allowance_frac) !== undefined ? String(round3((num(fr.allowance_frac) as number) * 100)) : ""} placeholder={fmt(info.allowance_frac * 100, 1)}
                onChange={(e) => setFramingField("allowance_frac", e.target.value === "" || Number.isNaN(Number(e.target.value)) ? undefined : Number(e.target.value) / 100)} />%</td></tr>
            <tr className="total"><th scope="row">Framing share{info.overridden_by_framing_frac ? " (calculated, not used)" : ""}</th><td>{pct(info.total_frac)}</td></tr>
          </tbody></table>
        )}
        {fr && !info && result && !result.ok && <p className="help warn">{result.error}</p>}
        {fr && !info && !(result && !result.ok) && <p className="help">Calculating…</p>}
        <label className="override">{fr ? "Override framing share (%)" : "Framing share of area (%)"}
          <input type="text" inputMode="decimal" aria-label="Framing share override (%)" value={override !== undefined ? String(round3(override * 100)) : ""} placeholder={fr ? "use calculated" : "0"}
            onChange={(e) => { const a: Obj = { ...assembly }; const v = e.target.value; if (v === "" || Number.isNaN(Number(v))) delete a.framing_frac; else a.framing_frac = Number(v) / 100; setAssembly(a); }} /></label>
        {info && <p className="help">The typical allowance comes from the framing factors the reference engine (OpenStudio-HPXML) uses; see data/README.md. Type your own if you know better.</p>}
      </div>
    );
  };
  const setDepth = (r: { start: number; end: number }, raw: string) => {
    setDepthText({ ...depthText, [r.start]: raw });
    const d = Number(raw);
    if (raw.trim() === "" || Number.isNaN(d) || d <= 0) { setDepthError({ ...depthError, [r.start]: "Enter the cavity depth in inches." }); return; }
    const li = leftoverIndex(r);
    const fills = layers.slice(r.start, (li < 0 ? r.end : li - 1) + 1);
    const used = fills.reduce((a, l) => a + thick(l), 0);
    if (used > d + 0.01) { setDepthError({ ...depthError, [r.start]: `The fills are ${round3(used)} in thick; they do not fit in a ${d} in cavity.` }); return; }
    setDepthError({ ...depthError, [r.start]: "" });
    writeRun(r, fills, d);
  };
  const addFill = (r: { start: number; end: number }) => {
    const li = leftoverIndex(r);
    const at = li < 0 ? r.end + 1 : li;
    const framing: Obj = {};
    if (layers[r.start].framing_material !== undefined) framing.framing_material = layers[r.start].framing_material;
    else framing.framing_r_per_inch_hr_ft2_f_btu_in = layers[r.start].framing_r_per_inch_hr_ft2_f_btu_in;
    write([...layers.slice(0, at), framing, ...layers.slice(at)]);
  };
  // Changing a fill's thickness keeps the cavity depth by shrinking or growing the leftover air space.
  const setFillThickness = (i: number, v: Json | undefined) => {
    const r = runOf(i);
    const li = r ? leftoverIndex(r) : -1;
    if (!r || li < 0 || i === li) { setLayer(i, { thickness_in: v } as Obj); return; }
    const depth = layers.slice(r.start, r.end + 1).reduce((a, l) => a + thick(l), 0);
    const fills = layers.slice(r.start, li).map((l, j) => (r.start + j === i ? { ...l, thickness_in: v } as Obj : l));
    for (const f of fills) if (f.thickness_in === undefined) delete f.thickness_in;
    const used = fills.reduce((a, l) => a + thick(l), 0);
    writeRun(r, fills, Math.max(depth, used));
  };
  const cavityHeader = (r: { start: number; end: number }): ReactNode => {
    const li = leftoverIndex(r);
    const depth = round3(layers.slice(r.start, r.end + 1).reduce((a, l) => a + thick(l), 0));
    const fillCount = (li < 0 ? r.end + 1 : li) - r.start;
    const err = depthError[r.start];
    return (
      <li key={`cavity-${r.start}`} className="cavity-head">
        <div className="cavity-row">
          <strong>Framed cavity{fillCount > 1 ? ` · ${fillCount} fills` : ""}</strong>
          <label>Cavity depth (in)<input type="text" inputMode="decimal" aria-label="Cavity depth (in)" value={depthText[r.start] ?? (depth ? String(depth) : "")}
            onChange={(e) => setDepth(r, e.target.value)} onBlur={() => { const t = { ...depthText }; delete t[r.start]; setDepthText(t); setDepthError({ ...depthError, [r.start]: "" }); }} /></label>
          <button className="btn small" onClick={() => addFill(r)}>{fillCount === 0 ? "+ Fill this cavity" : fillCount === 1 ? "Split cavity: add a fill" : "+ Add fill"}</button>
        </div>
        {err ? <p className="help warn" role="alert">{err}</p>
          : <p className="help">{fr && sizes[(fr.lumber as string)] && Math.abs((num(fr.depth_in) ?? sizes[fr.lumber as string].depth_in) - depth) > 0.01 ? `The ${fr.lumber} framing is ${num(fr.depth_in) ?? sizes[fr.lumber as string].depth_in} in deep. ` : ""}{li >= 0 ? `${round3(thick(layers[li]))} in ${fillCount ? "left over" : "of empty cavity"} is counted as a closed air space (R-1.0).` : "The fills below share one set of framing members."} Fills are listed inside to outside.</p>}
      </li>
    );
  };
  const move = (i: number, d: number) => { const next = [...layers]; const [x] = next.splice(i, 1); next.splice(i + d, 0, x); write(next); };
  const materials = lib.materials;
  // Grouped by material type. Any material can go in any layer, framed or not: `use` is only a hint.
  const groups = lib.material_categories.map((c) => ({ ...c, items: materials.filter((m) => m.category === c.id) })).filter((g) => g.items.length);
  const numText = (v: Json | undefined) => (num(v) === undefined ? "" : String(num(v)));
  const parse = (raw: string, old: Json | undefined): Json | undefined => {
    if (raw.trim() === "") return undefined;
    const n = Number(raw);
    if (Number.isNaN(n)) return old;
    return isWrapped(old) ? { ...(old as Obj), value: n } : n;
  };
  const switchMode = (toLayers: boolean) => {
    const next = { ...assembly };
    if (toLayers) { delete next.r_value_hr_ft2_f_btu; next.layers = []; } else { delete next.layers; delete next.framing_frac; next.r_value_hr_ft2_f_btu = result?.r_value ?? 10; }
    setAssembly(next);
  };
  const total = result?.ok && result.layers ? (result.film_inside_r ?? 0) + (result.film_outside_r ?? 0) + result.layers.reduce((a, l) => a + l.r_value, 0) : 0;
  return (
    <div className="layers">
      <div className="seg" role="tablist" aria-label="How the R-value is given">
        <button role="tab" aria-selected={useLayers} className={useLayers ? "on" : ""} onClick={() => !useLayers && switchMode(true)}>Build from layers</button>
        <button role="tab" aria-selected={!useLayers} className={!useLayers ? "on" : ""} onClick={() => useLayers && switchMode(false)}>Enter total R-value</button>
      </div>
      {useLayers && (
        <>
          <p className="help">List layers from the inside face to the outside face. Air films are added automatically. Tick “framed” for a layer that has studs, joists or rafters running through it, and set the framing share below. Any insulation can fill any cavity: pick the material, then enter the cavity depth as the thickness (2x4 = 3.5 in, 2x6 = 5.5 in, 2x8 = 7.25 in).</p>
          <ol className="layer-list">
            {layers.map((l, i) => {
              const mat = materials.find((m) => m.id === l.material);
              const fixed = mat && mat.r_value_hr_ft2_f_btu !== undefined && mat.r_per_inch_hr_ft2_f_btu_in === undefined;
              const framed = l.framing_material !== undefined || l.framing_r_per_inch_hr_ft2_f_btu_in !== undefined;
              const calc = fresh && result?.ok ? result.layers?.[i] : undefined;
              const run = runOf(i);
              return [run && run.start === i ? cavityHeader(run) : null, (
                <li key={i} className={`layer${run ? " in-cavity" : ""}${run && run.end === i ? " cavity-last" : ""}`}>
                  <div className="layer-top">
                    <span className="layer-n">{i + 1}</span>
                    <select aria-label="Material" value={(l.material as string) ?? ""} onChange={(e) => {
                      const m = materials.find((x) => x.id === e.target.value);
                      const run = runOf(i);
                      const keepDepth = run && leftoverIndex(run) >= 0;  // a fill's thickness is entered against the cavity depth
                      setLayer(i, { material: e.target.value || undefined, ...(m && !keepDepth && l.thickness_in === undefined && m.typical_thickness_in ? { thickness_in: m.typical_thickness_in } : {}) } as Obj);
                    }}>
                      <option value="">Custom layer (enter R-value)</option>
                      {groups.map((g) => <optgroup key={g.id} label={g.name}>{g.items.map((m) => <option key={m.id} value={m.id} title={`Usually: ${m.use}`}>{m.name}</option>)}</optgroup>)}
                    </select>
                    <span className="layer-r" title="R-value of this layer (between framing)">{calc ? `R-${fmt(calc.r_value, 2)}` : "—"}</span>
                    <span className="layer-btns">
                      <button className="icon" aria-label="Move layer toward inside" disabled={i === 0} onClick={() => move(i, -1)}>↑</button>
                      <button className="icon" aria-label="Move layer toward outside" disabled={i === layers.length - 1} onClick={() => move(i, 1)}>↓</button>
                      <button className="icon danger" aria-label="Remove layer" onClick={() => write(layers.filter((_, j) => j !== i))}>×</button>
                    </span>
                  </div>
                  <div className="layer-fields">
                    <label>Name<input type="text" value={(l.name as string) ?? ""} placeholder={mat?.name ?? "e.g. R-13 batt"} onChange={(e) => setLayer(i, { name: e.target.value || undefined } as Obj)} /></label>
                    <label>Thickness (in)<input type="text" inputMode="decimal" value={numText(l.thickness_in)} disabled={!!fixed && !framed} placeholder={mat?.typical_thickness_in !== undefined ? `${mat.typical_thickness_in} (typical)` : ""}
                      onChange={(e) => setFillThickness(i, parse(e.target.value, l.thickness_in))} /></label>
                    <label>Layer R-value<input type="text" inputMode="decimal" value={numText(l.r_value_hr_ft2_f_btu)} placeholder={mat ? "from material" : "required"}
                      onChange={(e) => setLayer(i, { r_value_hr_ft2_f_btu: parse(e.target.value, l.r_value_hr_ft2_f_btu) } as Obj)} /></label>
                    <label className="check"><input type="checkbox" checked={framed} onChange={(e) => setLayer(i, { framing_material: e.target.checked ? "softwood" : undefined, framing_r_per_inch_hr_ft2_f_btu_in: undefined } as unknown as Obj)} /> framed (wood)</label>
                  </div>
                  {mat?.confidence === "estimated" && <p className="help warn">Typical value, not yet tied to a published source. Enter the rated R-value if you know it.</p>}
                  {mat?.note && <p className="help">{mat.note}</p>}
                </li>
              )];
            })}
          </ol>
          <button className="btn small" onClick={() => write([...layers, {}])}>+ Add layer (toward outside)</button>
          <WallSection assembly={assembly} lib={lib} result={fresh ? result : null} />
          {runs.length > 0 || fr || assembly.framing_frac !== undefined ? framingPanel() : null}
        </>
      )}
      <div className={`rbox ${result && !result.ok ? "bad" : ""}${fresh ? "" : " stale"}`} aria-busy={!fresh}>
        {!result && <span className="muted">Calculating…</span>}
        {result && !result.ok && <span>{result.error}</span>}
        {result?.ok && (
          <>
            <div className="rbox-main"><span className="rbig">R-{fmt(result.r_value, 1)}</span><span className="muted">U = {fmt(result.u_factor, 3)} Btu/h·ft²·°F, air films included</span></div>
            {result.from_layers && result.layers && total > 0 && (
              <>
                <div className="buildup" aria-hidden="true">
                  <span style={{ flexGrow: result.film_inside_r }} className="film" title={`Inside air film R-${result.film_inside_r}`} />
                  {result.layers.map((l, i) => <span key={i} style={{ flexGrow: Math.max(l.r_value, 0.02) }} className={`seg-${i % 5}`} title={`${l.name}: R-${l.r_value}`} />)}
                  <span style={{ flexGrow: result.film_outside_r }} className="film" title={`Outside air film R-${result.film_outside_r}`} />
                </div>
                <p className="help">Between framing: R-{fmt(result.cavity_path_r, 1)}. Through framing: R-{fmt(result.framing_path_r, 1)}.
                  Air films: R-{fmt(result.film_inside_r, 2)} inside, R-{fmt(result.film_outside_r, 2)} outside (wind-washed).
                  {result.r_value_sheltered !== result.r_value && <> Facing an attic, crawlspace or porch instead: R-{fmt(result.r_value_sheltered, 1)}.</>}</p>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
