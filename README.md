# RightTon

Right-size your heating and cooling, and see what retrofits change.

RightTon is a free, open-source residential heating and cooling load calculator for real houses, including old and unusual ones: custom wall and ceiling assemblies, real ceiling heights, measured blower-door leakage (ACH50), and side-by-side retrofit scenarios. Your house data stays on your device.

**Use it:** <https://rightton.github.io/rightton/> (the web app; goes live once this work is merged to `main` and GitHub Pages is switched on, see [NEXT.md](NEXT.md)). It runs entirely in your browser: the calculation is the Python core compiled to run in the page, and no house data is uploaded.

**Status:** early development. The calculation core matches the reference engine on 448 test houses, the house file format is published, and the web interface is built. Printable reports and floor-plan import are not built yet.

## What is here

| | |
| --- | --- |
| [`app/`](app) | The web interface: house editor (rooms, assembly library with a layer builder, surfaces, openings, air and ducts, HVAC registers, equipment), results with a ranked component breakdown and a room-by-room view, scenario comparison, open and save house files. Desktop and phone. |
| [`core/`](core) | The calculation engine (Python, no dependencies). The only place load math lives. |
| [`schema/`](schema), [`docs/FORMAT.md`](docs/FORMAT.md) | The house file format (`*.rtn.json`, `*.rtn.yaml`): an open, versioned format any tool can write. |
| [`docs/FORMAT-GUIDE-FOR-LLMS.md`](docs/FORMAT-GUIDE-FOR-LLMS.md) | Paste this into any language model with a description of your house to get a house file. [How it was tested](docs/LLM-GUIDE-TEST.md). |
| [`examples/`](examples) | Example house files: NREL's base house and two fictional old houses. |
| [`data/`](data) | Materials, glazing presets, weather stations and defaults, each value with its source. |
| [`validation/`](validation) | Comparison against NREL's OpenStudio-HPXML: [results](validation/RESULTS.md). |

## Checking a house file

```bash
cd core
```

```bash
python -m rightton.validate ../examples/old-house.rtn.yaml
```

Problems are reported in plain English with where they are and how to fix them. YAML files need `pip install pyyaml`; JSON files need nothing.

## Running the web app locally

```bash
cd app
```

```bash
npm install
```

```bash
npm run dev
```

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
- A whole house file: `rightton.housefile.load(path)` then `rightton.housefile.to_building(house).building`.
- Tests: `python -m pytest core` (needs `pip install pytest pyyaml jsonschema`). Reference comparison: `python validation/compare.py`; results in [validation/RESULTS.md](validation/RESULTS.md).
- What comes next: [NEXT.md](NEXT.md).

**Not for permits.** RightTon is a homeowner planning estimate. Where a code-compliant load calculation is required, use ACCA-approved software through a contractor.

Licensed under the MIT License. Design-load logic is ported from NREL's [OpenStudio-HPXML](https://github.com/NatLabRockies/OpenStudio-HPXML) under its BSD-style license.
