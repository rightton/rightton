#!/usr/bin/env python3
"""Compare RightTon design loads with the reference engine (OpenStudio-HPXML).

Two ways to run:

1. Against fresh reference output (needs validation/run_reference.sh first):

       python validation/compare.py --reference-dir <output dir> --epw-dir <clone>/weather \
           --write-results --snapshot

   ``--snapshot`` saves the defaulted input (in.xml, gzipped) and the reference
   design loads of every compared house under validation/houses/ and
   validation/reference/, so that:

2. Against the committed snapshot (no reference engine needed; this is what the
   test suite and CI run):

       python validation/compare.py

Tolerances (SPEC.md): totals within 2 %, components within 5 %. Because the
reference reports whole Btu/h, a value also passes when it is within 1 Btu/h.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import gzip
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "core"))

import hpxml_reader  # noqa: E402
from rightton.engine import calculate  # noqa: E402

TOTAL_TOL = 0.02
COMPONENT_TOL = 0.05
ABS_TOL_BTUH = 1.0

# reference output name -> attribute of rightton.engine.Loads
MAPPING = {
    "Heating: Total": "heat_total",
    "Heating: Ducts": "heat_ducts",
    "Heating: Windows": "heat_windows",
    "Heating: Skylights": "heat_skylights",
    "Heating: Doors": "heat_doors",
    "Heating: Walls": "heat_walls",
    "Heating: Roofs": "heat_roofs",
    "Heating: Floors": "heat_floors",
    "Heating: Slabs": "heat_slabs",
    "Heating: Ceilings": "heat_ceilings",
    "Heating: Infiltration": "heat_infiltration",
    "Heating: Ventilation": "heat_ventilation",
    "Heating: Piping": "heat_piping",
    "Cooling Sensible: Total": "cool_sensible",
    "Cooling Sensible: Ducts": "cool_ducts_sens",
    "Cooling Sensible: Windows": "cool_windows",
    "Cooling Sensible: Skylights": "cool_skylights",
    "Cooling Sensible: Doors": "cool_doors",
    "Cooling Sensible: Walls": "cool_walls",
    "Cooling Sensible: Roofs": "cool_roofs",
    "Cooling Sensible: Floors": "cool_floors",
    "Cooling Sensible: Slabs": "cool_slabs",
    "Cooling Sensible: Ceilings": "cool_ceilings",
    "Cooling Sensible: Infiltration": "cool_infiltration_sens",
    "Cooling Sensible: Ventilation": "cool_ventilation_sens",
    "Cooling Sensible: Internal Gains": "cool_internal_sens",
    "Cooling Sensible: Blower Heat": "cool_blower_heat",
    "Cooling Sensible: AED Excursion": "cool_aed_excursion",
    "Cooling Latent: Total": "cool_latent",
    "Cooling Latent: Ducts": "cool_ducts_lat",
    "Cooling Latent: Infiltration": "cool_infiltration_lat",
    "Cooling Latent: Ventilation": "cool_ventilation_lat",
    "Cooling Latent: Internal Gains": "cool_internal_lat",
}
TOTALS = ("Heating: Total", "Cooling Sensible: Total", "Cooling Latent: Total")

HOUSES_DIR = HERE / "houses"
REFERENCE_JSON = HERE / "reference" / "design_loads.json"
EPW_DIR = HERE / "weather"


def read_reference_csv(path: Path) -> dict[str, float]:
    out = {}
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) > 1 and row[0].startswith("HVAC Design Load: "):
                out[row[0][len("HVAC Design Load: "):].replace(" (Btu/h)", "")] = float(row[1])
    return out


XML_NAMES = {"InternalLoads": "Internal Gains", "BlowerHeat": "Blower Heat", "AEDExcursion": "AED Excursion"}
XML_GROUPS = {"Heating": "Heating", "CoolingSensible": "Cooling Sensible", "CoolingLatent": "Cooling Latent"}


def read_reference_xml(design_loads_el) -> dict[str, float]:
    """Design loads the reference wrote into in.xml for a zone or a space."""
    out = {}
    for group in design_loads_el:
        for item in group:
            if group.tag in XML_GROUPS and item.tag != "AEDCurve":
                out[f"{XML_GROUPS[group.tag]}: {XML_NAMES.get(item.tag, item.tag)}"] = float(item.text)
    return out


def compare_loads(loads, reference: dict[str, float], label: str = "", room: bool = False):
    """Compare one Loads record with reference values. Returns (rows, failures, worst total, worst component)."""
    rows, failures = [], []
    worst_total = worst_component = 0.0
    for name, attr in MAPPING.items():
        if name not in reference:
            continue
        ref, mine = reference[name], getattr(loads, attr)
        if room:
            # The reference gives rooms no ventilation load; RightTon does (see RESULTS.md).
            if name == "Heating: Total":
                mine -= loads.heat_ventilation
            elif name == "Cooling Sensible: Total":
                mine -= loads.cool_ventilation_sens
            elif name in ("Heating: Ventilation", "Cooling Sensible: Ventilation"):
                continue
        diff = mine - ref
        rel = abs(diff) / abs(ref) if ref else (0.0 if abs(diff) <= ABS_TOL_BTUH else float("inf"))
        tol = TOTAL_TOL if name in TOTALS else COMPONENT_TOL
        ok = abs(diff) <= ABS_TOL_BTUH or rel <= tol
        if abs(diff) > ABS_TOL_BTUH:
            if name in TOTALS:
                worst_total = max(worst_total, rel)
            else:
                worst_component = max(worst_component, rel)
        rows.append({"name": label + name, "reference": ref, "rightton": round(mine, 1), "rel_diff": rel, "ok": ok})
        if not ok:
            failures.append(f"{label}{name}: RightTon {mine:.0f} vs reference {ref:.0f} ({rel:.1%})")
    return rows, failures, worst_total, worst_component


def compare_house(in_xml: Path, epw_dir: Path, reference: dict[str, float]) -> dict:
    """Returns {'status': 'pass'|'fail'|'skipped'|'error', 'reason', 'rows', 'worst_total',
    'worst_component', 'zones', 'rooms'} (zones/rooms: how many were compared individually)."""
    try:
        bldg = hpxml_reader.load(in_xml, epw_dir)
    except hpxml_reader.Unsupported as e:
        return {"status": "skipped", "reason": str(e)}
    try:
        results = calculate(bldg)
    except Exception as e:  # noqa: BLE001 - reported, not hidden
        return {"status": "error", "reason": f"{type(e).__name__}: {e}"}
    rows, failures, worst_total, worst_component = compare_loads(results.building, reference)
    n_zones = n_rooms = 0
    # Houses that define zones and spaces: compare each zone and each room too
    for zone in hpxml_reader.parse(in_xml).findall("Building/BuildingDetails/Zones/Zone"):
        zid = zone.find("SystemIdentifier").get("id")
        parts = []
        if zid in results.zones and zone.find("extension/DesignLoads") is not None:
            parts.append((results.zones[zid], zone.find("extension/DesignLoads"), f"zone {zid} / ", False))
            n_zones += 1
        for space in zone.findall("Spaces/Space"):
            sid = space.find("SystemIdentifier").get("id")
            if sid in results.rooms and space.find("extension/DesignLoads") is not None:
                parts.append((results.rooms[sid], space.find("extension/DesignLoads"), f"room {sid} / ", True))
                n_rooms += 1
        for loads, el, label, is_room in parts:
            r, f, wt, wc = compare_loads(loads, read_reference_xml(el), label, is_room)
            rows += r
            failures += f
            worst_total, worst_component = max(worst_total, wt), max(worst_component, wc)
    return {"status": "fail" if failures else "pass", "reason": "; ".join(failures), "rows": rows,
            "worst_total": worst_total, "worst_component": worst_component, "zones": n_zones, "rooms": n_rooms}


def iter_fresh(reference_dir: Path):
    for d in sorted(p for p in reference_dir.iterdir() if p.is_dir()):
        in_xml, annual = d / "run" / "in.xml", d / "run" / "results_annual.csv"
        if in_xml.exists() and annual.exists():
            yield d.name, in_xml, read_reference_csv(annual)


def iter_snapshot():
    reference = json.loads(REFERENCE_JSON.read_text())
    for name in sorted(reference):
        yield name, HOUSES_DIR / f"{name}.xml.gz", reference[name]


def run(args) -> dict[str, dict]:
    if args.reference_dir:
        houses = iter_fresh(Path(args.reference_dir))
        epw_dir = Path(args.epw_dir)
    else:
        houses = iter_snapshot()
        epw_dir = EPW_DIR
    results, snapshot = {}, {}
    for name, in_xml, reference in houses:
        if not reference:
            results[name] = {"status": "skipped", "reason": "reference engine reported no design loads"}
            continue
        results[name] = compare_house(in_xml, epw_dir, reference)
        if args.snapshot and results[name]["status"] in ("pass", "fail"):
            snapshot[name] = (in_xml, reference)
    if args.snapshot:
        write_snapshot(snapshot, epw_dir)
    return results


def write_snapshot(snapshot, epw_dir: Path) -> None:
    """Keep one house per distinct set of reference loads (many sample files differ
    only in appliances or schedules, which do not change design loads)."""
    HOUSES_DIR.mkdir(exist_ok=True)
    REFERENCE_JSON.parent.mkdir(exist_ok=True)
    EPW_DIR.mkdir(exist_ok=True)
    for old in [*HOUSES_DIR.glob("*.xml.gz"), *EPW_DIR.glob("*.json")]:
        old.unlink()
    kept, seen = {}, set()
    for name in sorted(snapshot, key=lambda n: (len(n), n)):
        in_xml, reference = snapshot[name]
        key = json.dumps(reference, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        kept[name] = reference
        with open(in_xml, "rb") as src, gzip.GzipFile(HOUSES_DIR / f"{name}.xml.gz", "wb", mtime=0) as dst:
            shutil.copyfileobj(src, dst)
        epw = hpxml_reader._txt(hpxml_reader.parse(in_xml).find("Building/BuildingDetails"),
                                "ClimateandRiskZones/WeatherStation/extension/EPWFilePath")
        target = (EPW_DIR / Path(epw).name).with_suffix(".json")
        if not target.exists():
            wx = hpxml_reader.load_weather(epw_dir, epw)
            target.write_text(json.dumps(dataclasses.asdict(wx), indent=1) + "\n")
    REFERENCE_JSON.write_text(json.dumps(kept, indent=1, sort_keys=True) + "\n")


def summarize(results: dict[str, dict]) -> str:
    by_status: dict[str, list[str]] = {}
    for name, r in results.items():
        by_status.setdefault(r["status"], []).append(name)
    compared = [r for r in results.values() if r["status"] in ("pass", "fail")]
    lines = [
        f"- Houses run: {len(results)}",
        f"- Compared: {len(compared)} (pass: {len(by_status.get('pass', []))}, "
        f"fail: {len(by_status.get('fail', []))})",
        f"- Skipped (feature not in RightTon v1): {len(by_status.get('skipped', []))}",
        f"- Errors: {len(by_status.get('error', []))}",
    ]
    if compared:
        lines.append(f"- Zones compared individually: {sum(r['zones'] for r in compared)}; "
                     f"rooms compared individually: {sum(r['rooms'] for r in compared)}")
        lines.append(f"- Largest difference in any total: {max(r['worst_total'] for r in compared):.2%}")
        lines.append(f"- Largest difference in any component: {max(r['worst_component'] for r in compared):.2%}")
    return "\n".join(lines)


def results_tables(results: dict[str, dict]) -> str:
    out = []
    fails = {n: r for n, r in results.items() if r["status"] == "fail"}
    errors = {n: r for n, r in results.items() if r["status"] == "error"}
    skipped: dict[str, list[str]] = {}
    for n, r in results.items():
        if r["status"] == "skipped":
            skipped.setdefault(r["reason"], []).append(n)
    if fails:
        out += ["### Outside tolerance", "", "| House | What differs |", "| --- | --- |"]
        out += [f"| `{n}` | {r['reason']} |" for n, r in fails.items()]
        out.append("")
    if errors:
        out += ["### Errors", "", "| House | Error |", "| --- | --- |"]
        out += [f"| `{n}` | {r['reason']} |" for n, r in errors.items()]
        out.append("")
    if skipped:
        out += ["### Skipped, by reason", "", "| Reason | Houses | Examples |", "| --- | --- | --- |"]
        for reason, names in sorted(skipped.items(), key=lambda kv: -len(kv[1])):
            examples = ", ".join(f"`{n}`" for n in names[:3])
            out.append(f"| {reason} | {len(names)} | {examples} |")
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference-dir", help="output dir of run_reference.sh (default: committed snapshot)")
    ap.add_argument("--epw-dir", help="folder with the EPW files (the reference clone's weather/ folder)")
    ap.add_argument("--snapshot", action="store_true", help="save compared houses and reference loads in the repo")
    ap.add_argument("--write-results", metavar="FILE", help="write the summary and tables (markdown) to FILE")
    ap.add_argument("--house", help="print the component table for one house")
    args = ap.parse_args()
    results = run(args)
    print(summarize(results))
    if args.house:
        for row in results[args.house].get("rows", []):
            print(f"{row['name']:60s} {row['rightton']:10.1f} {row['reference']:10.0f} {'' if row['ok'] else '<<<'}")
        print(results[args.house]["status"], results[args.house].get("reason", ""))
    for name, r in results.items():
        if r["status"] in ("fail", "error"):
            print(f"{r['status'].upper()} {name}: {r['reason']}")
    if args.write_results:
        Path(args.write_results).write_text(summarize(results) + "\n\n" + results_tables(results))
    return 1 if any(r["status"] in ("fail", "error") for r in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
