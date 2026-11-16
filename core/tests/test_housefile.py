"""House file format: reading, writing, round trips, scenarios, defaults, validation."""

import copy
import dataclasses
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import approx
from rightton import data, housefile, validate
from rightton.engine import calculate

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
sys.path.insert(0, str(ROOT / "validation"))
sys.path.insert(0, str(ROOT / "tools"))


def minimal():
    """One room, one wall with a window, no weather station."""
    return {
        "format_version": "1.0.0",
        "location": {"design_conditions": {
            "heating_outdoor_temp_f": 10, "cooling_outdoor_temp_f": 95, "daily_temp_range": "medium",
            "humidity_difference_gr_lb": 30, "latitude_deg": 40}},
        "assemblies": [{"id": "wall-r20", "type": "wall", "r_value_hr_ft2_f_btu": 20}],
        "zones": [{"id": "main"}],
        "rooms": [{"id": "living", "zone": "main", "floor_area_ft2": 1000, "occupant_count": 2,
                   "internal_sensible_gain_btu_hr": 1200, "internal_latent_gain_btu_hr": 100}],
        "surfaces": [{"id": "wall", "type": "wall", "inside": "living", "area_ft2": 400, "assembly": "wall-r20",
                      "azimuth_deg": 90}],
        "openings": [
            {"id": "window", "type": "window", "surface": "wall", "area_ft2": 40, "u_factor_btu_hr_ft2_f": 0.5,
             "shgc": 0.6},
            {"id": "door", "type": "door", "surface": "wall", "area_ft2": 20, "r_value_hr_ft2_f_btu": 5}],
        "air": {"infiltration": {"method": "blower_door", "air_changes_per_hr_at_50pa": 5}},
    }


def errors(house):
    return [i for i in validate.validate(house) if i.level == "error"]


def messages(house):
    return " | ".join(str(i) for i in validate.validate(house))


# --- Files ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["nrel-base-house.rtn.json", "old-house.rtn.json", "old-house.rtn.yaml",
                                  "llm-written-brick-bungalow.rtn.yaml"])
def test_examples_are_valid(name):
    assert not errors(housefile.load(EXAMPLES / name))


@pytest.mark.parametrize("name", ["nrel-base-house.rtn.json", "old-house.rtn.json"])
def test_json_load_save_round_trip_is_byte_identical(name, tmp_path):
    original = (EXAMPLES / name).read_text()
    housefile.save(housefile.load(EXAMPLES / name), tmp_path / name)
    assert (tmp_path / name).read_text() == original


def test_yaml_and_json_are_the_same_data():
    as_yaml = housefile.load(EXAMPLES / "old-house.rtn.yaml")
    as_json = housefile.load(EXAMPLES / "old-house.rtn.json")
    assert as_yaml == as_json
    # and converting JSON -> YAML -> JSON loses nothing
    assert housefile.loads(housefile.dumps(as_json, "yaml"), "yaml") == as_json
    assert housefile.dumps(housefile.loads(housefile.dumps(as_json, "yaml"), "yaml")) == housefile.dumps(as_json)


def test_extensions_survive_a_round_trip():
    house = minimal()
    house["extensions"] = {"my-cad-tool": {"layers": [1, 2, {"deep": True}], "version": "3.1"}}
    assert housefile.loads(housefile.dumps(house))["extensions"] == house["extensions"]
    assert not errors(house)


def test_bad_files_give_clear_errors():
    with pytest.raises(housefile.HouseFileError, match="not valid JSON"):
        housefile.loads("{not json")
    with pytest.raises(housefile.HouseFileError, match="must be an object"):
        housefile.loads("[1, 2]")
    assert housefile.format_of("a.rtn.yaml") == "yaml"
    assert housefile.format_of("a.rtn.json") == "json"


# --- Conversion to engine inputs -----------------------------------------------------------

