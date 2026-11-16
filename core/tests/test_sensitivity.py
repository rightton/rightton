"""Input confidence: load ranges from inputs that were not measured."""

import json

import pytest
from conftest import approx
from rightton import api, data, sensitivity
from test_housefile import minimal


def test_low_high_rules():
    # Relative: 20 +/- 20 % -> 16 .. 24
    assert sensitivity.low_high(20.0, {"kind": "relative", "amount": 0.2}) == (approx(16.0), approx(24.0))
    # Relative on a negative value keeps low < high: -1200 +/- 30 % -> -1560 .. -840
    assert sensitivity.low_high(-1200.0, {"kind": "relative", "amount": 0.3}) == (approx(-1560.0), approx(-840.0))
    # Absolute: 70 F +/- 2 -> 68 .. 72
    assert sensitivity.low_high(70.0, {"kind": "absolute", "amount": 2.0}) == (68.0, 72.0)
    # Limits: SHGC 0.95 +/- 15 % would reach 1.09 -> capped at 1
    assert sensitivity.low_high(0.95, {"kind": "relative", "amount": 0.15, "min": 0, "max": 1}) == (approx(0.8075), 1.0)
    # A side that cannot move is dropped: shielding class 5 +/- 1, limited to 1..5 -> only the low side
    assert sensitivity.low_high(5, {"kind": "absolute", "amount": 1.0, "min": 1, "max": 5}) == (4.0, None)
    # Low only: no shades (1.0) tested against shades at 0.6
    assert sensitivity.low_high(1.0, {"kind": "low_only", "amount": 0.6}) == (0.6, None)


def test_combined_range_adds_in_quadrature():
    # Two inputs: one moves the load +300 / -100, the other +400 / -200.
    # High = 1000 + sqrt(300^2 + 400^2) = 1500; low = 1000 - sqrt(100^2 + 200^2) = 1000 - 223.6 = 776.4
    low, high = sensitivity.combined_range(1000.0, [[300.0, -100.0], [-200.0, 400.0]])
    assert (low, high) == (approx(776.39, rel=1e-4), approx(1500.0))
    # An input that only lowers the load does not raise the high end
    assert sensitivity.combined_range(1000.0, [[-50.0]]) == (950.0, 1000.0)


def item(result, where, field):
    return next(i for i in result["items"] if i["where"] == where and i["field"] == field)


def test_single_input_effects_match_hand_calculation():
    # The minimal house (test_housefile): heating 5666.2 = window 1200 + door 240 + wall 1020 + air leakage 3206.2
    result = sensitivity.analyze(minimal())
    assert result["base"]["building"]["heating_btuh"] == approx(5666.2, rel=2e-4)
    # ACH50 5 +/- 25 %: air leakage 3206.2 * 0.75 = 2404.6 and * 1.25 = 4007.7 -> heating 4864.6 .. 6467.7
    ach = item(result, "air", "air_changes_per_hr_at_50pa")
    assert (ach["low"], ach["high"]) == (3.75, 6.25)
    assert ach["loads"]["low"]["building"]["heating_btuh"] == approx(4864.6, rel=2e-4)
    assert ach["loads"]["high"]["building"]["heating_btuh"] == approx(6467.7, rel=2e-4)
    # Wall assembly R-20 +/- 20 %: R-16 -> wall 60 / 16 * 340 = 1275 (+255); R-24 -> 850 (-170)
    wall = item(result, "assemblies: wall-r20", "r_value_hr_ft2_f_btu")
    assert wall["loads"]["low"]["building"]["heating_btuh"] == approx(5666.2 + 255.0, rel=2e-4)
    assert wall["loads"]["high"]["building"]["heating_btuh"] == approx(5666.2 - 170.0, rel=2e-4)
    # A default RightTon filled in: heating setpoint 70 +/- 2 F -> every heating load scales with 58/60 and 62/60
    # except air leakage, whose airflow also depends on the temperature difference; so only check direction and size
    setpoint = item(result, "RightTon default", "heating_setpoint_f")
    assert setpoint["loads"]["low"]["building"]["heating_btuh"] < 5666.2 < setpoint["loads"]["high"]["building"]["heating_btuh"]
    assert setpoint["confidence"] == "default" and "OpenStudio-HPXML" in setpoint["source"]
    # Zone results are reported too (one zone here, equal to the building)
    assert ach["loads"]["high"]["zone:main"]["heating_btuh"] == ach["loads"]["high"]["building"]["heating_btuh"]
    # Most influential first
    impacts = [i["impact_btuh"] for i in result["items"]]
    assert impacts == sorted(impacts, reverse=True)


