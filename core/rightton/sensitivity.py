"""Input confidence: how far the loads move if the inputs that were not measured are off.

SPEC.md, Outputs: "which results rest on defaults or estimates, and how much the
answer moves if each changes, shown as a load range".

For every numeric input in the house file that is not marked ``measured``, and
for the main defaults RightTon filled in, the house is recalculated with that one
input at the low end and at the high end of a plausible range
(``data/input_ranges.json``). Nothing here is load math: each variant is an
ordinary run of the engine on an edited copy of the house.

The combined range treats the inputs as independent and adds their effects in
quadrature (root sum of squares), separately upward and downward. It is a
planning indication, not a statistical confidence interval.
"""

from __future__ import annotations

import copy
import math
from typing import Callable, Optional

from . import data, engine, housefile
from .housefile import HouseFileError, is_wrapped

METRICS = ("heating_btuh", "cooling_sensible_btuh", "cooling_latent_btuh", "cooling_total_btuh")
SKIP_KEYS = {"extensions", "scenarios", "outline_ft", "project", "format_version"}


def _metrics(loads: engine.Loads) -> dict[str, float]:
    return {"heating_btuh": loads.heat_total, "cooling_sensible_btuh": loads.cool_sensible,
            "cooling_latent_btuh": loads.cool_latent, "cooling_total_btuh": loads.cool_total}


def _run(house: dict) -> Optional[dict]:
    """Loads of the building and of each zone, or None if this variant cannot be calculated
    (for example a wall made smaller than its windows)."""
    try:
        res = engine.calculate(housefile.to_building(house).building)
    except (HouseFileError, ValueError, ZeroDivisionError, KeyError):
        return None
    out = {"building": _metrics(res.building)}
    for zid, loads in res.zones.items():
        out[f"zone:{zid}"] = _metrics(loads)
    return out


def low_high(value: float, rule: dict) -> tuple[Optional[float], Optional[float]]:
    """Low and high test values for an input under a range rule."""
    kind, amount = rule["kind"], rule["amount"]
    if kind == "relative":
        low, high = value * (1 - amount), value * (1 + amount)
        if value < 0:
            low, high = high, low
    elif kind == "absolute":
        low, high = value - amount, value + amount
    elif kind == "low_only":
        return amount, None
    else:
        raise ValueError(f"Unknown range kind: {kind}")
    if "min" in rule:
        low, high = max(low, rule["min"]), max(high, rule["min"])
    if "max" in rule:
        low, high = min(low, rule["max"]), min(high, rule["max"])
    return (None if low == value else low), (None if high == value else high)


def combined_range(base: float, deltas: list[list[float]]) -> tuple[float, float]:
    """(low, high) around a base value from each input's changes in the result.

    For each input, its largest increase and largest decrease are taken; increases
    are added in quadrature, and so are decreases: high = base + sqrt(sum up^2).
    """
    up = sum(max(0.0, max(d)) ** 2 for d in deltas if d)
    down = sum(max(0.0, -min(d)) ** 2 for d in deltas if d)
    return base - math.sqrt(down), base + math.sqrt(up)


def _set(node, path: list, value) -> None:
    for key in path[:-1]:
        node = node[key]
    old = node.get(path[-1]) if isinstance(node, dict) else node[path[-1]]
    node[path[-1]] = {**old, "value": value} if is_wrapped(old) else value


