# RightTon

Right-size your heating and cooling, and see what retrofits change.

RightTon is a free, open-source residential heating and cooling load calculator for real houses, including old and unusual ones: custom wall and ceiling assemblies, real ceiling heights, measured blower-door leakage (ACH50), and side-by-side retrofit scenarios. Your house data stays on your device.

**Status:** early development. The calculation core is built and matches the reference engine on 441 of its sample houses; there is no user interface yet. See [SPEC.md](SPEC.md) for scope and method.

## Using the calculation core

The engine is a plain Python package with no dependencies (`core/rightton`).

```python
from rightton.engine import calculate
from rightton.model import *

house = Building(
    conditions=DesignConditions(heating_design_temp_f=25, cooling_design_temp_f=93, daily_temp_range="medium",
                                humidity_difference_grains=45, latitude_deg=30),
    zones=[Zone("main")],
    rooms=[Room("living", "main", floor_area_ft2=400, ceiling_height_ft=12, occupants=2)],
    walls=[Wall("north wall", "living", OUTSIDE, area_ft2=240, r_value=4.0)],
    windows=[Window("double-hung", "north wall", area_ft2=30, azimuth_deg=0, u_factor=1.0, shgc=0.7)],
    infiltration=Infiltration(ach50=12),
)
loads = calculate(house).building
print(loads.heat_total, loads.cool_sensible, loads.cool_latent)  # Btu/h
```

- Design conditions can be read from an EPW weather file: `rightton.weather.read_epw` and `design_conditions`.
- Wall, ceiling and floor R-values can be built from layers: `rightton.assemblies.Assembly`.
- Tests: `python -m pytest core`. Reference comparison: `python validation/compare.py`; results in [validation/RESULTS.md](validation/RESULTS.md).
- What comes next: [NEXT.md](NEXT.md).

**Not for permits.** RightTon is a homeowner planning estimate. Where a code-compliant load calculation is required, use ACCA-approved software through a contractor.

Licensed under the MIT License. Design-load logic is ported from NREL's [OpenStudio-HPXML](https://github.com/NatLabRockies/OpenStudio-HPXML) under its BSD-style license.
