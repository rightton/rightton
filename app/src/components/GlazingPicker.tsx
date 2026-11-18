// Window glass: a glazing from the house file's own library, a RightTon preset, or custom values from
// the window's NFRC label (which can be saved to the library and reused on other windows).
import { useEffect, useState } from "react";
import { list, setIn, uniqueId } from "../state";
import { num, slug } from "../schemaUtil";
import type { House, Json, Library, Obj } from "../types";

const CUSTOM = "__custom__";

export function GlazingPicker({ win, house, lib, onHouse }: { win: Obj; house: House; lib: Library; onHouse: (h: House) => void }) {
  const own = list(house, ["glazings"]);
  const openings = list(house, ["openings"]);
  const custom = win.glazing === undefined;
  const writeWindow = (next: Obj, h: House = house) => {
    const ops = list(h, ["openings"]).map((o) => (o.id === win.id ? next : o));
    onHouse(setIn(h, ["openings"], ops as Json) as House);
  };
  const choose = (v: string) => {
    const next: Obj = { ...win };
    if (v === CUSTOM) {
      const from = own.find((g) => g.id === win.glazing) ?? lib.glazing.find((g) => g.id === win.glazing);
      delete next.glazing;
      if (next.u_factor_btu_hr_ft2_f === undefined) next.u_factor_btu_hr_ft2_f = (from?.u_factor_btu_hr_ft2_f as Json) ?? 0.3;
      if (next.shgc === undefined) next.shgc = (from?.shgc as Json) ?? 0.3;
    } else {
      next.glazing = v;
      delete next.u_factor_btu_hr_ft2_f; delete next.shgc;
    }
    writeWindow(next);
  };
  // Typed text is kept while it is not yet a number ("0." on the way to "0.27").
  const [uText, setUText] = useState<string | null>(null);
  const [sText, setSText] = useState<string | null>(null);
  const [saveName, setSaveName] = useState("");
  useEffect(() => { setUText(null); setSText(null); setSaveName(""); }, [win.id]);
  const setNum = (key: string, raw: string, setText: (t: string | null) => void) => {
    setText(raw);
    const n = Number(raw);
    if (raw.trim() === "" || Number.isNaN(n)) return;
    writeWindow({ ...win, [key]: n });
  };
  const u = num(win.u_factor_btu_hr_ft2_f);
  const shgc = num(win.shgc);
  const badU = u !== undefined && (u < 0.1 || u > 1.5);
  const saveToLibrary = () => {
    const name = saveName.trim() || `U ${u} / SHGC ${shgc}`;
    const id = uniqueId(house, slug(saveName.trim() || `glazing-u${u}-shgc${shgc}`));
    const entry: Obj = { id, name, u_factor_btu_hr_ft2_f: win.u_factor_btu_hr_ft2_f as Json, shgc: win.shgc as Json, source: "NFRC label" };
    const h = setIn(house, ["glazings"], [...own, entry] as Json) as House;
    const next: Obj = { ...win, glazing: id };
    delete next.u_factor_btu_hr_ft2_f; delete next.shgc;
    writeWindow(next, h);
  };
  const users = (gid: unknown) => openings.filter((o) => o.glazing === gid).length;
  return (
    <div className="glazing-picker">
      <label className="field-label" htmlFor={`glz-${win.id}`}>Glass</label>
      <select id={`glz-${win.id}`} aria-label="Glazing" value={custom ? CUSTOM : (win.glazing as string)} onChange={(e) => choose(e.target.value)}>
        {own.length > 0 && <optgroup label="My glazings (from labels)">
          {own.map((g) => <option key={g.id as string} value={g.id as string}>{(g.name as string) || (g.id as string)} (U {num(g.u_factor_btu_hr_ft2_f)}, SHGC {num(g.shgc)})</option>)}
        </optgroup>}
        <optgroup label="Typical windows">
          {lib.glazing.map((g) => <option key={g.id} value={g.id}>{g.name} (U {g.u_factor_btu_hr_ft2_f}, SHGC {g.shgc})</option>)}
        </optgroup>
        <option value={CUSTOM}>Custom (from label)…</option>
      </select>
      {custom && (
        <div className="glazing-custom">
          <p className="help">Copy the two numbers from the window's NFRC label: the whole-window U-factor and Solar Heat Gain Coefficient. Do not use center-of-glass values from a glass brochure; they leave out the frame.</p>
          <div className="glazing-fields">
            <label>U-factor (Btu/h·ft²·°F)<input type="text" inputMode="decimal" aria-label="U-factor" value={uText ?? (u ?? "")} onChange={(e) => setNum("u_factor_btu_hr_ft2_f", e.target.value, setUText)} onBlur={() => setUText(null)} /></label>
            <label>SHGC (0 to 1)<input type="text" inputMode="decimal" aria-label="SHGC" value={sText ?? (shgc ?? "")} onChange={(e) => setNum("shgc", e.target.value, setSText)} onBlur={() => setSText(null)} /></label>
          </div>
          {badU && <p className="help warn">A label U-factor is usually between 0.15 and 1.3. Check this is the U-factor, not an R-value or a metric value.</p>}
          <div className="glazing-save">
            <label>Name (optional)<input type="text" aria-label="Glazing name" value={saveName} placeholder="e.g. New vinyl double-hung" onChange={(e) => setSaveName(e.target.value)} /></label>
            <button className="btn small" disabled={u === undefined || shgc === undefined} onClick={saveToLibrary}>Save for other windows</button>
          </div>
        </div>
      )}
      {!custom && own.some((g) => g.id === win.glazing) && <p className="help">From your glazings; {users(win.glazing)} opening(s) use it. Edit its values under Openings › My glazings.</p>}
    </div>
  );
}
