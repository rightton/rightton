// Assembly layer builder. The R-value shown is calculated by the Python core.
import { useEffect, useState } from "react";
import { engine, type AssemblyResult } from "../engine";
import { fmt, isWrapped, num } from "../schemaUtil";
import type { Json, Library, Obj } from "../types";

export function LayerBuilder({ assembly, setAssembly, lib }: { assembly: Obj; setAssembly: (a: Obj) => void; lib: Library }) {
  const layers = (Array.isArray(assembly.layers) ? assembly.layers : []) as Obj[];
  const [result, setResult] = useState<AssemblyResult | null>(null);
  const key = JSON.stringify(assembly);
  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => engine.assembly(assembly).then((r) => live && setResult(r)).catch(() => undefined), 150);
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
  const move = (i: number, d: number) => { const next = [...layers]; const [x] = next.splice(i, 1); next.splice(i + d, 0, x); write(next); };
  const materials = lib.materials;
  const uses = Array.from(new Set(materials.map((m) => m.use)));
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
          <p className="help">List layers from the inside face to the outside face. Air films are added automatically. Tick “framed” for a layer that has studs, joists or rafters running through it, and set the framing share below.</p>
          <ol className="layer-list">
            {layers.map((l, i) => {
              const mat = materials.find((m) => m.id === l.material);
              const fixed = mat && mat.r_value_hr_ft2_f_btu !== undefined && mat.r_per_inch_hr_ft2_f_btu_in === undefined;
              const framed = l.framing_material !== undefined || l.framing_r_per_inch_hr_ft2_f_btu_in !== undefined;
              const calc = result?.ok ? result.layers?.[i] : undefined;
              return (
                <li key={i} className="layer">
                  <div className="layer-top">
                    <span className="layer-n">{i + 1}</span>
                    <select aria-label="Material" value={(l.material as string) ?? ""} onChange={(e) => {
                      const m = materials.find((x) => x.id === e.target.value);
                      setLayer(i, { material: e.target.value || undefined, ...(m && l.thickness_in === undefined && m.typical_thickness_in ? { thickness_in: m.typical_thickness_in } : {}) } as Obj);
                    }}>
                      <option value="">Custom layer (enter R-value)</option>
                      {uses.map((u) => <optgroup key={u} label={u}>{materials.filter((m) => m.use === u).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</optgroup>)}
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
                      onChange={(e) => setLayer(i, { thickness_in: parse(e.target.value, l.thickness_in) } as Obj)} /></label>
                    <label>Layer R-value<input type="text" inputMode="decimal" value={numText(l.r_value_hr_ft2_f_btu)} placeholder={mat ? "from material" : "required"}
                      onChange={(e) => setLayer(i, { r_value_hr_ft2_f_btu: parse(e.target.value, l.r_value_hr_ft2_f_btu) } as Obj)} /></label>
                    <label className="check"><input type="checkbox" checked={framed} onChange={(e) => setLayer(i, { framing_material: e.target.checked ? "softwood" : undefined, framing_r_per_inch_hr_ft2_f_btu_in: undefined } as unknown as Obj)} /> framed (wood)</label>
                  </div>
                  {mat?.confidence === "estimated" && <p className="help warn">Typical value, not yet tied to a published source. Enter the rated R-value if you know it.</p>}
                  {mat?.note && <p className="help">{mat.note}</p>}
                </li>
              );
            })}
          </ol>
          <button className="btn small" onClick={() => write([...layers, {}])}>+ Add layer (toward outside)</button>
        </>
      )}
      <div className={`rbox ${result && !result.ok ? "bad" : ""}`}>
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
