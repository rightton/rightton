// The open house file, kept exactly as it would be saved. Edits replace the
// document immutably; unknown fields and extensions are never touched.
import { useCallback, useEffect, useReducer } from "react";
import type { House, Json, Obj } from "./types";

type State = { house: House; past: House[]; future: House[]; fileName: string; dirty: boolean };
type Action =
  | { type: "load"; house: House; fileName: string }
  | { type: "edit"; house: House }
  | { type: "undo" } | { type: "redo" } | { type: "saved" };

const STORAGE_KEY = "rightton.house.v1";

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "load": return { house: action.house, past: [], future: [], fileName: action.fileName, dirty: false };
    case "edit": return { ...state, house: action.house, past: [...state.past.slice(-49), state.house], future: [], dirty: true };
    case "undo": {
      const prev = state.past[state.past.length - 1];
      return prev ? { ...state, house: prev, past: state.past.slice(0, -1), future: [state.house, ...state.future], dirty: true } : state;
    }
    case "redo": {
      const next = state.future[0];
      return next ? { ...state, house: next, past: [...state.past, state.house], future: state.future.slice(1), dirty: true } : state;
    }
    case "saved": return { ...state, dirty: false };
  }
}

export function emptyHouse(): House {
  return {
    format_version: "1.1.0",
    project: { name: "New house" },
    location: {},
    assemblies: [],
    zones: [{ id: "main", name: "Whole house" }],
    rooms: [{ id: "room-1", name: "Room 1", zone: "main", floor_area_ft2: 200 }],
    spaces: [], surfaces: [], openings: [],
    air: { infiltration: { method: "leakiness_estimate", leakiness: "average" } },
  };
}

function stored(): { house: House; fileName: string } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export function useHouse() {
  const [state, dispatch] = useReducer(reducer, undefined, (): State => {
    const s = stored();
    return { house: s?.house ?? emptyHouse(), past: [], future: [], fileName: s?.fileName ?? "", dirty: false };
  });
  useEffect(() => {
    // Autosave on this device only (browser storage). Nothing is sent anywhere.
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ house: state.house, fileName: state.fileName })); } catch { /* storage full or disabled */ }
  }, [state.house, state.fileName]);
  const setHouse = useCallback((house: House) => dispatch({ type: "edit", house }), []);
  const update = useCallback((path: (string | number)[], value: Json | undefined) =>
    dispatch({ type: "edit", house: setIn(state.house, path, value) as House }), [state.house]);
  return {
    ...state, setHouse, update,
    load: (house: House, fileName: string) => dispatch({ type: "load", house, fileName }),
    undo: () => dispatch({ type: "undo" }), redo: () => dispatch({ type: "redo" }), markSaved: () => dispatch({ type: "saved" }),
    hadStored: stored() !== null,
  };
}

/** Immutable set (or delete when value is undefined) at a path of object keys and list indexes. */
export function setIn(node: Json | undefined, path: (string | number)[], value: Json | undefined): Json {
  if (path.length === 0) return value as Json;
  const [key, ...rest] = path;
  if (typeof key === "number") {
    const list = Array.isArray(node) ? [...node] : [];
    if (rest.length === 0 && value === undefined) list.splice(key, 1);
    else list[key] = setIn(list[key], rest, value);
    return list;
  }
  const obj: Obj = node && typeof node === "object" && !Array.isArray(node) ? { ...node } : {};
  if (rest.length === 0 && value === undefined) delete obj[key];
  else obj[key] = setIn(obj[key], rest, value);
  return obj;
}

export function getIn(node: Json | undefined, path: (string | number)[]): Json | undefined {
  let cur: Json | undefined = node;
  for (const key of path) {
    if (cur === null || cur === undefined || typeof cur !== "object") return undefined;
    cur = Array.isArray(cur) ? cur[key as number] : (cur as Obj)[key as string];
  }
  return cur;
}

export const list = (house: House, path: string[]): Obj[] => {
  const v = getIn(house, path);
  return Array.isArray(v) ? (v as Obj[]) : [];
};

/** Every id in the file, to keep new ids unique. */
export function allIds(house: House): Set<string> {
  const ids = new Set<string>();
  for (const path of ID_SECTIONS) for (const item of list(house, path)) if (typeof item.id === "string") ids.add(item.id);
  return ids;
}
export const ID_SECTIONS: string[][] = [["assemblies"], ["glazings"], ["zones"], ["rooms"], ["spaces"], ["surfaces"], ["openings"],
  ["air", "ventilation"], ["air", "ducts"], ["equipment"], ["hvac", "systems"], ["scenarios"]];

export function uniqueId(house: House, base: string): string {
  const ids = allIds(house);
  if (!ids.has(base)) return base;
  for (let n = 2; ; n++) if (!ids.has(`${base}-${n}`)) return `${base}-${n}`;
}

const REF_KEYS = new Set(["zone", "inside", "outside", "assembly", "surface", "system", "room", "location", "ceiling", "glazing"]);
const REF_LISTS = new Set(["supply_registers", "returns", "includes"]);

/** Rename an id everywhere it is referenced, including scenario paths. */
export function renameId(house: House, oldId: string, newId: string): House {
  const walk = (node: Json, key?: string): Json => {
    if (Array.isArray(node)) {
      if (key && REF_LISTS.has(key)) return node.map((v) => (v === oldId ? newId : v));
      return node.map((v) => walk(v));
    }
    if (node && typeof node === "object") {
      const out: Obj = {};
      for (const [k, v] of Object.entries(node)) {
        if (k === "extensions") out[k] = v; // other tools' data is never touched
        else if (k === "id" && v === oldId) out[k] = newId;
        else if (REF_KEYS.has(k) && v === oldId) out[k] = newId;
        else if ((k === "path" || k === "section") && typeof v === "string")
          out[k] = v.split("/").map((part) => (part === oldId ? newId : part)).join("/");
        else out[k] = walk(v, k);
      }
      return out;
    }
    return node;
  };
  return walk(house) as House;
}
