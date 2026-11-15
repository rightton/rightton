"""Windows and skylights: hand calculations. Latitude 40 is used so that table
values are read directly (40 is a table row)."""

import pytest
from conftest import approx
from rightton import fenestration as fen
from rightton.model import Skylight, Window


def window(**kw):
    defaults = dict(id="w", wall="wall", area_ft2=10.0, azimuth_deg=90.0, u_factor=0.5, shgc=0.6)
    defaults.update(kw)
    return Window(**defaults)


BASE = dict(latitude=40.0, u_factor=0.5, shgc=0.6, isc=1.0, ctd_f=20.0, daily_range_index=1)


@pytest.mark.parametrize("azimuth, index", [(180, 0), (270, 2), (0, 4), (90, 6), (135, 7), (157.5, 8), (360, 4)])
def test_orientation_index(azimuth, index):
    # Table order is S, SW, W, NW, N, NE, E, SE, S. Compass 157.5 is halfway
    # between SE and S and rounds up to the second S entry.
    assert fen.orientation_index(azimuth) == index


def test_interpolation_between_rows():
    # South peak solar factor: 91 at 28 deg, 121 at 34 deg -> at 31 deg: 106
    assert fen.interp_table((28.0, 34.0, 40.0), (91.0, 121.0, 149.0), 31.0) == approx(106.0)


def test_interpolation_extrapolates_at_both_ends():
    # Below the table: 91 + (25 - 28) / 6 * 30 = 76
    assert fen.interp_table((28.0, 34.0, 40.0), (91.0, 121.0, 149.0), 25.0) == approx(76.0)
    # Above the table, from the last two rows (34: 121, 40: 149): 149 + 2/6 * 28 = 158.333
    assert fen.interp_table((28.0, 34.0, 40.0), (91.0, 121.0, 149.0), 42.0) == approx(158.3333)


def test_storm_window_clear():
    # Clear storm over U-1.0, SHGC 0.6: U drops by 0.6435 * 1.0 - 0.1533 = 0.4902 -> 0.5098; SHGC x 0.9 = 0.54
    u, shgc = fen.storm_adjusted(1.0, 0.6, "clear")
    assert u == approx(0.5098)
    assert shgc == approx(0.54)


def test_storm_window_low_e():
    # Low-e storm over U-0.5: reduction 0.766 * 0.5 - 0.1532 = 0.2298 -> 0.2702; SHGC 0.6 x 0.8 = 0.48
    u, shgc = fen.storm_adjusted(0.5, 0.6, "low_e")
    assert u == approx(0.2702)
    assert shgc == approx(0.48)


def test_no_storm_window():
    assert fen.storm_adjusted(0.5, 0.6, None) == (0.5, 0.6)


@pytest.mark.parametrize("u, shgc, layers, glass, expected", [
    (1.0, 0.8, None, None, "1P Clear"),            # U >= 0.85 single; SHGC >= 0.62
    (1.0, 0.5, None, None, "1P Heat Absorbing"),   # 0.47 <= SHGC < 0.62
    (1.0, 0.3, None, None, "1P Reflective"),
    (0.5, 0.7, None, None, "2P Clear"),            # SHGC >= 0.595
    (0.5, 0.55, None, None, "2P Low-e Option 1"),  # >= 0.515
    (0.5, 0.47, None, None, "2P Low-e Option 2"),  # >= 0.455
    (0.35, 0.44, None, None, "2P Heat Absorbing"), # >= 0.38
    (0.35, 0.30, None, None, "2P Low-e Option 3"),
    (0.25, 0.5, None, None, "3P Clear"),           # U < 0.30 triple; SHGC >= 0.445
    (0.25, 0.3, None, None, "3P Heat Absorbing"),
    (0.5, 0.7, 2, "low_e_low_solar", "2P Low-e Option 3"),
    (0.5, 0.7, 2, "low_e", "2P Low-e Option 2"),
    (0.5, 0.7, 2, "low_e_high_solar", "2P Low-e Option 1"),
    (0.5, 0.7, 1, "tinted", "1P Heat Absorbing"),
    (0.5, 0.7, 3, "reflective", "3P Reflective"),
    (0.5, 0.7, 1, "clear", "1P Clear"),
])
def test_glass_description(u, shgc, layers, glass, expected):
    assert fen.glass_description(u, shgc, layers, glass) == expected


