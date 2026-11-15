# Ported from OpenStudio-HPXML (BSD-style license; see core/NOTICE-OpenStudio-HPXML.md).
# OpenStudio(R) HPXML, Copyright (c) 2008-2026, Alliance for Energy Innovation, LLC,
# and other contributors. All rights reserved.
#
# Source: HPXMLtoOpenStudio/resources/hvac_sizing.rb (functions named in each
# docstring) and materials.rb (foundation wall material conductivities).
"""Ground-contact heat loss: foundation walls and slabs."""

from __future__ import annotations

import math

from .assemblies import FILM_INDOOR_WALL, FILM_OUTDOOR

# Conductivity, Btu-in/h-ft2-F.
# origin: OS-HPXML materials.rb BaseMaterial.Concrete / Brick / Wood and
# Material.FoundationWallMaterial (block values "derived from Table 2 of
# https://ncma.org/resource/rvalues-ufactors-of-single-wythe-concrete-masonry-walls/")
CONCRETE_K_IN = 12.5
_FOUNDATION_WALL_K_IN = {
    "solid_concrete": CONCRETE_K_IN,
    "double_brick": 5.5,
    "wood": 0.8004,
    "concrete_block_solid_core": 8.5,
    "concrete_block": 5.0,
    "concrete_block_perlite_core": 2.0,
    "concrete_block_foam_core": 1.8,
    "concrete_block_vermiculite_core": 2.1,
}


def overlap(min1: float, max1: float, min2: float, max2: float) -> float:
    """Length of the overlap of two intervals. Source: MathTools.overlap."""
    return max(0.0, min(max1, max2) - max(min1, min2))


def concrete_r(thickness_in: float) -> float:
    """R-value (hr-ft2-F/Btu) of a concrete layer."""
    return thickness_in / CONCRETE_K_IN


def foundation_wall_material_r(wall_type: str, thickness_in: float) -> float:
    """R-value of the bare structural wall. Source: Material.FoundationWallMaterial."""
    if wall_type == "wood":
        thickness_in = 0.5  # open wood cavity wall: assume 0.5 in of sheathing
    return thickness_in / _FOUNDATION_WALL_K_IN[wall_type]


def foundation_wall_bare_r(fw) -> float:
    """Bare wall plus indoor and outdoor air films."""
    return foundation_wall_material_r(fw.wall_type, fw.thickness_in) + FILM_INDOOR_WALL + FILM_OUTDOOR


def foundation_wall_above_grade_u(fw, include_insulation: bool = True) -> float:
    """U-factor (Btu/h-ft2-F) of the above-grade part of a foundation wall.

    Source: HVACSizing.get_foundation_wall_above_grade_ufactor. The wall is cut
    into 1-ft horizontal strips; each strip gets the insulation that covers it.
    """
    if fw.r_value is not None or fw.assembly is not None:
        return 1.0 / fw.r
    assembly_r = foundation_wall_bare_r(fw)
    if not include_insulation:
        return 1.0 / assembly_r
    ag_depth = fw.height_ft - fw.depth_below_grade_ft
    if ag_depth <= 0:
        return 1.0 / assembly_r
    int_bottom = ag_depth - fw.insulation_interior_bottom_ft
    int_top = ag_depth - fw.insulation_interior_top_ft
    ext_bottom = ag_depth - fw.insulation_exterior_bottom_ft
    ext_top = ag_depth - fw.insulation_exterior_top_ft
    sum_u = 0.0
    for distance_to_grade in range(1, math.ceil(ag_depth) + 1):
        bin_top = min(distance_to_grade, ag_depth)
        bin_bottom = distance_to_grade - 1
        bin_size = bin_top - bin_bottom  # last strip may be under 1 ft
        r_wall = assembly_r
        r_wall += fw.insulation_interior_r * overlap(bin_bottom, bin_top, int_bottom, int_top) / bin_size
        r_wall += fw.insulation_exterior_r * overlap(bin_bottom, bin_top, ext_bottom, ext_top) / bin_size
        sum_u += (1.0 / r_wall) * bin_size
    return sum_u / ag_depth


