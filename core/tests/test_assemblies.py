"""Layered assemblies (parallel-path method): hand calculations."""

import pytest
from conftest import approx
from rightton.assemblies import Assembly, Layer, roof_interior_film_r


def framed_wall(cavity_r_per_inch):
    return Assembly(
        name="2x4 wall",
        position="wall",
        framing_fraction=0.25,
        layers=[
            Layer("gypsum board", thickness_in=0.5, r_per_inch=0.9),        # R 0.45
            Layer("cavity", thickness_in=3.5, r_per_inch=cavity_r_per_inch, framing_r_per_inch=1.25),
            Layer("board sheathing", r_value=0.62),
            Layer("wood siding", r_value=0.62),
        ],
    )


def test_insulated_stud_wall_r_value():
    # Films: 0.68 inside + 0.21 outside = 0.89
    # Cavity path:  0.89 + 0.45 + 3.5 * 3.714 (= 13.0) + 0.62 + 0.62 = 15.58
    # Framing path: 0.89 + 0.45 + 3.5 * 1.25  (= 4.375) + 0.62 + 0.62 = 6.955
    # U = 0.25 / 6.955 + 0.75 / 15.58 = 0.035945 + 0.048139 = 0.084084 -> R = 11.893
    wall = framed_wall(13.0 / 3.5)
    r_cavity, r_framing = wall.path_r_values()
    assert r_cavity == approx(15.58)
    assert r_framing == approx(6.955)
    assert wall.u_factor() == approx(0.084084)
    assert wall.r_value() == approx(11.893)


def test_plaster_on_lath_wall_with_empty_cavity():
    # Old balloon-framed wall, no insulation, all layers in series (no framing split):
    # films 0.89 + plaster on wood lath 0.40 + empty cavity air space 1.0
    # + diagonal board sheathing 0.94 + clapboard 0.80 = 4.03
    wall = Assembly(
        name="plaster/lath, empty cavity",
        layers=[Layer("plaster on wood lath", r_value=0.40), Layer("air space", r_value=1.0),
                Layer("3/4 in board sheathing", r_value=0.94), Layer("clapboard", r_value=0.80)],
    )
    assert wall.r_value() == approx(4.03)


def test_ceiling_under_attic_uses_still_air_film_both_sides():
    # Ceiling film (average of heat flow up 0.61 and down 0.92) = 0.765 each side.
    # 0.765 + 0.45 gypsum + 30 insulation + 0.765 = 31.98
    ceiling = Assembly(name="attic floor", position="ceiling", exposed_to_wind=False,
                       layers=[Layer("gypsum", r_value=0.45), Layer("loose fill", thickness_in=10, r_per_inch=3.0)])
    assert ceiling.r_value() == approx(31.98)


def test_floor_over_open_air():
    # Floor film (heat flow down) 0.92 inside, 0.21 outside wind film.
    # 0.92 + 0.94 subfloor + 0.21 = 2.07
    floor = Assembly(name="bare floor", position="floor", layers=[Layer("subfloor", r_value=0.94)])
    assert floor.r_value() == approx(2.07)


def test_layer_needs_a_resistance():
    with pytest.raises(ValueError):
        Assembly(name="bad", layers=[Layer("mystery", thickness_in=1.0)]).r_value()


def test_framing_fraction_must_be_below_one():
    with pytest.raises(ValueError):
        Assembly(name="bad", framing_fraction=1.0, layers=[Layer("x", r_value=1.0)]).u_factor()


def test_roof_interior_film_by_pitch():
    # Flat: up 0.002 * e^0 + 0.608 = 0.610; down 0.32 * e^0 + 0.6 = 0.920; average 0.765 (the ceiling value)
    assert roof_interior_film_r(0.0) == approx(0.765)
    # 12-in-12 = 45 degrees: up 0.002 * e^1.791 + 0.608 = 0.6200; down 0.32 * e^-0.693 + 0.6 = 0.7600; average 0.690
    assert roof_interior_film_r(12.0) == approx(0.690, rel=1e-3)
    # 6-in-12 = 26.565 degrees: up 0.002 * e^1.0573 + 0.608 = 0.61376; down 0.32 * e^-0.40910 + 0.6 = 0.81255; avg 0.71315
    assert roof_interior_film_r(6.0) == approx(0.71315, rel=2e-4)