def test_interior_shading_light_curtains_half_drawn():
    # U-0.35 / SHGC-0.44 glass is classed "2P Heat Absorbing"; light curtains = 0.60.
    # Half covered: 0.5 * 0.60 + 0.5 * 1.0 = 0.80
    w = window(u_factor=0.35, shgc=0.44, interior_shading_type="light_curtains", interior_shading_coverage=0.5)
    assert fen.interior_shading_coefficient(w) == approx(0.80)


def test_interior_shading_blinds_positions():
    # "2P Clear" (U 0.5, SHGC 0.7) with medium blinds: 0.59, fully covering the window.
    w = window(shgc=0.7, interior_shading_type="medium_blinds", interior_shading_coverage=1.0)
    assert fen.interior_shading_coefficient(w) == approx(0.59)
    w.blinds_position = "half_open"  # x 1.175 = 0.69325 -> rounded to 0.693
    assert fen.interior_shading_coefficient(w) == approx(0.693)
    w.blinds_position = "open"  # no shading
    assert fen.interior_shading_coefficient(w) == 1.0


def test_interior_shading_none_or_direct_value():
    assert fen.interior_shading_coefficient(window(interior_shading_type="none")) == 1.0
    assert fen.interior_shading_coefficient(window(interior_shading_coefficient=0.7)) == 0.7


def test_exterior_shading():
    assert fen.exterior_shading(window()) == (1.0, None)
    # Interior insect screen over the whole window: 1 - 0.1 * 1.0 = 0.9
    assert fen.exterior_shading(window(insect_screen="interior"))[0] == approx(0.9)
    # Exterior insect screen over half the window: 1 - 0.2 * 0.5 = 0.9
    assert fen.exterior_shading(window(insect_screen="exterior", insect_screen_coverage=0.5))[0] == approx(0.9)
    # Solar screens: handled as a 0.25 screen coefficient, not as an exterior coefficient
    assert fen.exterior_shading(window(exterior_shading_type="solar_screens")) == (1.0, 0.25)
    # Full exterior insect screen (0.8) and an exterior shading coefficient of 0.7: 0.56
    w = window(insect_screen="exterior", exterior_shading_coefficient=0.7)
    assert fen.exterior_shading(w)[0] == approx(0.56)


def test_east_window_average_htm_no_shade():
    # PSF east at 40 deg = 216; average CLF east, no interior shade = 0.38
    # HTM = 216 * 0.38 * 0.6 * 1.0 / 0.87 + 0.5 * 20 = 56.607 + 10 = 66.607 Btu/h-ft2
    assert fen.window_cooling_htm(azimuth_deg=90, **BASE) == approx(66.607)


def test_east_window_average_htm_with_interior_shade():
    # With interior shading the "shaded" CLF applies (east 0.32) and ISC = 0.8:
    # 216 * 0.32 * 0.6 * 0.8 / 0.87 + 10 = 38.135 + 10 = 48.135
    assert fen.window_cooling_htm(azimuth_deg=90, **{**BASE, "isc": 0.8}) == approx(48.135)


def test_east_window_hourly_htm_at_8am():
    # Hourly CLF east at 8:00, no shade = 0.51; temperature adjustment for a medium
    # daily range at 8:00 = -12.6 F -> CTD 7.4
    # 216 * 0.51 * 0.6 / 0.87 + 0.5 * 7.4 = 75.972 + 3.7 = 79.672
    assert fen.window_cooling_htm(azimuth_deg=90, hr=0, **BASE) == approx(79.672)


def test_north_window_average_htm():
    # PSF north = 35, CLF north = 0.48: 35 * 0.48 * 0.6 / 0.87 + 10 = 21.586
    assert fen.window_cooling_htm(azimuth_deg=0, **BASE) == approx(21.586)


def test_exterior_shading_coefficient_scales_whole_htm():
    assert fen.window_cooling_htm(azimuth_deg=90, esc=0.9, **BASE) == approx(66.607 * 0.9)


def test_solar_screen_blends_toward_north_value():
    # (66.607 - 21.586) * 0.25 + 21.586 = 32.841
    assert fen.window_cooling_htm(azimuth_deg=90, screen_sc=0.25, **BASE) == approx(32.841)


def test_south_window_overhang_partial_shade():
    # South HTM unshaded: PSF 149, CLF 0.24: 149 * 0.24 * 0.6 / 0.87 + 10 = 34.662
    # Average shade line multiplier, south, 40 deg = 2.60; 2 ft overhang -> shade line 5.2 ft
    # below the overhang. Glass runs from 1 ft to 6 ft below it: (5.2 - 1) / 5 = 84 % shaded.
    # HTM = 0.84 * 21.586 (north value) + 0.16 * 34.662 = 18.132 + 5.546 = 23.678
    htm = fen.window_cooling_htm(azimuth_deg=180, overhang_depth_ft=2.0, overhang_to_top_ft=1.0,
                                 overhang_to_bottom_ft=6.0, **BASE)
    assert htm == approx(23.678)