def test_minimal_house_matches_hand_calculation():
    # Same house as test_engine.one_room_house without ceiling and slab:
    # window 0.5 * 60 * 40 = 1200; door 0.2 * 60 * 20 = 240; wall 0.05 * 60 * 340 = 1020;
    # infiltration 3206.2 (ACH50 5 in 8000 ft3, see test_engine) -> heating 5666.2 Btu/h
    conv = housefile.to_building(minimal())
    loads = calculate(conv.building).building
    assert loads.heat_total == approx(5666.2, rel=2e-4)
    # cooling internal gains: 1200 + 2 * 230 = 1660
    assert loads.cool_internal_sens == approx(1660.0)


def test_numbers_with_sources_are_read_as_numbers():
    house = minimal()
    plain_result = calculate(housefile.to_building(house).building).building.heat_total
    house["air"]["infiltration"]["air_changes_per_hr_at_50pa"] = {"value": 5, "source": "blower door",
                                                                  "confidence": "measured"}
    house["surfaces"][0]["area_ft2"] = {"value": 400, "confidence": "estimated"}
    assert calculate(housefile.to_building(house).building).building.heat_total == approx(plain_result)
    stated = {i["path"]: i for i in housefile.stated_inputs(house)}
    assert stated["air/infiltration/air_changes_per_hr_at_50pa"]["confidence"] == "measured"
    assert stated["surfaces/wall/area_ft2"]["confidence"] == "estimated"
    assert stated["rooms/living/floor_area_ft2"]["confidence"] == "default"   # bare number


def test_defaults_are_applied_and_listed():
    house = minimal()
    for key in ("occupant_count", "internal_sensible_gain_btu_hr", "internal_latent_gain_btu_hr"):
        del house["rooms"][0][key]
    conv = housefile.to_building(house)
    used = {d["name"]: d for d in conv.defaults_used}
    # No bedroom count: 4 occupants; 2400 Btu/h appliances -> 2400 + 4 * 230 = 3320 Btu/h sensible
    assert calculate(conv.building).building.cool_internal_sens == approx(3320.0)
    assert used["occupant_count"]["confidence"] == "estimated"
    assert used["house_internal_sensible_gain_btu_hr"]["value"] == 2400.0
    assert used["heating_setpoint_f"]["value"] == 70.0 and "OpenStudio-HPXML" in used["heating_setpoint_f"]["source"]
    assert "shielding_class" in used and "ceiling_height_ft" in used
    # With a bedroom count: bedrooms + 1
    house["project"] = {"bedroom_count": 2}
    conv = housefile.to_building(house)
    assert calculate(conv.building).building.cool_internal_sens == approx(2400.0 + 3 * 230.0)
    assert every_default_has_a_source()


def every_default_has_a_source():
    return all(d["source"] and d["confidence"] in ("default", "estimated") and d["unit"]
               for d in data.defaults().values())


def test_data_files_carry_sources():
    assert every_default_has_a_source()
    for m in data.materials().values():
        assert m["source"] and m["confidence"] in ("default", "estimated")
        assert "r_per_inch_hr_ft2_f_btu_in" in m or "r_value_hr_ft2_f_btu" in m
    for g in data.glazing().values():
        assert g["source"] and 0 < g["shgc"] <= 1 and g["u_factor_btu_hr_ft2_f"] > 0


def test_weather_station_supplies_design_conditions():
    house = minimal()
    house["location"] = {"weather_station_id": "725650"}   # Denver: 6.8 F / 91.76 F, dry climate
    c = housefile.to_building(house).building.conditions
    assert (c.heating_design_temp_f, c.cooling_design_temp_f) == (6.8, 91.76)
    assert c.humidity_setpoint_frac == 0.45 and c.humidity_difference_grains == -28.8
    # An override wins over the station
    house["location"]["design_conditions"] = {"cooling_outdoor_temp_f": 95}
    assert housefile.to_building(house).building.conditions.cooling_design_temp_f == 95