def _candidates(house: dict, conv: housefile.Conversion) -> list[dict]:
    """Every input to vary: {label parts, value, confidence, rule name, apply(house_copy, new_value)}."""
    rules = data.input_ranges()
    items: list[dict] = []

    def add(where, field, value, confidence, rule_name, apply: Callable, source=""):
        if rule_name in rules:
            items.append({"where": where, "field": field, "value": value, "confidence": confidence,
                          "source": source, "rule": rule_name, "apply": apply})

    def walk(node, path: list, where: str):
        if isinstance(node, list):
            for i, child in enumerate(node):
                name = where
                if isinstance(child, dict) and "id" in child:
                    name = f"{path[0] if len(path) == 1 else '/'.join(map(str, path))}: {child.get('name') or child['id']}"
                elif isinstance(child, dict):
                    name = f"{where}, {str(path[-1]).rstrip('s')} {i + 1}"
                walk(child, path + [i], name)
            return
        if not isinstance(node, dict):
            return
        for key, child in node.items():
            if key in SKIP_KEYS:
                continue
            child_path = path + [key]
            number = child["value"] if is_wrapped(child) else child
            if isinstance(number, (int, float)) and not isinstance(number, bool) and (is_wrapped(child) or key in rules):
                confidence = child.get("confidence", "default") if is_wrapped(child) else "default"
                if confidence != "measured":
                    add(where, key, number, confidence, key,
                        lambda h, v, p=child_path: _set(h, p, v), child.get("source", "") if is_wrapped(child) else "")
            elif isinstance(child, (dict, list)):
                walk(child, child_path, where if path else key.replace("_", " "))

    walk(house, [], "")
    plain = housefile.plain(house)

    # Values that come from RightTon's lists rather than from the file
    glazing = data.glazing()
    for i, o in enumerate(plain.get("openings", [])):
        # A glazing from the file's own library is varied where it is defined (by the walk above).
        own = any(g.get("id") == o.get("glazing") for g in plain.get("glazings", []) or [])
        preset = glazing.get(o.get("glazing")) if o.get("type") == "window" and not own else None
        if preset and "u_factor_btu_hr_ft2_f" not in o and "shgc" not in o:
            where = f"openings: {o.get('name') or o['id']}"

            def set_glass(h, v, i=i, preset=preset, which="u"):
                h["openings"][i]["u_factor_btu_hr_ft2_f"] = v if which == "u" else preset["u_factor_btu_hr_ft2_f"]
                h["openings"][i]["shgc"] = v if which == "shgc" else preset["shgc"]
            add(where, "u_factor_btu_hr_ft2_f", preset["u_factor_btu_hr_ft2_f"], "default", "glazing_u_factor", set_glass,
                f"glazing preset {o['glazing']}")
            add(where, "shgc", preset["shgc"], "default", "glazing_shgc",
                lambda h, v, f=set_glass: f(h, v, which="shgc"), f"glazing preset {o['glazing']}")
    materials = data.materials()
    for ai, a in enumerate(plain.get("assemblies", [])):
        for li, lay in enumerate(a.get("layers", []) or []):
            mat = materials.get(lay.get("material"))
            if mat is None or "r_value_hr_ft2_f_btu" in lay or "r_per_inch_hr_ft2_f_btu_in" in lay:
                continue
            if "r_per_inch_hr_ft2_f_btu_in" in mat and "thickness_in" in lay:
                r = mat["r_per_inch_hr_ft2_f_btu_in"] * lay["thickness_in"]
            elif "r_value_hr_ft2_f_btu" in mat:
                r = mat["r_value_hr_ft2_f_btu"]
            else:
                r = mat["r_per_inch_hr_ft2_f_btu_in"] * mat.get("typical_thickness_in", 0)
            if r <= 0:
                continue
            estimated = mat["confidence"] == "estimated"
            add(f"assemblies: {a.get('name') or a['id']}", f"layer {li + 1} ({lay.get('name') or mat['name']}) R-value", round(r, 3),
                "estimated" if estimated else "default", "material_r_value_estimated" if estimated else "material_r_value",
                lambda h, v, ai=ai, li=li: h["assemblies"][ai]["layers"][li].__setitem__("r_value_hr_ft2_f_btu", v),
                "RightTon materials list")

    # Defaults RightTon filled in
    used = {}
    for d in conv.defaults_used:
        used.setdefault(d["name"], d)
    rooms = plain.get("rooms", [])
    total_area = sum(r["floor_area_ft2"] for r in rooms) or 1.0

    def spread(field):
        def apply(h, v):
            for i, r in enumerate(rooms):
                h["rooms"][i][field] = v * r["floor_area_ft2"] / total_area
        return apply

    def design(field):
        return lambda h, v: h.setdefault("location", {}).setdefault("design_conditions", {}).__setitem__(field, v)

    for name, d in used.items():
        where, conf, src = "RightTon default", d["confidence"], d["source"]
        if name in ("heating_setpoint_f", "cooling_setpoint_f", "cooling_indoor_humidity_frac", "ground_conductivity_btu_hr_ft_f"):
            add(where, name, d["value"], conf, name, design(name), src)
        elif name in ("occupant_count", "occupant_count_from_bedrooms"):
            add(where, "occupant_count", d["value"], conf, "occupant_count", spread("occupant_count"), src)
        elif name == "house_internal_sensible_gain_btu_hr":
            add(where, "internal_sensible_gain_btu_hr", d["value"], conf, "internal_sensible_gain_btu_hr",
                spread("internal_sensible_gain_btu_hr"), src)
        elif name == "shielding_class":
            add(where, name, d["value"], conf, name,
                lambda h, v: h["air"]["infiltration"].__setitem__("shielding_class", int(round(v))), src)
        elif name == "solar_absorptance_frac":
            def absorb(h, v):
                for a in h.get("assemblies", []):
                    if a.get("type") == "wall" and "solar_absorptance_frac" not in a:
                        a["solar_absorptance_frac"] = v
            add(where, name, d["value"], conf, name, absorb, src)
        elif name == "ceiling_height_ft":
            def heights(h, v):
                for r in h["rooms"]:
                    r.setdefault("ceiling_height_ft", v)
            add(where, name, d["value"], conf, name, heights, src)
        elif name == "interior_shading_coefficient":
            def shade(h, v):
                for o in h.get("openings", []):
                    if o.get("type") == "window" and "interior_shading" not in o:
                        o["interior_shading"] = {"coefficient_frac": v}
            add(where, "no_interior_shading", 1.0, conf, "no_interior_shading", shade, src)
    return items


