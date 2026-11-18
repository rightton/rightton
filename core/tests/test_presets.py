"""Masonry wall presets (issue #5): each loads into a house file and its R-value is hand-checked."""

import copy

import pytest
from conftest import approx
from rightton import api, data, housefile, validate
from test_housefile import minimal

FILMS = 0.68 + (0.17 + 0.25) / 2   # inside wall film + year-round outside film = 0.89
BRICK = 0.182                      # R per inch, OS-HPXML BaseMaterial.Brick k = 5.5 Btu-in/h-ft2-F
WOOD = 1.249                       # R per inch, OS-HPXML wood

EXPECTED_R = {
    # 0.89 + 8 in * 0.182 = 2.346
    "brick-solid-2-wythe": FILMS + 8 * BRICK,
    # 0.89 + 12 in * 0.182 = 3.074
    "brick-solid-3-wythe": FILMS + 12 * BRICK,
    # 0.89 + 0.75 in sand plaster * 0.199 (= 0.149) + 1.456 = 2.495
    "brick-solid-plaster-direct": FILMS + 0.75 * 0.199 + 8 * BRICK,
    # furring 1.5 in every 16 in, no allowance: ff = 0.09375
    # between furring: 0.89 + plaster on lath 0.51 + air space 1.0 + brick 1.456 = 3.856
    # through furring: 0.89 + 0.51 + 0.75 in * 1.249 (= 0.93675) + 1.456 = 3.79275
    # U = 0.09375 / 3.79275 + 0.90625 / 3.856 = 0.024718 + 0.235023 = 0.259742 -> R 3.850
    "brick-solid-plaster-furred": 3.8500,
    # 2x4 at 16 in: ff = 0.23 (data/framing.json)
    # between studs: 0.89 + gypsum 0.45 + air 1.0 + board sheathing 0.75 * 1.249 (= 0.93675) + air gap 1.0
    #                + brick 4 * 0.182 (= 0.728) = 5.00475
    # through studs: 0.89 + 0.45 + 3.5 * 1.249 (= 4.3715) + 0.93675 + 1.0 + 0.728 = 8.37625
    # U = 0.23 / 8.37625 + 0.77 / 5.00475 = 0.027459 + 0.153854 = 0.181312 -> R 5.515
    "brick-veneer-wood-frame": 5.5153,
}


def presets():
    return {p["id"]: p for p in data.assembly_presets()}


def test_every_preset_is_hand_checked():
    assert set(presets()) == set(EXPECTED_R)


@pytest.mark.parametrize("pid", sorted(EXPECTED_R))
def test_preset_r_value(pid):
    asm = copy.deepcopy(presets()[pid])
    assert housefile.assembly_r_value(asm, "wall", True) == approx(EXPECTED_R[pid], rel=2e-4)
    assert api.assembly(asm)["r_value"] == approx(EXPECTED_R[pid], abs_=0.006)


@pytest.mark.parametrize("pid", sorted(EXPECTED_R))
def test_preset_loads_into_a_house_file(pid):
    h = minimal()
    h["format_version"] = "1.1.0"
    asm = copy.deepcopy(presets()[pid])
    h["assemblies"].append(asm)
    h["surfaces"][0]["assembly"] = asm["id"]
    issues = validate.validate(h)
    assert not [i for i in issues if i.level == "error"], issues
    assert not [i for i in issues if "cavity" in i.message], issues
    housefile.to_building(h)


def test_masonry_presets_set_thermal_mass():
    p = presets()
    for pid in ("brick-solid-2-wythe", "brick-solid-3-wythe", "brick-solid-plaster-direct", "brick-solid-plaster-furred"):
        assert p[pid]["construction"] == "brick" and p[pid]["cladding"] == "brick"
    assert p["brick-veneer-wood-frame"]["construction"] == "wood_stud" and p["brick-veneer-wood-frame"]["cladding"] == "brick"


def test_sand_plaster_value():
    # CEC Title 24 'Plaster/Sand Aggregate - 1 in.': k = 5.0304 Btu-in/h-ft2-F -> R per inch 0.199
    assert data.materials()["plaster_sand_aggregate"]["r_per_inch_hr_ft2_f_btu_in"] == approx(1 / 5.0304, rel=2e-3)
