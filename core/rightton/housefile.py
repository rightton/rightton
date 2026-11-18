"""The RightTon house file: read, write, apply scenarios, convert to engine inputs.

The format is defined by ``schema/rightton-house.schema.json`` and explained in
``docs/FORMAT.md``. This module holds no load math: it moves inputs across and
applies RightTon's documented defaults (``data/defaults.json``), keeping a list
of every default it used.

A house is handled as plain ``dict`` data, exactly as it is in the file, so that
loading and saving do not change it and unknown ``extensions`` survive.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import data, ducts as duct_math, model as M, psychro, weather
from .assemblies import Assembly, Layer
from .framing import FramingShare, framing_share

FORMAT_VERSION = "1.1.0"  # 1.1: assemblies[].framing
SUPPORTED_MAJOR = 1

SECTION_LISTS = ("assemblies", "zones", "rooms", "spaces", "surfaces", "openings", "equipment", "scenarios")
OUTSIDE_WORDS = {"outdoors": M.OUTSIDE, "ground": M.GROUND, "adiabatic": M.ADIABATIC}
SPACE_KINDS = {
    "vented_attic": "attic_vented", "unvented_attic": "attic_unvented",
    "vented_crawlspace": "crawlspace_vented", "unvented_crawlspace": "crawlspace_unvented",
    "unconditioned_basement": "basement_unconditioned", "garage": "garage",
    "open_porch": "weighted", "custom": "weighted",
}


class HouseFileError(ValueError):
    """The house file cannot be used. The message says where and why."""


# --- Reading and writing ----------------------------------------------------------

def _yaml():
    try:
        import yaml  # noqa: PLC0415
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise HouseFileError("Reading or writing YAML needs the PyYAML package (pip install pyyaml). "
                             "JSON files need nothing extra.") from e
    return yaml


def format_of(path) -> str:
    name = str(path).lower()
    if name.endswith((".yaml", ".yml")):
        return "yaml"
    return "json"


def loads(text: str, fmt: str = "json") -> dict:
    """Parse a house file from text. Key order is kept."""
    try:
        house = _yaml().safe_load(text) if fmt == "yaml" else json.loads(text)
    except Exception as e:  # noqa: BLE001 - any parser error becomes one clear message
        raise HouseFileError(f"The file is not valid {fmt.upper()}: {e}") from e
    if not isinstance(house, dict):
        raise HouseFileError("A house file must be an object with fields such as format_version and rooms.")
    return house


def dumps(house: dict, fmt: str = "json") -> str:
    """Write a house file as text. JSON is the canonical form: two-space indent,
    keys in the order they are in the data, one trailing newline."""
    if fmt == "yaml":
        return _yaml().safe_dump(house, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100)
    return json.dumps(house, indent=2, ensure_ascii=False) + "\n"


def load(path) -> dict:
    return loads(Path(path).read_text(encoding="utf-8"), format_of(path))


def save(house: dict, path) -> None:
    Path(path).write_text(dumps(house, format_of(path)), encoding="utf-8")


# --- Quantities ---------------------------------------------------------------------

def is_wrapped(x) -> bool:
    return isinstance(x, dict) and "value" in x and set(x) <= {"value", "source", "confidence"}


def plain(x):
    """Copy of the data with every {value, source, confidence} replaced by its number."""
    if is_wrapped(x):
        return x["value"]
    if isinstance(x, dict):
        return {k: plain(v) for k, v in x.items()}
    if isinstance(x, list):
        return [plain(v) for v in x]
    return x


def label(item: dict) -> str:
    """How an item is named in messages."""
    if isinstance(item, dict) and item.get("name") and item.get("id"):
        return f'"{item["name"]}" (id {item["id"]})'
    if isinstance(item, dict) and item.get("id"):
        return f'"{item["id"]}"'
    return "item"


def stated_inputs(house: dict) -> list[dict]:
    """Every numeric input in the file with its source and confidence."""
    out = []

    def walk(x, path):
        if is_wrapped(x):
            out.append({"path": path, "value": x["value"], "source": x.get("source", ""),
                        "confidence": x.get("confidence", "default")})
        elif isinstance(x, dict):
            for k, v in x.items():
                if k not in ("extensions", "scenarios", "outline_ft"):
                    walk(v, f"{path}/{k}" if path else k)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                key = v["id"] if isinstance(v, dict) and "id" in v else str(i)
                walk(v, f"{path}/{key}")
        elif isinstance(x, (int, float)) and not isinstance(x, bool) and path and not path.endswith("count"):
            out.append({"path": path, "value": x, "source": "", "confidence": "default"})

    walk({k: v for k, v in house.items() if k != "format_version"}, "")
    return out


# --- Scenarios ----------------------------------------------------------------------

def _step(container, key: str, path: str):
    if isinstance(container, list):
        for item in container:
            if isinstance(item, dict) and item.get("id") == key:
                return item
        if key.isdigit() and int(key) < len(container):
            return container[int(key)]
        raise HouseFileError(f'Scenario path "{path}": nothing with id "{key}" was found there.')
    if isinstance(container, dict):
        if key not in container:
            raise HouseFileError(f'Scenario path "{path}": there is no "{key}" there.')
        return container[key]
    raise HouseFileError(f'Scenario path "{path}": "{key}" is not inside a section or an item.')


def _resolve_parent(house: dict, path: str):
    parts = [p for p in path.split("/") if p]
    if not parts:
        raise HouseFileError("A scenario path is empty.")
    node = house
    for key in parts[:-1]:
        node = _step(node, key, path)
    return node, parts[-1]


def scenario_order(house: dict, scenario_id: str) -> list[dict]:
    """The scenario and everything it includes, in the order changes are applied."""
    scenarios = {s["id"]: s for s in house.get("scenarios", [])}
    order: list[dict] = []

    def visit(sid, trail):
        if sid not in scenarios:
            raise HouseFileError(f'Scenario "{sid}" is not defined in scenarios.')
        if sid in trail:
            raise HouseFileError(f'Scenario "{sid}" includes itself (through {" -> ".join(trail)}).')
        for inc in scenarios[sid].get("includes", []):
            visit(inc, trail + [sid])
        if scenarios[sid] not in order:
            order.append(scenarios[sid])

    visit(scenario_id, [])
    return order


def apply_scenario(house: dict, scenario_id: str) -> dict:
    """A copy of the house with the scenario's changes applied (included scenarios first)."""
    out = copy.deepcopy(house)
    for scenario in scenario_order(house, scenario_id):
        for change in scenario.get("changes", []):
            op = change.get("op")
            if op == "set":
                parent, key = _resolve_parent(out, change["path"])
                if isinstance(parent, list):
                    target = _step(parent, key, change["path"])
                    parent[parent.index(target)] = copy.deepcopy(change["value"])
                else:
                    parent[key] = copy.deepcopy(change["value"])
            elif op == "add":
                node = out
                parts = [p for p in change["section"].split("/") if p]
                for i, key in enumerate(parts):
                    if isinstance(node, dict) and key not in node:
                        node[key] = [] if i == len(parts) - 1 else {}
                    node = _step(node, key, change["section"])
                if not isinstance(node, list):
                    raise HouseFileError(f'Scenario "{scenario["id"]}": "{change["section"]}" is not a list of items.')
                node.append(copy.deepcopy(change["item"]))
            elif op == "remove":
                parent, key = _resolve_parent(out, change["path"])
                if isinstance(parent, list):
                    parent.remove(_step(parent, key, change["path"]))
                else:
                    _step(parent, key, change["path"])
                    del parent[key]
            else:
                raise HouseFileError(f'Scenario "{scenario["id"]}": unknown change "{op}" (use set, add or remove).')
    return out


