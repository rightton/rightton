// Form fields generated from the house-file schema. Field names, units, allowed
// values and help text all come from the schema, so the forms cannot drift from the format.
import { useState, type ReactNode } from "react";
import { getIn, list } from "../state";
import { humanize, isIdRef, isQuantity, isWrapped, num, pretty, resolve, unitLabel } from "../schemaUtil";
import type { House, Json, Library, Obj, Schema } from "../types";

export type Ctx = { house: House; lib: Library; rename: (oldId: string, newId: string) => void };
type Option = { value: string; label: string; group?: string };

const named = (items: Obj[], group?: string): Option[] =>
  items.filter((i) => typeof i.id === "string").map((i) => ({ value: i.id as string, label: (i.name as string) || (i.id as string), group }));

/** Pick-list for fields that refer to something else by id. */
export function refOptions(name: string, ctx: Ctx, owner?: Obj): Option[] | null {
  const h = ctx.house;
  const rooms = named(list(h, ["rooms"]), "Rooms");
  const spaces = named(list(h, ["spaces"]), "Spaces");
  const words = (ws: string[]): Option[] => ws.map((w) => ({ value: w, label: pretty(w), group: "Outside" }));
  switch (name) {
    case "zone": return named(list(h, ["zones"]));
    case "inside": return [...rooms, ...spaces];
    case "outside": return [...words(["outdoors", "ground", "adiabatic"]), ...spaces, ...rooms].filter((o) => o.value !== owner?.inside);
    case "assembly": {
      const want = ({ wall: "wall", rim_joist: "wall", foundation_wall: "wall", roof: "roof", ceiling: "ceiling", floor: "floor" } as Record<string, string>)[owner?.type as string];
      const all = list(h, ["assemblies"]);
      const match = all.filter((a) => !want || a.type === want || (["ceiling", "floor"].includes(want) && ["ceiling", "floor"].includes(a.type as string)));
      return named(match.length ? match : all);
    }
    case "surface": {
      const kinds = owner?.type === "skylight" ? ["roof"] : ["wall", "foundation_wall"];
      return named(list(h, ["surfaces"]).filter((s) => kinds.includes(s.type as string)));
    }
    case "ceiling": return named(list(h, ["surfaces"]).filter((s) => s.type === "ceiling"));
    case "system": return named(list(h, ["hvac", "systems"]));
    case "room": return [...rooms, ...named(list(h, ["spaces"]).filter((s) => s.type === "conditioned"), "Conditioned spaces")];
    case "location": return [...words(["outdoors"]), ...spaces, ...rooms];
    case "material": case "framing_material":
      return ctx.lib.materials.filter((m) => name === "material" || m.r_per_inch_hr_ft2_f_btu_in !== undefined)
        .map((m) => ({ value: m.id, label: m.name, group: m.use }));
    case "glazing": return ctx.lib.glazing.map((g) => ({ value: g.id, label: `${g.name} (U ${g.u_factor_btu_hr_ft2_f}, SHGC ${g.shgc})` }));
    case "weather_station_id": return ctx.lib.stations.map((s) => ({ value: s.id, group: s.state, label: `${s.name}, ${s.state} (${Math.round(s.heating_f)}°F / ${Math.round(s.cooling_f)}°F)` }));
    case "supply_registers": case "returns": return rooms;
    case "includes": return named(list(h, ["scenarios"])).filter((o) => o.value !== owner?.id);
    default: return null;
  }
}

function Select({ value, options, onChange, placeholder, id }: { value: string | undefined; options: Option[]; onChange: (v: string | undefined) => void; placeholder: string; id?: string }) {
  const groups = Array.from(new Set(options.map((o) => o.group ?? "")));
  const missing = value !== undefined && value !== "" && !options.some((o) => o.value === value);
  return (
    <select id={id} className={missing ? "invalid" : ""} value={value ?? ""} onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value)}>
      <option value="">{placeholder}</option>
      {missing && <option value={value}>{value} (not found)</option>}
      {groups.map((g) => g === ""
        ? options.filter((o) => !o.group).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)
        : <optgroup key={g} label={g}>{options.filter((o) => o.group === g).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</optgroup>)}
    </select>
  );
}

