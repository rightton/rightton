"""Glazings library: window U-factor and SHGC entered once from an NFRC label (issue #6)."""

from conftest import approx
from rightton import api, housefile, sensitivity, validate
from rightton.engine import calculate
from test_housefile import minimal

LABEL = {"id": "label-027", "name": "New vinyl double-hung", "u_factor_btu_hr_ft2_f": 0.27, "shgc": 0.22,
         "source": "NFRC label"}


def with_library(glazing="label-027"):
    h = minimal()
    h["format_version"] = "1.1.0"
    h["glazings"] = [dict(LABEL)]
    h["openings"][0] = {"id": "window", "type": "window", "surface": "wall", "area_ft2": 40, "glazing": glazing}
    return h


def test_window_takes_values_from_the_library():
    w = housefile.to_building(with_library()).building.windows[0]
    assert (w.u_factor, w.shgc) == (0.27, 0.22)
    assert not [i for i in validate.validate(with_library()) if i.level == "error"]


def test_library_window_gives_the_same_loads_as_values_on_the_window():
    lib = calculate(housefile.to_building(with_library()).building).building
    direct = minimal()
    direct["openings"][0] = {"id": "window", "type": "window", "surface": "wall", "area_ft2": 40,
                             "u_factor_btu_hr_ft2_f": 0.27, "shgc": 0.22}
    ref = calculate(housefile.to_building(direct).building).building
    assert lib.heat_total == approx(ref.heat_total) and lib.cool_sensible == approx(ref.cool_sensible)
    # Window conduction at heating design: U * A * dT = 0.27 * 40 ft2 * (70 F - 10 F) = 648 Btu/h
    assert lib.heat_windows == approx(0.27 * 40 * (70 - 10))


def test_reused_by_many_windows_and_saved_round_trip(tmp_path):
    h = with_library()
    h["openings"].append({"id": "window2", "type": "window", "surface": "wall", "area_ft2": 10, "glazing": "label-027"})
    path = tmp_path / "h.rtn.json"
    housefile.save(h, path)
    again = housefile.load(path)
    assert again == h
    ws = housefile.to_building(again).building.windows
    assert [(w.u_factor, w.shgc) for w in ws] == [(0.27, 0.22), (0.27, 0.22)]


def test_checker_messages():
    issues = validate.validate(with_library("nope"))
    assert any(i.level == "error" and "label-027" in i.message and "not in the glazings library" in i.message for i in issues)
    h = with_library()
    h["glazings"][0]["id"] = "single_clear_wood"
    h["openings"][0]["glazing"] = "single_clear_wood"
    assert any("same id as the RightTon preset" in i.message for i in validate.validate(h))
    h = with_library()
    h["glazings"][0]["u_factor_btu_hr_ft2_f"] = 3.5    # an R-value typed by mistake
    assert any("unusual" in i.message for i in validate.validate(h))


def test_library_values_are_varied_where_they_are_defined():
    items = sensitivity.analyze(with_library())["items"]
    wheres = {(i["where"], i["field"]) for i in items}
    assert not any(w.startswith("openings") and f in ("u_factor_btu_hr_ft2_f", "shgc") for w, f in wheres)


def test_api_calculates_a_library_window():
    out = api.calculate(with_library())
    assert out["valid"] and out["baseline"]["building"]["heating_btuh"] > 0