# --- Conversion to engine inputs ------------------------------------------------------

@dataclass
class Conversion:
    building: M.Building
    defaults_used: list[dict] = field(default_factory=list)  # {name, value, unit, applies_to, source, confidence}
    assembly_r_values: dict[str, float] = field(default_factory=dict)  # by surface id


DEFAULT_ROOF_PITCH = 6.0  # rise per 12, as in data/defaults.json (roof_pitch_rise_per_12)


def assembly_for_surface(asm: dict, surface_type: str, exposed_to_wind: bool,
                         roof_pitch_rise_per_12: float = DEFAULT_ROOF_PITCH) -> Assembly:
    """Build the layered Assembly for an assembly entry as used by one surface."""
    materials = data.materials()
    layers = []
    for i, lay in enumerate(asm.get("layers", [])):
        mat = materials.get(lay.get("material")) if lay.get("material") else None
        if lay.get("material") and mat is None:
            raise HouseFileError(f'Assembly {label(asm)}, layer {i + 1}: material "{lay["material"]}" is not in the '
                                 "materials list. Use an id from the list or give r_value_hr_ft2_f_btu.")
        r_value = lay.get("r_value_hr_ft2_f_btu")
        r_per_inch = lay.get("r_per_inch_hr_ft2_f_btu_in")
        if r_value is None and r_per_inch is None and mat is not None:
            if "r_per_inch_hr_ft2_f_btu_in" in mat and "thickness_in" in lay:
                r_per_inch = mat["r_per_inch_hr_ft2_f_btu_in"]
            elif "r_value_hr_ft2_f_btu" in mat:
                r_value = mat["r_value_hr_ft2_f_btu"]
            elif "typical_thickness_in" in mat:
                r_value = mat["r_per_inch_hr_ft2_f_btu_in"] * mat["typical_thickness_in"]
        framing = lay.get("framing_r_per_inch_hr_ft2_f_btu_in")
        if framing is None and lay.get("framing_material"):
            fm = materials.get(lay["framing_material"])
            if fm is None or "r_per_inch_hr_ft2_f_btu_in" not in fm:
                raise HouseFileError(f'Assembly {label(asm)}, layer {i + 1}: framing_material '
                                     f'"{lay["framing_material"]}" is not a material with an R-value per inch.')
            framing = fm["r_per_inch_hr_ft2_f_btu_in"]
        name = lay.get("name") or (mat["name"] if mat else f"layer {i + 1}")
        if r_value is None and (r_per_inch is None or "thickness_in" not in lay):
            raise HouseFileError(f'Assembly {label(asm)}, layer {i + 1} ("{name}") has no usable R-value. Give '
                                 "material and thickness_in, or r_per_inch_hr_ft2_f_btu_in and thickness_in, "
                                 "or r_value_hr_ft2_f_btu.")
        layers.append(Layer(name=name, thickness_in=lay.get("thickness_in", 0.0), r_per_inch=r_per_inch,
                            r_value=r_value, framing_r_per_inch=framing, source=lay.get("source", "")))
    position = {"wall": "wall", "rim_joist": "wall", "foundation_wall": "wall", "roof": "roof",
                "ceiling": "ceiling", "floor": "floor"}[surface_type]
    return Assembly(name=asm.get("name", asm["id"]), layers=layers, position=position,
                    framing_fraction=framing_fraction(asm, surface_type), exposed_to_wind=exposed_to_wind,
                    roof_pitch_rise_per_12=roof_pitch_rise_per_12 if position == "roof" else 0.0)


def assembly_framing(asm: dict, surface_type: Optional[str] = None) -> Optional[FramingShare]:
    """Framing share worked out from the assembly's framing entry (lumber and spacing), or None."""
    fr = asm.get("framing")
    if not fr:
        return None
    try:
        return framing_share(surface_type or asm.get("type", "wall"), fr["spacing_in"], fr.get("lumber", "custom"),
                             fr.get("width_in"), fr.get("depth_in"), fr.get("allowance_frac"))
    except (ValueError, KeyError) as e:
        raise HouseFileError(f"Assembly {label(asm)}, framing: {e}") from None


def framed_cavities(asm: dict) -> list[tuple[int, int, float]]:
    """(first layer index, last layer index, total thickness in) of each run of consecutive framed
    layers: one framed cavity, possibly split into several fills."""
    runs, start = [], None
    layers = asm.get("layers", [])
    for i, lay in enumerate(layers + [{}]):
        framed = bool(lay.get("framing_material")) or lay.get("framing_r_per_inch_hr_ft2_f_btu_in") is not None
        if framed and start is None:
            start = i
        elif not framed and start is not None:
            runs.append((start, i - 1, round(sum(float(layers[j].get("thickness_in", 0.0)) for j in range(start, i)), 4)))
            start = None
    return runs


def framing_fraction(asm: dict, surface_type: Optional[str] = None) -> float:
    """framing_frac when given (an override), else the share from framing (lumber, spacing), else 0."""
    if asm.get("framing_frac") is not None:
        return asm["framing_frac"]
    share = assembly_framing(asm, surface_type)
    return share.total_frac if share else 0.0


def assembly_r_value(asm: dict, surface_type: str, exposed_to_wind: bool,
                     roof_pitch_rise_per_12: float = DEFAULT_ROOF_PITCH) -> float:
    """R-value (hr-ft2-F/Btu, films included) of an assembly as used by one surface."""
    asm = plain(asm)
    if asm.get("layers"):
        return assembly_for_surface(asm, surface_type, exposed_to_wind, roof_pitch_rise_per_12).r_value()
    if asm.get("r_value_hr_ft2_f_btu") is None:
        raise HouseFileError(f"Assembly {label(asm)} needs layers or r_value_hr_ft2_f_btu.")
    return asm["r_value_hr_ft2_f_btu"]


