"""Framing share from lumber size and spacing (issue #4): hand calculations."""

import pytest
from conftest import approx
from rightton import api, data, housefile, validate
from rightton.framing import framing_share, lumber_size, typical_allowance_frac


def test_lumber_sizes_set_cavity_depth():
    # Actual (dressed) sizes, OS-HPXML Material.Stud2x
    assert lumber_size("2x4") == (1.5, 3.5)
    assert lumber_size("2x6") == (1.5, 5.5)
    assert lumber_size("2x8") == (1.5, 7.25)
    assert lumber_size("2x10") == (1.5, 9.25)
    assert lumber_size("2x12") == (1.5, 11.25)
    assert lumber_size("4x4") == (3.5, 3.5)
    with pytest.raises(ValueError, match="Unknown lumber"):
        lumber_size("3x5")


def test_2x4_wall_at_16_in():
    # member share 1.5 in / 16 in = 0.09375
    # allowance = reference framing factor 0.23 (2x4 @ 16, OS-HPXML constructions.rb) - 0.09375 = 0.13625
    # total 0.09375 + 0.13625 = 0.23 (the reference engine's own value); cavity depth 3.5 in
    s = framing_share("wall", 16, "2x4")
    assert s.member_frac == approx(0.09375)
    assert s.allowance_frac == approx(0.13625)
    assert s.total_frac == approx(0.23)
    assert s.depth_in == 3.5
    assert "constructions.rb" in s.source


def test_2x6_wall_at_24_in():
    # member 1.5 / 24 = 0.0625; allowance 0.20 - 0.0625 = 0.1375; total 0.20; depth 5.5 in
    s = framing_share("wall", 24, "2x6")
    assert (s.member_frac, s.allowance_frac, s.total_frac, s.depth_in) == (approx(0.0625), approx(0.1375), approx(0.20), 5.5)


def test_in_between_spacing_and_other_surfaces():
    # 19.2 in: allowance interpolated 0.13625 + (0.1375 - 0.13625) * (19.2 - 16) / 8 = 0.13675
    # member 1.5 / 19.2 = 0.078125 -> total 0.214875
    assert framing_share("wall", 19.2, "2x4").total_frac == approx(0.214875)
    # 12 in is below the table: allowance held at the 16 in value; 1.5 / 12 + 0.13625 = 0.26125
    assert framing_share("wall", 12, "2x4").total_frac == approx(0.26125)
    # floor joists 2x10 @ 16: reference 0.13 -> 0.09375 + (0.13 - 0.09375) = 0.13
    assert framing_share("floor", 16, "2x10").total_frac == approx(0.13)
    # ceiling joists 2x6 @ 24: reference 0.10
    assert framing_share("ceiling", 24, "2x6").total_frac == approx(0.10)
    # rafters 2x8 @ 16: roof allowance 0.07 - 1.5/24 = 0.0075 at every spacing; 0.09375 + 0.0075 = 0.10125
    assert typical_allowance_frac("roof", 16) == approx(0.0075)
    assert framing_share("roof", 16, "2x8").total_frac == approx(0.10125)
    # 4x4 posts at 48 in: 3.5 / 48 = 0.072917 + wall allowance at 24+ (0.1375) = 0.210417
    assert framing_share("wall", 48, "4x4").total_frac == approx(0.210417)


def test_custom_and_override():
    # Old full-dimension 2x4 (2 in x 4 in) at 16 in: 2 / 16 = 0.125 + 0.13625 = 0.26125, depth 4 in
    s = framing_share("wall", 16, "custom", width_in=2, depth_in=4)
    assert (s.total_frac, s.depth_in) == (approx(0.26125), 4)
    # Allowance override: 0.09375 + 0.05 = 0.14375
    s = framing_share("wall", 16, "2x4", allowance_frac=0.05)
    assert s.total_frac == approx(0.14375) and s.allowance_overridden
    with pytest.raises(ValueError, match="width_in and depth_in"):
        framing_share("wall", 16, "custom")
    with pytest.raises(ValueError, match="larger than the member width"):
        framing_share("wall", 1, "2x4")


def wall(**extra):
    return {"id": "w", "type": "wall", "layers": [
        {"material": "gypsum_board", "thickness_in": 0.5},
        {"r_value_hr_ft2_f_btu": 13, "thickness_in": 3.5, "framing_material": "softwood"},
        {"material": "softwood", "thickness_in": 0.5},
        {"material": "wood_siding"}], **extra}


def test_framing_sets_the_assembly_r_value():
    # Same wall as test_housefile.test_layered_assembly_and_material_library, but framing share 0.23
    # from 2x4 @ 16 instead of a typed 0.25:
    # cavity path 16.0205, framing path 7.392 (see that test)
    # U = 0.23 / 7.392 + 0.77 / 16.0205 = 0.031115 + 0.048063 = 0.079178 -> R 12.630
    asm = wall(framing={"lumber": "2x4", "spacing_in": 16})
    assert housefile.assembly_r_value(asm, "wall", True) == approx(12.630, rel=2e-4)
    # framing_frac still wins when given
    assert housefile.assembly_r_value(wall(framing_frac=0.25, framing={"lumber": "2x4", "spacing_in": 16}), "wall", True) \
        == approx(12.401, rel=2e-4)
    out = api.assembly(asm)
    assert out["framing"]["member_frac"] == 0.0938 and out["framing"]["allowance_frac"] == approx(0.13625, abs_=1e-4)
    assert out["framing_frac_used"] == 0.23 and out["framing"]["depth_in"] == 3.5


def house_with(asm):
    from test_housefile import minimal
    h = minimal()
    h["assemblies"] = [asm]
    for s in h["surfaces"]:
        if s.get("assembly"):
            s["assembly"] = asm["id"]
    return h


def test_checker_compares_fills_with_cavity_depth():
    deep = wall(framing={"lumber": "2x4", "spacing_in": 16})
    deep["layers"][1]["thickness_in"] = 5.5
    issues = validate.validate(house_with(deep))
    assert any(i.level == "error" and "more than the 3.5 in cavity" in i.message for i in issues)
    short = wall(framing={"lumber": "2x6", "spacing_in": 24})
    issues = validate.validate(house_with(short))
    assert any(i.level == "warning" and "less than the 5.5 in cavity" in i.message for i in issues)
    ok = wall(framing={"lumber": "2x4", "spacing_in": 16})
    assert not [i for i in validate.validate(house_with(ok)) if "cavity" in i.message]
    bad = wall(framing={"lumber": "custom", "spacing_in": 16})
    assert any("width_in and depth_in" in i.message for i in validate.validate(house_with(bad)))


def test_old_1_0_files_still_load_and_validate():
    from test_housefile import EXAMPLES
    for name in ("old-house.rtn.yaml", "nrel-base-house.rtn.json"):
        h = housefile.load(EXAMPLES / name)
        assert h["format_version"] == "1.0.0"
        assert not [i for i in validate.validate(h) if i.level == "error"]
        housefile.to_building(h)


def test_framing_data_is_sourced():
    f = data.framing()
    assert "Stud2x" in f["lumber_source"] and "constructions.rb" in f["typical_framing_factors_source"]
