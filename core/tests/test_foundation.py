"""Foundation walls and slabs: hand calculations."""

import math

from conftest import approx
from rightton import foundation as F
from rightton.model import FoundationWall, Slab


def wall(**kw):
    defaults = dict(id="fw", inside="basement", area_ft2=800.0, height_ft=8.0, depth_below_grade_ft=7.0,
                    thickness_in=8.0, wall_type="solid_concrete")
    defaults.update(kw)
    return FoundationWall(**defaults)


def test_overlap():
    assert F.overlap(0, 1, 0.5, 3) == approx(0.5)
    assert F.overlap(0, 1, 2, 3) == 0.0


def test_material_r_values():
    # 8 in concrete at k = 12.5 Btu-in/h-ft2-F: 8 / 12.5 = 0.64
    assert F.foundation_wall_material_r("solid_concrete", 8.0) == approx(0.64)
    # Hollow block, k = 5.0: 8 / 5 = 1.6
    assert F.foundation_wall_material_r("concrete_block", 8.0) == approx(1.6)
    # Wood foundation wall is treated as 0.5 in of sheathing, k = 0.8004: 0.5 / 0.8004 = 0.6247
    assert F.foundation_wall_material_r("wood", 8.0) == approx(0.6247)
    assert F.concrete_r(4.0) == approx(0.32)


def test_above_grade_u_uninsulated():
    # 0.64 concrete + 0.68 inside film + 0.21 outside film = 1.53 -> U = 0.65359
    assert F.foundation_wall_above_grade_u(wall()) == approx(0.65359)


def test_above_grade_u_full_height_exterior_insulation():
    # One 1-ft strip above grade, fully covered by R-10: 1 / (1.53 + 10) = 0.08673
    fw = wall(insulation_exterior_r=10.0, insulation_exterior_top_ft=0.0, insulation_exterior_bottom_ft=8.0)
    assert F.foundation_wall_above_grade_u(fw) == approx(0.08673)
    # Ignoring the insulation layers gives the bare wall again
    assert F.foundation_wall_above_grade_u(fw, include_insulation=False) == approx(0.65359)


def test_above_grade_u_partial_insulation():
    # 2 ft above grade (8 ft wall, 6 ft below). Interior R-10 covers only the top foot.
    # Strip nearest grade: bare, U = 1/1.53 = 0.65359. Top strip: 1/11.53 = 0.08673.
    # Average = (0.65359 + 0.08673) / 2 = 0.37016
    fw = wall(depth_below_grade_ft=6.0, insulation_interior_r=10.0, insulation_interior_top_ft=0.0,
              insulation_interior_bottom_ft=1.0)
    assert F.foundation_wall_above_grade_u(fw) == approx(0.37016)


def test_above_grade_u_from_assembly_r():
    assert F.foundation_wall_above_grade_u(wall(r_value=12.5)) == approx(0.08)


def test_below_grade_u_with_soil():
    # 2 ft below grade, bare wall, soil k = 0.8 Btu/h-ft-F.
    # Wall without outside film: 1.53 - 0.21 = 1.32
    # Strip 0-1 ft (avg depth 0.5): R_soil = pi * 0.5 / 2 / 0.8 = 0.98175; U = 1 / 2.30175 = 0.43445
    # Strip 1-2 ft (avg depth 1.5): R_soil = pi * 1.5 / 2 / 0.8 = 2.94524; U = 1 / 4.26524 = 0.23445
    # Average 0.33445, x 0.85 for soil storage = 0.28428
    fw = wall(depth_below_grade_ft=2.0)
    assert F.foundation_wall_below_grade_u(fw, True, 0.8) == approx(0.28428)


def test_below_grade_u_without_soil():
    # Every strip is the bare wall without outside film: 1 / 1.32 = 0.75758 (no 0.85 factor)
    assert F.foundation_wall_below_grade_u(wall(depth_below_grade_ft=2.0), False, 0.8) == approx(0.75758)


def test_below_grade_u_partial_depth_strip_and_insulation():
    # 1.5 ft below grade (8 ft wall), exterior R-5 from the top of the wall down 7 ft
    # (i.e. to 0.5 ft below grade), no soil resistance.
    # Strip 0-1 ft: half covered -> R = 1.32 + 5 * 0.5 = 3.82 -> U = 0.26178, weight 1.0 ft
    # Strip 1-1.5 ft: not covered -> R = 1.32 -> U = 0.75758, weight 0.5 ft
    # Average = (0.26178 * 1 + 0.75758 * 0.5) / 1.5 = 0.42705
    fw = wall(depth_below_grade_ft=1.5, insulation_exterior_r=5.0, insulation_exterior_top_ft=0.0,
              insulation_exterior_bottom_ft=7.0)
    assert F.foundation_wall_below_grade_u(fw, False, 0.8) == approx(0.42705)


