"""Opaque envelope temperature differences: hand calculations."""

import pytest
from conftest import approx
from rightton import envelope as env


@pytest.mark.parametrize("wall_type, siding, u, group", [
    ("wood_stud", "wood", 1 / 22.7, "B-C"),   # U 0.044 <= 0.048 -> J -> B-C
    ("wood_stud", "wood", 0.08, "E-F"),       # 0.075 < U <= 0.086 -> D -> E-F
    ("wood_stud", "wood", 0.25, "G"),         # above every threshold -> A -> G (lightest)
    ("wood_stud", "brick", 0.09, "C"),        # veneer: 0.083 < U <= 0.095 -> I -> C
    ("steel_stud", "wood", 0.11, "F"),        # 0.105 < U <= 0.120 -> C -> F
    ("double_wood_stud", "wood", 0.03, "B-C"),
    ("double_wood_stud", "stone", 0.03, "B"),
    ("sip", "wood", 0.07, "D"),               # U >= 0.061 -> G -> D
    ("sip", "wood", 0.055, "C"),              # 0.050 <= U < 0.061 -> I -> C
    ("cmu", "wood", 0.10, "D"),               # 0.080 < U <= 0.108 -> G -> D
    ("brick", "wood", 0.25, "D"),             # U >= 0.1985 -> G -> D
    ("stone", "wood", 0.05, "B"),             # below 0.079 -> K -> B
    ("log", "wood", 0.09, "C-D"),             # 0.0865 <= U < 0.097 -> H -> C-D
    ("icf", "wood", 0.05, "B"),
])
def test_wall_group(wall_type, siding, u, group):
    assert env.wall_group(wall_type, siding, u) == group


@pytest.mark.parametrize("wall_type, thickness, u, group", [
    ("solid_concrete", 8.0, 0.6536, "D"),      # U >= 0.206 -> G -> D
    ("solid_concrete", 8.0, 0.0867, "B-C"),    # 0.071 <= U < 0.0915 -> J -> B-C
    ("solid_concrete", 4.0, 0.30, "E"),        # 4 in table: U >= 0.249 -> E -> E
    ("concrete_block", 8.0, 0.16, "D-E"),      # 0.1525 <= U < 0.222 -> F -> D-E
    ("concrete_block_solid_core", 8.0, 0.05, "B-C"),  # 0.049 <= U < 0.065 -> J -> B-C
    ("wood", 8.0, 0.05, "B"),
])
def test_foundation_wall_group(wall_type, thickness, u, group):
    assert env.foundation_wall_group(wall_type, thickness, u) == group


def test_wall_color_from_absorptance():
    assert env.wall_color(0.5) == "light"
    assert env.wall_color(0.7) == "medium"
    assert env.wall_color(0.9) == "dark"


def test_wall_cltd_normal_case():
    # Group B-C base 19.65 F x medium color 0.83 = 16.3095
    # Outdoor design 91.76 F: + (91.76 - 95) = -3.24; high daily range: -5
    # CLTD = 16.3095 - 3.24 - 5 = 8.0695 F
    assert env.wall_cltd("B-C", "medium", 16.76, 91.76, 2) == approx(8.0695)


def test_wall_cltd_dark_light_frame_wall_hot_day():
    # Group G base 38 F x dark 1.0 = 38; design 100 F: +5; low daily range: +4 -> 47 F
    assert env.wall_cltd("G", "dark", 25.0, 100.0, 0) == approx(47.0)


def test_wall_cltd_small_cooling_difference():
    # CTD 5 F (< 10): correction = 5 - 20 - 0 (medium range) = -15
    # B-C medium: 16.3095 - 15 = 1.3095 F
    assert env.wall_cltd("B-C", "medium", 5.0, 80.0, 1) == approx(1.3095)
    # Low range: correction = 5 - 20 - 4 = -19 -> negative, floored at 0
    assert env.wall_cltd("B-C", "medium", 5.0, 80.0, 0) == 0.0


def test_roof_cltd():
    # R-25 roof: base 30 F; dark asphalt shingles: no multiplier; 95 F day, medium range -> 30
    assert env.roof_cltd(25.0, "asphalt_shingles", "dark", 95.0, 1) == approx(30.0)
    # R-10: base 45; white metal x 0.65 = 29.25; 100 F day +5; low range +4 -> 38.25
    assert env.roof_cltd(10.0, "metal", "white", 100.0, 0) == approx(38.25)
    # R-35: base 27; medium clay tile x 0.65 = 17.55
    assert env.roof_cltd(35.0, "clay_tile", "medium", 95.0, 1) == approx(17.55)
    # R-5: base 50; dark wood shingles x 0.83 = 41.5; 90 F day -5; high range -5 -> 31.5
    assert env.roof_cltd(5.0, "wood_shingles", "dark", 90.0, 2) == approx(31.5)
    # R-14: base 38; light asphalt shingles x 0.83 = 31.54
    assert env.roof_cltd(14.0, "asphalt_shingles", "light", 95.0, 1) == approx(31.54)
    # R-20: base 31; white asphalt shingles x 0.83 = 25.73
    assert env.roof_cltd(20.0, "asphalt_shingles", "white", 95.0, 1) == approx(25.73)


def test_door_cltd():
    # CTD 20 F + 11 (medium range) = 31; low: +15 = 35; high: +6 = 26
    assert env.door_cltd(20.0, 1) == approx(31.0)
    assert env.door_cltd(20.0, 0) == approx(35.0)
    assert env.door_cltd(20.0, 2) == approx(26.0)


def test_exposed_horizontal_ctd():
    # CTD 20 - 5 + 4 (low range) = 19
    assert env.exposed_horizontal_ctd(20.0, 0) == approx(19.0)


def test_floor_over_vented_crawlspace():
    # TD 60 F, floor U 0.05, wall U 0.30: 60 / (1 + 4 * 0.05 / (0.30 + 0.11)) = 60 / 1.487805 = 40.328 F
    assert env.floor_over_enclosed_space_td(60.0, 0.05, 0.30, vented=True) == approx(40.328)


def test_floor_over_sealed_crawlspace_or_basement():
    # 0.30 * 60 / (4 * 0.05 + 0.30) = 18 / 0.5 = 36 F
    assert env.floor_over_enclosed_space_td(60.0, 0.05, 0.30, vented=False) == approx(36.0)