def to_building(house: dict, scenario: Optional[str] = None) -> Conversion:
    """Engine inputs for the house (or for one of its scenarios).

    Raises HouseFileError for problems that stop the calculation. Run
    ``rightton.validate`` first for a complete, friendlier list.
    """
    if scenario:
        house = apply_scenario(house, scenario)
    h = plain(house)
    dflt = data.defaults()
    used: list[dict] = []

    def default(name, applies_to, value=None):
        d = dflt[name]
        v = d["value"] if value is None else value
        used.append({"name": name, "value": v, "unit": d["unit"], "applies_to": applies_to,
                     "source": d["source"], "confidence": d["confidence"]})
        return v

    def custom_default(name, value, unit, applies_to, source):
        used.append({"name": name, "value": value, "unit": unit, "applies_to": applies_to, "source": source,
                     "confidence": "estimated"})
        return value

    conditions = _conditions(h.get("location", {}), default, custom_default)

    zones = [M.Zone(z["id"], z.get("heating_setpoint_f"), z.get("cooling_setpoint_f"),
                    bool(z.get("radiant_floor_heat", False))) for z in h.get("zones", [])]
    rooms_in = h.get("rooms", [])
    total_area = sum(r["floor_area_ft2"] for r in rooms_in) or 1.0

    def house_total(field_name, default_name):
        """A per-room input, or a house-wide default shared by floor area."""
        if any(field_name in r for r in rooms_in):
            return None
        if default_name == "occupant_count":
            beds = h.get("project", {}).get("bedroom_count")
            if beds is not None:
                return default("occupant_count_from_bedrooms", "all rooms, by floor area", beds + 1.0)
        return default(default_name, "all rooms, by floor area")

    occupants_total = house_total("occupant_count", "occupant_count")
    sensible_total = house_total("internal_sensible_gain_btu_hr", "house_internal_sensible_gain_btu_hr")
    latent_total = house_total("internal_latent_gain_btu_hr", "house_internal_latent_gain_btu_hr")

    rooms = []
    for r in rooms_in:
        share = r["floor_area_ft2"] / total_area

        def per_room(field_name, total):
            return r.get(field_name, 0.0) if total is None else total * share

        if "ceiling_height_ft" not in r:
            default("ceiling_height_ft", f"room {label(r)}")
        rooms.append(M.Room(
            id=r["id"], zone=r["zone"], floor_area_ft2=r["floor_area_ft2"],
            ceiling_height_ft=r.get("ceiling_height_ft", dflt["ceiling_height_ft"]["value"]),
            occupants=per_room("occupant_count", occupants_total),
            internal_sensible_btuh=per_room("internal_sensible_gain_btu_hr", sensible_total),
            internal_latent_btuh=per_room("internal_latent_gain_btu_hr", latent_total),
            below_grade=bool(r.get("below_grade", False)),
            infiltration_share=r.get("infiltration_share_frac")))

    buffers = []
    conditioned_space_volume = 0.0
    for s in h.get("spaces", []):
        if s["type"] == "conditioned":
            if "zone" not in s:
                raise HouseFileError(f'Space {label(s)} is "conditioned", so it must name the zone that conditions it.')
            rooms.append(M.Room(id=s["id"], zone=s["zone"], floor_area_ft2=0.0, ceiling_height_ft=0.0))
            conditioned_space_volume += s.get("volume_ft3", 0.0)
            continue
        b = M.BufferSpace(id=s["id"], kind=SPACE_KINDS[s["type"]], volume_ft3=s.get("volume_ft3", 0.0),
                          vent_sla=s.get("vent_area_per_floor_area_frac"), vent_ach=s.get("vent_air_changes_per_hr"),
                          heating_design_temp_f=s.get("heating_design_temp_f"),
                          cooling_design_temp_f=s.get("cooling_design_temp_f"))
        if s["type"] == "open_porch":
            b.indoor_weight, b.outdoor_weight, b.ground_weight = 0.0, 1.0, 0.0
        elif s["type"] == "custom":
            b.indoor_weight = s.get("indoor_weight_frac", 0.0)
            b.outdoor_weight = s.get("outdoor_weight_frac", 1.0 if "indoor_weight_frac" not in s
                                     and "ground_weight_frac" not in s else 0.0)
            b.ground_weight = s.get("ground_weight_frac", 0.0)
            b.min_temp_f = s.get("min_temp_f")
            b.duct_regain = s.get("duct_regain_frac", 0.0)
        buffers.append(b)

    bldg = M.Building(conditions=conditions, zones=zones, rooms=rooms, buffer_spaces=buffers)
    conv = Conversion(building=bldg, defaults_used=used)
    assemblies = {a["id"]: a for a in h.get("assemblies", [])}

    def side(ref):
        return OUTSIDE_WORDS.get(ref, ref)

    def get_assembly(s):
        ref = s.get("assembly")
        if ref not in assemblies:
            raise HouseFileError(f'Surface {label(s)}: assembly "{ref}" is not defined in assemblies.')
        return assemblies[ref]

    surface_azimuth = {}
    for s in h.get("surfaces", []):
        kind = s["type"]
        surface_azimuth[s["id"]] = s.get("azimuth_deg")
        default_outside = "ground" if kind in ("foundation_wall", "slab") else "outdoors"
        outside = side(s.get("outside", default_outside))
        common = dict(id=s["id"], inside=s["inside"], outside=outside, area_ft2=s.get("area_ft2", 0.0))
        exposed = outside == M.OUTSIDE
        if kind in ("wall", "rim_joist"):
            asm = get_assembly(s)
            r = assembly_r_value(asm, kind, exposed)
            if "solar_absorptance_frac" not in asm and exposed and bldg.is_room(s["inside"]):
                default("solar_absorptance_frac", f"assembly {label(asm)}")
            cladding = asm.get("cladding", "wood")
            bldg.walls.append(M.Wall(
                **common, r_value=r, wall_type="wood_stud" if kind == "rim_joist" else asm.get("construction", "wood_stud"),
                siding=cladding if cladding in ("brick", "stone") else "wood",
                solar_absorptance=asm.get("solar_absorptance_frac", dflt["solar_absorptance_frac"]["value"]),
                is_rim_joist=kind == "rim_joist"))
            conv.assembly_r_values[s["id"]] = r
        elif kind == "foundation_wall":
            r = assembly_r_value(get_assembly(s), kind, False) if s.get("assembly") else None
            ii, ei = s.get("interior_insulation", {}), s.get("exterior_insulation", {})
            if "thickness_in" not in s and r is None:
                default("foundation_wall_thickness_in", f"surface {label(s)}")
            bldg.foundation_walls.append(M.FoundationWall(
                **common, r_value=r, height_ft=s["height_ft"], depth_below_grade_ft=s["depth_below_grade_ft"],
                thickness_in=s.get("thickness_in", dflt["foundation_wall_thickness_in"]["value"]),
                wall_type=s.get("material", "solid_concrete"),
                insulation_interior_r=ii.get("r_value_hr_ft2_f_btu", 0.0),
                insulation_interior_top_ft=ii.get("distance_to_top_ft", 0.0),
                insulation_interior_bottom_ft=ii.get("distance_to_bottom_ft", 0.0),
                insulation_exterior_r=ei.get("r_value_hr_ft2_f_btu", 0.0),
                insulation_exterior_top_ft=ei.get("distance_to_top_ft", 0.0),
                insulation_exterior_bottom_ft=ei.get("distance_to_bottom_ft", 0.0),
                azimuth_deg=s.get("azimuth_deg"), length_ft=s.get("length_ft")))
            if r is not None:
                conv.assembly_r_values[s["id"]] = r
        elif kind == "roof":
            asm = get_assembly(s)
            if "pitch_rise_per_12" not in s:
                default("roof_pitch_rise_per_12", f"surface {label(s)}")
            r = assembly_r_value(asm, kind, True, s.get("pitch_rise_per_12", dflt["roof_pitch_rise_per_12"]["value"]))
            common["outside"] = M.OUTSIDE
            bldg.roofs.append(M.Roof(**common, r_value=r, roof_type=asm.get("roofing", "asphalt_shingles"),
                                     roof_color=asm.get("roof_color", "medium"),
                                     radiant_barrier=bool(asm.get("radiant_barrier", False)),
                                     pitch=s.get("pitch_rise_per_12", dflt["roof_pitch_rise_per_12"]["value"])))
            conv.assembly_r_values[s["id"]] = r
        elif kind in ("ceiling", "floor"):
            r = assembly_r_value(get_assembly(s), kind, exposed)
            bldg.floors.append(M.Floor(**common, r_value=r, is_ceiling=kind == "ceiling"))
            conv.assembly_r_values[s["id"]] = r
        elif kind == "slab":
            pi, ui, xi = (s.get("perimeter_insulation", {}), s.get("under_slab_insulation", {}),
                          s.get("exterior_horizontal_insulation", {}))
            if "thickness_in" not in s:
                default("slab_thickness_in", f"surface {label(s)}")
            bldg.slabs.append(M.Slab(
                id=s["id"], inside=s["inside"], area_ft2=s["area_ft2"], exposed_perimeter_ft=s["exposed_perimeter_ft"],
                thickness_in=s.get("thickness_in", dflt["slab_thickness_in"]["value"]),
                perimeter_insulation_r=pi.get("r_value_hr_ft2_f_btu", 0.0),
                perimeter_insulation_depth_ft=pi.get("depth_ft", 0.0),
                under_slab_insulation_r=ui.get("r_value_hr_ft2_f_btu", 0.0),
                under_slab_insulation_width_ft=ui.get("width_ft", 0.0),
                under_slab_insulation_spans_slab=bool(ui.get("whole_slab", False)),
                exterior_horizontal_insulation_r=xi.get("r_value_hr_ft2_f_btu", 0.0),
                exterior_horizontal_insulation_width_ft=xi.get("width_ft", 0.0),
                exterior_horizontal_insulation_depth_below_grade_ft=xi.get("depth_below_grade_ft", 0.0)))

    glazing = data.glazing()
    for o in h.get("openings", []):
        area = opening_area_ft2(o)
        kind = o["type"]
        storm = o.get("storm_window", "none")
        storm = None if storm == "none" else storm
        if kind == "window":
            u, shgc, layers, gtype = (o.get("u_factor_btu_hr_ft2_f"), o.get("shgc"), o.get("glass_layers"),
                                      o.get("glass_type"))
            if u is None or shgc is None:
                preset = glazing.get(o.get("glazing"))
                if preset is None:
                    raise HouseFileError(f"Window {label(o)} needs u_factor_btu_hr_ft2_f and shgc, or a glazing preset.")
                u = preset["u_factor_btu_hr_ft2_f"] if u is None else u
                shgc = preset["shgc"] if shgc is None else shgc
                layers = preset["glass_layers"] if layers is None else layers
                gtype = preset["glass_type"] if gtype is None else gtype
            azimuth = o.get("azimuth_deg", surface_azimuth.get(o["surface"]))
            shade = o.get("interior_shading")
            ext = o.get("exterior_shading", {})
            screen = o.get("insect_screen")
            hang = o.get("overhang", {})
            if shade is None:
                default("interior_shading_coefficient", f"window {label(o)}")
            bldg.windows.append(M.Window(
                id=o["id"], wall=o["surface"], area_ft2=area, azimuth_deg=0.0 if azimuth is None else azimuth,
                u_factor=u, shgc=shgc, storm=storm,
                interior_shading_type=(shade or {}).get("type"),
                interior_shading_coverage=(shade or {}).get("coverage_frac", 0.5),
                blinds_position=(shade or {}).get("blinds_position", "closed"),
                interior_shading_coefficient=(shade or {}).get("coefficient_frac", 1.0),
                glass_layers=layers, glass_type=gtype if layers else None,
                exterior_shading_type=ext.get("type") if ext.get("type") in ("solar_screens", "solar_film") else None,
                exterior_shading_coefficient=ext.get("coefficient_frac"),
                insect_screen=(screen or {}).get("location"),
                insect_screen_coverage=(screen or {}).get("coverage_frac", 1.0),
                overhang_depth_ft=hang.get("depth_ft", 0.0),
                overhang_to_window_top_ft=hang.get("distance_to_window_top_ft", 0.0),
                overhang_to_window_bottom_ft=hang.get("distance_to_window_bottom_ft", 0.0)))
        elif kind == "door":
            bldg.doors.append(M.Door(id=o["id"], wall=o["surface"], area_ft2=area, r_value=o["r_value_hr_ft2_f_btu"]))
        elif kind == "skylight":
            azimuth = o.get("azimuth_deg", surface_azimuth.get(o["surface"]))
            curb, shaft = o.get("curb", {}), o.get("shaft", {})
            bldg.skylights.append(M.Skylight(
                id=o["id"], roof=o["surface"], area_ft2=area, azimuth_deg=180.0 if azimuth is None else azimuth,
                u_factor=o["u_factor_btu_hr_ft2_f"], shgc=o["shgc"], ceiling=o.get("ceiling"), storm=storm,
                interior_shading_coefficient=o.get("interior_shading_coefficient_frac", 1.0),
                curb_area_ft2=curb.get("area_ft2"), curb_r_value=curb.get("r_value_hr_ft2_f_btu"),
                shaft_area_ft2=shaft.get("area_ft2"), shaft_r_value=shaft.get("r_value_hr_ft2_f_btu")))

    _space_volumes(bldg, h, dflt, default)
    _air(bldg, h, default, dflt, conditioned_space_volume)
    _hvac(bldg, h, default, dflt)

    for e in h.get("equipment", []):
        room = bldg.room(e["room"])
        if room is None:
            raise HouseFileError(f'Equipment {label(e)}: room "{e["room"]}" is not a room or a conditioned space.')
        room.equipment_sensible_btuh += e.get("sensible_heat_btu_hr", 0.0)
        room.equipment_latent_btuh += e.get("latent_heat_btu_hr", 0.0)
    return conv


