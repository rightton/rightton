import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import YAML from "yaml";
import { Field, ObjectForm, type Ctx } from "./components/Field";
import { GlazingPicker } from "./components/GlazingPicker";
import { LayerBuilder } from "./components/LayerBuilder";
import { RoomContents } from "./components/RoomContents";
import { ResultsView } from "./components/Results";
import { ScenarioEditor } from "./components/ScenarioEditor";
import { SectionEditor, type SectionProps } from "./components/SectionEditor";
import { engine } from "./engine";
import { fmt, itemSchema, num, pretty, resolve, schemaAt, setRootSchema, slug } from "./schemaUtil";
import { emptyHouse, getIn, list, renameId, useHouse } from "./state";
import type { CalcOutput, House, Json, Library, Obj, Ranges, Schema } from "./types";

type Page = "results" | "location" | "rooms" | "assemblies" | "surfaces" | "openings" | "air" | "hvac" | "scenarios" | "issues";
const PAGES: { key: Page; label: string }[] = [
  { key: "results", label: "Results" }, { key: "location", label: "Location" }, { key: "rooms", label: "Rooms" },
  { key: "assemblies", label: "Assemblies" }, { key: "surfaces", label: "Surfaces" }, { key: "openings", label: "Openings" },
  { key: "air", label: "Air & ducts" }, { key: "hvac", label: "HVAC" }, { key: "scenarios", label: "Scenarios" }, { key: "issues", label: "Check" },
];
const EXAMPLES = [
  { file: "nrel-base-house.rtn.json", label: "NREL base house (Denver, 2,700 ft²)" },
  { file: "old-house.rtn.yaml", label: "Fictional 1920s raised cottage (Houston)" },
  { file: "llm-written-brick-bungalow.rtn.yaml", label: "Fictional 1930s brick bungalow (Baltimore)" },
];

function parseFile(name: string, text: string): House {
  const data = /\.ya?ml$/i.test(name) ? YAML.parse(text) : JSON.parse(text);
  if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("This file does not hold a house (it should be an object with rooms, zones and so on).");
  return data as House;
}

function Tabs<T extends string>({ value, options, onChange }: { value: T; options: { key: T; label: string }[]; onChange: (v: T) => void }) {
  return <div className="seg tabs">{options.map((o) => <button key={o.key} className={value === o.key ? "on" : ""} onClick={() => onChange(o.key)}>{o.label}</button>)}</div>;
}

