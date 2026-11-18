"""Check a RightTon house file and explain every problem in plain English.

    python -m rightton.validate house.rtn.json
    python -m rightton.validate house.rtn.yaml --json

Two layers of checks:

1. The published JSON Schema (``schema/rightton-house.schema.json``): field names,
   types, allowed values, required fields. The checker here understands the part
   of JSON Schema the house schema uses and words its findings for people.
2. Checks a schema cannot express: every reference resolves, ids are unique,
   windows fit in their walls, every room belongs to a zone, scenarios apply.

Each finding says where it is and how to fix it.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from dataclasses import asdict, dataclass
from typing import Optional

from . import data, housefile
from .housefile import HouseFileError, label, plain

OUTSIDE_WORDS = ("outdoors", "ground", "adiabatic")


@dataclass
class Issue:
    level: str  # "error" or "warning"
    where: str  # human-readable location
    message: str  # what is wrong and how to fix it

    def __str__(self) -> str:
        return f"{self.level.upper()}: {self.where}: {self.message}" if self.where else \
            f"{self.level.upper()}: {self.message}"


# --- Layer 1: schema ---------------------------------------------------------------

def _type_name(x) -> str:
    if isinstance(x, bool):
        return "true/false"
    if isinstance(x, (int, float)):
        return "a number"
    if isinstance(x, str):
        return "text"
    if isinstance(x, list):
        return "a list"
    if isinstance(x, dict):
        return "an object"
    return "empty (null)"


_TYPE_WORDS = {"string": "text (in quotes)", "number": "a number", "integer": "a whole number",
               "boolean": "true or false", "object": "an object ({...})", "array": "a list ([...])"}


def _is_type(x, t: str) -> bool:
    if t == "string":
        return isinstance(x, str)
    if t == "number":
        return isinstance(x, (int, float)) and not isinstance(x, bool)
    if t == "integer":
        return isinstance(x, int) and not isinstance(x, bool)
    if t == "boolean":
        return isinstance(x, bool)
    if t == "object":
        return isinstance(x, dict)
    if t == "array":
        return isinstance(x, list)
    return True


def _join(path: str, key: str) -> str:
    return f"{path} > {key}" if path else key


def _item_path(path: str, index: int, item) -> str:
    if isinstance(item, dict) and item.get("id"):
        return f"{path} > {label(item)}"
    return f"{path} > item {index + 1}"


class _SchemaChecker:
    def __init__(self, schema: dict):
        self.root = schema
        self.issues: list[Issue] = []

    def error(self, where: str, message: str) -> None:
        self.issues.append(Issue("error", where, message))

    def resolve(self, schema: dict) -> dict:
        while "$ref" in schema:
            target = self.root
            for part in schema["$ref"].lstrip("#/").split("/"):
                target = target[part]
            merged = dict(target)
            merged.update({k: v for k, v in schema.items() if k != "$ref"})
            schema = merged
        return schema

    def check(self, value, schema: dict, path: str) -> None:
        raw = schema
        schema = self.resolve(schema)
        if raw.get("$ref") == "#/$defs/quantity":
            self.check_quantity(value, schema, path)
            return
        if raw.get("$ref") == "#/$defs/id":
            if not isinstance(value, str) or not re.match(schema["pattern"], value):
                self.error(path, f"{json.dumps(value)} is not a valid id. Ids use lowercase letters, digits, hyphens "
                                 'and underscores, and start with a letter or digit (for example "north-wall").')
            return
        if "oneOf" in schema and "x-discriminator" in schema:
            self.check_discriminated(value, schema, path)
            return
        if "const" in schema:
            if value != schema["const"]:
                self.error(path, f"must be {json.dumps(schema['const'])}, not {json.dumps(value)}.")
            return
        expected = schema.get("type")
        if expected and not _is_type(value, expected):
            self.error(path, f"must be {_TYPE_WORDS[expected]}, but it is {_type_name(value)}"
                             + (f" ({json.dumps(value)})." if not isinstance(value, (dict, list)) else "."))
            return
        if "enum" in schema and value not in schema["enum"]:
            close = difflib.get_close_matches(str(value), [str(v) for v in schema["enum"]], n=1)
            hint = f' Did you mean "{close[0]}"?' if close else ""
            self.error(path, f"{json.dumps(value)} is not one of the allowed values: "
                             + ", ".join(str(v) for v in schema["enum"]) + "." + hint)
        if "pattern" in schema and isinstance(value, str) and not re.match(schema["pattern"], value):
            self.error(path, f"{json.dumps(value)} does not have the expected form ({schema.get('description', '')})")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                self.error(path, f"{value} is too small; the smallest allowed value is {schema['minimum']}.")
            if "maximum" in schema and value > schema["maximum"]:
                self.error(path, f"{value} is too large; the largest allowed value is {schema['maximum']}.")
        if isinstance(value, list):
            if len(value) < schema.get("minItems", 0):
                self.error(path, f"needs at least {schema['minItems']} item(s); it has {len(value)}.")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                self.error(path, f"may have at most {schema['maxItems']} item(s); it has {len(value)}.")
            if "items" in schema:
                for i, item in enumerate(value):
                    self.check(item, schema["items"], _item_path(path, i, item))
        if isinstance(value, dict) and "properties" in schema:
            self.check_object(value, schema, path)

    def check_object(self, value: dict, schema: dict, path: str) -> None:
        props = schema["properties"]
        for name in schema.get("required", []):
            if name not in value:
                desc = self.resolve(props[name]).get("description", "")
                self.error(path, f'is missing "{name}". Add it. ({desc})' if desc else f'is missing "{name}". Add it.')
        for key, item in value.items():
            if key in props:
                self.check(item, props[key], _join(path, key))
            elif schema.get("additionalProperties") is False:
                self.error(path, f'"{key}" is not a field here.' + self.suggest(key, props))

    @staticmethod
    def suggest(key: str, props: dict) -> str:
        with_unit = [p for p in props if p.startswith(key + "_")]
        if with_unit:
            return (f' Field names carry their unit: use "{with_unit[0]}"' +
                    (f' (or {", ".join(json.dumps(p) for p in with_unit[1:3])})' if len(with_unit) > 1 else "") + ".")
        close = difflib.get_close_matches(key, list(props), n=1, cutoff=0.6)
        if close:
            return f' Did you mean "{close[0]}"?'
        return " Allowed fields: " + ", ".join(props) + "."

    def check_quantity(self, value, schema: dict, path: str) -> None:
        number = value
        if isinstance(value, dict):
            extra = set(value) - {"value", "source", "confidence"}
            if "value" not in value:
                self.error(path, 'is written as an object, so it needs a "value" (the number), optionally with '
                                 '"source" and "confidence".')
                return
            if extra:
                self.error(path, f'has unexpected field(s) {", ".join(sorted(extra))}; a number with its source is '
                                 'written {"value": ..., "source": "...", "confidence": "measured"}.')
            if "confidence" in value and value["confidence"] not in ("measured", "estimated", "default"):
                self.error(path, f'confidence {json.dumps(value["confidence"])} must be "measured", "estimated" or '
                                 '"default".')
            if "source" in value and not isinstance(value["source"], str):
                self.error(path, "source must be text.")
            number = value["value"]
        if not _is_type(number, "number"):
            unit = schema.get("x-unit")
            self.error(path, f"must be a number{f' ({unit})' if unit else ''}, without units or quotes; "
                             f"it is {_type_name(number)}" + (f" ({json.dumps(number)})." if not isinstance(number, (dict, list)) else "."))
            return
        if "x-min" in schema and number < schema["x-min"]:
            self.error(path, f"{number} is too small; it cannot be less than {schema['x-min']}.")
        if "x-max" in schema and number > schema["x-max"]:
            self.error(path, f"{number} is too large; it cannot be more than {schema['x-max']}"
                             + (" (fractions are written 0 to 1, not as percent)." if schema["x-max"] <= 1 else "."))

    def check_discriminated(self, value, schema: dict, path: str) -> None:
        key = schema["x-discriminator"]
        branches = {b["properties"][key]["const"]: b for b in schema["oneOf"]}
        if not isinstance(value, dict):
            self.error(path, f"must be an object ({{...}}), but it is {_type_name(value)}.")
            return
        kind = value.get(key)
        if kind not in branches:
            close = difflib.get_close_matches(str(kind), list(branches), n=1)
            self.error(path, (f'is missing "{key}".' if kind is None else f'"{key}" is {json.dumps(kind)}.')
                       + f' "{key}" must be one of: ' + ", ".join(branches) + "."
                       + (f' Did you mean "{close[0]}"?' if close else ""))
            return
        self.check_object(value, branches[kind], path)


def check_schema(house, schema: Optional[dict] = None) -> list[Issue]:
    checker = _SchemaChecker(schema or data.schema())
    if not isinstance(house, dict):
        return [Issue("error", "", "A house file must be an object with fields such as format_version and rooms.")]
    checker.check(house, checker.root, "")
    return checker.issues


# --- Layer 2: things a schema cannot express ------------------------------------------

def _items(h: dict, section: str) -> list[dict]:
    node = h
    for part in section.split("/"):
        node = node.get(part, {}) if isinstance(node, dict) else {}
    return [x for x in node if isinstance(x, dict)] if isinstance(node, list) else []


ID_SECTIONS = ("assemblies", "glazings", "zones", "rooms", "spaces", "surfaces", "openings", "air/ventilation", "air/ducts",
               "equipment", "hvac/systems", "scenarios")


def check_meaning(house: dict) -> list[Issue]:
    """Checks beyond the schema. Assumes the file passed the schema check well enough
    to be read; anything unreadable is skipped rather than crashing."""
    issues: list[Issue] = []
    h = plain(house)

    def error(where, message):
        issues.append(Issue("error", where, message))

    def warn(where, message):
        issues.append(Issue("warning", where, message))

    version = str(h.get("format_version", ""))
    if version and version.split(".")[0].isdigit() and int(version.split(".")[0]) != housefile.SUPPORTED_MAJOR:
        error("format_version", f"this file is version {version}; this reader handles version "
                                f"{housefile.SUPPORTED_MAJOR}.x. Convert the file or use a matching RightTon release.")

    # Unique ids
    seen: dict[str, str] = {}
    for section in ID_SECTIONS:
        for item in _items(h, section):
            if "id" not in item:
                continue
            where = f"{section.replace('/', ' > ')} > {label(item)}"
            if item["id"] in seen:
                error(where, f'the id "{item["id"]}" is already used in {seen[item["id"]]}. Ids must be unique across '
                             "the whole file; rename one of them.")
            elif item["id"] in OUTSIDE_WORDS:
                error(where, f'"{item["id"]}" is a reserved word and cannot be used as an id.')
            else:
                seen[item["id"]] = section.replace("/", " > ")

    zones = {z["id"]: z for z in _items(h, "zones") if "id" in z}
    rooms = {r["id"]: r for r in _items(h, "rooms") if "id" in r}
    spaces = {s["id"]: s for s in _items(h, "spaces") if "id" in s}
    assemblies = {a["id"]: a for a in _items(h, "assemblies") if "id" in a}
    surfaces = {s["id"]: s for s in _items(h, "surfaces") if "id" in s}
    systems = {s["id"]: s for s in _items(h, "hvac/systems") if "id" in s}
    conditioned_spaces = {k for k, s in spaces.items() if s.get("type") == "conditioned"}
    places = set(rooms) | set(spaces)

    def known(kind, options):
        return ("Defined " + kind + ": " + ", ".join(sorted(options)) + ".") if options else f"No {kind} are defined yet."

    # Rooms and zones
    for r in rooms.values():
        if r.get("zone") is not None and r["zone"] not in zones:
            error(f"rooms > {label(r)} > zone", f'zone "{r["zone"]}" is not defined in zones. Add a zone with that '
                                                 f"id or fix the reference. {known('zones', zones)}")
    for z in zones.values():
        if not any(r.get("zone") == z["id"] for r in rooms.values()):
            warn(f"zones > {label(z)}", "no room belongs to this zone, so it will have no load. Remove it or assign rooms to it.")
    for s in spaces.values():
        where = f"spaces > {label(s)}"
        if s.get("type") == "conditioned":
            if "zone" not in s:
                error(where, 'a "conditioned" space must name the zone that conditions it: add "zone".')
            elif s["zone"] not in zones:
                error(f"{where} > zone", f'zone "{s["zone"]}" is not defined in zones. {known("zones", zones)}')
        if s.get("type") == "custom" and not any(k in s for k in ("heating_design_temp_f", "cooling_design_temp_f")):
            weights = [s.get(k, 0.0) for k in ("indoor_weight_frac", "outdoor_weight_frac", "ground_weight_frac")]
            if any(k in s for k in ("indoor_weight_frac", "outdoor_weight_frac", "ground_weight_frac")) \
                    and abs(sum(weights) - 1.0) > 0.01:
                warn(where, f"the indoor, outdoor and ground weights add up to {sum(weights):g}; they should add up to 1.")

    # Assemblies
    for a in assemblies.values():
        where = f"assemblies > {label(a)}"
        has_layers, has_r = bool(a.get("layers")), a.get("r_value_hr_ft2_f_btu") is not None
        if not has_layers and not has_r:
            error(where, "needs either layers (a list, inside to outside) or r_value_hr_ft2_f_btu for the whole assembly.")
        elif has_layers and has_r:
            warn(where, "has both layers and r_value_hr_ft2_f_btu; the layers are used and the R-value is ignored. Remove one.")
        if has_layers and a.get("type") in ("wall", "roof", "ceiling", "floor"):
            try:
                r = housefile.assembly_r_value(a, a["type"], True)
                if r > 100:
                    warn(where, f"works out to R-{r:.0f}, which is unusually high. Check thicknesses (inches) and R-values.")
            except HouseFileError as e:
                error(where, str(e))
            except (KeyError, TypeError, ValueError):
                pass  # already reported by the schema check
        if a.get("framing") and has_layers:
            try:
                share = housefile.assembly_framing(a)
            except HouseFileError as e:
                error(f"{where} > framing", str(e))
                share = None
            if share is not None:
                for first, last, depth_in in housefile.framed_cavities(a):
                    span = f"layers {first + 1} to {last + 1}" if last > first else f"layer {first + 1}"
                    if depth_in > share.depth_in + 0.01:
                        error(where, f"the framed {span} add up to {depth_in:g} in, more than the {share.depth_in:g} in "
                                     "cavity of the framing. Make the fills thinner or the framing deeper.")
                    elif depth_in < share.depth_in - 0.01:
                        warn(where, f"the framed {span} add up to {depth_in:g} in, less than the {share.depth_in:g} in "
                                    "cavity of the framing. Add a framed air_space_closed layer for the rest of the "
                                    "depth, or check the thicknesses.")
        if a.get("framing") and has_layers and not any(
                l.get("framing_material") or l.get("framing_r_per_inch_hr_ft2_f_btu_in") is not None for l in a["layers"]):
            warn(f"{where} > framing", "framing is given but no layer is framed, so it has no effect. Mark the cavity "
                                       "layer with framing_material.")

    # Surfaces
    opening_area: dict[str, float] = {}
    for o in _items(h, "openings"):
        try:
            opening_area[o.get("surface")] = opening_area.get(o.get("surface"), 0.0) + housefile.opening_area_ft2(o)
        except (HouseFileError, TypeError):
            pass
    surfaces_of: dict[str, int] = {}
    for s in surfaces.values():
        where = f"surfaces > {label(s)}"
        kind = s.get("type")
        inside = s.get("inside")
        if inside is not None and inside not in places:
            error(f"{where} > inside", f'"{inside}" is not the id of a room or a space. {known("rooms and spaces", places)}')
        elif inside is not None:
            surfaces_of[inside] = surfaces_of.get(inside, 0) + 1
        outside = s.get("outside")
        if outside is not None:
            if outside not in OUTSIDE_WORDS and outside not in places:
                error(f"{where} > outside", f'"{outside}" must be "outdoors", "ground", "adiabatic", or the id of a '
                                            f"room or space. {known('rooms and spaces', places)}")
            elif outside == inside:
                error(f"{where} > outside", "is the same as inside. A surface separates two different places.")
            elif outside in places:
                surfaces_of[outside] = surfaces_of.get(outside, 0) + 1
            if kind == "roof" and outside != "outdoors":
                error(f"{where} > outside", 'a roof always faces "outdoors"; remove "outside".')
        if inside in places and inside not in rooms and inside not in conditioned_spaces \
                and outside in places and outside not in spaces:
            warn(where, f'"inside" is the unconditioned space "{inside}" and "outside" is the room "{outside}". It '
                        "works, but a surface between a room and a space is clearer with the room as inside.")
        ref = s.get("assembly")
        if ref is not None:
            if ref not in assemblies:
                error(f"{where} > assembly", f'assembly "{ref}" is not defined in assemblies. Add an assembly with that '
                                             f"id or fix the reference. {known('assemblies', assemblies)}")
            else:
                wanted = {"wall": "wall", "rim_joist": "wall", "foundation_wall": "wall", "roof": "roof",
                          "ceiling": "ceiling", "floor": "floor"}.get(kind)
                got = assemblies[ref].get("type")
                if wanted and got and got != wanted and {wanted, got} != {"ceiling", "floor"}:
                    warn(f"{where} > assembly", f'this {kind} uses assembly "{ref}", which is described as a {got} '
                                                 "assembly. Check that the right assembly is referenced.")
        if kind == "foundation_wall" and isinstance(s.get("height_ft"), (int, float)) \
                and isinstance(s.get("depth_below_grade_ft"), (int, float)) and s["depth_below_grade_ft"] > s["height_ft"]:
            error(where, f'depth_below_grade_ft ({s["depth_below_grade_ft"]:g}) is more than height_ft '
                         f'({s["height_ft"]:g}). The depth below grade is the buried part of the wall height.')
        area = s.get("area_ft2")
        if isinstance(area, (int, float)) and opening_area.get(s["id"], 0.0) > area + 1e-6:
            error(where, f'its windows, doors and skylights add up to {opening_area[s["id"]]:.1f} ft2, more than the '
                         f"surface's own area_ft2 of {area:g}. area_ft2 is the gross area including openings; "
                         "increase it, or check each opening's size and count.")
    for r in rooms.values():
        if not surfaces_of.get(r["id"]):
            warn(f"rooms > {label(r)}", "no surface names this room as inside or outside, so it has no walls, ceiling "
                                        "or floor in the calculation. Add its surfaces (interior rooms can be left bare).")

    # Glazings library
    glazing = data.glazing()
    own_glazings = {g["id"]: g for g in _items(h, "glazings") if "id" in g}
    for gid, g in own_glazings.items():
        where = f"glazings > {label(g)}"
        if gid in glazing:
            warn(where, f'has the same id as the RightTon preset "{gid}"; windows naming it get your values, not the '
                        "preset's. Rename it if that is not what you meant.")
        u = g.get("u_factor_btu_hr_ft2_f")
        if isinstance(u, (int, float)) and (u < 0.1 or u > 1.5):
            warn(where, f"a whole-window U-factor of {u:g} is unusual (labels run from about 0.15 to 1.3). Check that "
                        "it is the U-factor, not the R-value or a metric value.")

    # Openings
    for o in _items(h, "openings"):
        where = f"openings > {label(o)}"
        kind = o.get("type")
        target = surfaces.get(o.get("surface"))
        if o.get("surface") is not None and target is None:
            error(f"{where} > surface", f'"{o["surface"]}" is not the id of a surface. {known("surfaces", surfaces)}')
        elif target is not None:
            allowed = {"window": ("wall", "foundation_wall"), "door": ("wall", "foundation_wall"),
                       "skylight": ("roof",)}.get(kind, ())
            if allowed and target.get("type") not in allowed:
                error(f"{where} > surface", f'a {kind} must be in a {" or ".join(allowed).replace("_", " ")}; '
                                            f'"{o["surface"]}" is a {str(target.get("type")).replace("_", " ")}.')
            if kind in ("window", "skylight") and "azimuth_deg" not in o and "azimuth_deg" not in target \
                    and target.get("outside", "outdoors") == "outdoors":
                error(where, f'the direction it faces is unknown. Add azimuth_deg (0 north, 90 east, 180 south, 270 '
                             f'west) to the {kind} or to its surface "{o["surface"]}".')
        if "area_ft2" not in o and not ("width_ft" in o and "height_ft" in o):
            error(where, "needs a size: add area_ft2 (of one unit), or width_ft and height_ft.")
        if kind == "window":
            if o.get("glazing") is not None and o["glazing"] not in glazing and o["glazing"] not in own_glazings:
                mine = f' Your glazings library has: {", ".join(own_glazings)}.' if own_glazings else ""
                error(f"{where} > glazing", f'"{o["glazing"]}" is not in the glazings library or the presets.{mine} '
                                            "Presets: " + ", ".join(glazing) + ".")
            elif ("u_factor_btu_hr_ft2_f" not in o or "shgc" not in o) and o.get("glazing") is None:
                error(where, 'needs its glass described: add "glazing" (a preset such as "single_clear_wood"), or '
                             "both u_factor_btu_hr_ft2_f and shgc.")
            shade = o.get("interior_shading")
            if isinstance(shade, dict) and "type" not in shade and "coefficient_frac" not in shade:
                error(f"{where} > interior_shading", 'needs "type" (e.g. "light_curtains") or "coefficient_frac".')
            hang = o.get("overhang")
            if isinstance(hang, dict) and all(isinstance(hang.get(k), (int, float)) for k in
                                              ("distance_to_window_top_ft", "distance_to_window_bottom_ft")) \
                    and hang["distance_to_window_bottom_ft"] <= hang["distance_to_window_top_ft"]:
                error(f"{where} > overhang", "distance_to_window_bottom_ft must be larger than distance_to_window_top_ft "
                                             "(both are measured down from the overhang).")
        if kind == "skylight" and o.get("ceiling") is not None:
            ceiling = surfaces.get(o["ceiling"])
            if ceiling is None or ceiling.get("type") != "ceiling":
                error(f"{where} > ceiling", f'"{o["ceiling"]}" must be the id of a ceiling surface.')

    # Location
    loc = h.get("location") if isinstance(h.get("location"), dict) else {}
    dc = loc.get("design_conditions") if isinstance(loc.get("design_conditions"), dict) else {}
    if loc.get("weather_station_id") is not None:
        stations = data.weather_stations()
        if str(loc["weather_station_id"]) not in stations:
            error("location > weather_station_id",
                  f'"{loc["weather_station_id"]}" is not in RightTon\'s station list. Use a listed station id (see '
                  "docs/FORMAT.md), or remove it and give the design conditions yourself: heating_outdoor_temp_f, "
                  "cooling_outdoor_temp_f, daily_temp_range, humidity_difference_gr_lb, latitude_deg.")
    else:
        missing = [n for n in ("heating_outdoor_temp_f", "cooling_outdoor_temp_f", "daily_temp_range",
                               "humidity_difference_gr_lb", "latitude_deg") if n not in dc]
        if missing:
            error("location", "there is no weather_station_id, so location > design_conditions must give: "
                              + ", ".join(missing) + ". Or add a weather_station_id.")
    if all(isinstance(dc.get(k), (int, float)) for k in ("heating_outdoor_temp_f", "cooling_outdoor_temp_f")) \
            and dc["heating_outdoor_temp_f"] >= dc["cooling_outdoor_temp_f"]:
        error("location > design_conditions", "heating_outdoor_temp_f (the cold winter design temperature) must be "
                                              "lower than cooling_outdoor_temp_f (the hot summer one).")

    # Air
    air = h.get("air") if isinstance(h.get("air"), dict) else {}
    inf = air.get("infiltration")
    if not isinstance(inf, dict):
        warn("air", "there is no air > infiltration, so the house is calculated with no air leakage at all. Add a "
                    'blower-door result (air_changes_per_hr_at_50pa) or a leakiness estimate.')
    elif inf.get("method") == "blower_door":
        given = [k for k in ("air_changes_per_hr_at_50pa", "airflow_cfm_at_50pa", "natural_air_changes_per_hr",
                             "leakage_area_in2") if k in inf]
        if not given:
            error("air > infiltration", 'method is "blower_door" but no leakage number is given. Add '
                                        "air_changes_per_hr_at_50pa (ACH50) or airflow_cfm_at_50pa (CFM50), or change "
                                        'method to "leakiness_estimate" and add leakiness.')
        elif len(given) > 1:
            warn("air > infiltration", f"more than one leakage number is given ({', '.join(given)}); only {given[0]} is used.")
    elif inf.get("method") == "leakiness_estimate" and "leakiness" not in inf:
        error("air > infiltration", 'method is "leakiness_estimate", so add leakiness: very_tight, tight, average, '
                                    "leaky or very_leaky.")

    # HVAC and ducts
    by_zone: dict[str, list[str]] = {}
    for s in systems.values():
        where = f"hvac > systems > {label(s)}"
        if s.get("zone") is not None and s["zone"] not in zones:
            error(f"{where} > zone", f'zone "{s["zone"]}" is not defined in zones. {known("zones", zones)}')
        else:
            by_zone.setdefault(s.get("zone"), []).append(s["id"])
        zone_rooms = {r["id"] for r in rooms.values() if r.get("zone") == s.get("zone")}
        for key in ("supply_registers", "returns"):
            for rid in s.get(key, []) if isinstance(s.get(key), list) else []:
                if rid not in rooms and rid not in conditioned_spaces:
                    error(f"{where} > {key}", f'"{rid}" is not the id of a room. {known("rooms", rooms)}')
                elif rid in rooms and rid not in zone_rooms:
                    warn(f"{where} > {key}", f'room "{rid}" is in zone "{rooms[rid].get("zone")}", but this system '
                                             f'serves zone "{s.get("zone")}".')
        if isinstance(s.get("supply_registers"), list) and s["supply_registers"]:
            unserved = sorted(zone_rooms - set(s["supply_registers"]))
            if unserved:
                warn(where, "these rooms in its zone have no supply register listed, so the results give them a load "
                            "but no air is delivered there: " + ", ".join(unserved) + ".")
    for zone, ids in by_zone.items():
        for mode in ("heating", "cooling"):
            active = [i for i in ids if systems[i].get(mode, "none") != "none"]
            if len(active) > 1:
                error("hvac > systems", f'zone "{zone}" has more than one {mode} system ({", ".join(active)}). This '
                                        f"version handles one {mode} system per zone: combine them, or split the "
                                        "rooms into separate zones.")
    for d in _items(h, "air/ducts"):
        where = f"air > ducts > {label(d)}"
        if d.get("system") is not None and d["system"] not in systems:
            error(f"{where} > system", f'"{d["system"]}" is not the id of a system in hvac > systems. '
                                       f"{known('systems', systems)}")
        cfm = [k for k in ("supply_leakage_cfm_at_25pa", "return_leakage_cfm_at_25pa") if k in d]
        frac = [k for k in ("supply_leakage_frac", "return_leakage_frac") if k in d]
        if cfm and frac:
            error(where, "leakage is given both in cfm at 25 Pa and as fractions. Use one kind for both supply and return.")
        for i, seg in enumerate(d.get("segments", []) if isinstance(d.get("segments"), list) else []):
            if not isinstance(seg, dict):
                continue
            seg_where = f"{where} > segment {i + 1}"
            location = seg.get("location")
            if location is not None and location != "outdoors" and location not in places:
                error(f"{seg_where} > location", f'"{location}" must be "outdoors" or the id of a room or space. '
                                                 f"{known('rooms and spaces', places)}")
            if "surface_area_ft2" not in seg and "share_of_ducts_frac" not in seg:
                error(seg_where, "needs surface_area_ft2, or share_of_ducts_frac to have the area estimated.")
    for e in _items(h, "equipment"):
        if e.get("room") is not None and e["room"] not in rooms and e["room"] not in conditioned_spaces:
            error(f"equipment > {label(e)} > room", f'"{e["room"]}" is not the id of a room or a conditioned space. '
                                                    f"{known('rooms', rooms)}")
    return issues


def check_scenarios(house: dict) -> list[Issue]:
    issues = []
    for sc in house.get("scenarios", []) if isinstance(house.get("scenarios"), list) else []:
        if not isinstance(sc, dict) or "id" not in sc:
            continue
        where = f"scenarios > {label(sc)}"
        try:
            changed = housefile.apply_scenario(house, sc["id"])
        except HouseFileError as e:
            issues.append(Issue("error", where, str(e)))
            continue
        except (KeyError, TypeError, AttributeError):
            continue  # malformed change, already reported by the schema check
        changed = {k: v for k, v in changed.items() if k != "scenarios"}
        for issue in check_schema(changed) + check_meaning(changed):
            if issue.level == "error":
                issues.append(Issue("error", where, f"after its changes are applied, the house has a problem: "
                                                    f"{issue.where}: {issue.message}"))
    return issues


def validate(house) -> list[Issue]:
    """All findings for a house (errors first). No errors means the file can be calculated."""
    issues = check_schema(house)
    if not isinstance(house, dict):
        return issues
    schema_errors = bool(issues)
    issues += check_meaning(house)
    if not any(i.level == "error" for i in issues):
        baseline_ok = True
        try:
            housefile.to_building(house).building.validate()
        except (HouseFileError, ValueError) as e:
            baseline_ok = False
            issues.append(Issue("error", "", str(e)))
        if baseline_ok:
            issues += check_scenarios(house)
    elif not schema_errors:
        pass
    seen, unique = set(), []
    for issue in issues:
        key = (issue.level, issue.where, issue.message)
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    return sorted(unique, key=lambda i: i.level != "error")


def summary(house: dict) -> str:
    def n(section):
        return len(_items(house, section))
    return (f"{n('rooms')} room(s) in {n('zones')} zone(s), {n('spaces')} space(s), {n('surfaces')} surface(s), "
            f"{n('openings')} opening(s), {n('assemblies')} assembl{'y' if n('assemblies') == 1 else 'ies'}, "
            f"{n('scenarios')} scenario(s)")


def main(argv=None) -> int:
    args = [a for a in (sys.argv[1:] if argv is None else argv)]
    as_json = "--json" in args
    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        print("Usage: python -m rightton.validate <house file .rtn.json or .rtn.yaml> [--json]")
        return 2
    try:
        house = housefile.load(paths[0])
    except (OSError, HouseFileError) as e:
        if as_json:
            print(json.dumps({"valid": False, "issues": [{"level": "error", "where": "", "message": str(e)}]}))
        else:
            print(f"ERROR: {e}")
        return 1
    issues = validate(house)
    errors = [i for i in issues if i.level == "error"]
    if as_json:
        print(json.dumps({"valid": not errors, "issues": [asdict(i) for i in issues]}, indent=2))
    else:
        for issue in issues:
            print(issue)
        if errors:
            print(f"\n{paths[0]}: NOT valid: {len(errors)} error(s), {len(issues) - len(errors)} warning(s).")
        else:
            print(f"{paths[0]}: valid RightTon house file ({summary(house)})"
                  + (f", {len(issues)} warning(s)." if issues else "."))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