def test_layered_assembly_and_material_library():
    # gypsum 0.5 in * 0.90 = 0.45; softwood-framed cavity 3.5 in: batt R-13 / framing 3.5 * 1.249 = 4.3715;
    # sheathing 0.5 * 1.249 = 0.6245; wood siding (typical 0.75 in) 0.75 * 1.408 = 1.056; films 0.68 + 0.21
    # cavity path 0.89 + 0.45 + 13 + 0.6245 + 1.056 = 16.0205; framing path 0.89 + 0.45 + 4.3715 + 1.6805 = 7.392
    # U = 0.25 / 7.392 + 0.75 / 16.0205 = 0.033820 + 0.046815 = 0.080636 -> R 12.401
    asm = {"id": "w", "type": "wall", "framing_frac": 0.25, "layers": [
        {"material": "gypsum_board", "thickness_in": 0.5},
        {"r_value_hr_ft2_f_btu": 13, "thickness_in": 3.5, "framing_material": "softwood"},
        {"material": "softwood", "thickness_in": 0.5},
        {"material": "wood_siding"}]}
    assert housefile.assembly_r_value(asm, "wall", True) == approx(12.401, rel=2e-4)
    # The same wall facing a garage has a still-air film outside: 0.68 instead of 0.21 on both paths
    # U = 0.25 / 7.862 + 0.75 / 16.4905 = 0.031799 + 0.045481 = 0.077279 -> R 12.940
    assert housefile.assembly_r_value(asm, "wall", False) == approx(12.940, rel=2e-4)
    with pytest.raises(housefile.HouseFileError, match="not in the materials list"):
        housefile.assembly_r_value({"id": "x", "type": "wall", "layers": [{"material": "unobtainium"}]}, "wall", True)


def test_opening_count_and_size():
    # 3 windows of 3 ft x 5 ft = 45 ft2
    assert housefile.opening_area_ft2({"id": "w", "count": 3, "width_ft": 3, "height_ft": 5}) == 45
    assert housefile.opening_area_ft2({"id": "w", "area_ft2": 12}) == 12


def test_glazing_preset_and_storm_window():
    house = minimal()
    house["openings"][0] = {"id": "window", "type": "window", "surface": "wall", "area_ft2": 40,
                            "glazing": "single_clear_wood", "storm_window": "clear"}
    w = housefile.to_building(house).building.windows[0]
    assert (w.u_factor, w.shgc, w.storm, w.glass_layers) == (0.89, 0.64, "clear", 1)
    assert w.azimuth_deg == 90   # from the wall


def test_conditioned_space_and_equipment():
    house = housefile.load(EXAMPLES / "old-house.rtn.yaml")
    conv = housefile.to_building(house)
    res = calculate(conv.building)
    # The sealed attic is a conditioned space: its roof and gables load the zone, the ceilings below carry nothing
    assert res.rooms["attic"].heat_roofs > 0 and res.rooms["parlor"].heat_ceilings == 0
    # Ducts are all inside it and leak nothing to outside: no duct load
    assert res.building.heat_ducts == approx(0.0, abs_=1e-6) and res.building.cool_ducts_sens == approx(0.0, abs_=1e-6)
    # The dehumidifier is its own line
    assert res.building.cool_equipment_sens == 1800 and res.building.cool_equipment_lat == -1200
    # Windows behind the porch get the shaded-glass load, less per ft2 than the same glass in the open
    per_ft2 = {d.id: d.cool_htm for d in res.surfaces if d.kind == "windows"}
    assert per_ft2["parlor-south-windows"] < per_ft2["bedroom-front-east-windows"]
    # Blower-door volume includes the sealed attic: 5 rooms x 11 ft + sunroom 9 ft + 6000 ft3
    assert conv.building.infiltration.volume_ft3 == approx(1200 * 11 + 120 * 9 + 6000)


# --- Scenarios ---------------------------------------------------------------------------

