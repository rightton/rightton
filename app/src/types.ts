export type Json = string | number | boolean | null | Json[] | { [key: string]: Json };
export type Obj = { [key: string]: Json };
export type House = Obj;

export type Schema = {
  type?: string; description?: string; properties?: Record<string, Schema>; required?: string[];
  items?: Schema; enum?: (string | number)[]; const?: string; oneOf?: Schema[]; anyOf?: Schema[]; $ref?: string;
  minimum?: number; maximum?: number; minItems?: number; $defs?: Record<string, Schema>;
  "x-unit"?: string; "x-min"?: number; "x-max"?: number; "x-discriminator"?: string; additionalProperties?: boolean;
};

export type Library = {
  format_version: string; schema: Schema;
  materials: { id: string; name: string; r_per_inch_hr_ft2_f_btu_in?: number; r_value_hr_ft2_f_btu?: number;
    typical_thickness_in?: number; category: string; use: string; source: string; confidence: string; note?: string }[];
  material_categories: { id: string; name: string }[];
  assembly_presets: Obj[];
  framing: { lumber: Record<string, { width_in: number; depth_in: number }>; spacings_in: number[] };
  glazing: { id: string; name: string; u_factor_btu_hr_ft2_f: number; shgc: number }[];
  stations: { id: string; name: string; state: string; heating_f: number; cooling_f: number; latitude_deg: number }[];
  defaults: Record<string, { value: Json; unit: string; applies_when: string; source: string; confidence: string }>;
};

export type Component = { key: string; label: string; btuh: number };
export type Loads = {
  heating_btuh: number; cooling_sensible_btuh: number; cooling_latent_btuh: number; cooling_total_btuh: number;
  cooling_tons: number; sensible_heat_ratio: number; heating_components: Component[];
  cooling_sensible_components: Component[]; cooling_latent_components: Component[]; hourly_fenestration_btuh: number[];
};
export type RoomResult = Loads & { id: string; name: string; zone: string; peak_cooling_sensible_btuh: number; infiltration_share: number };
export type SurfaceResult = { kind: string; id: string; name: string; room: string; room_name: string; area_ft2: number;
  heating_btuh: number; cooling_btuh: number; r_value: number | null };
export type DefaultUsed = { name: string; value: Json; unit: string; applies_to: string; source: string; confidence: string };
export type Result = {
  building: Loads; zones: (Loads & { id: string; name: string })[]; rooms: RoomResult[]; surfaces: SurfaceResult[];
  infiltration: { method: string; ach50: number | null; leakage_area_in2: number | null; stack_coefficient: number | null;
    wind_coefficient: number | null; heating_cfm: number; cooling_cfm: number };
  design: { heating_outdoor_temp_f: number; cooling_outdoor_temp_f: number; heating_setpoint_f: number; cooling_setpoint_f: number;
    humidity_difference_gr_lb: number; daily_temp_range: string; space_temps_f: { id: string; name: string; heating: number; cooling: number }[] };
  sizing: { cooling_capacity_min_btuh: number; cooling_capacity_max_btuh: number; cooling_sensible_needed_btuh: number;
    cooling_latent_needed_btuh: number; heating_capacity_min_btuh: number; basis: string };
  defaults_used: DefaultUsed[]; assembly_r_values: Record<string, number>;
};
export type Issue = { level: "error" | "warning"; where: string; message: string };
export type ScenarioResult = { id: string; name: string; description: string; cost_usd: number | null; result?: Result; error?: string };
export type CalcOutput = { valid: boolean; issues: Issue[]; baseline: Result | null; scenarios: ScenarioResult[];
  stated_inputs: { path: string; value: number; source: string; confidence: string }[] };

export type RangeMetrics = { heating_btuh: number; cooling_sensible_btuh: number; cooling_latent_btuh: number; cooling_total_btuh: number };
export type RangeItem = { where: string; field: string; value: number; low: number | null; high: number | null; confidence: string;
  source: string; range_basis: string; impact_btuh: number; loads: { low?: Record<string, RangeMetrics>; high?: Record<string, RangeMetrics> } };
export type Ranges = { base: Record<string, RangeMetrics>; items: RangeItem[]; varied: number; not_calculable: number; method: string;
  combined: Record<string, Record<keyof RangeMetrics, { base: number; low: number; high: number }>> };
