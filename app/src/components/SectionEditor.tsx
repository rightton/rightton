// List-and-detail editor for one list in the house file (rooms, surfaces, openings ...).
import { useState, type ReactNode } from "react";
import { list, setIn, uniqueId } from "../state";
import { branchTypes, itemSchema, pretty, resolve, slug } from "../schemaUtil";
import type { House, Json, Obj, Schema } from "../types";
import { ObjectForm, type Ctx } from "./Field";

export type SectionProps = {
  title: string; singular: string; intro?: string; path: string[]; schema: Schema; ctx: Ctx; onEdit: (house: House) => void;
  summary: (item: Obj) => string; badge?: (item: Obj) => ReactNode; groupBy?: (item: Obj) => string;
  newItem: (type: string | undefined, id: string) => Obj; primary?: string[]; hide?: string[] | ((item: Obj) => string[]);
  extra?: (item: Obj, setItem: (item: Obj) => void) => ReactNode;
};

export function SectionEditor(p: SectionProps) {
  const items = list(p.ctx.house, p.path);
  const [selected, setSelected] = useState<string | null>(null);
  const types = branchTypes(p.schema).filter(Boolean);
  const index = items.findIndex((i) => i.id === selected);
  const current = index >= 0 ? items[index] : null;
  const write = (next: Obj[]) => p.onEdit(setIn(p.ctx.house, p.path, next as Json) as House);
  const add = (type?: string) => {
    const id = uniqueId(p.ctx.house, slug(type ?? p.singular));
    write([...items, p.newItem(type, id)]);
    setSelected(id);
  };
  const setItem = (item: Obj) => { write(items.map((it, i) => (i === index ? item : it))); if (item.id !== selected) setSelected(item.id as string); };
  const remove = () => { write(items.filter((_, i) => i !== index)); setSelected(null); };
  const duplicate = () => {
    if (!current) return;
    const id = uniqueId(p.ctx.house, `${current.id}-copy`);
    const copy = { ...structuredClone(current), id, ...(current.name ? { name: `${current.name} (copy)` } : {}) };
    write([...items.slice(0, index + 1), copy, ...items.slice(index + 1)]);
    setSelected(id);
  };
  const groups = p.groupBy ? Array.from(new Set(items.map(p.groupBy))) : [""];
  const schema = current ? itemSchema(p.schema, current.type as string | undefined) : resolve({});
  return (
    <section className={`md ${current ? "has-detail" : ""}`}>
      <div className="md-list">
        <div className="md-head">
          <div><h2>{p.title}</h2>{p.intro && <p className="muted">{p.intro}</p>}</div>
        </div>
        <div className="add-row">
          {types.length > 1
            ? types.map((t) => <button key={t} className="btn small" onClick={() => add(t)}>+ {pretty(t)}</button>)
            : <button className="btn" onClick={() => add(types[0])}>+ Add {p.singular}</button>}
        </div>
        {items.length === 0 && <p className="empty">None yet.</p>}
        {groups.map((g) => (
          <div key={g}>
            {g && <h3 className="group-head">{g}</h3>}
            <ul className="rows">
              {items.filter((i) => !p.groupBy || p.groupBy(i) === g).map((item) => (
                <li key={item.id as string}>
                  <button className={`row ${item.id === selected ? "selected" : ""}`} onClick={() => setSelected(item.id as string)}>
                    <span className="row-main">
                      <span className="row-title">{(item.name as string) || (item.id as string)}</span>
                      <span className="row-sub">{p.summary(item)}</span>
                    </span>
                    {p.badge && <span className="row-badge">{p.badge(item)}</span>}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="md-detail">
        {!current && <div className="placeholder"><p>Select {p.singular === "opening" || p.singular === "assembly" ? "an" : "a"} {p.singular} to edit it, or add a new one.</p></div>}
        {current && (
          <div className="card detail">
            <div className="detail-head">
              <button className="btn ghost back" onClick={() => setSelected(null)}>← All {p.title.toLowerCase()}</button>
              <div className="detail-title">
                <h3>{(current.name as string) || (current.id as string)}</h3>
                {typeof current.type === "string" && <span className="tag">{pretty(current.type)}</span>}
              </div>
              <div className="detail-actions">
                <button className="btn ghost small" onClick={duplicate}>Duplicate</button>
                <button className="btn ghost small danger" onClick={remove}>Delete</button>
              </div>
            </div>
            <ObjectForm schema={schema} value={current} onChange={setItem} ctx={p.ctx} primary={p.primary}
              hide={typeof p.hide === "function" ? p.hide(current) : p.hide} middle={p.extra?.(current, setItem)} />
          </div>
        )}
      </div>
    </section>
  );
}