def test_sloped_roof_assembly_uses_the_pitch_film():
    # R-30 deck insulation on a 12-in-12 roof: 0.690 inside film + 30 + 0.21 outside film = 30.90
    roof = Assembly(name="roof", position="roof", roof_pitch_rise_per_12=12.0, layers=[Layer("foam", r_value=30.0)])
    assert roof.r_value() == approx(30.90, rel=1e-4)
    # The same layers flat: 0.765 + 30 + 0.21 = 30.975
    assert Assembly(name="roof", position="roof", layers=[Layer("foam", r_value=30.0)]).r_value() == approx(30.975)


# --- Split cavities (issue #3): several fills in one framed cavity --------------------------------

from rightton import housefile  # noqa: E402
from rightton.assemblies import split_cavity  # noqa: E402

WOOD_R_PER_IN = 1.249  # softwood, OS-HPXML materials.rb


def _split_wall(fills, depth_in=5.5):
    return Assembly("2x6 split cavity", position="wall", framing_fraction=0.25, layers=[
        Layer("gypsum", thickness_in=0.5, r_per_inch=0.9),                              # R 0.45
        *split_cavity(depth_in, fills, WOOD_R_PER_IN),
        Layer("plywood sheathing", thickness_in=0.5, r_per_inch=WOOD_R_PER_IN),         # R 0.6245
    ])


def test_split_cavity_foam_and_batt_with_leftover_air_space():
    # 2x6 cavity (5.5 in): 2 in closed-cell foam (R-5.0/in) + 2 in mineral wool batt (R-4.2/in)
    # leaves 1.5 in, modeled as a closed air space R-1.0.
    # Cavity path:  films 0.89 + 0.45 + 10.0 + 8.4 + 1.0 + 0.6245 = 21.3645
    # Framing path: films 0.89 + 0.45 + 5.5 in * 1.249 (= 6.8695, full member depth) + 0.6245 = 8.834
    # U = 0.25 / 8.834 + 0.75 / 21.3645 = 0.028300 + 0.035105 = 0.063405 Btu/h-ft2-F -> R 15.772
    wall = _split_wall([Layer("closed-cell foam", thickness_in=2, r_per_inch=5.0),
                        Layer("mineral wool batt", thickness_in=2, r_per_inch=4.2)])
    assert [lay.name for lay in wall.layers][1:4] == ["closed-cell foam", "mineral wool batt", "air space (rest of cavity)"]
    assert sum(lay.framing_r for lay in wall.layers[1:4]) == approx(5.5 * WOOD_R_PER_IN)
    r_cavity, r_framing = wall.path_r_values()
    assert r_cavity == approx(21.3645)
    assert r_framing == approx(8.834)
    assert wall.u_factor() == approx(0.063405)
    assert wall.r_value() == approx(15.772)


def test_split_cavity_filled_to_depth_has_no_air_space():
    # 2 in foam + 3.5 in batt = 5.5 in: cavity path 0.89 + 0.45 + 10.0 + 14.7 + 0.6245 = 26.6645
    # U = 0.25 / 8.834 + 0.75 / 26.6645 = 0.028300 + 0.028127 = 0.056427 -> R 17.722
    wall = _split_wall([Layer("closed-cell foam", thickness_in=2, r_per_inch=5.0),
                        Layer("mineral wool batt", thickness_in=3.5, r_per_inch=4.2)])
    assert len(wall.layers) == 4
    assert wall.r_value() == approx(17.722)


def test_split_cavity_rejects_fills_deeper_than_the_cavity():
    with pytest.raises(ValueError, match="only 5.5 in deep"):
        split_cavity(5.5, [Layer("foam", thickness_in=3, r_per_inch=5), Layer("batt", thickness_in=3, r_per_inch=4.2)],
                     WOOD_R_PER_IN)


def test_split_cavity_as_consecutive_framed_layers_in_a_house_file():
    # The house file writes a split cavity as consecutive framed layers; the leftover air space is a
    # framed air_space_closed layer whose thickness is the leftover depth. Same numbers as above.
    asm = {"id": "w", "type": "wall", "framing_frac": 0.25, "layers": [
        {"material": "gypsum_board", "thickness_in": 0.5},
        {"material": "spray_foam_closed_cell", "thickness_in": 2, "framing_material": "softwood"},
        {"r_per_inch_hr_ft2_f_btu_in": 4.2, "thickness_in": 2, "framing_material": "softwood"},
        {"material": "air_space_closed", "thickness_in": 1.5, "framing_material": "softwood"},
        {"material": "softwood", "thickness_in": 0.5}]}
    assert housefile.assembly_r_value(asm, "wall", True) == approx(15.772, rel=2e-4)
