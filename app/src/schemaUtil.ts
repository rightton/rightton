// Helpers for reading the house-file JSON Schema, which drives the forms.
import type { Json, Obj, Schema } from "./types";

let root: Schema = {};
export function setRootSchema(schema: Schema) { root = schema; }
export function rootSchema(): Schema { return root; }

export function resolve(schema: Schema): Schema {
  let s = schema;
  while (s.$ref) {
    let target: any = root;
    for (const part of s.$ref.replace(/^#\//, "").split("/")) target = target[part];
    const { $ref: _ref, ...rest } = s;
    s = { ...target, ...rest };
  }
  return s;
}

export const isQuantity = (s: Schema) => s.$ref === "#/$defs/quantity";
export const isIdRef = (s: Schema) => s.$ref === "#/$defs/id";

/** Schema of the items of a list section, picking the branch for a given `type` where the list is mixed. */
export function itemSchema(listSchema: Schema, type?: string): Schema {
  const items = resolve(resolve(listSchema).items ?? {});
  if (items.oneOf) {
    const key = items["x-discriminator"] ?? "type";
    return items.oneOf.find((b) => b.properties?.[key]?.const === type) ?? items.oneOf[0];
  }
  return items;
}

export function branchTypes(listSchema: Schema): string[] {
  const items = resolve(resolve(listSchema).items ?? {});
  const key = items["x-discriminator"] ?? "type";
  return (items.oneOf ?? []).map((b) => b.properties?.[key]?.const as string);
}

export function schemaAt(path: string[]): Schema {
  let s = resolve(root);
  for (const key of path) s = resolve(s.properties?.[key] ?? {});
  return s;
}

// --- Quantities: a bare number, or {value, source, confidence} -----------------
export type Wrapped = { value: number; source?: string; confidence?: string };
export const isWrapped = (v: Json | undefined): v is Wrapped & Obj =>
  typeof v === "object" && v !== null && !Array.isArray(v) && "value" in v;
export function num(v: Json | undefined): number | undefined {
  if (typeof v === "number") return v;
  if (isWrapped(v) && typeof v.value === "number") return v.value;
  return undefined;
}

// --- Labels -------------------------------------------------------------------------
const UNIT_SUFFIXES = ["_hr_ft2_f_btu_in", "_hr_ft2_f_btu", "_btu_hr_ft2_f", "_btu_hr_ft_f", "_btu_hr", "_cfm_per_ton",
  "_cfm_at_50pa", "_cfm_at_25pa", "_per_hr_at_50pa", "_per_hr", "_per_floor_area_frac", "_rise_per_12", "_gr_lb", "_lb_lb",
  "_ft2", "_ft3", "_in2", "_ft", "_in", "_frac", "_deg", "_cfm", "_pa", "_usd", "_hr", "_f"];
const SPECIAL: Record<string, string> = {
  shgc: "SHGC (solar heat gain coefficient)", u_factor_btu_hr_ft2_f: "U-factor", r_value_hr_ft2_f_btu: "R-value",
  air_changes_per_hr_at_50pa: "ACH50 (air changes per hour at 50 Pa)", airflow_cfm_at_50pa: "CFM50 (airflow at 50 Pa)",
  id: "Id", hvac: "HVAC", pitch_rise_per_12: "Roof pitch (rise per 12)", framing_frac: "Framing share of area",
  heating_outdoor_temp_f: "Heating design temperature (outdoor)", cooling_outdoor_temp_f: "Cooling design temperature (outdoor)",
  humidity_difference_gr_lb: "Humidity difference", r_per_inch_hr_ft2_f_btu_in: "R per inch",
  framing_r_per_inch_hr_ft2_f_btu_in: "Framing R per inch", cost_usd: "Cost", supply_registers: "Rooms with supply registers",
  returns: "Rooms with returns", includes: "Applies these scenarios first", vent_area_per_floor_area_frac: "Vent area per floor area",
};
export function humanize(name: string): string {
  if (SPECIAL[name]) return SPECIAL[name];
  let base = name;
  for (const suffix of UNIT_SUFFIXES) if (base.endsWith(suffix) && base.length > suffix.length) { base = base.slice(0, -suffix.length); break; }
  base = base.replace(/_/g, " ");
  return base.charAt(0).toUpperCase() + base.slice(1);
}
export function unitLabel(schema: Schema): string {
  const unit = schema["x-unit"];
  if (!unit || unit === "none") return "";
  return ({ "0-1": "0–1", "hr-ft2-F/Btu": "R", "Btu/h-ft2-F": "U", "ft2": "ft²", "ft3": "ft³", "in2": "in²", "1/h": "/h",
    "hr-ft2-F/Btu per in": "R/in", "F": "°F", "deg": "°", "US dollars": "$", "cfm per 12,000 Btu/h": "cfm/ton" } as Record<string, string>)[unit] ?? unit;
}
export const pretty = (value: string) => value.replace(/_/g, " ");

export function fmt(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  return n.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function slug(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "item";
}
