// A room's own walls, ceilings, floors and their windows and doors, edited without leaving the room.
// The Surfaces and Openings pages still show everything; this is the same data seen from one room.
import { useState, type ReactNode } from "react";
import { list, setIn, uniqueId } from "../state";
import { itemSchema, num, pretty, slug, fmt } from "../schemaUtil";
import type { House, Json, Library, Obj, Schema } from "../types";
import { ObjectForm, type Ctx } from "./Field";
import { GlazingPicker } from "./GlazingPicker";

type Props = {
  room: Obj; ctx: Ctx; lib: Library; onHouse: (h: House) => void;
  surfacesSchema: Schema; openingsSchema: Schema;
  surfaceTemplate: (type: string, id: string, inside: string) => Obj;
  openingTemplate: (type: string, id: string, surface: string) => Obj;
  nameOf: (id: Json | undefined) => string; badge: (item: Obj) => ReactNode;
};

const GROUPS: { label: string; types: string[] }[] = [
  { label: "Walls", types: ["wall", "rim_joist", "foundation_wall"] },
  { label: "Ceilings and roofs", types: ["ceiling", "roof"] },
  { label: "Floors", types: ["floor", "slab"] },
];
const ADD_SURFACES = ["wall", "ceiling", "floor", "roof", "slab", "foundation_wall"];
const LABEL: Record<string, string> = { wall: "Wall", rim_joist: "Rim joist", foundation_wall: "Foundation wall", ceiling: "Ceiling", roof: "Roof",
  floor: "Floor", slab: "Slab", window: "Window", door: "Door", skylight: "Skylight" };
const cap = (t: unknown) => LABEL[t as string] ?? pretty(String(t));
const OPENINGS_FOR: Record<string, string[]> = { wall: ["window", "door"], foundation_wall: ["window", "door"], roof: ["skylight"] };