def test_measured_inputs_are_not_varied():
    house = minimal()
    house["air"]["infiltration"]["air_changes_per_hr_at_50pa"] = {"value": 5, "source": "blower door", "confidence": "measured"}
    result = sensitivity.analyze(house)
    assert not [i for i in result["items"] if i["field"] == "air_changes_per_hr_at_50pa"]
    # ... and the combined range narrows accordingly
    wider = sensitivity.analyze(minimal())["combined"]["building"]["heating_btuh"]
    narrower = result["combined"]["building"]["heating_btuh"]
    assert narrower["high"] - narrower["low"] < wider["high"] - wider["low"]
    # An estimate is varied and keeps its label
    house["air"]["infiltration"]["air_changes_per_hr_at_50pa"]["confidence"] = "estimated"
    assert item(sensitivity.analyze(house), "air", "air_changes_per_hr_at_50pa")["confidence"] == "estimated"


def test_combined_range_is_consistent_with_the_items():
    result = sensitivity.analyze(minimal())
    base = result["base"]["building"]["heating_btuh"]
    deltas = [[run["building"]["heating_btuh"] - base for run in i["loads"].values()] for i in result["items"]]
    low, high = sensitivity.combined_range(base, deltas)
    combined = result["combined"]["building"]["heating_btuh"]
    assert (combined["low"], combined["high"]) == (pytest.approx(low, abs=0.1), pytest.approx(high, abs=0.1))
    assert combined["low"] < base < combined["high"]


def test_values_from_presets_and_materials_are_varied():
    house = minimal()
    house["openings"][0] = {"id": "window", "type": "window", "surface": "wall", "area_ft2": 40, "glazing": "double_clear_wood"}
    house["assemblies"][0] = {"id": "wall-r20", "type": "wall", "layers": [
        {"material": "gypsum_board", "thickness_in": 0.5}, {"material": "cellulose_loose_fill", "thickness_in": 5.5}]}
    result = sensitivity.analyze(house)
    # Preset U 0.51 +/- 15 %: window heating 0.51 * 60 * 40 = 1224 -> +/- 183.6
    u = item(result, "openings: window", "u_factor_btu_hr_ft2_f")
    base = result["base"]["building"]["heating_btuh"]
    assert u["loads"]["high"]["building"]["heating_btuh"] - base == approx(183.6, rel=1e-3)
    assert "glazing preset" in u["source"]
    # A layer whose material value is itself an estimate is tested over the wider +/- 30 %:
    # 5.5 in * 3.5 = R-19.25 -> 13.475 .. 25.025
    layer = next(i for i in result["items"] if i["field"].startswith("layer 2"))
    assert layer["confidence"] == "estimated"
    assert (layer["low"], layer["high"]) == (approx(13.475), approx(25.025))


def test_every_rule_is_usable_and_examples_run():
    for name, rule in data.input_ranges().items():
        assert rule["kind"] in ("relative", "absolute", "low_only") and rule["amount"] > 0 and rule["what"], name
    from rightton import housefile
    from pathlib import Path
    examples = Path(__file__).resolve().parents[2] / "examples"
    out = json.loads(api.call("sensitivity", json.dumps(housefile.load(examples / "old-house.rtn.yaml"))))
    assert out["ok"] and out["result"]["varied"] > 50 and out["result"]["not_calculable"] == 0
    b = out["result"]["combined"]["building"]["cooling_total_btuh"]
    assert b["low"] < b["base"] < b["high"]