/** A number with an optional source and confidence. */
export function QuantityInput({ value, schema, onChange, id, placeholder }: { value: Json | undefined; schema: Schema; onChange: (v: Json | undefined) => void; id?: string; placeholder?: string }) {
  const wrapped = isWrapped(value);
  const [open, setOpen] = useState(false);
  const n = num(value);
  const [text, setText] = useState<string | null>(null);
  const shown = text ?? (n === undefined ? "" : String(n));
  const unit = unitLabel(schema);
  const commit = (raw: string) => {
    if (raw.trim() === "") { onChange(undefined); return; }
    const parsed = Number(raw);
    if (Number.isNaN(parsed)) return;
    onChange(wrapped ? { ...(value as Obj), value: parsed } : parsed);
  };
  const lo = schema["x-min"], hi = schema["x-max"];
  const bad = n !== undefined && ((lo !== undefined && n < lo) || (hi !== undefined && n > hi));
  const confidence = wrapped ? ((value as Obj).confidence as string) ?? "default" : null;
  return (
    <div className="quantity">
      <div className="input-row">
        <input id={id} className={bad ? "invalid" : ""} type="text" inputMode="decimal" value={shown} placeholder={placeholder}
          onChange={(e) => { setText(e.target.value); commit(e.target.value); }} onBlur={() => setText(null)} />
        {unit && <span className="unit">{unit}</span>}
        <button type="button" className={`source-btn ${confidence ?? ""}`} title="Where this number came from" aria-label="Source and confidence"
          disabled={n === undefined} onClick={() => setOpen(!open)}>{confidence ? confidence : "source"}</button>
      </div>
      {open && n !== undefined && (
        <div className="source-row">
          <input type="text" placeholder="Where did this number come from?" value={wrapped ? ((value as Obj).source as string) ?? "" : ""}
            onChange={(e) => onChange({ value: n, ...(e.target.value ? { source: e.target.value } : {}), confidence: confidence ?? "estimated" })} />
          <select value={confidence ?? ""} onChange={(e) => {
            if (e.target.value === "") onChange(n);
            else onChange({ value: n, ...(wrapped && (value as Obj).source ? { source: (value as Obj).source } : {}), confidence: e.target.value });
          }}>
            <option value="">no note</option><option value="measured">measured</option><option value="estimated">estimated</option><option value="default">default</option>
          </select>
        </div>
      )}
    </div>
  );
}

function MultiSelect({ value, options, onChange }: { value: string[]; options: Option[]; onChange: (v: string[] | undefined) => void }) {
  const toggle = (v: string) => {
    const next = value.includes(v) ? value.filter((x) => x !== v) : [...value, v];
    onChange(next.length ? next : undefined);
  };
  if (!options.length) return <p className="muted small">Nothing to choose from yet.</p>;
  return (
    <div className="chips">
      {options.map((o) => (
        <button type="button" key={o.value} className={`chip ${value.includes(o.value) ? "on" : ""}`} aria-pressed={value.includes(o.value)} onClick={() => toggle(o.value)}>{o.label}</button>
      ))}
      {options.length > 1 && <button type="button" className="chip ghost" onClick={() => onChange(value.length === options.length ? undefined : options.map((o) => o.value))}>
        {value.length === options.length ? "none" : "all"}</button>}
    </div>
  );
}

function IdInput({ value, onRename }: { value: string; onRename: (v: string) => void }) {
  const [text, setText] = useState<string | null>(null);
  const shown = text ?? value;
  const ok = /^[a-z0-9][a-z0-9_-]*$/.test(shown);
  return <input type="text" className={ok ? "mono" : "mono invalid"} value={shown} spellCheck={false}
    onChange={(e) => setText(e.target.value)} onBlur={() => { if (text !== null && ok && text !== value) onRename(text); setText(null); }} />;
}

