"""The JSON interface used by the web app."""

import json
from pathlib import Path

from conftest import approx
from rightton import api, housefile

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def call(name, payload):
    out = json.loads(api.call(name, json.dumps(payload)))
    assert out["ok"], out
    return out["result"]


def test_calculate_base_house_matches_reference_and_adds_up():
    out = call("calculate", housefile.load(EXAMPLES / "nrel-base-house.rtn.json"))
    b = out["baseline"]["building"]
    # Reference engine: 41,543 / 27,993 / 265 Btu/h
    assert (round(b["heating_btuh"]), round(b["cooling_sensible_btuh"]), round(b["cooling_latent_btuh"])) == (41543, 27993, 265)
    # Components add up to the totals shown
    assert sum(c["btuh"] for c in b["heating_components"]) == approx(b["heating_btuh"], rel=1e-4)
    assert sum(c["btuh"] for c in b["cooling_sensible_components"]) == approx(b["cooling_sensible_btuh"], rel=1e-4)
    assert sum(c["btuh"] for c in b["cooling_latent_components"]) == approx(b["cooling_latent_btuh"], rel=1e-3)
    # (27,993 + 265) / 12,000 = 2.355 tons; sizing range 90 % .. 115 % of 28,258 = 25,432 .. 32,497
    assert b["cooling_tons"] == approx(2.355, rel=1e-3)
    sizing = out["baseline"]["sizing"]
    assert (sizing["cooling_capacity_min_btuh"], sizing["cooling_capacity_max_btuh"]) == (25432, 32497)
    assert sizing["heating_capacity_min_btuh"] == 41543
    # The blower-door conversion is shown: 80 cfm heating, 41 cfm cooling (reference output)
    assert round(out["baseline"]["infiltration"]["heating_cfm"]) == 80
    assert 40.4 < out["baseline"]["infiltration"]["cooling_cfm"] < 41.5


def test_calculate_old_house_scenarios_and_rooms():
    out = call("calculate", housefile.load(EXAMPLES / "old-house.rtn.yaml"))
    assert out["valid"] and len(out["scenarios"]) == 5
    base = out["baseline"]
    assert all("result" in s for s in out["scenarios"])
    assert all(s["result"]["building"]["heating_btuh"] < base["building"]["heating_btuh"] for s in out["scenarios"])
    rooms = {r["id"]: r for r in base["rooms"]}
    assert rooms["parlor"]["name"] == "Parlor" and rooms["sunroom"]["cooling_sensible_btuh"] > 0
    # Rooms add up to the house (zone-level excursion aside)
    total = sum(r["heating_btuh"] for r in base["rooms"])
    assert total == approx(base["building"]["heating_btuh"], rel=1e-3)
    assert any(d["name"] == "occupant_count_from_bedrooms" for d in base["defaults_used"])
    assert any(i["confidence"] == "measured" for i in out["stated_inputs"])
    assert base["design"]["space_temps_f"]


def test_invalid_house_returns_issues_not_results():
    house = housefile.load(EXAMPLES / "nrel-base-house.rtn.json")
    house["rooms"][0]["zone"] = "nowhere"
    out = call("calculate", house)
    assert out["valid"] is False and out["baseline"] is None
    assert "is not defined in zones" in out["issues"][0]["message"]


def test_assembly_layer_builder():
    # Plaster on lath 0.51 + empty cavity 1.0 (framing 3.75 in softwood = 4.684) + board 0.937 + siding 1.056, films 0.89
    # cavity path 4.393; framing path 8.077; U = 0.2 / 8.077 + 0.8 / 4.393 = 0.02476 + 0.18211 = 0.20687 -> R 4.83
    house = housefile.load(EXAMPLES / "old-house.rtn.yaml")
    out = call("assembly", house["assemblies"][0])
    assert out["ok"] and out["r_value"] == approx(4.83, rel=2e-3)
    assert out["cavity_path_r"] == approx(4.39, rel=2e-3) and len(out["layers"]) == 4
    assert out["r_value_sheltered"] > out["r_value"]
    bad = call("assembly", {"id": "x", "type": "wall", "layers": [{"material": "nope"}]})
    assert bad["ok"] is False and "materials list" in bad["error"]
    assert call("assembly", {"id": "x", "type": "wall", "r_value_hr_ft2_f_btu": 20})["u_factor"] == 0.05


def test_library_and_conversions():
    lib = call("library", {})
    assert lib["format_version"] == "1.1.0" and len(lib["stations"]) >= 20 and lib["schema"]["title"]
    text = (EXAMPLES / "old-house.rtn.yaml").read_text()
    as_json = call("to_json", {"text": text, "format": "yaml"})
    assert as_json == (EXAMPLES / "old-house.rtn.json").read_text()
    assert housefile.loads(call("to_yaml", json.loads(as_json)), "yaml") == json.loads(as_json)
    bad = json.loads(api.call("to_json", json.dumps({"text": "{oops", "format": "json"})))
    assert bad["ok"] is False and "not valid JSON" in bad["error"]


def test_design_conditions_from_epw_text(tmp_path):
    from test_weather import write_epw
    text = write_epw(tmp_path / "t.epw", lambda i: 10.0).read_text()
    out = call("design_conditions_from_epw", text)
    dc = out["design_conditions"]
    assert out["weather_station_name"] == "Testville"
    assert dc["heating_outdoor_temp_f"]["value"] == 14.0 and dc["cooling_outdoor_temp_f"]["value"] == 91.4
    assert "EPW weather file" in dc["latitude_deg"]["source"] and dc["daily_temp_range"] == "medium"
