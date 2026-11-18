"""JSON-in, JSON-out entry points for user interfaces.

The web app runs these functions (through Pyodide) and only displays what they
return; it does no load math of its own. Everything here takes and returns plain
JSON-compatible data or JSON text.
"""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from typing import Optional

from . import data, engine, housefile, sensitivity as sensitivity_module, validate as validator, weather
from .housefile import HouseFileError

# Display names and grouping of the load components, in report order.
HEATING_COMPONENTS = [
    ("heat_walls", "Walls"), ("heat_windows", "Windows"), ("heat_skylights", "Skylights"), ("heat_doors", "Doors"),
    ("heat_ceilings", "Ceilings"), ("heat_roofs", "Roofs"), ("heat_floors", "Floors"), ("heat_slabs", "Slabs"),
    ("heat_infiltration", "Air leakage"), ("heat_ventilation", "Ventilation"), ("heat_ducts", "Ducts"),
    ("heat_piping", "Piping"), ("heat_interzone", "From other zones"),
]
COOLING_SENSIBLE_COMPONENTS = [
    ("cool_walls", "Walls"), ("cool_windows", "Windows"), ("cool_aed_excursion", "Windows: peak-hour excursion"),
    ("cool_skylights", "Skylights"), ("cool_doors", "Doors"), ("cool_ceilings", "Ceilings"), ("cool_roofs", "Roofs"),
    ("cool_floors", "Floors"), ("cool_infiltration_sens", "Air leakage"), ("cool_ventilation_sens", "Ventilation"),
    ("cool_internal_sens", "People, appliances, lighting"), ("cool_equipment_sens", "Equipment (e.g. dehumidifier)"),
    ("cool_ducts_sens", "Ducts"), ("cool_blower_heat", "Blower heat"), ("cool_interzone", "From other zones"),
]
COOLING_LATENT_COMPONENTS = [
    ("cool_infiltration_lat", "Air leakage"), ("cool_ventilation_lat", "Ventilation"),
    ("cool_internal_lat", "People and appliances"), ("cool_equipment_lat", "Equipment (e.g. dehumidifier)"),
    ("cool_ducts_lat", "Ducts"),
]

# origin: OpenStudio-HPXML hvac_sizing.rb get_hvac_size_limits (single-speed equipment):
# cooling capacity between 90 % and 115 % of the total cooling load.
COOLING_SIZE_RANGE = (0.90, 1.15)


def _loads_json(loads: engine.Loads) -> dict:
    def group(components):
        return [{"key": key, "label": label, "btuh": round(getattr(loads, key), 1)} for key, label in components
                if abs(getattr(loads, key)) >= 0.05]
    return {
        "heating_btuh": round(loads.heat_total, 1),
        "cooling_sensible_btuh": round(loads.cool_sensible, 1),
        "cooling_latent_btuh": round(loads.cool_latent, 1),
        "cooling_total_btuh": round(loads.cool_total, 1),
        "cooling_tons": round(loads.cool_tons, 3),
        "sensible_heat_ratio": round(loads.sensible_heat_ratio, 3),
        "heating_components": group(HEATING_COMPONENTS),
        "cooling_sensible_components": group(COOLING_SENSIBLE_COMPONENTS),
        "cooling_latent_components": group(COOLING_LATENT_COMPONENTS),
        "hourly_fenestration_btuh": [round(v, 1) for v in loads.hourly_fenestration],
    }