def test_basement_slab_u():
    # Depth 7 ft, shortest side 37.5 ft, k = 0.8, uninsulated:
    # k * 1.47 / pi = 0.37433
    # ln(18.75 + 3.5 + 0.37433) - ln(3.5 + 0.37433) = 3.11902 - 1.35437 = 1.76465
    # U_avg = (2 * 0.8 / (pi * 37.5)) * 1.76465 = 0.013581 * 1.76465 = 0.023966
    # x 0.85 = 0.020371; insulated: x 0.7 = 0.014260
    assert F.basement_slab_u(False, 7.0, 37.5, 0.8) == approx(0.020371)
    assert F.basement_slab_u(True, 7.0, 37.5, 0.8) == approx(0.014260)


def _slab_series(k, r_at_radius):
    """The slab edge-loss equation written out: for path radius N = 8..13 ft, sum
    1/R over 1-ft strips at radius 0..N, where the soil path is max(pi*r - 1, 0)
    long and films add 1.14; F is the mean of the six sums."""
    sums = []
    for n in range(8, 14):
        sums.append(sum(1.0 / (r_at_radius(r) + 1.14 + max(math.pi * r - 1.0, 0.0) / k) for r in range(n + 1)))
    return sum(sums) / 6.0


def test_slab_f_value_uninsulated():
    # 4 in slab: concrete 0.32 + gravel 0.65 * (12 - 4) = 5.2 -> 5.52 under the slab, 0 at the edge.
    # First terms (k = 0.8): r=0: 1/1.14 = 0.8772; r=1: 1/(5.52 + 1.14 + 2.677) = 0.1071; ...
    slab = Slab(id="s", inside="room", area_ft2=1000.0, exposed_perimeter_ft=130.0, thickness_in=4.0)
    expected = _slab_series(0.8, lambda r: 0.0 if r == 0 else 5.52)
    assert 1.2 < expected < 1.5  # sanity: published F-values for bare slabs are of this order
    assert F.slab_f_value(slab, 0.8) == approx(expected)


def test_slab_f_value_first_terms_by_hand():
    # Check the series helper itself against hand arithmetic for N = 8 only:
    # r: 0      1      2      3      4      5      6      7      8
    # soil path (pi r - 1): 0, 2.1416, 5.2832, 8.4248, 11.5664, 14.7080, 17.8496, 20.9911, 24.1327
    # R = 5.52 + 1.14 + path / 0.8 (r >= 1); R(0) = 1.14
    # R: 1.14, 9.337, 13.264, 17.191, 21.118, 25.045, 28.972, 32.899, 36.826
    # 1/R: 0.87719 0.10710 0.07539 0.05817 0.04735 0.03993 0.03452 0.03040 0.02715 -> sum 1.29720
    total = sum(1.0 / (((0.0 if r == 0 else 5.52)) + 1.14 + max(math.pi * r - 1.0, 0.0) / 0.8) for r in range(9))
    assert total == approx(1.29720, rel=2e-4)


def test_slab_f_value_with_perimeter_and_under_slab_insulation():
    # R-10 perimeter insulation 2 ft deep: adds 10 at the edge (r = 0) and for r <= 2.
    # R-5 under-slab insulation 4 ft wide: adds 5 for 1 <= r <= 4.
    slab = Slab(id="s", inside="room", area_ft2=1000.0, exposed_perimeter_ft=130.0, thickness_in=4.0,
                perimeter_insulation_r=10.0, perimeter_insulation_depth_ft=2.0,
                under_slab_insulation_r=5.0, under_slab_insulation_width_ft=4.0)

    def r_at(r):
        if r == 0:
            return 10.0
        return 5.52 + (10.0 if r <= 2 else 0.0) + (5.0 if r <= 4 else 0.0)

    assert F.slab_f_value(slab, 0.8) == approx(_slab_series(0.8, r_at))


def test_slab_f_value_whole_slab_and_exterior_horizontal_insulation():
    # R-5 under the whole slab; R-8 exterior horizontal wing 3 ft wide, 1 ft below grade:
    # it applies for 1 <= r <= sqrt(1 + 9) = 3.16, i.e. r = 1, 2, 3.
    slab = Slab(id="s", inside="room", area_ft2=1000.0, exposed_perimeter_ft=130.0, thickness_in=4.0,
                under_slab_insulation_r=5.0, under_slab_insulation_spans_slab=True,
                exterior_horizontal_insulation_r=8.0, exterior_horizontal_insulation_width_ft=3.0,
                exterior_horizontal_insulation_depth_below_grade_ft=1.0)

    def r_at(r):
        if r == 0:
            return 0.0
        return 5.52 + 5.0 + (8.0 if 1 <= r <= 3 else 0.0)

    assert F.slab_f_value(slab, 0.8) == approx(_slab_series(0.8, r_at))
