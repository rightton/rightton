"""Layer-by-layer assembly R-values (parallel-path method).

This module is RightTon's own (it is not ported): the reference engine takes a
finished assembly R-value as input, while RightTon lets the user build the
assembly from layers so that old-house constructions (plaster on lath, board
sheathing, empty balloon-frame cavities) can be described as they are.

Method: the isothermal-planes-free "parallel path" method described in the
ASHRAE Handbook of Fundamentals (chapter on heat, air and moisture control in
building assemblies): heat flows through the framing path and the cavity path
side by side, each path being its layers in series including air films, and the
two path U-factors are area-weighted by the framing fraction.

Air film R-values (hr-ft2-F/Btu) are the ones the reference engine uses, which it
cites as ASHRAE Handbook of Fundamentals 2005, chapter 25, Table 1
(OS-HPXML materials.rb, Material.AirFilm*).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# origin: OS-HPXML materials.rb -> ASHRAE HoF 2005 F25.2 Table 1
FILM_INDOOR_WALL = 0.68  # vertical surface, still air
FILM_INDOOR_FLOOR_DOWN = 0.92  # horizontal surface, heat flow down
FILM_INDOOR_HORIZ_UP = 0.61  # horizontal surface, heat flow up
FILM_INDOOR_HORIZ_AVERAGE = (FILM_INDOOR_FLOOR_DOWN + FILM_INDOOR_HORIZ_UP) / 2.0
FILM_OUTDOOR_WINTER = 0.17  # 15 mph wind
FILM_OUTDOOR_SUMMER = 0.25  # 7.5 mph wind
FILM_OUTDOOR = (FILM_OUTDOOR_WINTER + FILM_OUTDOOR_SUMMER) / 2.0  # year-round value used by the reference

# Interior film by surface position; the film on the far side is FILM_OUTDOOR
# when exposed to wind, otherwise the same still-air film as the near side.
_INDOOR_FILM = {
    "wall": FILM_INDOOR_WALL,
    "ceiling": FILM_INDOOR_HORIZ_AVERAGE,
    "floor": FILM_INDOOR_FLOOR_DOWN,
    "roof": FILM_INDOOR_HORIZ_AVERAGE,  # [CONFIRM] reference varies this with roof pitch
}


@dataclass
class Layer:
    """One layer of an assembly, listed from inside to outside.

    Give the thermal resistance either as ``r_per_inch`` (with ``thickness_in``)
    or as a fixed ``r_value`` (e.g. an air space or a rated product).
    A framed layer also has ``framing_r_per_inch``: the material that replaces
    the cavity fill over the framing fraction of the area.
    """

    name: str
    thickness_in: float = 0.0
    r_per_inch: Optional[float] = None
    r_value: Optional[float] = None
    framing_r_per_inch: Optional[float] = None
    source: str = ""  # where the R-value came from (shown in reports)

    @property
    def cavity_r(self) -> float:
        if self.r_value is not None:
            return self.r_value
        if self.r_per_inch is None:
            raise ValueError(f"Layer '{self.name}' needs r_per_inch or r_value.")
        return self.r_per_inch * self.thickness_in

    @property
    def framing_r(self) -> float:
        if self.framing_r_per_inch is None:
            return self.cavity_r
        return self.framing_r_per_inch * self.thickness_in


@dataclass
class Assembly:
    name: str
    layers: list[Layer] = field(default_factory=list)
    position: str = "wall"  # wall, ceiling, floor, roof
    framing_fraction: float = 0.0  # share of area that is framing (0..1)
    exposed_to_wind: bool = True  # False when the far side is an attic, crawlspace, etc.

    @property
    def film_inside_r(self) -> float:
        return _INDOOR_FILM[self.position]

    @property
    def film_outside_r(self) -> float:
        return FILM_OUTDOOR if self.exposed_to_wind else _INDOOR_FILM[self.position]

    def path_r_values(self) -> tuple[float, float]:
        """(cavity path R, framing path R), each including both air films."""
        films = self.film_inside_r + self.film_outside_r
        r_cavity = films + sum(layer.cavity_r for layer in self.layers)
        r_framing = films + sum(layer.framing_r for layer in self.layers)
        return r_cavity, r_framing

    def u_factor(self) -> float:
        """Area-weighted U-factor (Btu/h-ft2-F): U = ff/R_framing + (1-ff)/R_cavity."""
        r_cavity, r_framing = self.path_r_values()
        ff = self.framing_fraction
        if not 0.0 <= ff < 1.0:
            raise ValueError("framing_fraction must be in [0, 1).")
        return ff / r_framing + (1.0 - ff) / r_cavity

    def r_value(self) -> float:
        """Effective assembly R-value (hr-ft2-F/Btu), air films included."""
        return 1.0 / self.u_factor()