def _result(house: dict, scenario: Optional[str]) -> dict:
    conv = housefile.to_building(house, scenario)
    res = engine.calculate(conv.building)
    h = housefile.plain(housefile.apply_scenario(house, scenario) if scenario else house)
    names = {}
    for section in ("rooms", "spaces", "zones", "surfaces", "openings"):
        for item in h.get(section, []):
            names[item["id"]] = item.get("name") or item["id"]
    zone_of = {r.id: r.zone for r in conv.building.rooms}
    inf = res.infiltration
    total = res.building
    lo, hi = COOLING_SIZE_RANGE
    return {
        "building": _loads_json(total),
        "zones": [{"id": zid, "name": names.get(zid, zid), **_loads_json(loads)} for zid, loads in res.zones.items()],
        "rooms": [{"id": rid, "name": names.get(rid, rid), "zone": zone_of[rid],
                   "peak_cooling_sensible_btuh": round(res.room_peak_cool_sensible[rid], 1),
                   "infiltration_share": round(res.room_wall_area_ratio[rid], 4), **_loads_json(loads)}
                  for rid, loads in res.rooms.items()],
        "surfaces": [{"kind": d.kind, "id": d.id, "name": names.get(d.id, d.id), "room": d.room,
                      "room_name": names.get(d.room, d.room), "area_ft2": round(d.area_ft2, 1),
                      "heating_btuh": round(d.heat_btuh, 1), "cooling_btuh": round(d.cool_btuh, 1),
                      "r_value": round(conv.assembly_r_values[d.id], 2) if d.id in conv.assembly_r_values else None}
                     for d in res.surfaces],
        "infiltration": {
            "method": inf.method,
            "ach50": None if inf.ach50 is None else round(inf.ach50, 2),
            "leakage_area_in2": None if inf.ela_in2 is None else round(inf.ela_in2, 1),
            "stack_coefficient": inf.stack_coefficient, "wind_coefficient": inf.wind_coefficient,
            "heating_cfm": round(inf.net_heating_cfm, 1), "cooling_cfm": round(inf.net_cooling_cfm, 1),
        },
        "design": {
            "heating_outdoor_temp_f": conv.building.conditions.heating_design_temp_f,
            "cooling_outdoor_temp_f": conv.building.conditions.cooling_design_temp_f,
            "heating_setpoint_f": conv.building.conditions.heating_setpoint_f,
            "cooling_setpoint_f": conv.building.conditions.cooling_setpoint_f,
            "humidity_difference_gr_lb": conv.building.conditions.humidity_difference_grains,
            "daily_temp_range": conv.building.conditions.daily_temp_range,
            "space_temps_f": [{"id": sid, "name": names.get(sid, sid), "heating": round(res.heating_design_temps[sid], 1),
                               "cooling": round(res.cooling_design_temps[sid], 1)} for sid in res.heating_design_temps],
        },
        "sizing": {
            "cooling_capacity_min_btuh": round(total.cool_total * lo), "cooling_capacity_max_btuh": round(total.cool_total * hi),
            "cooling_sensible_needed_btuh": round(total.cool_sensible), "cooling_latent_needed_btuh": round(max(total.cool_latent, 0.0)),
            "heating_capacity_min_btuh": round(total.heat_total),
            "basis": "Cooling equipment between 90 % and 115 % of the total cooling load at design conditions "
                     "(the single-speed sizing limits used by OpenStudio-HPXML); heating output at least the heating load.",
        },
        "defaults_used": conv.defaults_used,
        "assembly_r_values": {k: round(v, 2) for k, v in conv.assembly_r_values.items()},
    }


def validate(house: dict) -> dict:
    issues = validator.validate(house)
    return {"valid": not any(i.level == "error" for i in issues), "issues": [dataclasses.asdict(i) for i in issues]}


def calculate(house: dict) -> dict:
    """Validate, then calculate the baseline and every scenario.

    Returns {"valid", "issues", "baseline", "scenarios": [...], "stated_inputs"}; "baseline" is None when the
    file has errors. A scenario that cannot be calculated carries "error" instead of "result".
    """
    out = validate(house)
    out.update(baseline=None, scenarios=[], stated_inputs=[])
    if not out["valid"]:
        return out
    try:
        out["baseline"] = _result(house, None)
    except (HouseFileError, ValueError, ZeroDivisionError) as e:
        out["valid"] = False
        out["issues"].insert(0, {"level": "error", "where": "", "message": f"The house could not be calculated: {e}"})
        return out
    out["stated_inputs"] = housefile.stated_inputs(house)
    for sc in house.get("scenarios", []):
        entry = {"id": sc["id"], "name": sc.get("name") or sc["id"], "description": sc.get("description", ""),
                 "cost_usd": housefile.plain(sc.get("cost_usd"))}
        try:
            entry["result"] = _result(house, sc["id"])
        except (HouseFileError, ValueError, ZeroDivisionError) as e:
            entry["error"] = str(e)
        out["scenarios"].append(entry)
    return out


def sensitivity(house: dict) -> dict:
    """Input confidence: load ranges from the inputs that were not measured (see rightton.sensitivity)."""
    return sensitivity_module.analyze(house)