def test_scenario_set_add_remove():
    house = minimal()
    house["scenarios"] = [
        {"id": "tight", "changes": [{"op": "set", "path": "air/infiltration/air_changes_per_hr_at_50pa", "value": 2}]},
        {"id": "no-door", "changes": [{"op": "remove", "path": "openings/door"}]},
        {"id": "more-glass", "changes": [{"op": "add", "section": "openings", "item": {
            "id": "window-2", "type": "window", "surface": "wall", "area_ft2": 30, "u_factor_btu_hr_ft2_f": 0.5,
            "shgc": 0.6}}]},
        {"id": "all", "includes": ["tight", "no-door", "more-glass"], "changes": []},
    ]
    assert not errors(house)
    base = calculate(housefile.to_building(house).building).building
    tight = calculate(housefile.to_building(house, "tight").building).building
    # Infiltration scales with ACH50: 3206.2 * 2 / 5 = 1282.5
    assert tight.heat_infiltration == approx(1282.5, rel=2e-4)
    assert tight.heat_walls == base.heat_walls
    everything = housefile.apply_scenario(house, "all")
    assert [o["id"] for o in everything["openings"]] == ["window", "window-2"]
    assert everything["air"]["infiltration"]["air_changes_per_hr_at_50pa"] == 2
    assert house["air"]["infiltration"]["air_changes_per_hr_at_50pa"] == 5   # baseline untouched
    # No door, 30 ft2 more window: wall net 400 - 70 = 330 -> 0.05 * 60 * 330 = 990
    assert calculate(housefile.to_building(house, "all").building).building.heat_walls == approx(990.0)


def test_old_house_scenarios_reduce_load_and_do_not_simply_add():
    house = housefile.load(EXAMPLES / "old-house.rtn.yaml")

    def heat(s=None):
        return calculate(housefile.to_building(house, s).building).building.heat_total

    base = heat()
    savings = {s: base - heat(s) for s in ("air-seal", "dense-pack-walls", "insulate-floor", "storm-windows")}
    assert all(v > 0 for v in savings.values())
    assert 0 < base - heat("everything") <= sum(savings.values()) + 1.0


def test_scenario_problems_are_reported():
    house = minimal()
    house["scenarios"] = [{"id": "bad", "changes": [{"op": "set", "path": "surfaces/nowhere/assembly", "value": "x"}]}]
    assert 'nothing with id "nowhere"' in messages(house)
    house["scenarios"] = [{"id": "breaks", "changes": [{"op": "set", "path": "surfaces/wall/assembly", "value": "gone"}]}]
    text = messages(house)
    assert "scenarios" in text and 'assembly "gone" is not defined' in text
    house["scenarios"] = [{"id": "a", "includes": ["b"], "changes": []}, {"id": "b", "includes": ["a"], "changes": []}]
    assert "includes itself" in messages(house)


# --- Validator messages -----------------------------------------------------------------

def test_valid_minimal_house_has_no_errors():
    assert not errors(minimal())


