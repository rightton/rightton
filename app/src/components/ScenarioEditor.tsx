// Editor for one scenario's list of changes (set / add / remove against the baseline).
import { list } from "../state";
import type { House, Json, Obj } from "../types";

function leafPaths(house: House): string[] {
  const out: string[] = [];
  const walk = (node: Json, path: string, depth: number) => {
    if (out.length > 1500 || depth > 6) return;
    if (Array.isArray(node)) {
      node.forEach((v, i) => { if (v && typeof v === "object" && !Array.isArray(v)) walk(v, `${path}/${typeof v.id === "string" ? v.id : i}`, depth + 1); });
    } else if (node && typeof node === "object") {
      if ("value" in node && Object.keys(node).every((k) => ["value", "source", "confidence"].includes(k))) { out.push(path); return; }
      for (const [k, v] of Object.entries(node)) { if (k === "id" || k === "outline_ft") continue; walk(v, path ? `${path}/${k}` : k, depth + 1); }
    } else if (path) out.push(path);
  };
  for (const key of ["assemblies", "rooms", "spaces", "surfaces", "openings", "air", "hvac", "equipment", "zones", "location"]) if (house[key] !== undefined) walk(house[key], key, 0);
  return out;
}

const show = (v: Json | undefined) => (v === undefined ? "" : typeof v === "string" ? v : JSON.stringify(v));
const parse = (text: string): Json => { try { return JSON.parse(text); } catch { return text; } };

export function ScenarioEditor({ scenario, setScenario, house }: { scenario: Obj; setScenario: (s: Obj) => void; house: House }) {
  const changes = (Array.isArray(scenario.changes) ? scenario.changes : []) as Obj[];
  const write = (next: Obj[]) => setScenario({ ...scenario, changes: next as Json });
  const set = (i: number, c: Obj) => write(changes.map((x, j) => (j === i ? c : x)));
  const paths = leafPaths(house);
  const sections = ["openings", "surfaces", "assemblies", "rooms", "spaces", "equipment", "air/ventilation", "air/ducts", "hvac/systems",
    ...list(house, ["assemblies"]).map((a) => `assemblies/${a.id}/layers`)];
  const ach = paths.find((p) => p.startsWith("air/infiltration/air_changes") || p.startsWith("air/infiltration/airflow_cfm"));
  return (
    <div className="changes">
      <h4>Changes against the baseline</h4>
      <p className="help">A path is section/id/field, for example <span className="mono">surfaces/north-wall/assembly</span> or <span className="mono">air/infiltration/air_changes_per_hr_at_50pa</span>. Start typing to pick from this house’s fields. Values may be a number, text, or JSON.</p>
      <datalist id="paths">{paths.map((p) => <option key={p} value={p} />)}</datalist>
      <datalist id="sections">{sections.map((p) => <option key={p} value={p} />)}</datalist>
      <ol className="change-list">
        {changes.map((c, i) => (
          <li key={i} className="change">
            <select aria-label="Kind of change" value={(c.op as string) ?? "set"} onChange={(e) => set(i, e.target.value === "add" ? { op: "add", section: "openings", item: {} } : e.target.value === "remove" ? { op: "remove", path: (c.path as string) ?? "" } : { op: "set", path: (c.path as string) ?? "", value: "" })}>
              <option value="set">Set</option><option value="add">Add</option><option value="remove">Remove</option>
            </select>
            {c.op === "add" ? (
              <>
                <input aria-label="Section" list="sections" className="mono" placeholder="section, e.g. openings" value={(c.section as string) ?? ""} onChange={(e) => set(i, { ...c, section: e.target.value })} />
                <textarea aria-label="New item as JSON" className="mono" rows={3} placeholder='{"id": "new-window", "type": "window", …}' defaultValue={JSON.stringify(c.item ?? {}, null, 1)}
                  onBlur={(e) => { const v = parse(e.target.value); if (v && typeof v === "object" && !Array.isArray(v)) set(i, { ...c, item: v }); }} />
              </>
            ) : (
              <>
                <input aria-label="Path" list="paths" className="mono" placeholder="section/id/field" value={(c.path as string) ?? ""} onChange={(e) => set(i, { ...c, path: e.target.value })} />
                {c.op !== "remove" && <input aria-label="New value" className="mono" placeholder="new value" defaultValue={show(c.value)} key={`${i}-${show(c.value)}`}
                  onBlur={(e) => set(i, { ...c, value: parse(e.target.value) })} />}
              </>
            )}
            <button className="icon danger" aria-label="Remove this change" onClick={() => write(changes.filter((_, j) => j !== i))}>×</button>
          </li>
        ))}
      </ol>
      <div className="add-row">
        <button className="btn small" onClick={() => write([...changes, { op: "set", path: "", value: "" }])}>+ Change a value</button>
        {ach && <button className="btn small" onClick={() => write([...changes, { op: "set", path: ach, value: "" }])}>+ Air sealing (new blower-door number)</button>}
        <button className="btn small" onClick={() => write([...changes, { op: "add", section: "openings", item: {} }])}>+ Add an item</button>
        <button className="btn small" onClick={() => write([...changes, { op: "remove", path: "" }])}>+ Remove an item</button>
      </div>
    </div>
  );
}