def analyze(house: dict) -> dict:
    """Load ranges for a house. Returns
    {"base", "items": [...most influential first...], "combined", "varied", "not_calculable"}.

    Each item: where, field, value, low, high, confidence, source, and for the building
    and each zone the loads at the low and the high test value.
    """
    conv = housefile.to_building(house)
    base = _run(house)
    if base is None:
        raise HouseFileError("The house cannot be calculated, so no ranges can be worked out.")
    rules = data.input_ranges()
    results, failed = [], 0
    for cand in _candidates(house, conv):
        rule = rules[cand["rule"]]
        low, high = low_high(cand["value"], rule)
        runs = {}
        for side, value in (("low", low), ("high", high)):
            if value is None:
                continue
            variant = copy.deepcopy(house)
            try:
                cand["apply"](variant, value)
            except (KeyError, IndexError, TypeError):
                continue
            run = _run(variant)
            if run is None:
                failed += 1
            else:
                runs[side] = run
        if not runs:
            continue
        impact = max(abs(run["building"][m] - base["building"][m]) for run in runs.values()
                     for m in ("heating_btuh", "cooling_total_btuh"))
        results.append({"where": cand["where"], "field": cand["field"], "value": cand["value"], "low": low, "high": high,
                        "confidence": cand["confidence"], "source": cand["source"], "range_basis": rule["what"],
                        "impact_btuh": round(impact, 1),
                        "loads": {side: {scope: {m: round(v, 1) for m, v in vals.items()} for scope, vals in run.items()}
                                  for side, run in runs.items()}})
    results.sort(key=lambda r: -r["impact_btuh"])

    combined = {}
    for scope, vals in base.items():
        combined[scope] = {}
        for m in METRICS:
            deltas = [[run[scope][m] - vals[m] for run in r["loads"].values() if scope in run] for r in results]
            low, high = combined_range(vals[m], deltas)
            combined[scope][m] = {"base": round(vals[m], 1), "low": round(low, 1), "high": round(high, 1)}
    return {"base": {scope: {m: round(v, 1) for m, v in vals.items()} for scope, vals in base.items()},
            "items": results, "combined": combined, "varied": len(results), "not_calculable": failed,
            "method": "Each input that was not measured is moved to the low and high end of a plausible range, one at a "
                      "time, and the house is recalculated. The combined range adds the separate effects in quadrature "
                      "(as if the inputs were independent). The ranges tested are RightTon's judgment, listed in "
                      "data/input_ranges.json."}