def assembly(asm: dict) -> dict:
    """R-value of one assembly entry, with the layer-by-layer build-up, for the layer builder."""
    asm = housefile.plain(asm)
    kind = asm.get("type", "wall")
    try:
        if not asm.get("layers"):
            r = housefile.assembly_r_value(asm, kind, True)
            return {"ok": True, "r_value": round(r, 2), "u_factor": round(1.0 / r, 4), "layers": [], "from_layers": False}
        built = housefile.assembly_for_surface(asm, kind, True)
        share = housefile.assembly_framing(asm)
        framing_info = None if share is None else {
            "width_in": share.width_in, "depth_in": share.depth_in, "spacing_in": share.spacing_in,
            "member_frac": round(share.member_frac, 4), "allowance_frac": round(share.allowance_frac, 4),
            "allowance_overridden": share.allowance_overridden, "total_frac": round(share.total_frac, 4),
            "overridden_by_framing_frac": asm.get("framing_frac") is not None, "source": share.source}
        sheltered = housefile.assembly_for_surface(asm, kind, False)
        cavity, framing = built.path_r_values()
        return {
            "ok": True, "from_layers": True,
            "r_value": round(built.r_value(), 2), "u_factor": round(built.u_factor(), 4),
            "r_value_sheltered": round(sheltered.r_value(), 2),
            "cavity_path_r": round(cavity, 2), "framing_path_r": round(framing, 2),
            "film_inside_r": round(built.film_inside_r, 2), "film_outside_r": round(built.film_outside_r, 2),
            "framing_frac_used": round(built.framing_fraction, 4), "framing": framing_info,
            "layers": [{"name": lay.name, "r_value": round(lay.cavity_r, 2),
                        "framing_r_value": round(lay.framing_r, 2) if lay.framing_r_per_inch is not None else None}
                       for lay in built.layers],
        }
    except (HouseFileError, ValueError, KeyError, TypeError, ZeroDivisionError) as e:
        return {"ok": False, "error": str(e)}


def library() -> dict:
    """Everything the interface needs to build its forms and pick lists."""
    return {
        "format_version": housefile.FORMAT_VERSION,
        "schema": data.schema(),
        "materials": list(data.materials().values()),
        "material_categories": [{"id": cid, "name": name} for cid, name in data.material_categories().items()],
        "glazing": list(data.glazing().values()),
        "framing": {"lumber": data.framing()["lumber"], "spacings_in": data.framing()["spacings_in"]},
        "stations": [{"id": sid, "name": s["city"], "state": s.get("state", ""), "heating_f": s["heating_drybulb_f"],
                      "cooling_f": s["cooling_drybulb_f"], "latitude_deg": s["latitude_deg"]}
                     for sid, s in data.weather_stations().items()],
        "defaults": data.defaults(),
    }


def design_conditions_from_epw(epw_text: str) -> dict:
    """Read an EPW weather file (as text) and return fields for location.design_conditions,
    each with its source, plus the station name."""
    fd, path = tempfile.mkstemp(suffix=".epw")
    try:
        with os.fdopen(fd, "w", encoding="latin-1", newline="") as f:
            f.write(epw_text)
        wx = weather.read_epw(path)
    finally:
        os.unlink(path)
    dc = weather.design_conditions(wx)
    source = f"EPW weather file: {wx.city} (WMO {wx.wmo})"

    def q(value, digits):
        return {"value": round(value, digits), "source": source, "confidence": "default"}

    return {
        "weather_station_name": wx.city,
        "design_conditions": {
            "heating_outdoor_temp_f": q(dc.heating_design_temp_f, 2), "cooling_outdoor_temp_f": q(dc.cooling_design_temp_f, 2),
            "daily_temp_range": dc.daily_temp_range, "humidity_difference_gr_lb": q(dc.humidity_difference_grains, 1),
            "latitude_deg": q(dc.latitude_deg, 2), "elevation_ft": q(dc.elevation_ft, 0),
            "cooling_indoor_humidity_frac": q(dc.humidity_setpoint_frac, 2),
            "cooling_outdoor_humidity_ratio_lb_lb": q(dc.cooling_humidity_ratio, 5),
            "annual_average_temp_f": q(dc.annual_avg_drybulb_f, 1), "ground_temp_winter_f": q(dc.ground_temp_winter_f, 1),
            "ground_temp_summer_f": q(dc.ground_temp_summer_f, 1), "weather_shielding_factor": q(dc.wsf, 2),
        },
    }


def call(name: str, payload_json: str) -> str:
    """Single text-in, text-out entry point: call one of the functions above by name."""
    functions = {"validate": validate, "calculate": calculate, "assembly": assembly, "sensitivity": sensitivity,
                 "library": lambda _: library(), "design_conditions_from_epw": design_conditions_from_epw,
                 "to_json": lambda p: housefile.dumps(housefile.loads(p["text"], p.get("format", "json"))),
                 "to_yaml": lambda house: housefile.dumps(house, "yaml")}
    try:
        return json.dumps({"ok": True, "result": functions[name](json.loads(payload_json))})
    except HouseFileError as e:
        return json.dumps({"ok": False, "error": str(e)})
    except Exception as e:  # noqa: BLE001 - reported to the interface rather than lost in a worker
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})