def opening_area_ft2(o: dict) -> float:
    """Total area of an opening entry: count x (area_ft2, or width_ft x height_ft)."""
    o = plain(o)
    each = o.get("area_ft2")
    if each is None:
        if "width_ft" not in o or "height_ft" not in o:
            raise HouseFileError(f"Opening {label(o)} needs area_ft2, or width_ft and height_ft.")
        each = o["width_ft"] * o["height_ft"]
    return each * o.get("count", 1)


def _conditions(location: dict, default, custom_default) -> M.DesignConditions:
    dc = location.get("design_conditions", {})
    station_id = location.get("weather_station_id")
    heat_sp = dc["heating_setpoint_f"] if "heating_setpoint_f" in dc else default("heating_setpoint_f", "house")
    cool_sp = dc["cooling_setpoint_f"] if "cooling_setpoint_f" in dc else default("cooling_setpoint_f", "house")
    k_soil = (dc["ground_conductivity_btu_hr_ft_f"] if "ground_conductivity_btu_hr_ft_f" in dc
              else default("ground_conductivity_btu_hr_ft_f", "house"))
    rh = dc.get("cooling_indoor_humidity_frac")
    if station_id is not None:
        station = data.weather_stations().get(str(station_id))
        if station is None:
            raise HouseFileError(
                f'location.weather_station_id "{station_id}" is not in RightTon\'s station list. Use a listed station, '
                "or remove it and give heating_outdoor_temp_f, cooling_outdoor_temp_f, daily_temp_range, "
                "humidity_difference_gr_lb and latitude_deg under location.design_conditions.")
        wanted = {f.name for f in dataclasses.fields(weather.Weather)}
        wx = weather.Weather(**{k: v for k, v in station.items() if k in wanted})
        if rh is None:
            default("cooling_indoor_humidity_frac", "house")
        c = weather.design_conditions(wx, heating_setpoint_f=heat_sp, cooling_setpoint_f=cool_sp,
                                      humidity_setpoint_frac=rh, ground_conductivity_btu_h_ft_f=k_soil)
    else:
        needed = ("heating_outdoor_temp_f", "cooling_outdoor_temp_f", "daily_temp_range",
                  "humidity_difference_gr_lb", "latitude_deg")
        missing = [n for n in needed if n not in dc]
        if missing:
            raise HouseFileError("location has no weather_station_id, so location.design_conditions must give: "
                                 + ", ".join(missing) + ".")
        if rh is None:
            rh = default("cooling_indoor_humidity_frac", "house", 0.45 if dc["humidity_difference_gr_lb"] < 0 else 0.5)
        c = M.DesignConditions(
            heating_design_temp_f=dc["heating_outdoor_temp_f"], cooling_design_temp_f=dc["cooling_outdoor_temp_f"],
            daily_temp_range=dc["daily_temp_range"], humidity_difference_grains=dc["humidity_difference_gr_lb"],
            latitude_deg=dc["latitude_deg"], elevation_ft=dc.get("elevation_ft", 0.0),
            heating_setpoint_f=heat_sp, cooling_setpoint_f=cool_sp, humidity_setpoint_frac=rh,
            ground_conductivity_btu_h_ft_f=k_soil)
        src = "RightTon estimate used when no weather station is given"
        p = psychro.standard_pressure_psi(c.elevation_ft)
        w_in = psychro.humidity_ratio_from_rh(cool_sp, rh, p)
        c.cooling_humidity_ratio = w_in + c.humidity_difference_grains / psychro.GRAINS_PER_LB
        if "annual_average_temp_f" not in dc:
            c.annual_avg_drybulb_f = custom_default(
                "annual_average_temp_f", round((c.heating_design_temp_f + c.cooling_design_temp_f) / 2.0, 1), "F",
                "house (only affects unconditioned basements, crawlspaces and garages)",
                src + ": midpoint of the heating and cooling design temperatures")
        for name, offset in (("ground_temp_winter_f", -10.0), ("ground_temp_summer_f", 10.0)):
            if name not in dc:
                annual = dc.get("annual_average_temp_f", c.annual_avg_drybulb_f)
                setattr(c, name, custom_default(name, round(annual + offset, 1), "F",
                                                "house (only affects unconditioned basements and ducts under slabs)",
                                                src + ": annual average temperature -/+ 10 F"))
        if "weather_shielding_factor" not in dc:
            c.wsf = custom_default("weather_shielding_factor", 0.5, "none",
                                   "house (only affects vented attics and crawlspaces)",
                                   src + ": mid-range value")
    # Explicit overrides win over station values
    for key, attr in (("heating_outdoor_temp_f", "heating_design_temp_f"),
                      ("cooling_outdoor_temp_f", "cooling_design_temp_f"),
                      ("daily_temp_range", "daily_temp_range"),
                      ("humidity_difference_gr_lb", "humidity_difference_grains"),
                      ("latitude_deg", "latitude_deg"), ("elevation_ft", "elevation_ft"),
                      ("cooling_indoor_humidity_frac", "humidity_setpoint_frac"),
                      ("cooling_outdoor_humidity_ratio_lb_lb", "cooling_humidity_ratio"),
                      ("annual_average_temp_f", "annual_avg_drybulb_f"),
                      ("ground_temp_winter_f", "ground_temp_winter_f"),
                      ("ground_temp_summer_f", "ground_temp_summer_f"),
                      ("weather_shielding_factor", "wsf")):
        if key in dc:
            setattr(c, attr, dc[key])
    return c


