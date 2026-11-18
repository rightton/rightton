"""Material library: grouping by type, and any insulation in any framed cavity (issue #1)."""

import pytest
from conftest import approx
from rightton import api, data, housefile

INSULATION_CATEGORIES = ("batts", "loose_fill", "spray_foam", "rigid_boards")

# Actual depth of the cavity a nominal member makes (in). 2x4 = 3.5 in, 2x8 = 7.25 in.
CAVITY_2X4_IN = 3.5
CAVITY_2X8_IN = 7.25


def test_every_material_has_a_known_category():
    categories = data.material_categories()
    for m in data.materials().values():
        assert m["category"] in categories, m["id"]
        assert m["use"], m["id"]  # kept as a hint
    grouped = data.materials_by_category()
    assert [cid for cid, _, _ in grouped] == list(categories)
    assert sum(len(ms) for _, _, ms in grouped) == len(data.materials())
    assert all(ms for _, _, ms in grouped), "no empty category"


def test_picker_groups_are_material_types():
    lib = api.library()
    names = [c["name"] for c in lib["material_categories"]]
    for wanted in ("Gypsum and plaster", "Wood", "Batts and blankets", "Loose fill and blown-in", "Spray foam",
                   "Rigid boards", "Masonry and concrete", "Cladding and siding", "Roofing", "Flooring"):
        assert wanted in names
    by_cat = {cid: {m["id"] for m in ms} for cid, _, ms in data.materials_by_category()}
    assert {"spray_foam_closed_cell", "spray_foam_open_cell"} <= by_cat["spray_foam"]
    assert {"xps_board", "eps_board", "polyiso_board"} <= by_cat["rigid_boards"]


def _framed(material, depth_in, kind, ff):
    """Gypsum inside, the fill in a softwood-framed cavity, plus 1/2 in plywood deck for roofs."""
    layers = [{"material": "gypsum_board", "thickness_in": 0.5},
              {"material": material, "thickness_in": depth_in, "framing_material": "softwood"}]
    if kind == "roof":
        layers.append({"material": "softwood", "thickness_in": 0.5})
    return {"id": "a", "type": kind, "framing_frac": ff, "layers": layers}


def insulations():
    return [m for m in data.materials().values() if m["category"] in INSULATION_CATEGORIES]


@pytest.mark.parametrize("material", [m["id"] for m in insulations()])
@pytest.mark.parametrize("kind,depth_in", [("wall", CAVITY_2X4_IN), ("roof", CAVITY_2X8_IN)])
def test_any_insulation_fills_any_cavity(material, kind, depth_in):
    m = data.materials()[material]
    asm = _framed(material, depth_in, kind, 0.25)
    built = housefile.assembly_for_surface(asm, kind, True, roof_pitch_rise_per_12=0)
    fill_r = m["r_per_inch_hr_ft2_f_btu_in"] * depth_in  # R per inch * cavity depth
    assert built.layers[1].cavity_r == approx(fill_r)
    assert built.layers[1].framing_r == approx(1.249 * depth_in)  # softwood across the full member depth
    r = built.r_value()
    assert 0 < r < built.path_r_values()[0]
    # The interface's assembly call accepts it as well
    assert api.assembly(asm)["ok"]


def test_spray_foam_in_a_2x4_wall_hand_calc():
    # films 0.68 + 0.21 = 0.89; gypsum 0.5 in * 0.9 = 0.45
    # cavity path: 0.89 + 0.45 + 3.5 in * 5.0 (closed-cell foam) = 18.84
    # framing path: 0.89 + 0.45 + 3.5 in * 1.249 (softwood) = 5.7115
    # U = 0.25 / 5.7115 + 0.75 / 18.84 = 0.043771 + 0.039809 = 0.083580 Btu/h-ft2-F -> R 11.965
    asm = _framed("spray_foam_closed_cell", CAVITY_2X4_IN, "wall", 0.25)
    assert housefile.assembly_r_value(asm, "wall", True) == approx(11.9645, rel=2e-4)


def test_mineral_wool_in_a_2x8_rafter_bay_hand_calc():
    # flat roof: inside film (0.61 + 0.92) / 2 = 0.765, outside 0.21 -> films 0.975
    # gypsum 0.45; plywood deck 0.5 * 1.249 = 0.6245
    # cavity path: 0.975 + 0.45 + 7.25 in * 4.2 (mineral wool batt) + 0.6245 = 32.4995
    # framing path: 0.975 + 0.45 + 7.25 in * 1.249 + 0.6245 = 11.10475
    # U = 0.10 / 11.10475 + 0.90 / 32.4995 = 0.0090052 + 0.0276927 = 0.0366979 -> R 27.250
    asm = _framed("mineral_wool_batt", CAVITY_2X8_IN, "roof", 0.10)
    assert housefile.assembly_r_value(asm, "roof", True, roof_pitch_rise_per_12=0) == approx(27.2495, rel=2e-4)


def test_mineral_wool_board_is_a_rigid_board():
    m = data.materials()["mineral_wool_board"]
    assert m["category"] == "rigid_boards" and "continuous" in m["use"]
    # 1.5 in board at R-4.2 per inch = R-6.3, the same as a 1.5 in layer in an assembly
    asm = {"id": "ci", "type": "wall", "layers": [{"material": "mineral_wool_board", "thickness_in": 1.5}]}
    built = housefile.assembly_for_surface(asm, "wall", True)
    assert built.layers[0].cavity_r == approx(6.3)
    # Unconfirmed source: flagged so the app warns
    assert m["confidence"] == "estimated" and "[CONFIRM]" in m["source"]