def foundation_wall_below_grade_u(fw, include_soil: bool, ground_conductivity: float) -> float:
    """Effective U-factor (Btu/h-ft2-F) of the below-grade part of a foundation wall.

    Source: HVACSizing.get_foundation_wall_below_grade_ufactor ("Manual J Section
    A12-4" per the reference). Each 1-ft strip sees a soil path whose length is a
    quarter circle of radius equal to the strip's average depth:
    R_soil = (pi * depth / 2) / k_soil. With soil, the result is cut 15% for soil
    thermal storage.
    """
    ag_depth = fw.height_ft - fw.depth_below_grade_ft
    if fw.r_value is not None or fw.assembly is not None:
        constr_r = fw.r
        ins_int_r = ins_ext_r = 0.0
        int_top = int_bottom = ext_top = ext_bottom = 0.0
    else:
        constr_r = foundation_wall_bare_r(fw)
        ins_int_r, ins_ext_r = fw.insulation_interior_r, fw.insulation_exterior_r
        int_top = fw.insulation_interior_top_ft - ag_depth
        int_bottom = fw.insulation_interior_bottom_ft - ag_depth
        ext_top = fw.insulation_exterior_top_ft - ag_depth
        ext_bottom = fw.insulation_exterior_bottom_ft - ag_depth
    depth = fw.depth_below_grade_ft
    sum_u = 0.0
    for distance_to_grade in range(1, math.ceil(depth) + 1):
        r_wall = constr_r - FILM_OUTDOOR  # no outdoor air film below grade
        bin_top = distance_to_grade - 1
        bin_bottom = min(distance_to_grade, depth)
        bin_size = bin_bottom - bin_top
        bin_avg_depth = (bin_top + bin_bottom) / 2.0
        r_wall += ins_int_r * overlap(bin_top, bin_bottom, int_top, int_bottom) / bin_size
        r_wall += ins_ext_r * overlap(bin_top, bin_bottom, ext_top, ext_bottom) / bin_size
        if include_soil:
            r_soil = (math.pi * bin_avg_depth / 2.0) / ground_conductivity
            sum_u += (1.0 / (r_soil + r_wall)) * bin_size
        else:
            sum_u += (1.0 / r_wall) * bin_size
    u_wall = sum_u / depth
    if include_soil:
        u_wall *= 0.85  # origin: MJ8 (15% decrease for soil thermal storage), via the reference
    return u_wall


# origin: OS-HPXML calc_slab_f_value ("Based on calibration to Table 4A values by
# Tony Fontanini")
SLAB_GRAVEL_R_PER_INCH = 0.65
# origin: MJ8 Figure A12-6 pg 517 via calc_slab_f_value: indoor finish + indoor
# air film + exposed air film
SLAB_AIR_FILMS_R = 0.05 + 0.92 + 0.17


def slab_f_value(slab, ground_conductivity: float) -> float:
    """Slab-on-grade edge loss factor F (Btu/h-ft-F of exposed perimeter).

    Source: HVACSizing.calc_slab_f_value ("Manual J Section A12-8" per the
    reference). Heat leaves through 1-ft-wide strips at radius 0..N ft from the
    edge, each through a soil arc of length (pi * radius - 1); F is the sum of the
    strip U-factors, averaged over N = 8..13 ft.
    """
    f_values = []
    for path_radius in range(8, 14):
        u_sum = 0.0
        for radius in range(0, path_radius + 1):
            soil_path_ft = max(math.pi * radius - 1.0, 0.0)
            r_ins = 0.0
            if radius == 0:
                r_concrete = 0.0
                r_gravel = 0.0  # no gravel on the edge
                if slab.perimeter_insulation_depth_ft > 0:
                    r_ins = slab.perimeter_insulation_r
            else:
                r_concrete = concrete_r(slab.thickness_in)
                r_gravel = max(SLAB_GRAVEL_R_PER_INCH * (12.0 - slab.thickness_in), 0.0)
                if slab.under_slab_insulation_spans_slab or radius <= slab.under_slab_insulation_width_ft:
                    r_ins += slab.under_slab_insulation_r
                if radius <= slab.perimeter_insulation_depth_ft:
                    r_ins += slab.perimeter_insulation_r
                if slab.exterior_horizontal_insulation_r > 0:
                    depth = slab.exterior_horizontal_insulation_depth_below_grade_ft
                    if radius >= depth:
                        hyp = math.sqrt(depth**2 + slab.exterior_horizontal_insulation_width_ft**2)
                        if radius <= hyp:
                            r_ins += slab.exterior_horizontal_insulation_r
            r_soil = soil_path_ft / ground_conductivity
            u_sum += 1.0 / (r_concrete + r_gravel + r_ins + SLAB_AIR_FILMS_R + r_soil)
        f_values.append(u_sum)
    return sum(f_values) / len(f_values)


def basement_slab_u(is_insulated: bool, depth_below_grade_ft: float, shortest_width_ft: float,
                    ground_conductivity: float) -> float:
    """U-factor (Btu/h-ft2-F) of a basement floor 2 ft or more below grade.

    Source: HVACSizing.calc_basement_slab_ufactor ("Manual J Section A12-7 and
    ASHRAE HoF 2013 pg 18.31 Eq 40" per the reference).
    """
    r_other = 1.47  # origin: ASHRAE HoF, via the reference
    z_f, w_b, k = depth_below_grade_ft, shortest_width_ft, ground_conductivity
    u_avg = (2.0 * k / (math.pi * w_b)) * (
        math.log(w_b / 2.0 + z_f / 2.0 + (k * r_other) / math.pi) - math.log(z_f / 2.0 + (k * r_other) / math.pi)
    )
    u = 0.85 * u_avg  # soil storage effect
    if is_insulated:
        u *= 0.7  # origin: MJ8 via the reference (insulated floors)
    return u