def _space_volumes(bldg: M.Building, h: dict, dflt, default) -> None:
    """Estimate the volume of spaces that do not give one (mirrors the reference's
    Geometry.calculate_zone_volume: attic = footprint x height / 3 from roof pitch;
    others = floor area x height)."""
    heights = dflt["space_height_ft"]["value"]
    kind_of = {s["id"]: s["type"] for s in h.get("spaces", [])}
    for space in bldg.buffer_spaces:
        if space.volume_ft3 or space.kind == "weighted":
            continue
        if space.kind in ("attic_vented", "attic_unvented"):
            roofs = [r for r in bldg.roofs if r.inside == space.id]
            if not roofs:
                space.volume_ft3 = 0.01
                continue
            pitch = sum(r.pitch for r in roofs) / len(roofs)
            footprint = sum(r.area_ft2 for r in roofs) / math.sqrt((pitch / 12.0) ** 2 + 1)
            height = 0.5 * math.sin(math.atan(pitch / 12.0)) * math.sqrt(footprint) if pitch > 0 else 2.0
            space.volume_ft3 = max(footprint * height / 3.0, 0.01)
        else:
            area = sum(s.area_ft2 for s in bldg.slabs if s.inside == space.id)
            if area == 0:
                area = sum(f.area_ft2 for f in bldg.floors if space.id in (f.inside, f.outside))
            wall_heights = [fw.height_ft for fw in bldg.foundation_walls if fw.inside == space.id]
            height = max(wall_heights) if wall_heights else heights[kind_of[space.id]]
            space.volume_ft3 = area * height
        default("space_height_ft", f'space "{space.id}" (volume {space.volume_ft3:.0f} ft3)', round(space.volume_ft3))
        if space.kind == "attic_vented" and space.vent_sla is None and space.vent_ach is None:
            default("vented_attic_vent_area_frac", f'space "{space.id}"')
        if space.kind == "crawlspace_vented" and space.vent_sla is None:
            default("vented_crawlspace_vent_area_frac", f'space "{space.id}"')