export function Field({ name, schema, value, onChange, ctx, owner, required }: {
  name: string; schema: Schema; value: Json | undefined; onChange: (v: Json | undefined) => void; ctx: Ctx; owner?: Obj; required?: boolean;
}) {
  const s = resolve(schema);
  const fieldId = `f-${name}-${String(owner?.id ?? "")}`;
  const options = refOptions(name, ctx, owner);
  let input;
  let wide = false;
  if (name === "id") {
    input = <IdInput value={(value as string) ?? ""} onRename={(v) => ctx.rename(value as string, v)} />;
  } else if (isQuantity(schema)) {
    input = <QuantityInput id={fieldId} value={value} schema={schema} onChange={onChange} />;
  } else if (s.type === "array" && options) {
    input = <MultiSelect value={(value as string[]) ?? []} options={options} onChange={onChange} />;
    wide = true;
  } else if (options) {
    input = <Select id={fieldId} value={value as string | undefined} options={options} onChange={onChange} placeholder={required ? "Choose…" : "—"} />;
  } else if (s.enum) {
    input = <Select id={fieldId} value={value === undefined ? undefined : String(value)} placeholder={required ? "Choose…" : "default"}
      options={s.enum.map((v) => ({ value: String(v), label: pretty(String(v)) }))}
      onChange={(v) => onChange(v === undefined ? undefined : s.type === "integer" ? Number(v) : v)} />;
  } else if (s.type === "boolean") {
    input = <label className="check"><input type="checkbox" checked={value === true} onChange={(e) => onChange(e.target.checked ? true : undefined)} /> Yes</label>;
  } else if (s.type === "integer") {
    input = <input id={fieldId} type="text" inputMode="numeric" value={value === undefined ? "" : String(value)}
      onChange={(e) => { const v = e.target.value.trim(); if (v === "") onChange(undefined); else if (/^\d+$/.test(v)) onChange(Number(v)); }} />;
  } else if (name === "notes" || name === "description") {
    input = <textarea id={fieldId} rows={2} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value || undefined)} />;
    wide = true;
  } else if (isIdRef(schema) || s.type === "string") {
    input = <input id={fieldId} type="text" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value || undefined)} />;
  } else {
    return null;
  }
  return (
    <div className={`field ${wide ? "wide" : ""}`}>
      <label htmlFor={fieldId}>{humanize(name)}{required && <span className="req" title="Required"> *</span>}</label>
      {input}
      {(schema.description ?? s.description) && name !== "id" && name !== "name" && <p className="help">{schema.description ?? s.description}</p>}
    </div>
  );
}

const SKIP = new Set(["outline_ft", "layers", "segments", "changes", "op"]);

/** A whole object's fields: required ones first, the rest under "More options". Nested objects become optional groups. */
export function ObjectForm({ schema, value, onChange, ctx, primary, hide, flat, middle }: {
  schema: Schema; value: Obj; onChange: (v: Obj) => void; ctx: Ctx; primary?: string[]; hide?: string[]; flat?: boolean; middle?: ReactNode;
}) {
  const s = resolve(schema);
  const props = Object.entries(s.properties ?? {}).filter(([k, sub]) => !SKIP.has(k) && !hide?.includes(k) && resolve(sub).const === undefined);
  const required = new Set(s.required ?? []);
  const set = (key: string, v: Json | undefined) => {
    const next = { ...value };
    if (v === undefined) delete next[key]; else next[key] = v;
    onChange(next);
  };
  const isGroup = (sub: Schema) => { const r = resolve(sub); return r.type === "object" && !!r.properties && !isQuantity(sub); };
  const isMain = (k: string) => required.has(k) || primary?.includes(k) || k === "name";
  const simple = props.filter(([, sub]) => !isGroup(sub));
  const groups = props.filter(([, sub]) => isGroup(sub));
  const main = simple.filter(([k]) => flat || isMain(k));
  const more = simple.filter(([k]) => !flat && !isMain(k));
  const moreSet = more.filter(([k]) => value[k] !== undefined).length + groups.filter(([k]) => value[k] !== undefined).length;
  const render = ([k, sub]: [string, Schema]) => <Field key={k} name={k} schema={sub} value={value[k]} onChange={(v) => set(k, v)} ctx={ctx} owner={value} required={required.has(k)} />;
  const renderGroup = ([k, sub]: [string, Schema]) => {
    const present = value[k] !== undefined;
    return (
      <fieldset key={k} className={`group ${present ? "on" : ""}`}>
        <legend>
          <label className="check"><input type="checkbox" checked={present} onChange={(e) => set(k, e.target.checked ? {} : undefined)} /> {humanize(k)}</label>
        </legend>
        {!present && <p className="help">{resolve(sub).description}</p>}
        {present && <ObjectForm schema={sub} value={(getIn(value, [k]) as Obj) ?? {}} onChange={(v) => set(k, v)} ctx={ctx} flat />}
      </fieldset>
    );
  };
  return (
    <div className="form">
      <div className="fields">{main.map(render)}</div>
      {middle}
      {flat && groups.map(renderGroup)}
      {!flat && (more.length > 0 || groups.length > 0) && (
        <details className="more" open={moreSet > 0}>
          <summary>More options{moreSet > 0 && <span className="count">{moreSet} set</span>}</summary>
          <div className="fields">{more.map(render)}</div>
          {groups.map(renderGroup)}
        </details>
      )}
    </div>
  );
}
