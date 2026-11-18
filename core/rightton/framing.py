"""Framing share of a framed assembly from lumber size and spacing.

Framing share (fraction of the area that is framing) = member share + allowance:

- member share = actual member width / spacing (1.5 in / 16 in = 0.09375 for 2x4 at 16 in o.c.);
- allowance = the extra framing a real wall, floor or roof has (plates, headers, corners, blocking,
  window and door framing). It is derived from the reference engine's typical framing factors
  (data/framing.json, OpenStudio-HPXML constructions.rb): allowance = typical framing factor -
  member share at the same spacing. Between the tabulated spacings it is interpolated linearly;
  outside them the nearest value is used. [CONFIRM] the interpolation is RightTon's own choice.

Lumber size also sets the cavity depth (2x4 = 3.5 in, 2x6 = 5.5 in, ...), the actual sizes from
OpenStudio-HPXML materials.rb Material.Stud2x.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import data


@dataclass
class FramingShare:
    width_in: float           # actual member width (in)
    depth_in: float           # actual member depth = cavity depth (in)
    spacing_in: float         # on-center spacing (in)
    member_frac: float        # width / spacing
    allowance_frac: float     # plates, headers, corners, window framing
    allowance_overridden: bool
    total_frac: float         # member + allowance, capped below 1
    source: str


def lumber_size(lumber: str) -> tuple[float, float]:
    """(width_in, depth_in) of a nominal lumber size such as "2x6"."""
    sizes = data.framing()["lumber"]
    if lumber not in sizes:
        raise ValueError(f'Unknown lumber size "{lumber}". Use one of {", ".join(sizes)}, or "custom" with width_in and depth_in.')
    s = sizes[lumber]
    return s["width_in"], s["depth_in"]


def typical_allowance_frac(surface_type: str, spacing_in: float) -> float:
    """Allowance for plates, headers, corners and window framing (fraction of area), for walls,
    floors, ceilings or roofs at the given on-center spacing."""
    kind = {"rim_joist": "wall", "foundation_wall": "wall"}.get(surface_type, surface_type)
    table = data.framing()["typical_framing_factors"][kind]
    # origin: OS-HPXML constructions.rb framing factors (see data/framing.json); each tabulated point is a
    # nominal 2x member, 1.5 in wide (Material.Stud2x(2)).
    points = sorted((p["spacing_in"], p["framing_factor_frac"] - 1.5 / p["spacing_in"]) for p in table)
    if spacing_in <= points[0][0]:
        return points[0][1]
    if spacing_in >= points[-1][0]:
        return points[-1][1]
    for (s0, a0), (s1, a1) in zip(points, points[1:]):
        if s0 <= spacing_in <= s1:
            return a0 + (a1 - a0) * (spacing_in - s0) / (s1 - s0)
    raise AssertionError("unreachable")


def framing_share(surface_type: str, spacing_in: float, lumber: str = "custom", width_in: Optional[float] = None,
                  depth_in: Optional[float] = None, allowance_frac: Optional[float] = None) -> FramingShare:
    """Framing share from lumber and spacing. ``width_in``/``depth_in`` override the nominal size's
    actual dimensions (required for "custom", e.g. old full-dimension lumber)."""
    if lumber != "custom":
        w, d = lumber_size(lumber)
        width_in = w if width_in is None else width_in
        depth_in = d if depth_in is None else depth_in
    if width_in is None or depth_in is None:
        raise ValueError("Custom lumber needs width_in and depth_in (the actual member size).")
    if spacing_in <= width_in:
        raise ValueError(f"Spacing {spacing_in:g} in must be larger than the member width {width_in:g} in.")
    member = width_in / spacing_in
    overridden = allowance_frac is not None
    allowance = allowance_frac if overridden else typical_allowance_frac(surface_type, spacing_in)
    total = min(member + allowance, 0.99)
    src = data.framing()["typical_framing_factors_source"]
    return FramingShare(width_in, depth_in, spacing_in, member, allowance, overridden, total,
                        "allowance entered by the user" if overridden else src)