def _air(bldg: M.Building, h: dict, default, dflt, conditioned_space_volume: float) -> None:
    air = h.get("air", {})
    inf = air.get("infiltration")
    if inf:
        if "shielding_class" not in inf and inf["method"] == "blower_door":
            default("shielding_class", "air.infiltration")
        if "stories_above_grade" not in inf:
            default("stories_above_grade", "air.infiltration")
        volume = inf.get("volume_ft3")
        if volume is None and conditioned_space_volume and inf["method"] == "blower_door":
            volume = sum(r.floor_area_ft2 * r.ceiling_height_ft for r in bldg.rooms) + conditioned_space_volume
        bldg.infiltration = M.Infiltration(
            method="blower_door" if inf["method"] == "blower_door" else "default_table",
            ach50=inf.get("air_changes_per_hr_at_50pa"), cfm50=inf.get("airflow_cfm_at_50pa"),
            house_pressure_pa=inf.get("test_pressure_pa", 50.0), natural_ach=inf.get("natural_air_changes_per_hr"),
            ela_in2=inf.get("leakage_area_in2"), leakiness=inf.get("leakiness"),
            volume_ft3=volume if inf["method"] == "blower_door" else None, height_ft=inf.get("height_ft"),
            shielding_class=inf.get("shielding_class", dflt["shielding_class"]["value"]),
            exterior_fraction=inf.get("exterior_envelope_frac", 1.0),
            unit_height_above_grade_ft=inf.get("unit_height_above_grade_ft", 0.0),
            site_shielding=inf.get("site_shielding", "normal"), has_fireplace=bool(inf.get("fireplace", False)))
        bldg.stories_above_grade = inf.get("stories_above_grade", dflt["stories_above_grade"]["value"])
        bldg.facility_type = ("single_family_detached" if inf.get("building_type", "detached") == "detached"
                              else "attached")
        if inf["method"] != "blower_door" and inf.get("volume_ft3") is not None:
            bldg.above_grade_volume_ft3 = inf["volume_ft3"]
    for fan in air.get("ventilation", []):
        flow = fan["airflow_cfm"] * fan.get("hours_per_day_hr", 24.0) / 24.0
        bldg.ventilation_fans.append(M.VentilationFan(fan["type"], flow, fan.get("sensible_recovery_frac", 0.0),
                                                      fan.get("latent_recovery_frac", 0.0)))


def _hvac(bldg: M.Building, h: dict, default, dflt) -> None:
    duct_sets = {}
    for d in h.get("air", {}).get("ducts", []):
        duct_sets.setdefault(d["system"], []).append(d)
    for system in h.get("hvac", {}).get("systems", []):
        heating, cooling = system.get("heating", "none"), system.get("cooling", "none")
        heat_defaults = dflt["heating_airflow_cfm_per_ton"]["value"]
        ds = M.DistributionSystem(
            zone=system["zone"], has_heating=heating != "none", has_cooling=cooling != "none",
            heating_cfm_per_ton=system.get("heating_airflow_cfm_per_ton", heat_defaults.get(heating, 240.0)),
            cooling_cfm_per_ton=system.get("cooling_airflow_cfm_per_ton", dflt["cooling_airflow_cfm_per_ton"]["value"]),
            blower_heat_btuh=system.get("blower_heat_btu_hr", 0.0), piping_btuh=system.get("piping_loss_btu_hr", 0.0))
        served_area = sum(r.floor_area_ft2 for r in bldg.zone_rooms(system["zone"]))
        n_returns = max(len(system.get("returns", [])), 1)
        for d in duct_sets.get(system["id"], []):
            fracs = ("supply_leakage_frac" in d) or ("return_leakage_frac" in d)
            cfms = ("supply_leakage_cfm_at_25pa" in d) or ("return_leakage_cfm_at_25pa" in d)
            if fracs and cfms:
                raise HouseFileError(f"Ducts {label(d)}: give leakage either in cfm at 25 Pa or as fractions, not both.")
            if fracs:
                ds.leakage_units = "fraction"
                ds.supply_leakage += d.get("supply_leakage_frac", 0.0)
                ds.return_leakage += d.get("return_leakage_frac", 0.0)
            else:
                ds.supply_leakage += d.get("supply_leakage_cfm_at_25pa", 0.0)
                ds.return_leakage += d.get("return_leakage_cfm_at_25pa", 0.0)
            for i, seg in enumerate(d["segments"]):
                where = f"ducts {label(d)}, segment {i + 1}"
                area = seg.get("surface_area_ft2")
                if area is None:
                    if "share_of_ducts_frac" not in seg:
                        raise HouseFileError(f"{where.capitalize()} needs surface_area_ft2 or share_of_ducts_frac.")
                    if seg["type"] == "supply":
                        per_ft2 = default("duct_supply_area_per_floor_area", where)
                    else:
                        per_ft2 = min(default("duct_return_area_per_floor_area_per_return", where) * n_returns, 0.25)
                    area = per_ft2 * served_area * seg["share_of_ducts_frac"]
                r_eff = seg.get("effective_r_value_hr_ft2_f_btu")
                if r_eff is None:
                    f_rect = default("duct_rectangular_fraction", where)[seg["type"]]
                    r_eff = duct_math.duct_effective_r_value(seg.get("insulation_r_value_hr_ft2_f_btu", 0.0),
                                                             seg["type"], f_rect)
                ds.ducts.append(M.Duct(seg["type"], OUTSIDE_WORDS.get(seg["location"], seg["location"]), area, r_eff))
        bldg.distribution_systems.append(ds)


# --- Conversion from engine inputs (used to convert the reference sample houses) ------

def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return slug or "item"