export function App() {
  const doc = useHouse();
  const { house } = doc;
  const [lib, setLib] = useState<Library | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [out, setOut] = useState<CalcOutput | null>(null);
  const [ranges, setRanges] = useState<Ranges | null>(null);
  const [busy, setBusy] = useState(true);
  const [page, setPage] = useState<Page>("results");
  const [sub, setSub] = useState<Record<string, string>>({ rooms: "rooms", air: "leakage", hvac: "systems" });
  const [notice, setNotice] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const epwInput = useRef<HTMLInputElement>(null);
  const run = useRef(0);

  useEffect(() => {
    engine.library().then((l) => { setRootSchema(l.schema); setLib(l); }).catch((e) => setEngineError(e.message));
  }, []);

  const loadExample = useCallback(async (file: string) => {
    const text = await (await fetch(`./examples/${file}`)).text();
    doc.load(parseFile(file, text), file.replace(/\.ya?ml$/, ".json"));
    setPage("results"); setMenu(false);
  }, [doc]);

  // First visit: open NREL's sample house, which the user edits or replaces.
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; if (!doc.hadStored) loadExample(EXAMPLES[0].file).catch(() => undefined); }
  }, [doc.hadStored, loadExample]);

  useEffect(() => {
    if (!lib) return;
    const id = ++run.current;
    setBusy(true);
    const timer = setTimeout(() => {
      engine.calculate(house).then((o) => {
        if (run.current !== id) return;
        setOut(o); setBusy(false); setRanges(null);
        // Input-confidence ranges take a few seconds (a recalculation per input), so they follow the main result.
        if (o.baseline) engine.sensitivity(house).then((r) => { if (run.current === id) setRanges(r); }).catch(() => undefined);
      })
        .catch((e) => { if (run.current === id) { setBusy(false); setNotice(`Calculation failed: ${e.message}`); } });
    }, 350);
    return () => clearTimeout(timer);
  }, [house, lib]);

  const ctx: Ctx | null = useMemo(() => lib && { house, lib, rename: (a, b) => doc.setHouse(renameId(house, a, b)) }, [house, lib, doc]);
  const errors = out?.issues.filter((i) => i.level === "error").length ?? 0;
  const warnings = out?.issues.filter((i) => i.level === "warning").length ?? 0;
  const projectName = (getIn(house, ["project", "name"]) as string) ?? "";

  const open = async (file: File) => {
    try { doc.load(parseFile(file.name, await file.text()), file.name.replace(/\.ya?ml$/i, ".json")); setPage("results"); setNotice(null); }
    catch (e) { setNotice(`Could not open ${file.name}: ${e instanceof Error ? e.message : e}`); }
  };
  const save = () => {
    const name = doc.fileName || `${slug(projectName || "house")}.rtn.json`;
    // A file saved by this app is written in the app's format version (same major version only: an older
    // 1.x file is also a valid file of the current 1.x version).
    const out: Obj = { ...house };
    const [ma, mi] = String(out.format_version ?? "").split(".").map(Number);
    const [cma, cmi] = (lib?.format_version ?? "").split(".").map(Number);
    if (lib && ma === cma && mi < cmi) out.format_version = lib.format_version;
    const blob = new Blob([JSON.stringify(out, null, 2) + "\n"], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name.endsWith(".rtn.json") ? name : name.replace(/(\.json)?$/, ".rtn.json");
    a.click(); URL.revokeObjectURL(a.href); doc.markSaved();
  };
  const importEpw = async (file: File) => {
    try {
      const r = await engine.epw(await file.text());
      const location = { ...((house.location as Obj) ?? {}), weather_station_name: r.weather_station_name, design_conditions: r.design_conditions as Json };
      delete (location as Obj).weather_station_id;
      doc.update(["location"], location);
      setNotice(`Design conditions read from ${file.name} (${r.weather_station_name}).`);
    } catch (e) { setNotice(`Could not read ${file.name}: ${e instanceof Error ? e.message : e}`); }
  };

  const status = engineError ? { cls: "bad", text: "Engine failed to load" } : !lib ? { cls: "busy", text: "Loading engine…" }
    : busy ? { cls: "busy", text: "Calculating…" } : errors ? { cls: "bad", text: `${errors} problem${errors === 1 ? "" : "s"} to fix` }
    : { cls: "ok", text: warnings ? `Up to date · ${warnings} note${warnings === 1 ? "" : "s"}` : "Up to date" };
  const b = out?.baseline?.building;

  return (
    <div className="app">
      <header className="top">
        <div className="brand"><span className="logo" aria-hidden="true">R</span><span className="brand-name">RightTon</span></div>
        <input className="project-name" aria-label="Project name" value={projectName} placeholder="Project name" onChange={(e) => doc.update(["project", "name"], e.target.value || undefined)} />
        <div className="top-actions">
          <button className="btn ghost icon-btn" onClick={doc.undo} disabled={!doc.past.length} aria-label="Undo" title="Undo">↶</button>
          <button className="btn ghost icon-btn" onClick={doc.redo} disabled={!doc.future.length} aria-label="Redo" title="Redo">↷</button>
          <div className="menu-wrap">
            <button className="btn ghost" onClick={() => setMenu(!menu)} aria-expanded={menu}>File ▾</button>
            {menu && (
              <div className="menu" role="menu" onMouseLeave={() => setMenu(false)}>
                <button role="menuitem" onClick={() => { setMenu(false); fileInput.current?.click(); }}>Open a house file…</button>
                <button role="menuitem" onClick={() => { setMenu(false); save(); }}>Save house file (.rtn.json)</button>
                <button role="menuitem" onClick={() => { setMenu(false); doc.load(emptyHouse(), ""); setPage("rooms"); }}>New empty house</button>
                <div className="menu-label">Examples</div>
                {EXAMPLES.map((e) => <button role="menuitem" key={e.file} onClick={() => loadExample(e.file)}>{e.label}</button>)}
              </div>
            )}
          </div>
          <button className="btn primary" onClick={save}>Save{doc.dirty ? " •" : ""}</button>
        </div>
        <input ref={fileInput} type="file" accept=".json,.yaml,.yml" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) open(f); e.target.value = ""; }} />
        <input ref={epwInput} type="file" accept=".epw" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) importEpw(f); e.target.value = ""; }} />
      </header>
      <div className="strip">
        <span className={`status ${status.cls}`}><span className="dot" />{status.text}</span>
        {b && <span className="strip-loads"><span className="heat-text">Heating {fmt(b.heating_btuh)}</span><span className="cool-text">Cooling {fmt(b.cooling_total_btuh)} Btu/h · {fmt(b.cooling_tons, 2)} tons</span></span>}
      </div>
      <nav className="nav" aria-label="Sections">
        {PAGES.map((p) => (
          <button key={p.key} className={page === p.key ? "on" : ""} aria-current={page === p.key ? "page" : undefined} onClick={() => setPage(p.key)}>
            {p.label}{p.key === "issues" && errors + warnings > 0 && <span className={`badge ${errors ? "bad" : ""}`}>{errors + warnings}</span>}
          </button>
        ))}
      </nav>
      <main className="main">
        {notice && <div className="notice" role="status">{notice}<button className="icon" aria-label="Dismiss" onClick={() => setNotice(null)}>×</button></div>}
        {engineError && <div className="card"><h3>The calculation engine could not start</h3><p>{engineError}</p><p className="muted">RightTon runs its calculations in your browser using WebAssembly. Try a current version of Chrome, Edge, Firefox or Safari.</p></div>}
        {page === "results" && <ResultsView out={out} busy={busy || !lib} ranges={ranges} />}
        {ctx && lib && page !== "results" && <Editors page={page} ctx={ctx} lib={lib} out={out} sub={sub} setSub={(k, v) => setSub({ ...sub, [k]: v })} doc={doc} pickEpw={() => epwInput.current?.click()} go={setPage} />}
        <footer className="foot">
          <p><strong>A homeowner planning estimate, not a design for permits or rebates.</strong> Where those require an ACCA-approved load calculation, a contractor must provide one. RightTon is a residential heating and cooling load calculator based on published open methods; its calculation is checked against NREL’s OpenStudio-HPXML.</p>
          <p>Your house data stays on this device: it is kept in this browser and in the files you save. Nothing is uploaded. Format {lib?.format_version ?? ""} · <a href="https://github.com/rightton/rightton">Source and documentation</a></p>
        </footer>
      </main>
    </div>
  );
}