def test_overhang_too_short_or_fully_shading():
    kw = dict(azimuth_deg=180, overhang_to_top_ft=1.0, overhang_to_bottom_ft=6.0, **BASE)
    # 0.3 ft overhang: shade line 0.78 ft, above the glass -> unshaded value
    assert fen.window_cooling_htm(overhang_depth_ft=0.3, **kw) == approx(34.662)
    # 3 ft overhang: shade line 7.8 ft, below the sill -> north (fully shaded) value
    assert fen.window_cooling_htm(overhang_depth_ft=3.0, **kw) == approx(21.586)


def test_overhang_hourly_uses_period_multiplier():
    # At noon (hr = 4) the hourly shade line multiplier, south, 40 deg, is 1.9:
    # 2 ft overhang -> 3.8 ft; (3.8 - 1) / 5 = 56 % shaded.
    # Hourly CLF at 12:00, no shade: south 0.59, north 0.76; medium-range adjustment -2.9 -> CTD 17.1
    # HTM_d = 149 * 0.59 * 0.6 / 0.87 + 0.5 * 17.1 = 60.628 + 8.55 = 69.178
    # HTM_n = 35 * 0.76 * 0.6 / 0.87 + 8.55 = 18.345 + 8.55 = 26.895
    # 0.56 * 26.895 + 0.44 * 69.178 = 15.061 + 30.438 = 45.499
    htm = fen.window_cooling_htm(azimuth_deg=180, hr=4, overhang_depth_ft=2.0, overhang_to_top_ft=1.0,
                                 overhang_to_bottom_ft=6.0, **BASE)
    assert htm == approx(45.499, rel=2e-4)


def test_skylight_u_effective_with_curb_and_shaft():
    # U 0.5 + curb (5 ft2 at R-2 over 10 ft2 of skylight) 0.5 * 0.5 = 0.25
    #       + shaft (20 ft2 at R-10) 0.1 * 2.0 = 0.20  -> 0.95
    sky = Skylight(id="s", roof="r", area_ft2=10.0, azimuth_deg=180, u_factor=0.5, shgc=0.6,
                   curb_area_ft2=5.0, curb_r_value=2.0, shaft_area_ft2=20.0, shaft_r_value=10.0)
    assert fen.skylight_u_effective(sky) == approx(0.95)


def test_skylight_htm_on_12_in_12_south_roof():
    # Tilt 45 deg. Horizontal part: cos 45 * PSF_horiz 247 * CLF_horiz 0.68 = 118.766
    # Vertical part: sin 45 * PSF south 149 * CLF south 0.24 = 25.286
    # (118.766 + 25.286) * 0.6 / 0.87 + 0.5 * (20 + 15) = 99.346 + 17.5 = 116.846
    htm = fen.skylight_cooling_htm(latitude=40.0, azimuth_deg=180, pitch=12.0, u_effective=0.5, shgc=0.6,
                                   isc=1.0, ctd_f=20.0, daily_range_index=1)
    assert htm == approx(116.846)


def test_skylight_htm_flat_roof_with_shade_hourly():
    # Flat roof: only the horizontal part. Hour 13:00 (hr = 5), interior shade (ISC 0.5):
    # shaded horizontal CLF at 13:00 = 0.85; adjustment (medium) = -1.3 -> CTD 18.7
    # 247 * 0.85 * 0.6 * 0.5 / 0.87 + 0.5 * (18.7 + 15) = 72.397 + 16.85 = 89.247
    htm = fen.skylight_cooling_htm(latitude=40.0, azimuth_deg=180, pitch=0.0, u_effective=0.5, shgc=0.6,
                                   isc=0.5, ctd_f=20.0, daily_range_index=1, hr=5)
    assert htm == approx(89.247, rel=2e-4)


def test_aed_excursion():
    # Eleven hours at 100 and one at 400 Btu/h: average 125, limit 1.3 * 125 = 162.5,
    # excursion = 400 - 162.5 = 237.5
    assert fen.aed_excursion([100.0] * 11 + [400.0]) == approx(237.5)
    # A flat curve never exceeds 1.3 x its average
    assert fen.aed_excursion([250.0] * 12) == 0.0
