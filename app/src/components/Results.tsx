// Results: headline loads, ranked component breakdown, room-by-room view, sizing
// guidance, input confidence. Every number shown comes from the Python core.
import { useState } from "react";
import { fmt, pretty } from "../schemaUtil";
import type { CalcOutput, Component, Loads, Result } from "../types";

type Mode = "heating" | "sensible" | "latent";
const MODES: { key: Mode; label: string; unit: string }[] = [
  { key: "heating", label: "Heating", unit: "Btu/h" }, { key: "sensible", label: "Cooling: temperature", unit: "Btu/h" },
  { key: "latent", label: "Cooling: moisture", unit: "Btu/h" }];
const comps = (l: Loads, m: Mode): Component[] => (m === "heating" ? l.heating_components : m === "sensible" ? l.cooling_sensible_components : l.cooling_latent_components);
const total = (l: Loads, m: Mode) => (m === "heating" ? l.heating_btuh : m === "sensible" ? l.cooling_sensible_btuh : l.cooling_latent_btuh);

export function Bars({ items, compare, compareLabel }: { items: Component[]; compare?: Component[]; compareLabel?: string }) {
  const keys = Array.from(new Set([...items.map((c) => c.key), ...(compare ?? []).map((c) => c.key)]));
  const rows = keys.map((k) => ({ key: k, label: (items.find((c) => c.key === k) ?? compare!.find((c) => c.key === k)!).label,
    a: items.find((c) => c.key === k)?.btuh ?? 0, b: compare?.find((c) => c.key === k)?.btuh }))
    .sort((x, y) => Math.abs(y.a) - Math.abs(x.a));
  const max = Math.max(1, ...rows.flatMap((r) => [Math.abs(r.a), Math.abs(r.b ?? 0)]));
  const sum = rows.reduce((acc, r) => acc + Math.max(r.a, 0), 0) || 1;
  if (!rows.length) return <p className="muted">Nothing to show.</p>;
  return (
    <ul className="bars">
      {rows.map((r) => (
        <li key={r.key}>
          <div className="bar-label"><span>{r.label}</span>
            <span className="bar-value">{fmt(r.a)}{r.b !== undefined && <span className={`delta ${r.b - r.a < 0 ? "good" : r.b - r.a > 0 ? "bad" : ""}`}> → {fmt(r.b)}</span>}
              {r.b === undefined && r.a > 0 && <span className="pct">{fmt((r.a / sum) * 100)}%</span>}</span></div>
          <div className="bar-track"><div className={`bar ${r.a < 0 ? "neg" : ""}`} style={{ width: `${(Math.abs(r.a) / max) * 100}%` }} /></div>
          {r.b !== undefined && <div className="bar-track thin" title={compareLabel}><div className={`bar alt ${r.b < 0 ? "neg" : ""}`} style={{ width: `${(Math.abs(r.b) / max) * 100}%` }} /></div>}
        </li>
      ))}
    </ul>
  );
}

function Headline({ r, base }: { r: Result; base?: Result }) {
  const b = r.building;
  const d = (now: number, was?: number) => was === undefined || Math.abs(now - was) < 0.5 ? null
    : <span className={`delta ${now < was ? "good" : "bad"}`}>{now < was ? "−" : "+"}{fmt(Math.abs(now - was))} ({fmt(Math.abs((now - was) / (was || 1)) * 100)}%)</span>;
  return (
    <div className="headline">
      <div className="stat heat"><span className="stat-label">Heating load</span><span className="stat-value">{fmt(b.heating_btuh)}</span><span className="stat-unit">Btu/h</span>{d(b.heating_btuh, base?.building.heating_btuh)}</div>
      <div className="stat cool"><span className="stat-label">Cooling: temperature (sensible)</span><span className="stat-value">{fmt(b.cooling_sensible_btuh)}</span><span className="stat-unit">Btu/h</span>{d(b.cooling_sensible_btuh, base?.building.cooling_sensible_btuh)}</div>
      <div className="stat wet"><span className="stat-label">Cooling: moisture (latent)</span><span className="stat-value">{fmt(b.cooling_latent_btuh)}</span><span className="stat-unit">Btu/h</span>{d(b.cooling_latent_btuh, base?.building.cooling_latent_btuh)}</div>
      <div className="stat"><span className="stat-label">Total cooling</span><span className="stat-value">{fmt(b.cooling_tons, 2)}</span><span className="stat-unit">tons ({fmt(b.cooling_total_btuh)} Btu/h)</span>
        <span className="stat-note">{fmt(b.sensible_heat_ratio * 100)}% of it is temperature, {fmt((1 - b.sensible_heat_ratio) * 100)}% moisture</span></div>
    </div>
  );
}