type Doc = ReturnType<typeof useHouse>;

function Editors({ page, ctx, lib, out, sub, setSub, doc, pickEpw, go }: {
  page: Page; ctx: Ctx; lib: Library; out: CalcOutput | null; sub: Record<string, string>; setSub: (k: string, v: string) => void; doc: Doc; pickEpw: () => void; go: (p: Page) => void;
}) {
  const house = ctx.house;
  const root = resolve(lib.schema);
  const prop = (...path: string[]): Schema => schemaAt(path);
  const first = (path: string[], pred?: (o: Obj) => boolean) => (list(house, path).find((o) => !pred || pred(o))?.id as string | undefined);
  const nameOf = (id: Json | undefined) => {
    if (typeof id !== "string") return "";
    for (const p of [["rooms"], ["spaces"], ["zones"], ["surfaces"], ["assemblies"], ["hvac", "systems"]]) { const f = list(house, p).find((o) => o.id === id); if (f) return (f.name as string) || id; }
    return pretty(id);
  };
  const surf = new Map<string, { h: number; c: number }>();
  for (const s of out?.baseline?.surfaces ?? []) { const e = surf.get(s.id) ?? { h: 0, c: 0 }; e.h += s.heating_btuh; e.c += s.cooling_btuh; surf.set(s.id, e); }
  const loadBadge = (item: Obj): ReactNode => { const e = surf.get(item.id as string); return e ? <><span className="heat-text">{fmt(e.h)}</span><span className="cool-text">{fmt(e.c)}</span></> : null; };
  const roomBadge = (item: Obj): ReactNode => { const r = out?.baseline?.rooms.find((x) => x.id === item.id); return r ? <><span className="heat-text">{fmt(r.heating_btuh)}</span><span className="cool-text">{fmt(r.cooling_sensible_btuh)}</span></> : null; };
  const common = { ctx, onEdit: doc.setHouse };
  const section = (p: Omit<SectionProps, "ctx" | "onEdit">) => <SectionEditor key={p.path.join("/")} {...common} {...p} />;
  const area = (o: Obj) => { const a = num(o.area_ft2) ?? (num(o.width_ft) !== undefined && num(o.height_ft) !== undefined ? num(o.width_ft)! * num(o.height_ft)! : undefined); return a === undefined ? "" : `${fmt(a * ((o.count as number) ?? 1))} ft²`; };
  const legend = <p className="legend"><span className="heat-text">heating</span> / <span className="cool-text">cooling</span> load in Btu/h</p>;

  // New-item templates shared by the Surfaces page and each room's own surfaces.
  const surfaceTemplate = (type: string | undefined, id: string, inside: string): Obj => {
    const want = ({ wall: "wall", rim_joist: "wall", roof: "roof", ceiling: "ceiling", floor: "floor" } as Record<string, string>)[type ?? ""];
    const assembly = first(["assemblies"], (a) => a.type === want) ?? "";
    const base: Obj = { id, type: type ?? "wall", inside, area_ft2: 100 };
    if (type === "wall" || type === "rim_joist") return { ...base, assembly, azimuth_deg: 180 };
    if (type === "roof") return { ...base, assembly, pitch_rise_per_12: 6 };
    if (type === "ceiling") return { ...base, outside: first(["spaces"], (s) => String(s.type).includes("attic")) ?? "outdoors", assembly };
    if (type === "floor") return { ...base, outside: first(["spaces"], (s) => /crawl|basement|garage/.test(String(s.type))) ?? "outdoors", assembly };
    if (type === "foundation_wall") return { ...base, height_ft: 8, depth_below_grade_ft: 6 };
    return { ...base, exposed_perimeter_ft: 40 };
  };
  const walls = (o: Obj) => ["wall", "foundation_wall"].includes(o.type as string);
  const openingTemplate = (type: string | undefined, id: string, surface: string): Obj => type === "door" ? { id, type: "door", surface, width_ft: 3, height_ft: 6.67, r_value_hr_ft2_f_btu: 4.4 }
    : type === "skylight" ? { id, type: "skylight", surface, area_ft2: 8, u_factor_btu_hr_ft2_f: 0.6, shgc: 0.4 }
    : { id, type: "window", surface, count: 1, width_ft: 3, height_ft: 5, glazing: "double_clear_wood" };

  if (page === "location") {
    const loc = (house.location as Obj) ?? {};
    const setLoc = (v: Obj) => doc.update(["location"], v);
    const dcSchema = prop("location", "design_conditions");
    return (
      <div className="stack">
        <div className="card">
          <h2>Location</h2>
          <p className="muted">RightTon needs the outdoor design conditions for your area. Pick the nearest weather station, load an EPW weather file for a closer one, or type the conditions in. There is no address field: the nearest station is all it needs.</p>
          <div className="fields">
            <Field name="weather_station_id" schema={resolve(root.properties!.location).properties!.weather_station_id} value={loc.weather_station_id} ctx={ctx}
              onChange={(v) => { const n = { ...loc }; if (v === undefined) delete n.weather_station_id; else { n.weather_station_id = v; n.weather_station_name = lib.stations.find((s) => s.id === v)?.name ?? ""; } setLoc(n); }} />
            <div className="field"><label>Another location</label><button className="btn" onClick={pickEpw}>Load an EPW weather file…</button>
              <p className="help">Free EPW files for thousands of stations are published at climate.onebuilding.org. The file is read in your browser; only the design summary is kept in the house file.</p></div>
          </div>
        </div>
        <div className="card">
          <h3>Design conditions</h3>
          <p className="muted">Leave blank to use the weather station’s values and RightTon’s defaults. Anything entered here overrides them.</p>
          <ObjectForm schema={dcSchema} value={(loc.design_conditions as Obj) ?? {}} ctx={ctx} primary={["heating_outdoor_temp_f", "cooling_outdoor_temp_f", "daily_temp_range", "humidity_difference_gr_lb", "latitude_deg", "heating_setpoint_f", "cooling_setpoint_f"]}
            onChange={(v) => { const n = { ...loc }; if (Object.keys(v).length) n.design_conditions = v; else delete n.design_conditions; setLoc(n); }} />
        </div>
      </div>
    );
  }

  if (page === "rooms") {
    return (
      <div className="stack">
        <Tabs value={sub.rooms} onChange={(v) => setSub("rooms", v)} options={[{ key: "rooms", label: "Rooms" }, { key: "zones", label: "Zones" }, { key: "spaces", label: "Attics, crawlspaces, porches" }]} />
        {sub.rooms === "rooms" && <>{legend}{section({ title: "Rooms", singular: "room", path: ["rooms"], schema: root.properties!.rooms, badge: roomBadge,
          intro: "Conditioned, lived-in rooms. Each has its own floor area and ceiling height.",
          summary: (r) => `${fmt(num(r.floor_area_ft2))} ft² · ${num(r.ceiling_height_ft) ?? 8} ft ceiling · ${nameOf(r.zone)}`, primary: ["ceiling_height_ft"],
          extra: (r) => <RoomContents room={r} ctx={ctx} lib={lib} onHouse={doc.setHouse} surfacesSchema={root.properties!.surfaces} openingsSchema={root.properties!.openings}
            surfaceTemplate={surfaceTemplate} openingTemplate={openingTemplate} nameOf={nameOf} badge={loadBadge} />,
          newItem: (_t, id) => ({ id, name: "New room", zone: first(["zones"]) ?? "", floor_area_ft2: 150 }) })}</>}
        {sub.rooms === "zones" && section({ title: "Zones", singular: "zone", path: ["zones"], schema: root.properties!.zones,
          intro: "A zone is a group of rooms on one thermostat. Most houses have one; add another for an upstairs with its own system.",
          summary: (z) => `${list(house, ["rooms"]).filter((r) => r.zone === z.id).length} room(s)`, newItem: (_t, id) => ({ id, name: "New zone" }) })}
        {sub.rooms === "spaces" && section({ title: "Spaces", singular: "space", path: ["spaces"], schema: root.properties!.spaces,
          intro: "Places that are not lived-in rooms but that walls, ceilings, floors or ducts border: attics, crawlspaces, unconditioned basements, garages, open porches, and sealed (conditioned) attics.",
          summary: (s) => pretty((s.type as string) ?? ""), primary: ["type", "zone", "volume_ft3"], newItem: (_t, id) => ({ id, name: "Attic", type: "vented_attic" }) })}
      </div>
    );
  }

  if (page === "assemblies") {
    return section({ title: "Assemblies", singular: "assembly", path: ["assemblies"], schema: root.properties!.assemblies,
      intro: "Wall, roof, ceiling and floor constructions. Define each once, layer by layer, and use it on any number of surfaces.",
      summary: (a) => `${pretty((a.type as string) ?? "")} · ${Array.isArray(a.layers) ? `${a.layers.length} layer(s)` : num(a.r_value_hr_ft2_f_btu) !== undefined ? `R-${num(a.r_value_hr_ft2_f_btu)}` : "no R-value yet"} · used by ${list(house, ["surfaces"]).filter((s) => s.assembly === a.id).length}`,
      primary: ["type"],
      hide: (a) => ["r_value_hr_ft2_f_btu", "framing_frac", "framing", ...(a.type === "wall" ? [] : ["construction", "cladding", "solar_absorptance_frac"]),
        ...(a.type === "roof" ? [] : ["roofing", "roof_color", "radiant_barrier"])],
      newItem: (_t, id) => ({ id, name: "New assembly", type: "wall", layers: [] }),
      extra: (a, setA) => (<>
        {!Array.isArray(a.layers) && <div className="fields"><Field name="r_value_hr_ft2_f_btu" schema={itemSchema(root.properties!.assemblies).properties!.r_value_hr_ft2_f_btu} value={a.r_value_hr_ft2_f_btu} ctx={ctx} owner={a} required
          onChange={(v) => { const n = { ...a }; if (v === undefined) delete n.r_value_hr_ft2_f_btu; else n.r_value_hr_ft2_f_btu = v; setA(n); }} /></div>}
        <LayerBuilder assembly={a} setAssembly={setA} lib={lib} />
        </>) });
  }

  if (page === "surfaces") {
    return <>{legend}{section({ title: "Surfaces", singular: "surface", path: ["surfaces"], schema: root.properties!.surfaces, badge: loadBadge,
      intro: "Walls, roofs, ceilings, floors and slabs. Each belongs to a room (or to an attic or crawlspace) and says what is on its other side.",
      groupBy: (s) => nameOf(s.inside) || "No room",
      summary: (s) => `${pretty(s.type as string)} · ${fmt(num(s.area_ft2))} ft²${s.outside ? ` · to ${nameOf(s.outside)}` : ""}${s.assembly ? ` · ${nameOf(s.assembly)}` : ""}`,
      primary: ["outside", "azimuth_deg", "thickness_in", "material", "pitch_rise_per_12"], newItem: (t, id) => surfaceTemplate(t, id, t === "roof" ? first(["spaces"], (s) => String(s.type).includes("attic")) ?? first(["rooms"]) ?? "" : first(["rooms"]) ?? "") })}</>;
  }

  if (page === "openings") {
    const glazingName = (id: Json | undefined) => (list(house, ["glazings"]).find((g) => g.id === id)?.name as string) || pretty(String(id));
    const tab = sub.openings ?? "openings";
    return (
      <div className="stack">
        <Tabs value={tab} onChange={(v) => setSub("openings", v)} options={[{ key: "openings", label: "Windows, doors, skylights" }, { key: "glazings", label: `My glazings (${list(house, ["glazings"]).length})` }]} />
        {tab === "openings" && <>{legend}{section({ title: "Openings", singular: "opening", path: ["openings"], schema: root.properties!.openings, badge: loadBadge,
          intro: "Windows, doors and skylights. Enter one typical unit and how many there are.",
          groupBy: (o) => nameOf(o.surface) || "No surface",
          summary: (o) => `${(o.count as number) > 1 ? `${o.count} × ` : ""}${pretty(o.type as string)} · ${area(o)}${o.glazing ? ` · ${glazingName(o.glazing)}` : o.type === "window" && num(o.u_factor_btu_hr_ft2_f) !== undefined ? ` · U ${num(o.u_factor_btu_hr_ft2_f)} / SHGC ${num(o.shgc)}` : ""}${o.storm_window && o.storm_window !== "none" ? " + storm" : ""}`,
          primary: ["count", "width_ft", "height_ft", "storm_window", "azimuth_deg"],
          hide: (o) => (o.type === "window" ? ["glazing", "u_factor_btu_hr_ft2_f", "shgc"] : []),
          extra: (o) => (o.type === "window" ? <GlazingPicker win={o} house={house} lib={lib} onHouse={doc.setHouse} /> : null),
          newItem: (type, id): Obj => openingTemplate(type, id, (type === "skylight" ? first(["surfaces"], (s) => s.type === "roof") : first(["surfaces"], walls)) ?? "") })}</>}
        {tab === "glazings" && section({ title: "My glazings", singular: "glazing", path: ["glazings"], schema: root.properties!.glazings,
          intro: "Window glass described once from an NFRC label (whole-window U-factor and SHGC) and used by any number of windows.",
          summary: (g) => `U ${num(g.u_factor_btu_hr_ft2_f) ?? "?"} · SHGC ${num(g.shgc) ?? "?"} · used by ${list(house, ["openings"]).filter((o) => o.glazing === g.id).length}`,
          primary: ["u_factor_btu_hr_ft2_f", "shgc", "source"],
          newItem: (_t, id): Obj => ({ id, name: "New glazing", u_factor_btu_hr_ft2_f: 0.3, shgc: 0.3, source: "NFRC label" }) })}
      </div>
    );
  }

  if (page === "air") {
    const air = (house.air as Obj) ?? {};
    const segSchema = resolve(itemSchema(prop("air", "ducts")).properties!.segments);
    return (
      <div className="stack">
        <Tabs value={sub.air} onChange={(v) => setSub("air", v)} options={[{ key: "leakage", label: "Air leakage" }, { key: "ventilation", label: "Ventilation" }, { key: "ducts", label: "Ducts" }]} />
        {sub.air === "leakage" && (
          <div className="card">
            <h2>Air leakage</h2>
            <p className="muted">If the house has had a blower-door test, enter the result (ACH50 or CFM50) and mark it measured. RightTon converts it to airflow on the design winter and summer days and shows the conversion on the Results page.</p>
            <ObjectForm schema={prop("air", "infiltration")} value={(air.infiltration as Obj) ?? {}} ctx={ctx}
              primary={["air_changes_per_hr_at_50pa", "airflow_cfm_at_50pa", "leakiness", "stories_above_grade", "shielding_class"]}
              onChange={(v) => doc.update(["air", "infiltration"], v)} />
          </div>
        )}
        {sub.air === "ventilation" && section({ title: "Ventilation", singular: "fan", path: ["air", "ventilation"], schema: prop("air", "ventilation"),
          intro: "Fans that ventilate the whole house on a schedule (not bath or kitchen spot fans).",
          summary: (v) => `${pretty(v.type as string)} · ${fmt(num(v.airflow_cfm))} cfm`, newItem: (_t, id) => ({ id, name: "Ventilation fan", type: "exhaust", airflow_cfm: 50 }) })}
        {sub.air === "ducts" && section({ title: "Ducts", singular: "duct system", path: ["air", "ducts"], schema: prop("air", "ducts"),
          intro: "Where the ducts run and how leaky they are. Ducts inside rooms or a sealed attic lose nothing to outside.",
          summary: (d) => `${nameOf(d.system)} · ${(d.segments as Json[] | undefined)?.length ?? 0} segment(s)`,
          primary: ["supply_leakage_cfm_at_25pa", "return_leakage_cfm_at_25pa"],
          newItem: (_t, id) => ({ id, system: first(["hvac", "systems"]) ?? "", segments: [{ type: "supply", location: first(["spaces"]) ?? "outdoors", share_of_ducts_frac: 1, insulation_r_value_hr_ft2_f_btu: 6 }, { type: "return", location: first(["spaces"]) ?? "outdoors", share_of_ducts_frac: 1, insulation_r_value_hr_ft2_f_btu: 6 }] }),
          extra: (d, setD) => {
            const segs = (Array.isArray(d.segments) ? d.segments : []) as Obj[];
            return (
              <div className="sublist"><h4>Duct segments</h4>
                {segs.map((seg, i) => (
                  <div key={i} className="subitem"><div className="subitem-head"><strong>{pretty((seg.type as string) ?? "segment")} · {nameOf(seg.location)}</strong>
                    <button className="icon danger" aria-label="Remove segment" onClick={() => setD({ ...d, segments: segs.filter((_, j) => j !== i) as Json })}>×</button></div>
                    <ObjectForm schema={segSchema.items!} value={seg} ctx={ctx} flat onChange={(v) => setD({ ...d, segments: segs.map((s, j) => (j === i ? v : s)) as Json })} /></div>
                ))}
                <button className="btn small" onClick={() => setD({ ...d, segments: [...segs, { type: "supply", location: "outdoors", share_of_ducts_frac: 0.5 }] as Json })}>+ Add segment</button>
              </div>
            );
          } })}
      </div>
    );
  }

  if (page === "hvac") {
    return (
      <div className="stack">
        <Tabs value={sub.hvac} onChange={(v) => setSub("hvac", v)} options={[{ key: "systems", label: "Systems and registers" }, { key: "equipment", label: "Heat-producing equipment" }]} />
        {sub.hvac === "systems" && section({ title: "Systems", singular: "system", path: ["hvac", "systems"], schema: prop("hvac", "systems"),
          intro: "What heats and cools each zone and which rooms have registers. Sizes are not entered: the calculation tells you what is needed.",
          summary: (s) => `${nameOf(s.zone)} · ${pretty((s.heating as string) ?? "no heating")} / ${pretty((s.cooling as string) ?? "no cooling")}`,
          primary: ["heating", "cooling", "supply_registers", "returns"],
          newItem: (_t, id) => ({ id, name: "Heating and cooling system", zone: first(["zones"]) ?? "", heating: "furnace", cooling: "central_ac" }) })}
        {sub.hvac === "equipment" && section({ title: "Equipment", singular: "item", path: ["equipment"], schema: root.properties!.equipment,
          intro: "Equipment that gives off heat while the air conditioner runs, such as a dehumidifier. Its heat is a real cooling load and is shown on its own line.",
          summary: (e) => `${pretty(e.type as string)} · ${fmt(num(e.sensible_heat_btu_hr))} Btu/h · ${nameOf(e.room)}`, primary: ["latent_heat_btu_hr"],
          newItem: (_t, id) => ({ id, name: "Dehumidifier", type: "dehumidifier", room: first(["rooms"]) ?? "", sensible_heat_btu_hr: 1500 }) })}
      </div>
    );
  }

  if (page === "scenarios") {
    return section({ title: "Scenarios", singular: "scenario", path: ["scenarios"], schema: root.properties!.scenarios,
      intro: "What-if versions of the house: air sealing, insulation, new windows. Each is a short list of changes; results for all of them are compared on the Results page.",
      summary: (s) => { const r = out?.scenarios.find((x) => x.id === s.id); const base = out?.baseline; return `${(s.changes as Json[] | undefined)?.length ?? 0} change(s)${r?.result && base ? ` · heating ${fmt(r.result.building.heating_btuh - base.building.heating_btuh)} · cooling ${fmt(r.result.building.cooling_total_btuh - base.building.cooling_total_btuh)} Btu/h` : r?.error ? " · cannot be calculated" : ""}`; },
      primary: ["description", "cost_usd", "includes"], newItem: (_t, id) => ({ id, name: "New scenario", changes: [] }),
      extra: (s, setS) => <ScenarioEditor scenario={s} setScenario={setS} house={house} /> });
  }

  // page === "issues"
  const issues = out?.issues ?? [];
  return (
    <div className="card">
      <h2>Check</h2>
      <p className="muted">The same checks as <span className="mono">python -m rightton.validate</span>: the file format, and whether everything fits together.</p>
      {!out && <p className="muted">Checking…</p>}
      {out && issues.length === 0 && <p className="ok-text">No problems found. This is a valid RightTon house file.</p>}
      <ul className="issues">{issues.map((i, n) => <li key={n} className={i.level}><span className={`pill ${i.level}`}>{i.level === "error" ? "must fix" : "note"}</span>{i.where && <strong>{i.where}</strong>} {i.message}</li>)}</ul>
      {issues.length > 0 && <p className="help">Go to <button className="link" onClick={() => go("surfaces")}>Surfaces</button>, <button className="link" onClick={() => go("openings")}>Openings</button> or the section named in each message to fix it.</p>}
      <details><summary>House file (JSON)</summary><pre className="json">{JSON.stringify(house, null, 2)}</pre></details>
    </div>
  );
}