export function RoomContents(p: Props) {
  const house = p.ctx.house;
  const rid = p.room.id as string;
  const surfaces = list(house, ["surfaces"]);
  const openings = list(house, ["openings"]);
  const mine = surfaces.filter((s) => s.inside === rid || s.outside === rid);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const toggle = (id: string, v: boolean) => setOpen({ ...open, [id]: v });

  const writeList = (key: "surfaces" | "openings", next: Obj[], h: House = house) => setIn(h, [key], next as Json) as House;
  const setSurface = (s: Obj) => {
    const old = surfaces.find((x) => x.id === s.id) ? s.id : undefined;
    p.onHouse(writeList("surfaces", surfaces.map((x) => (x.id === old ? s : x))));
  };
  const setOpening = (o: Obj) => p.onHouse(writeList("openings", openings.map((x) => (x.id === o.id ? o : x))));
  const addSurface = (type: string) => {
    const id = uniqueId(house, slug(`${(p.room.name as string) || rid} ${type}`));
    p.onHouse(writeList("surfaces", [...surfaces, p.surfaceTemplate(type, id, rid)]));
    toggle(id, true);
  };
  const removeSurface = (s: Obj) => {
    // Its windows and doors go with it.
    const h = writeList("surfaces", surfaces.filter((x) => x.id !== s.id));
    p.onHouse(writeList("openings", openings.filter((o) => o.surface !== s.id), h));
  };
  const addOpening = (type: string, surface: string) => {
    const id = uniqueId(house, slug(`${surface} ${type}`));
    p.onHouse(writeList("openings", [...openings, p.openingTemplate(type, id, surface)]));
    toggle(id, true);
  };
  const removeOpening = (o: Obj) => p.onHouse(writeList("openings", openings.filter((x) => x.id !== o.id)));
  const area = (o: Obj) => { const a = num(o.area_ft2) ?? (num(o.width_ft) !== undefined && num(o.height_ft) !== undefined ? num(o.width_ft)! * num(o.height_ft)! : undefined); return a === undefined ? "" : `${fmt(a * ((num(o.count) as number) ?? 1))} ft²`; };
  const facing = (s: Obj) => (num(s.azimuth_deg) !== undefined ? ` · faces ${compass(num(s.azimuth_deg)!)}` : "");

  const openingCard = (o: Obj) => (
    <details key={o.id as string} className="rc-item rc-opening" open={!!open[o.id as string]}>
      <summary onClick={(e) => { e.preventDefault(); toggle(o.id as string, !open[o.id as string]); }}><span className="rc-title">{(o.name as string) || cap(o.type)}</span>
        <span className="rc-sub">{(num(o.count) ?? 1) > 1 ? `${num(o.count)} × ` : ""}{cap(o.type)} · {area(o)}</span>
        <span className="row-badge">{p.badge(o)}</span></summary>
      <div className="rc-body">
        <ObjectForm schema={itemSchema(p.openingsSchema, o.type as string)} value={o} onChange={setOpening} ctx={p.ctx} primary={["count", "width_ft", "height_ft", "storm_window"]}
          hide={o.type === "window" ? ["surface", "glazing", "u_factor_btu_hr_ft2_f", "shgc"] : ["surface"]}
          middle={o.type === "window" ? <GlazingPicker win={o} house={house} lib={p.lib} onHouse={p.onHouse} /> : undefined} />
        <button className="btn ghost small danger" onClick={() => removeOpening(o)}>Delete {cap(o.type).toLowerCase()}</button>
      </div>
    </details>
  );

  const surfaceCard = (s: Obj) => {
    const own = openings.filter((o) => o.surface === s.id);
    const other = s.inside === rid ? s.outside : s.inside;
    return (
      <details key={s.id as string} className="rc-item" open={!!open[s.id as string]}>
        <summary onClick={(e) => { e.preventDefault(); toggle(s.id as string, !open[s.id as string]); }}><span className="rc-title">{(s.name as string) || (s.id as string)}</span>
          <span className="rc-sub">{cap(s.type)} · {fmt(num(s.area_ft2))} ft²{other ? ` · to ${p.nameOf(other)}` : s.type === "wall" ? " · to outdoors" : ""}{facing(s)}{own.length ? ` · ${own.length} opening(s)` : ""}</span>
          <span className="row-badge">{p.badge(s)}</span></summary>
        <div className="rc-body">
          <ObjectForm schema={itemSchema(p.surfacesSchema, s.type as string)} value={s} onChange={setSurface} ctx={p.ctx} primary={["outside", "azimuth_deg", "pitch_rise_per_12"]} />
          {(OPENINGS_FOR[s.type as string] ?? []).length > 0 && (
            <div className="rc-openings">
              <h5>{s.type === "roof" ? "Skylights in this roof" : `Windows and doors in this ${cap(s.type).toLowerCase()}`}</h5>
              {own.length === 0 && <p className="help">None.</p>}
              {own.map(openingCard)}
              <div className="add-row">{OPENINGS_FOR[s.type as string].map((t) => <button key={t} className="btn small" onClick={() => addOpening(t, s.id as string)}>+ {cap(t)}</button>)}</div>
            </div>
          )}
          <button className="btn ghost small danger" onClick={() => removeSurface(s)}>Delete {cap(s.type).toLowerCase()}{own.length ? " and its openings" : ""}</button>
        </div>
      </details>
    );
  };

  return (
    <div className="room-contents">
      <h4>Walls, ceilings and floors of this room</h4>
      <p className="help">Each surface belongs to this room and says what is on its other side. Interior walls between rooms on the same thermostat can be left out.</p>
      {GROUPS.map((g) => {
        const items = mine.filter((s) => g.types.includes(s.type as string));
        return items.length ? <div key={g.label} className="rc-group"><h5>{g.label}</h5>{items.map(surfaceCard)}</div> : null;
      })}
      {mine.length === 0 && <p className="empty">No surfaces yet.</p>}
      <div className="add-row">{ADD_SURFACES.map((t) => <button key={t} className="btn small" onClick={() => addSurface(t)}>+ {cap(t)}</button>)}</div>
    </div>
  );
}

function compass(deg: number): string {
  const names = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"];
  return names[Math.round((((deg % 360) + 360) % 360) / 45) % 8];
}