@pytest.mark.parametrize("mutate, expected", [
    (lambda h: h["surfaces"][0].update(area=5), 'use "area_ft2"'),
    (lambda h: h["surfaces"][0].update(assembly="nope"), 'assembly "nope" is not defined in assemblies'),
    (lambda h: h["rooms"][0].update(zone="upstairs"), 'zone "upstairs" is not defined in zones'),
    (lambda h: h["rooms"][0].update(floor_area_ft2="1000 sq ft"), "must be a number (ft2), without units or quotes"),
    (lambda h: h["openings"][0].update(area_ft2=500), "more than the surface's own area_ft2 of 400"),
    (lambda h: h["openings"][0].update(type="windw"), 'Did you mean "window"?'),
    (lambda h: h["openings"][0].update(surface="roof"), '"roof" is not the id of a surface'),
    (lambda h: h["surfaces"][0].update(inside="attic"), '"attic" is not the id of a room or a space'),
    (lambda h: h["surfaces"][0].update(id="living"), 'the id "living" is already used in rooms'),
    (lambda h: h["surfaces"][0].update(id="North Wall"), "is not a valid id"),
    (lambda h: h["surfaces"][0].pop("azimuth_deg"), "the direction it faces is unknown"),
    (lambda h: h["openings"][0].pop("shgc"), "needs its glass described"),
    (lambda h: h["openings"][0].update(interior_shading={"type": "light_blinds", "coverage_frac": 50}),
     "fractions are written 0 to 1, not as percent"),
    (lambda h: h["air"]["infiltration"].pop("air_changes_per_hr_at_50pa"), "no leakage number is given"),
    (lambda h: h["air"]["infiltration"].update(shielding_class=9), "the largest allowed value is 5"),
    (lambda h: h["location"]["design_conditions"].pop("latitude_deg"), "must give: latitude_deg"),
    (lambda h: h["location"].update(weather_station_id="000000"), "is not in RightTon's station list"),
    (lambda h: h.pop("zones"), 'is missing "zones"'),
    (lambda h: h.update(format_version="2.0.0"), "does not have the expected form"),
    (lambda h: h["assemblies"][0].pop("r_value_hr_ft2_f_btu"), "needs either layers"),
    (lambda h: h["assemblies"][0].update(layers=[{"material": "styrofoam", "thickness_in": 1}]),
     "not in the materials list"),
    (lambda h: h["surfaces"].append({"id": "fw", "type": "foundation_wall", "inside": "living", "area_ft2": 100,
                                     "height_ft": 4, "depth_below_grade_ft": 6}), "is more than height_ft"),
    (lambda h: h.update(hvac={"systems": [{"id": "a", "zone": "main", "heating": "furnace"},
                                            {"id": "b", "zone": "main", "heating": "boiler"}]}),
     "more than one heating system"),
    (lambda h: h.update(equipment=[{"id": "dh", "type": "dehumidifier", "room": "cellar",
                                    "sensible_heat_btu_hr": 1}]), '"cellar" is not the id of a room'),
    (lambda h: h["air"]["infiltration"].update(air_changes_per_hr_at_50pa={"value": 5, "confidence": "sure"}),
     'must be "measured", "estimated" or "default"'),
])
def test_validator_explains_the_problem(mutate, expected):
    house = minimal()
    mutate(house)
    assert errors(house), "expected an error"
    assert expected in messages(house)


def test_warnings_do_not_block():
    house = minimal()
    del house["air"]
    house["rooms"].append({"id": "closet", "zone": "main", "floor_area_ft2": 20})
    issues = validate.validate(house)
    assert not [i for i in issues if i.level == "error"]
    text = " | ".join(str(i) for i in issues)
    assert "no air leakage at all" in text and "no surface names this room" in text


def test_command_line(tmp_path):
    run = lambda *a: subprocess.run([sys.executable, "-m", "rightton.validate", *a], capture_output=True, text=True,
                                    cwd=ROOT / "core")
    ok = run(str(EXAMPLES / "old-house.rtn.yaml"))
    assert ok.returncode == 0 and "valid RightTon house file (6 room(s)" in ok.stdout
    bad = minimal()
    bad["rooms"][0]["zone"] = "nope"
    path = tmp_path / "bad.rtn.json"
    housefile.save(bad, path)
    out = run(str(path))
    assert out.returncode == 1 and "NOT valid: 1 error(s)" in out.stdout
    as_json = json.loads(run(str(path), "--json").stdout)
    assert as_json["valid"] is False and as_json["issues"][0]["level"] == "error"
    assert run().returncode == 2


# --- Schema, documents and the reference houses agree ---------------------------------------

def test_schema_is_valid_json_schema_and_agrees_with_our_checker():
    jsonschema = pytest.importorskip("jsonschema")
    schema = data.schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    standard = jsonschema.Draft202012Validator(schema)
    for name in ("nrel-base-house.rtn.json", "old-house.rtn.json"):
        house = housefile.load(EXAMPLES / name)
        assert not list(standard.iter_errors(house))
        assert not validate.check_schema(house)
    # Files our checker rejects on schema grounds are rejected by a standard validator too
    for mutate in (lambda h: h["surfaces"][0].update(area=5), lambda h: h["rooms"][0].update(floor_area_ft2="x"),
                   lambda h: h["openings"][0].update(type="windw"), lambda h: h.pop("zones"),
                   lambda h: h["surfaces"][0].update(id="North Wall")):
        house = minimal()
        mutate(house)
        assert validate.check_schema(house) and list(standard.iter_errors(house))