def from_building(bldg: M.Building, name: str = "", description: str = "") -> dict:
    """A house file equivalent to a Building. Every value is written out, so the
    file reproduces the Building exactly and no RightTon default is involved."""
    c = bldg.conditions
    ids: dict[str, str] = {}
    taken: set[str] = set()

    def new_id(original) -> str:
        if original in ids:
            return ids[original]
        base = _slug(original)
        candidate, n = base, 2
        while candidate in taken:
            candidate, n = f"{base}-{n}", n + 1
        taken.add(candidate)
        ids[original] = candidate
        return candidate

    for item in [*bldg.zones, *bldg.rooms, *bldg.buffer_spaces]:
        new_id(item.id)

    def side(ref, inside=None):
        if ref == inside:  # same place on both sides (e.g. a party wall inside an attic): no heat flow
            return "adiabatic"
        return {M.OUTSIDE: "outdoors", M.GROUND: "ground", M.ADIABATIC: "adiabatic"}.get(ref) or ids[ref]

    assemblies: list[dict] = []
    assembly_ids: dict[str, str] = {}

    def assembly(kind, r_value, **attrs) -> str:
        key = json.dumps([kind, r_value, attrs], sort_keys=True)
        if key not in assembly_ids:
            aid = f"{kind}-assembly-{len(assemblies) + 1}"
            taken.add(aid)
            assemblies.append({"id": aid, "type": kind, "r_value_hr_ft2_f_btu": r_value, **attrs})
            assembly_ids[key] = aid
        return assembly_ids[key]

    house: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "project": {"name": name, "description": description},
        "location": {"design_conditions": {
            "heating_outdoor_temp_f": c.heating_design_temp_f, "cooling_outdoor_temp_f": c.cooling_design_temp_f,
            "daily_temp_range": c.daily_temp_range, "humidity_difference_gr_lb": c.humidity_difference_grains,
            "latitude_deg": c.latitude_deg, "elevation_ft": c.elevation_ft,
            "heating_setpoint_f": c.heating_setpoint_f, "cooling_setpoint_f": c.cooling_setpoint_f,
            "cooling_indoor_humidity_frac": c.humidity_setpoint_frac,
            "ground_conductivity_btu_hr_ft_f": c.ground_conductivity_btu_h_ft_f,
            "cooling_outdoor_humidity_ratio_lb_lb": c.cooling_humidity_ratio,
            "annual_average_temp_f": c.annual_avg_drybulb_f, "ground_temp_winter_f": c.ground_temp_winter_f,
            "ground_temp_summer_f": c.ground_temp_summer_f, "weather_shielding_factor": c.wsf}},
        "assemblies": assemblies,
        "zones": [], "rooms": [], "spaces": [], "surfaces": [], "openings": [],
    }
    for z in bldg.zones:
        zone = {"id": ids[z.id]}
        if z.heating_setpoint_f is not None:
            zone["heating_setpoint_f"] = z.heating_setpoint_f
        if z.cooling_setpoint_f is not None:
            zone["cooling_setpoint_f"] = z.cooling_setpoint_f
        if z.has_radiant_floor:
            zone["radiant_floor_heat"] = True
        house["zones"].append(zone)
    for r in bldg.rooms:
        room = {"id": ids[r.id], "name": r.id, "zone": ids[r.zone], "floor_area_ft2": r.floor_area_ft2,
                "ceiling_height_ft": r.ceiling_height_ft, "occupant_count": r.occupants,
                "internal_sensible_gain_btu_hr": r.internal_sensible_btuh,
                "internal_latent_gain_btu_hr": r.internal_latent_btuh}
        if r.below_grade:
            room["below_grade"] = True
        if r.infiltration_share is not None:
            room["infiltration_share_frac"] = r.infiltration_share
        house["rooms"].append(room)
    reverse_kinds = {v: k for k, v in SPACE_KINDS.items() if k not in ("open_porch", "custom")}
    for b in bldg.buffer_spaces:
        space = {"id": ids[b.id], "name": b.id, "type": reverse_kinds.get(b.kind, "custom"), "volume_ft3": b.volume_ft3}
        if b.kind == "weighted":
            space.update(indoor_weight_frac=b.indoor_weight, outdoor_weight_frac=b.outdoor_weight,
                         ground_weight_frac=b.ground_weight, duct_regain_frac=b.duct_regain)
            if b.min_temp_f is not None:
                space["min_temp_f"] = b.min_temp_f
            del space["volume_ft3"]
        for attr, key in (("vent_sla", "vent_area_per_floor_area_frac"), ("vent_ach", "vent_air_changes_per_hr"),
                          ("heating_design_temp_f", "heating_design_temp_f"),
                          ("cooling_design_temp_f", "cooling_design_temp_f")):
            if getattr(b, attr) is not None:
                space[key] = getattr(b, attr)
        house["spaces"].append(space)

    surfaces = house["surfaces"]
    for w in bldg.walls:
        asm = assembly("wall", w.r, construction=w.wall_type, cladding=w.siding if w.siding in ("brick", "stone") else "wood",
                       solar_absorptance_frac=w.solar_absorptance)
        surfaces.append({"id": new_id(w.id), "type": "rim_joist" if w.is_rim_joist else "wall", "inside": ids[w.inside],
                         "outside": side(w.outside, w.inside), "area_ft2": w.area_ft2, "assembly": asm})
    for fw in bldg.foundation_walls:
        s = {"id": new_id(fw.id), "type": "foundation_wall", "inside": ids[fw.inside], "outside": side(fw.outside, fw.inside),
             "area_ft2": fw.area_ft2, "height_ft": fw.height_ft, "depth_below_grade_ft": fw.depth_below_grade_ft,
             "thickness_in": fw.thickness_in, "material": fw.wall_type}
        if fw.r_value is not None:
            s["assembly"] = assembly("wall", fw.r_value)
        if fw.azimuth_deg is not None:
            s["azimuth_deg"] = fw.azimuth_deg
        if fw.length_ft is not None:
            s["length_ft"] = fw.length_ft
        for prefix, key in (("insulation_interior", "interior_insulation"), ("insulation_exterior", "exterior_insulation")):
            if getattr(fw, prefix + "_r") or getattr(fw, prefix + "_bottom_ft"):
                s[key] = {"r_value_hr_ft2_f_btu": getattr(fw, prefix + "_r"),
                          "distance_to_top_ft": getattr(fw, prefix + "_top_ft"),
                          "distance_to_bottom_ft": getattr(fw, prefix + "_bottom_ft")}
        surfaces.append(s)
    for r in bldg.roofs:
        asm = assembly("roof", r.r, roofing=r.roof_type, roof_color=r.roof_color, radiant_barrier=r.radiant_barrier)
        surfaces.append({"id": new_id(r.id), "type": "roof", "inside": ids[r.inside], "area_ft2": r.area_ft2,
                         "assembly": asm, "pitch_rise_per_12": r.pitch})
    for f in bldg.floors:
        kind = "ceiling" if f.is_ceiling else "floor"
        surfaces.append({"id": new_id(f.id), "type": kind, "inside": ids[f.inside], "outside": side(f.outside, f.inside),
                         "area_ft2": f.area_ft2, "assembly": assembly(kind, f.r)})
    for sl in bldg.slabs:
        s = {"id": new_id(sl.id), "type": "slab", "inside": ids[sl.inside], "area_ft2": sl.area_ft2,
             "exposed_perimeter_ft": sl.exposed_perimeter_ft, "thickness_in": sl.thickness_in}
        if sl.perimeter_insulation_r or sl.perimeter_insulation_depth_ft:
            s["perimeter_insulation"] = {"r_value_hr_ft2_f_btu": sl.perimeter_insulation_r,
                                         "depth_ft": sl.perimeter_insulation_depth_ft}
        if sl.under_slab_insulation_r or sl.under_slab_insulation_width_ft or sl.under_slab_insulation_spans_slab:
            s["under_slab_insulation"] = {"r_value_hr_ft2_f_btu": sl.under_slab_insulation_r,
                                          "width_ft": sl.under_slab_insulation_width_ft,
                                          "whole_slab": sl.under_slab_insulation_spans_slab}
        if sl.exterior_horizontal_insulation_r or sl.exterior_horizontal_insulation_width_ft:
            s["exterior_horizontal_insulation"] = {
                "r_value_hr_ft2_f_btu": sl.exterior_horizontal_insulation_r,
                "width_ft": sl.exterior_horizontal_insulation_width_ft,
                "depth_below_grade_ft": sl.exterior_horizontal_insulation_depth_below_grade_ft}
        surfaces.append(s)

    for w in bldg.windows:
        o = {"id": new_id(w.id), "type": "window", "surface": ids[w.wall], "area_ft2": w.area_ft2,
             "azimuth_deg": w.azimuth_deg, "u_factor_btu_hr_ft2_f": w.u_factor, "shgc": w.shgc}
        if w.glass_layers:
            o["glass_layers"] = w.glass_layers
            o["glass_type"] = w.glass_type or "clear"
        if w.storm:
            o["storm_window"] = w.storm
        if w.interior_shading_type in (None, "other"):
            o["interior_shading"] = {"coefficient_frac": w.interior_shading_coefficient}
        elif w.interior_shading_type != "none":
            o["interior_shading"] = {"type": w.interior_shading_type, "coverage_frac": w.interior_shading_coverage,
                                     "blinds_position": w.blinds_position}
        else:
            o["interior_shading"] = {"coefficient_frac": 1.0}
        if w.exterior_shading_type:
            o["exterior_shading"] = {"type": w.exterior_shading_type}
        elif w.exterior_shading_coefficient is not None:
            o["exterior_shading"] = {"type": "other", "coefficient_frac": w.exterior_shading_coefficient}
        if w.insect_screen:
            o["insect_screen"] = {"location": w.insect_screen, "coverage_frac": w.insect_screen_coverage}
        if w.overhang_depth_ft:
            o["overhang"] = {"depth_ft": w.overhang_depth_ft, "distance_to_window_top_ft": w.overhang_to_window_top_ft,
                             "distance_to_window_bottom_ft": w.overhang_to_window_bottom_ft}
        house["openings"].append(o)
    for d in bldg.doors:
        house["openings"].append({"id": new_id(d.id), "type": "door", "surface": ids[d.wall], "area_ft2": d.area_ft2,
                                  "r_value_hr_ft2_f_btu": d.r_value})
    for sk in bldg.skylights:
        o = {"id": new_id(sk.id), "type": "skylight", "surface": ids[sk.roof], "area_ft2": sk.area_ft2,
             "azimuth_deg": sk.azimuth_deg, "u_factor_btu_hr_ft2_f": sk.u_factor, "shgc": sk.shgc,
             "interior_shading_coefficient_frac": sk.interior_shading_coefficient}
        if sk.ceiling:
            o["ceiling"] = ids[sk.ceiling]
        if sk.storm:
            o["storm_window"] = sk.storm
        if sk.curb_area_ft2 is not None and sk.curb_r_value is not None:
            o["curb"] = {"area_ft2": sk.curb_area_ft2, "r_value_hr_ft2_f_btu": sk.curb_r_value}
        if sk.shaft_area_ft2 is not None and sk.shaft_r_value is not None:
            o["shaft"] = {"area_ft2": sk.shaft_area_ft2, "r_value_hr_ft2_f_btu": sk.shaft_r_value}
        house["openings"].append(o)

    air: dict[str, Any] = {}
    inf = bldg.infiltration
    if inf is not None:
        out = {"method": "blower_door" if inf.method == "blower_door" else "leakiness_estimate"}
        for attr, key in (("ach50", "air_changes_per_hr_at_50pa"), ("cfm50", "airflow_cfm_at_50pa"),
                          ("natural_ach", "natural_air_changes_per_hr"), ("ela_in2", "leakage_area_in2"),
                          ("leakiness", "leakiness"), ("height_ft", "height_ft")):
            if getattr(inf, attr) is not None:
                out[key] = getattr(inf, attr)
        if inf.sla is not None:
            out["leakage_area_in2"] = inf.sla * bldg.cfa_ft2 * 144.0
        if inf.house_pressure_pa != 50.0:
            out["test_pressure_pa"] = inf.house_pressure_pa
        volume = inf.volume_ft3 if inf.method == "blower_door" else bldg.above_grade_volume_ft3
        if volume is not None:
            out["volume_ft3"] = volume
        out.update(shielding_class=inf.shielding_class, stories_above_grade=bldg.stories_above_grade,
                   building_type="detached" if bldg.facility_type == "single_family_detached" else "attached")
        if inf.exterior_fraction != 1.0:
            out["exterior_envelope_frac"] = inf.exterior_fraction
        if inf.unit_height_above_grade_ft > 0 and bldg.facility_type != "single_family_detached":
            out["unit_height_above_grade_ft"] = inf.unit_height_above_grade_ft
        if inf.site_shielding != "normal":
            out["site_shielding"] = inf.site_shielding
        if inf.has_fireplace:
            out["fireplace"] = True
        air["infiltration"] = out
    if bldg.ventilation_fans:
        air["ventilation"] = []
        for i, fan in enumerate(bldg.ventilation_fans, start=1):
            v = {"id": new_id(f"ventilation-{i}"), "type": fan.fan_type, "airflow_cfm": fan.flow_cfm}
            if fan.sensible_effectiveness:
                v["sensible_recovery_frac"] = fan.sensible_effectiveness
            if fan.latent_effectiveness:
                v["latent_recovery_frac"] = fan.latent_effectiveness
            air["ventilation"].append(v)
    systems = []
    for i, ds in enumerate(bldg.distribution_systems, start=1):
        sid = new_id(f"system-{i}")
        system = {"id": sid, "zone": ids[ds.zone], "heating": "furnace" if ds.has_heating else "none",
                  "cooling": "central_ac" if ds.has_cooling else "none",
                  "heating_airflow_cfm_per_ton": ds.heating_cfm_per_ton,
                  "cooling_airflow_cfm_per_ton": ds.cooling_cfm_per_ton}
        if ds.blower_heat_btuh:
            system["blower_heat_btu_hr"] = ds.blower_heat_btuh
        if ds.piping_btuh:
            system["piping_loss_btu_hr"] = ds.piping_btuh
        systems.append(system)
        if ds.ducts:
            d: dict[str, Any] = {"id": new_id(f"ducts-{i}"), "system": sid}
            supply, ret = ds.supply_leakage, ds.return_leakage
            if ds.leakage_units == "fraction":
                d.update(supply_leakage_frac=supply, return_leakage_frac=ret)
            else:
                if ds.leakage_units == "cfm50":
                    supply, ret = (x * (25.0 / 50.0) ** 0.65 for x in (supply, ret))
                d.update(supply_leakage_cfm_at_25pa=supply, return_leakage_cfm_at_25pa=ret)
            d["segments"] = [{"type": seg.duct_type, "location": side(seg.location),
                              "surface_area_ft2": seg.surface_area_ft2 * seg.area_multiplier,
                              "effective_r_value_hr_ft2_f_btu": seg.effective_r_value} for seg in ds.ducts]
            air.setdefault("ducts", []).append(d)
    if air:
        house["air"] = air
    equipment = []
    for r in bldg.rooms:
        if r.equipment_sensible_btuh or r.equipment_latent_btuh:
            equipment.append({"id": new_id(f"equipment-{r.id}"), "type": "other", "room": ids[r.id],
                              "sensible_heat_btu_hr": r.equipment_sensible_btuh,
                              "latent_heat_btu_hr": r.equipment_latent_btuh})
    if equipment:
        house["equipment"] = equipment
    if systems:
        house["hvac"] = {"systems": systems}
    for key in ("spaces", "openings"):
        if not house[key]:
            del house[key]
    return house
