#!/usr/bin/env python3
"""Regenerate the reference tables in docs/FORMAT.md and docs/FORMAT-GUIDE-FOR-LLMS.md
from the schema and the data files, and examples/old-house.rtn.json from its YAML twin.

    python tools/gen_format_docs.py          # rewrite the files
    python tools/gen_format_docs.py --check  # exit 1 if any file is out of date

Text between ``<!-- BEGIN GENERATED: name -->`` and ``<!-- END GENERATED: name -->``
is owned by this script; everything else in the documents is written by hand.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
from rightton import data, housefile  # noqa: E402

SCHEMA = data.schema()


def resolve(s):
    while "$ref" in s:
        target = SCHEMA
        for part in s["$ref"].lstrip("#/").split("/"):
            target = target[part]
        s = {**target, **{k: v for k, v in s.items() if k != "$ref"}}
    return s


def kind(raw):
    if raw.get("$ref") == "#/$defs/quantity":
        unit = raw.get("x-unit", "")
        rng = ""
        if "x-min" in raw and "x-max" in raw:
            rng = f", {raw['x-min']} to {raw['x-max']}"
        elif "x-min" in raw:
            rng = f", at least {raw['x-min']}"
        return f"number ({unit}{rng})" if unit and unit != "none" else f"number{rng and ' (' + rng[2:] + ')'}"
    if raw.get("$ref") == "#/$defs/id":
        return "id"
    s = resolve(raw)
    if "const" in s:
        return f'`"{s["const"]}"`'
    if "enum" in s:
        return "one of: " + ", ".join(f"`{v}`" for v in s["enum"])
    t = s.get("type")
    if t == "array":
        inner = s.get("items", {})
        if inner.get("$ref") == "#/$defs/id":
            return "list of ids"
        return "list"
    if t == "integer":
        lo, hi = s.get("minimum"), s.get("maximum")
        return "whole number" + (f" ({lo} to {hi})" if lo is not None and hi is not None else
                                 f" (at least {lo})" if lo is not None else "")
    return {"string": "text", "boolean": "true / false", "object": "object", "number": "number"}.get(t, "any")


def table(obj, level, title, out, compact=False):
    obj = resolve(obj)
    required = set(obj.get("required", []))
    out.append(f"{'#' * level} {title}\n")
    if obj.get("description"):
        out.append(obj["description"] + "\n")
    out.append("| Field | Required | Type and unit | Meaning |")
    out.append("| --- | --- | --- | --- |")
    nested = []
    for name, raw in obj["properties"].items():
        s = resolve(raw)
        desc = (raw.get("description") or s.get("description", "")).replace("|", "\\|")
        out.append(f"| `{name}` | {'yes' if name in required else ''} | {kind(raw)} | {desc} |")
        if raw.get("$ref"):
            continue
        if s.get("type") == "object" and "properties" in s:
            nested.append((f"{title} > {name}", s))
        elif s.get("type") == "array" and resolve(s.get("items", {})).get("properties"):
            nested.append((f"{title} > {name} (each item)", resolve(s["items"])))
    out.append("")
    for sub_title, sub in nested:
        table(sub, min(level + 1, 5), sub_title, out)


def field_reference():
    out = []
    props = SCHEMA["properties"]
    out.append("| Top-level field | Required | Meaning |\n| --- | --- | --- |")
    for name, raw in props.items():
        out.append(f"| `{name}` | {'yes' if name in SCHEMA['required'] else ''} | {resolve(raw).get('description', '')} |")
    out.append("")
    for name in ("project", "location"):
        table(props[name], 3, name, out)
    for name in ("assemblies", "zones", "rooms", "spaces"):
        s = resolve(props[name])
        out.append(f"### {name}\n\n{s['description']}\n")
        table(s["items"], 4, f"{name} (each item)", out)
    for name in ("surfaces", "openings"):
        s = resolve(props[name])
        out.append(f"### {name}\n\n{s['description']} The `type` field decides which other fields apply.\n")
        for branch in s["items"]["oneOf"]:
            table(branch, 4, f'{name}: type `{branch["properties"]["type"]["const"]}`', out)
    table(props["air"], 3, "air", out)
    s = resolve(props["equipment"])
    out.append(f"### equipment\n\n{s['description']}\n")
    table(s["items"], 4, "equipment (each item)", out)
    table(props["hvac"], 3, "hvac", out)
    s = resolve(props["scenarios"])
    out.append(f"### scenarios\n\n{s['description']}\n")
    table(s["items"], 4, "scenarios (each item)", out)
    for branch in s["items"]["properties"]["changes"]["items"]["oneOf"]:
        table(branch, 5, f'change: op `{branch["properties"]["op"]["const"]}`', out)
    out.append(f"### extensions\n\n{props['extensions']['description']}\n")
    q = SCHEMA["$defs"]["quantity"]["anyOf"][1]
    table(q, 3, "A number with its source", out)
    return "\n".join(out)


def materials_table():
    out = ["| Material id | Name | R per inch | Fixed R | Typical thickness (in) | Confidence | Source |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for m in data.materials().values():
        out.append(f"| `{m['id']}` | {m['name']} | {m.get('r_per_inch_hr_ft2_f_btu_in', '')} | "
                   f"{m.get('r_value_hr_ft2_f_btu', '')} | {m.get('typical_thickness_in', '')} | {m['confidence']} | {m['source']} |")
    return "\n".join(out)


def materials_compact():
    out = ["| Material id | What it is | R per inch | Fixed R | Typical thickness (in) |", "| --- | --- | --- | --- | --- |"]
    for m in data.materials().values():
        out.append(f"| `{m['id']}` | {m['name']} | {m.get('r_per_inch_hr_ft2_f_btu_in', '')} | "
                   f"{m.get('r_value_hr_ft2_f_btu', '')} | {m.get('typical_thickness_in', '')} |")
    return "\n".join(out)


def glazing_table():
    out = ["| Glazing id | Description | U-factor (Btu/h-ft2-F) | SHGC |", "| --- | --- | --- | --- |"]
    for g in data.glazing().values():
        out.append(f"| `{g['id']}` | {g['name']} | {g['u_factor_btu_hr_ft2_f']} | {g['shgc']} |")
    return "\n".join(out)


def stations_table():
    out = ["| weather_station_id | Station | State | Heating design (F) | Cooling design (F) | Latitude | Design values from |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for sid, s in data.weather_stations().items():
        out.append(f'| `"{sid}"` | {s["city"]} | {s["state"]} | {s["heating_drybulb_f"]:.0f} | {s["cooling_drybulb_f"]:.0f} | '
                   f'{s["latitude_deg"]:.1f} | {"header" if s["design_source"].startswith("EPW") else "hourly data"} |')
    return "\n".join(out)


def stations_compact():
    """One line per state: id and station name, for the LLM guide."""
    by_state = {}
    for sid, s in data.weather_stations().items():
        by_state.setdefault(s["state"], []).append(f"{sid} {s['city']}")
    return "\n".join(f"- **{state}**: " + "; ".join(names) for state, names in sorted(by_state.items()))


def stations_page():
    n = len(data.weather_stations())
    return (f"# Weather stations\n\n{n} U.S. stations usable as `location.weather_station_id` in a house file "
            "(write the id in quotes). Generated by `python tools/gen_format_docs.py` from "
            "`data/weather_stations.json`; do not edit by hand.\n\n"
            f"Source: {data.weather_stations_source()}\n\n"
            "Heating design is the 99 % drybulb temperature and cooling design the 1 % drybulb temperature. "
            "\"header\" means the values are the ASHRAE design conditions printed in the weather file; \"hourly data\" "
            "means the file has none and RightTon derived them from its 8,760 hourly values, as the reference engine does.\n\n"
            + stations_table() + "\n")


def defaults_table():
    out = ["| Default | Value | Unit | Used when | Confidence | Source |", "| --- | --- | --- | --- | --- | --- |"]
    for name, d in data.defaults().items():
        value = json.dumps(d["value"]) if isinstance(d["value"], dict) else d["value"]
        out.append(f"| `{name}` | {value} | {d['unit']} | {d['applies_when']} | {d['confidence']} | {d['source']} |")
    return "\n".join(out)


def enum_list():
    """Compact list of every field with fixed allowed values, for the LLM guide."""
    found = {}

    def walk(s, path):
        s = resolve(s) if "$ref" in s and s["$ref"] not in ("#/$defs/quantity", "#/$defs/id") else s
        if "enum" in s and s.get("type") == "string":
            found.setdefault(path.split(".")[-1] + " (" + path.rsplit(".", 1)[0] + ")", s["enum"])
        for name, sub in s.get("properties", {}).items():
            walk(sub, f"{path}.{name}" if path else name)
        if "items" in s:
            walk(s["items"], path)
        for branch in s.get("oneOf", []):
            const = branch.get("properties", {}).get("type", {}).get("const")
            walk(branch, f"{path}[{const}]" if const else path)

    walk(SCHEMA, "")
    out = ["| Field (where) | Allowed values |", "| --- | --- |"]
    for key, values in found.items():
        out.append(f"| `{key}` | {', '.join(values)} |")
    return "\n".join(out)


def example_yaml():
    return "```yaml\n" + (ROOT / "examples" / "old-house.rtn.yaml").read_text() + "```"


BLOCKS = {"field-reference": field_reference, "materials": materials_table, "materials-compact": materials_compact,
          "glazing": glazing_table, "stations-compact": stations_compact, "defaults": defaults_table, "enums": enum_list,
          "example-old-house": example_yaml}


def render(text):
    def repl(match):
        name = match.group(1)
        return f"<!-- BEGIN GENERATED: {name} -->\n{BLOCKS[name]()}\n<!-- END GENERATED: {name} -->"
    return re.sub(r"<!-- BEGIN GENERATED: ([a-z-]+) -->.*?<!-- END GENERATED: \1 -->", repl, text, flags=re.S)


def outputs():
    result = {}
    for doc in ("docs/FORMAT.md", "docs/FORMAT-GUIDE-FOR-LLMS.md"):
        path = ROOT / doc
        if path.exists():
            result[path] = render(path.read_text())
    result[ROOT / "docs" / "WEATHER-STATIONS.md"] = stations_page()
    yaml_twin = ROOT / "examples" / "old-house.rtn.yaml"
    result[ROOT / "examples" / "old-house.rtn.json"] = housefile.dumps(housefile.load(yaml_twin))
    return result


def main():
    stale = []
    for path, text in outputs().items():
        if not path.exists() or path.read_text() != text:
            stale.append(path)
            if "--check" not in sys.argv:
                path.write_text(text)
    if "--check" in sys.argv and stale:
        print("Out of date (run python tools/gen_format_docs.py):", *[str(p.relative_to(ROOT)) for p in stale])
        return 1
    print("updated:" if stale else "up to date", *[str(p.relative_to(ROOT)) for p in stale])
    return 0


if __name__ == "__main__":
    sys.exit(main())