def test_every_schema_field_has_a_description():
    missing = []

    def walk(s, path):
        for name, sub in s.get("properties", {}).items():
            if not sub.get("description"):
                missing.append(f"{path}.{name}")
            walk(sub, f"{path}.{name}")
        if isinstance(s.get("items"), dict):
            walk(s["items"], path)
        for branch in s.get("oneOf", []):
            walk(branch, path)

    walk(data.schema(), "")
    assert not missing


def test_documents_and_json_example_are_generated_from_the_schema():
    import gen_format_docs
    stale = [str(p.relative_to(ROOT)) for p, text in gen_format_docs.outputs().items()
             if not p.exists() or p.read_text() != text]
    assert not stale, f"run python tools/gen_format_docs.py: {stale}"


def schema_field_names():
    names = set()

    def walk(s):
        for name, sub in s.get("properties", {}).items():
            names.add(name)
            walk(sub)
        if isinstance(s.get("items"), dict):
            walk(s["items"])
        for branch in s.get("oneOf", []) + s.get("anyOf", []):
            walk(branch)

    schema = data.schema()
    walk(schema)
    for d in schema["$defs"].values():
        walk(d)
    return names


@pytest.mark.parametrize("doc", ["FORMAT.md", "FORMAT-GUIDE-FOR-LLMS.md"])
def test_documents_mention_every_field_and_only_real_fields(doc):
    text = (ROOT / "docs" / doc).read_text()
    names = schema_field_names()
    assert not sorted(n for n in names if not re.search(r"\b" + re.escape(n) + r"\b", text))
    # Anything written like a unit-bearing field name must be a real field
    known = names | set(data.materials()) | set(data.glazing()) | set(data.defaults())
    suspicious = {w for w in re.findall(r"`([a-z][a-z0-9_]*_(?:ft2|ft|in|f|frac|btu|hr|cfm|deg|pa|ft3|in2|usd|lb))`", text)}
    assert not sorted(suspicious - known)


def test_guide_example_is_valid_and_calculates():
    text = (ROOT / "docs" / "FORMAT-GUIDE-FOR-LLMS.md").read_text()
    example = re.search(r"```yaml\n# guide-example\n(.*?)```", text, re.S).group(1)
    house = housefile.loads(example, "yaml")
    assert not validate.validate(house)   # no errors and no warnings
    assert calculate(housefile.to_building(house).building).building.heat_total > 0


def test_reference_houses_survive_conversion_to_the_format():
    """Every house in the reference snapshot, converted to a house file and read back,
    is valid and gives exactly the same loads."""
    import compare
    import hpxml_reader
    count = 0
    for name, in_xml, _ in compare.iter_snapshot():
        bldg = hpxml_reader.load(in_xml, compare.EPW_DIR)
        house = housefile.loads(housefile.dumps(housefile.from_building(bldg, name)))
        assert not errors(house), name
        direct, via_file = calculate(bldg).building, calculate(housefile.to_building(house).building).building
        for f in dataclasses.fields(direct):
            a, b = getattr(direct, f.name), getattr(via_file, f.name)
            assert a == pytest.approx(b, rel=1e-9, abs=1e-6), (name, f.name)
        count += 1
    assert count >= 121


def test_nrel_example_reproduces_reference_loads():
    # Reference engine output for base.xml: 41,543 / 27,993 / 265 Btu/h
    conv = housefile.to_building(housefile.load(EXAMPLES / "nrel-base-house.rtn.json"))
    loads = calculate(conv.building).building
    assert (round(loads.heat_total), round(loads.cool_sensible), round(loads.cool_latent)) == (41543, 27993, 265)
    assert conv.defaults_used == []   # every value is written out in that file


def test_house_written_by_a_language_model_from_the_guide_alone():
    """docs/LLM-GUIDE-TEST.md: a model given only the guide and a prose description wrote this file.
    It must stay valid, with no warnings, and its scenarios must calculate."""
    house = housefile.load(EXAMPLES / "llm-written-brick-bungalow.rtn.yaml")
    assert not validate.validate(house)
    base = calculate(housefile.to_building(house).building).building.heat_total
    for scenario in house["scenarios"]:
        assert calculate(housefile.to_building(house, scenario["id"]).building).building.heat_total < base