function Rooms({ r }: { r: Result }) {
  const [open, setOpen] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("heating");
  return (
    <div className="card">
      <h3>Room by room</h3>
      <p className="muted">Each room’s share of the load. “Own peak” is the room at its own worst hour, which matters when a room’s windows all face one way.</p>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Room</th><th className="n">Heating</th><th className="n">Cooling, temp.</th><th className="n">Cooling, moisture</th><th className="n">Own peak (temp.)</th><th className="n">Share of air leakage</th></tr></thead>
          <tbody>
            {r.rooms.map((room) => (
              <tr key={room.id} className={open === room.id ? "selected" : ""} onClick={() => setOpen(open === room.id ? null : room.id)} tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && setOpen(open === room.id ? null : room.id)}>
                <td><span className="caret">{open === room.id ? "▾" : "▸"}</span> {room.name}</td>
                <td className="n">{fmt(room.heating_btuh)}</td><td className="n">{fmt(room.cooling_sensible_btuh)}</td><td className="n">{fmt(room.cooling_latent_btuh)}</td>
                <td className="n">{fmt(room.peak_cooling_sensible_btuh)}</td><td className="n">{fmt(room.infiltration_share * 100)}%</td>
              </tr>
            ))}
          </tbody>
          <tfoot><tr><td>Whole house</td><td className="n">{fmt(r.building.heating_btuh)}</td><td className="n">{fmt(r.building.cooling_sensible_btuh)}</td><td className="n">{fmt(r.building.cooling_latent_btuh)}</td><td /><td /></tr></tfoot>
        </table>
      </div>
      {open && (() => {
        const room = r.rooms.find((x) => x.id === open)!;
        const surfaces = r.surfaces.filter((s) => s.room === open).sort((a, b) => (mode === "heating" ? b.heating_btuh - a.heating_btuh : b.cooling_btuh - a.cooling_btuh));
        return (
          <div className="room-detail">
            <div className="room-detail-head"><h4>{room.name}</h4>
              <div className="seg">{MODES.map((m) => <button key={m.key} className={mode === m.key ? "on" : ""} onClick={() => setMode(m.key)}>{m.label}</button>)}</div></div>
            <div className="two">
              <div><Bars items={comps(room, mode)} /></div>
              {mode !== "latent" && <div className="table-wrap"><table className="data compact">
                <thead><tr><th>Surface or opening</th><th className="n">Area</th><th className="n">R</th><th className="n">Btu/h</th></tr></thead>
                <tbody>{surfaces.map((s, i) => <tr key={i}><td>{s.name} <span className="muted small">{pretty(s.kind)}</span></td><td className="n">{fmt(s.area_ft2)}</td>
                  <td className="n">{s.r_value ? fmt(s.r_value, 1) : ""}</td><td className="n">{fmt(mode === "heating" ? s.heating_btuh : s.cooling_btuh)}</td></tr>)}</tbody></table></div>}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

export function Scenarios({ out, pick }: { out: CalcOutput; pick: (id: string | null) => void }) {
  const base = out.baseline!;
  if (!out.scenarios.length) return null;
  const row = (name: string, r: Result | undefined, id: string | null, cost: number | null, error?: string) => {
    if (!r) return <tr key={id}><td>{name}</td><td colSpan={7} className="bad-text">{error}</td></tr>;
    const dh = r.building.heating_btuh - base.building.heating_btuh, dc = r.building.cooling_total_btuh - base.building.cooling_total_btuh;
    const cell = (v: number) => (id === null ? "" : <span className={`delta ${v < -0.5 ? "good" : v > 0.5 ? "bad" : ""}`}>{v > 0 ? "+" : ""}{fmt(v)}</span>);
    return (
      <tr key={id ?? "baseline"} onClick={() => pick(id)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && pick(id)}>
        <td>{name}</td><td className="n">{fmt(r.building.heating_btuh)}</td><td className="n">{cell(dh)}</td>
        <td className="n">{fmt(r.building.cooling_sensible_btuh)}</td><td className="n">{fmt(r.building.cooling_latent_btuh)}</td>
        <td className="n">{fmt(r.building.cooling_tons, 2)}</td><td className="n">{cell(dc)}</td>
        <td className="n">{cost ? `$${fmt(cost)}` : ""}{cost && dh < 0 ? <span className="muted small"> · {fmt((-dh / cost) * 1000)} Btu/h per $1,000</span> : ""}</td>
      </tr>
    );
  };
  return (
    <div className="card">
      <h3>Scenario comparison</h3>
      <p className="muted">Each scenario is the baseline house with a few changes. Savings from separate scenarios do not simply add up; a combined scenario shows the real total. Select a row to see its breakdown above.</p>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Scenario</th><th className="n">Heating</th><th className="n">Change</th><th className="n">Cooling, temp.</th><th className="n">Cooling, moisture</th><th className="n">Tons</th><th className="n">Change (total cooling)</th><th className="n">Your cost</th></tr></thead>
          <tbody>{row("Baseline (the house as it is)", base, null, null)}{out.scenarios.map((s) => row(s.name, s.result, s.id, s.cost_usd, s.error))}</tbody>
        </table>
      </div>
    </div>
  );
}

function Guidance({ r }: { r: Result }) {
  const s = r.sizing, inf = r.infiltration, d = r.design;
  return (
    <div className="two cards">
      <div className="card">
        <h3>What to ask a contractor for</h3>
        <ul className="plain">
          <li><strong>Cooling:</strong> equipment with {fmt(s.cooling_capacity_min_btuh)} to {fmt(s.cooling_capacity_max_btuh)} Btu/h ({fmt(s.cooling_capacity_min_btuh / 12000, 1)} to {fmt(s.cooling_capacity_max_btuh / 12000, 1)} tons) of total capacity at {fmt(d.cooling_outdoor_temp_f)}°F outdoors and {fmt(d.cooling_setpoint_f)}°F indoors.</li>
          <li>Of that, it must remove at least <strong>{fmt(s.cooling_sensible_needed_btuh)} Btu/h of heat</strong> and <strong>{fmt(s.cooling_latent_needed_btuh)} Btu/h of moisture</strong>. A bigger unit is not safer: it runs in short bursts and removes less moisture.</li>
          <li><strong>Heating:</strong> at least {fmt(s.heating_capacity_min_btuh)} Btu/h of output at {fmt(d.heating_outdoor_temp_f)}°F outdoors.</li>
        </ul>
        <p className="help">{s.basis} Equipment comes in steps of about half a ton (6,000 Btu/h), so pick the size nearest the load, not the next one up “to be safe”.</p>
      </div>
      <div className="card">
        <h3>Design conditions and air leakage</h3>
        <ul className="plain">
          <li>Outdoors: {fmt(d.heating_outdoor_temp_f, 1)}°F in winter, {fmt(d.cooling_outdoor_temp_f, 1)}°F in summer ({d.daily_temp_range} daily swing); outdoor air holds {fmt(d.humidity_difference_gr_lb, 1)} grains/lb {d.humidity_difference_gr_lb >= 0 ? "more" : "less"} moisture than indoor air.</li>
          {inf.method === "blower_door" && inf.leakage_area_in2 !== null && <li>Blower door{inf.ach50 !== null ? ` ${fmt(inf.ach50, 1)} ACH50` : ""} → leakage area {fmt(inf.leakage_area_in2)} in² → <strong>{fmt(inf.heating_cfm)} cfm</strong> of outdoor air on the design winter day and <strong>{fmt(inf.cooling_cfm)} cfm</strong> on the design summer day.</li>}
          {inf.method === "default_table" && <li>Leakiness estimate → {fmt(inf.heating_cfm)} cfm in winter, {fmt(inf.cooling_cfm)} cfm in summer.</li>}
          {inf.method === "none" && <li className="bad-text">No air leakage is entered, so none is counted.</li>}
          {d.space_temps_f.map((t) => <li key={t.id}>{t.name}: {fmt(t.heating)}°F in winter, {fmt(t.cooling)}°F in summer.</li>)}
        </ul>
      </div>
    </div>
  );
}

function Confidence({ out, r }: { out: CalcOutput; r: Result }) {
  const counts = { measured: 0, estimated: 0, default: 0 } as Record<string, number>;
  for (const i of out.stated_inputs) counts[i.confidence] = (counts[i.confidence] ?? 0) + 1;
  const grouped = new Map<string, { d: (typeof r.defaults_used)[number]; where: string[] }>();
  for (const d of r.defaults_used) { const g = grouped.get(d.name) ?? { d, where: [] }; g.where.push(d.applies_to); grouped.set(d.name, g); }
  const noted = out.stated_inputs.filter((i) => i.confidence !== "default" || i.source);
  return (
    <div className="card">
      <h3>What this answer rests on</h3>
      <p className="muted">{counts.measured} input{counts.measured === 1 ? "" : "s"} marked measured, {counts.estimated} estimated, {counts.default} entered without a note, and {grouped.size} filled in by RightTon’s defaults (below). Mark numbers as measured or estimated with the “source” button next to any number.</p>
      {noted.length > 0 && <details><summary>Inputs with a source note ({noted.length})</summary>
        <div className="table-wrap"><table className="data compact"><thead><tr><th>Input</th><th className="n">Value</th><th>Confidence</th><th>Source</th></tr></thead>
          <tbody>{noted.map((i) => <tr key={i.path}><td className="mono small">{i.path}</td><td className="n">{i.value}</td><td><span className={`pill ${i.confidence}`}>{i.confidence}</span></td><td>{i.source}</td></tr>)}</tbody></table></div></details>}
      <details><summary>Defaults RightTon filled in ({grouped.size})</summary>
        <div className="table-wrap"><table className="data compact"><thead><tr><th>Default</th><th className="n">Value</th><th>Applied to</th><th>Source</th></tr></thead>
          <tbody>{Array.from(grouped.values()).map(({ d, where }) => <tr key={d.name}><td>{pretty(d.name)} {d.confidence === "estimated" && <span className="pill estimated">estimated</span>}</td>
            <td className="n">{typeof d.value === "object" ? JSON.stringify(d.value) : String(d.value)} <span className="muted small">{d.unit}</span></td>
            <td>{where.length > 2 ? `${where.length} items` : where.join("; ")}</td><td className="small">{d.source}</td></tr>)}</tbody></table></div></details>
    </div>
  );
}

export function ResultsView({ out, busy }: { out: CalcOutput | null; busy: boolean }) {
  const [mode, setMode] = useState<Mode>("heating");
  const [scenario, setScenario] = useState<string | null>(null);
  if (!out) return <div className="card"><p className="muted">{busy ? "Starting the calculation engine (this takes a few seconds the first time)…" : "No results yet."}</p></div>;
  if (!out.baseline) return (
    <div className="card"><h3>The house file has problems</h3><p className="muted">Fix these and the results appear here.</p>
      <ul className="issues">{out.issues.filter((i) => i.level === "error").map((i, n) => <li key={n} className="error"><strong>{i.where}</strong> {i.message}</li>)}</ul></div>
  );
  const picked = out.scenarios.find((s) => s.id === scenario && s.result);
  const r = picked?.result ?? out.baseline;
  return (
    <div className="results">
      {out.scenarios.length > 0 && (
        <div className="scenario-pick"><label htmlFor="scn">Showing</label>
          <select id="scn" value={picked ? picked.id : ""} onChange={(e) => setScenario(e.target.value || null)}>
            <option value="">Baseline (the house as it is)</option>{out.scenarios.filter((s) => s.result).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>{picked && <span className="muted">changes shown against the baseline</span>}</div>
      )}
      <Headline r={r} base={picked ? out.baseline : undefined} />
      <div className="card">
        <div className="card-head"><h3>Where the load comes from</h3>
          <div className="seg">{MODES.map((m) => <button key={m.key} className={mode === m.key ? "on" : ""} onClick={() => setMode(m.key)}>{m.label}</button>)}</div></div>
        <p className="muted">{fmt(total(r.building, mode))} Btu/h in total, largest first.{picked && " Thin bars and the second number are this scenario; thick bars are the baseline."}</p>
        {picked ? <Bars items={comps(out.baseline.building, mode)} compare={comps(r.building, mode)} compareLabel={picked.name} /> : <Bars items={comps(r.building, mode)} />}
      </div>
      <Scenarios out={out} pick={setScenario} />
      <Rooms r={r} />
      <Guidance r={r} />
      <Confidence out={out} r={r} />
    </div>
  );
}
