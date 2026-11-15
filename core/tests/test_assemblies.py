"""Layered assemblies (parallel-path method): hand calculations."""

import pytest
from conftest import approx
from rightton.assemblies import Assembly, Layer


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
