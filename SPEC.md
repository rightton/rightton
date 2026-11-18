# RightTon — Specification v0.1

RightTon is a free, open-source residential heating and cooling load calculator that lets a homeowner describe an older or unusual house as it actually is, and compare retrofits against equipment size before buying.

## Purpose

**Who it is for:** homeowners and owner-builders whose houses don't fit builder-grade defaults: older houses, mixed construction, partial retrofits, unusual ceiling heights.

**The problem with existing tools:**

- Assemblies are picked from short lists that rarely match real construction (plaster on lath, diagonal board sheathing, partial spray-foam retrofits).
- Ceiling heights, framing and foundation types assume modern construction.
- Air leakage is a "tight / average / leaky" choice, so a measured blower door number (ACH50) can't be used.
- Latent (moisture) load is buried, though in humid climates it drives comfort and the cost of oversizing.
- Comparing "air seal + insulate" against "bigger unit" means re-running the whole calculation by hand.

**Success for v1:** a user can enter a multi-room zone, get sensible and latent cooling loads and a heating load with a component breakdown, and compare several retrofit scenarios.

## Scope

v1 calculates peak design loads (the equipment-size question), room by room and zone by zone. It does not estimate annual energy bills or design ducts.

| In v1 | Later | Out |
| --- | --- | --- |
| Cooling load, sensible + latent | AutoCAD floor-plan import (DXF, one closed outline per room) | Permit or code-compliance submittals |
| Heating load | Annual energy and bill estimates | Duct design |
| Room-by-room loads, each room with its own ceiling height and surfaces; zones built from rooms | Equipment selection against manufacturer performance data | Commercial buildings |
| Heat transfer between zones (e.g. upstairs over a conditioned downstairs) | Utility-bill calibration | |
| Custom layered assemblies, any ceiling height | Register and duct airflow by room | |
| Measured ACH50 or estimated leakage | | |
| Scenario comparison | | |
| Printable report + saved project file | | |

Each zone's load is the sum of its rooms at the zone's peak hour; each room's own peak is shown too.

## Calculation method

A hybrid. The calculation engine is a Python package that can be used directly (scripts, Jupyter) and runs in the browser through Pyodide (Python compiled to run inside a web page). Its results are checked against NREL's OpenStudio-HPXML.

| Option | How it works | Pros | Cons |
| --- | --- | --- | --- |
| A. Own engine | Port a published residential design-load method to Python | Instant, works on a phone, no install, every equation visible | We own correctness; needs strong testing |
| B. Front end for OpenStudio-HPXML | App writes an HPXML building file; NREL's engine computes loads | Validated, maintained by a national lab, BSD-style license | Needs a machine with OpenStudio installed; slower; heavier setup |
| **C. Hybrid (chosen)** | A for daily use; HPXML export so B can verify A | Speed of A, credibility of B | Two code paths to keep consistent |

**Source of the method:** port the design-load logic from [OpenStudio-HPXML](https://github.com/NatLabRockies/OpenStudio-HPXML) (`HPXMLtoOpenStudio/resources/hvac_sizing.rb`) rather than invent one.

- That file computes design loads directly, without running an EnergyPlus simulation, and already calculates loads per space (room). Heat pump, geothermal and equipment-selection parts can be skipped in v1.
- Outdoor design conditions come from open EPW weather files for the nearest station.
- Infiltration: measured ACH50 is converted to design-condition airflow with the same published method the reference engine uses, and the conversion is shown to the user.
- Latent load: infiltration and ventilation moisture, people, and any dehumidifier's heat output reported separately from sensible load.

## Inputs

Every input has a visible default, a source note, and a confidence flag (measured / estimated / default), so the report shows which numbers the answer rests on.

| Group | What the user enters | Old-house needs this covers |
| --- | --- | --- |
| Location | ZIP or weather station; indoor setpoints (cooling temperature and humidity, heating temperature) | Design conditions pulled automatically; override allowed |
| Zones and rooms | Rooms with floor area and ceiling height; rooms grouped into zones; which surfaces border other zones | 10–14 ft ceilings; mixed heights; upstairs over conditioned downstairs |
| Assemblies | Layer-by-layer builder (material, thickness, R per inch), framing type and spacing, air films added automatically | Plaster on lath, diagonal board sheathing, partial spray foam, foam board over sheathing, uninsulated balloon framing |
| Walls / roof / ceiling / floor | Area, orientation, color, assembly, what is on the other side | Conditioned attic, raised floor over vented crawlspace, porch roofs |
| Windows and doors | Count, size, orientation; type (single-pane wood, storm-over-single, double, low-e) or entered U and SHGC; overhangs, porches, interior blinds | Old double-hungs with or without storm windows; deep porch shading |
| Air leakage | ACH50 from a blower door test, or a guided estimate; share assigned to each zone | Direct measured input instead of tight/average/leaky |
| Ducts | Location (conditioned attic, crawlspace, inside), insulation, leakage | Ducts inside a sealed attic count as nearly zero loss |
| Internal gains | Occupants, appliances, lighting; equipment adding heat (e.g. a dehumidifier discharging into the system) | Dehumidifier heat is a real cooling load |
| Ventilation | Mechanical fresh-air flow, if any | |

**User data stays on the user's device.** Each project is saved only as a local file: no account, no server copy. The app opens with NREL's sample house, which the user edits or replaces.

## House file format

The house file is an open, fully specified format that any tool can write or edit: a CAD exporter, the RightTon web app, a script, or an LLM given the format guide and a description of a house. The format is a public contract, independent of the RightTon app.

**Definition**

- One data model, defined by a published, versioned [JSON Schema](https://json-schema.org) (a machine-readable definition that validators in every common language can check files against): `schema/rightton-house.schema.json`.
- Every file declares `format_version` (semantic versioning). Readers accept older minor versions; breaking changes bump the major version and ship a converter.
- Every field in the schema has a plain-English description, allowed values, and units. `docs/FORMAT.md` is the human reference and must agree with the schema (a test checks this).
- `docs/FORMAT-GUIDE-FOR-LLMS.md`: a compact, self-contained authoring guide (data model, rules, worked example, common mistakes) that a person can paste into any LLM along with a description of their house to get a valid file.

**Encoding**

- JSON is canonical; the app always saves JSON.
- YAML is accepted for hand authoring. It is the same data model, validated by the same schema; YAML ↔ JSON conversion is lossless.
- File names: `*.rtn.json` / `*.rtn.yaml`.

**Data model rules**

- US units only in v1, and every quantity's unit is in its field name (`area_ft2`, `height_ft`, `r_value_hr_ft2_f_btu`, `u_factor_btu_hr_ft2_f`, `azimuth_deg`). No unitless numbers that could be read two ways.
- Everything has an `id`; references are by id (a window names its wall, a wall names its room and its assembly). Assemblies are defined once in an `assemblies` library and reused by id.
- Top-level sections: `format_version`, `project`, `location`, `assemblies`, `glazings` (window glazings entered from labels, reused by id), `zones`, `rooms`, `spaces` (attic, crawlspace, garage, porch, conditioned-but-unoccupied spaces), `surfaces`, `openings`, `air` (infiltration, ventilation, ducts), `equipment` (heat-producing equipment such as dehumidifiers), `hvac` (systems, which rooms have supply registers and returns), `scenarios`, `extensions`.
- Any numeric input may be a bare number or `{ "value": …, "source": "…", "confidence": "measured" | "estimated" | "default" }`. A bare number means `default`.
- Geometry is optional: a surface needs an area, and may also carry a polygon outline (for CAD tools and future 3D views). The engine uses areas.
- Scenarios are lists of changes against the baseline (`set` a field by id path, `add` or `remove` an item), so they stay small and readable.
- `extensions`: tools store their own data under their own key (e.g. `extensions.my-cad-tool`); every reader must preserve extensions it does not understand when re-saving.
- Location is a weather station identifier and optional design-condition overrides. There is no address field.

**Tooling (in `core/`)**

- `python -m rightton.validate house.rtn.json`: schema check plus checks the schema cannot express (references resolve, windows fit in their walls, every room belongs to a zone), with plain-English error messages that say where and how to fix.
- Load → save round-trips without change.
- `examples/`: NREL's base house converted to the format, and a fictional old house (balloon-frame walls, single-pane windows behind porches, a sunroom, raised floor over a vented crawlspace, conditioned attic with ducts) written for both YAML and JSON.

## Outputs

The headline is three numbers per zone and room — sensible cooling, latent cooling, heating, in Btu/h — with the breakdown that explains them directly underneath.

- **Load summary:** sensible, latent and total cooling; heating; equivalent tons; sensible heat ratio (the share of cooling that is temperature rather than moisture).
- **Component breakdown:** load from each wall, roof/ceiling, floor, window group, infiltration, ducts, people and equipment, as a ranked bar chart.
- **Sizing guidance:** the capacity range the load supports, with the sensible and latent capacity a unit needs at design conditions, written for a homeowner talking to a contractor.
- **Input confidence:** which results rest on defaults or estimates, and how much the answer moves if each changes, shown as a load range.
- **Printable report** to hand a contractor, clearly labeled as a homeowner estimate.
- **Project file** (JSON) to save and reopen; **HPXML export** for checking against the reference engine.

## Scenario comparison

A scenario is a copy of the baseline house with only the changed items edited; the app shows each scenario's load next to the baseline and the difference.

- Create a scenario by duplicating the baseline and changing items (replace these windows, set ACH50 to a target, add crawlspace floor insulation).
- Scenarios can be stacked to show combined effect, since savings don't simply add.
- Comparison view: one row per scenario — sensible, latent, heating, tons, change from baseline — plus a side-by-side component chart.
- Each scenario can carry a cost the user enters, so load reduction per dollar can be compared. The app never supplies prices.

## Validation

The engine is not trusted until its loads match the reference engine on standard test houses within tolerance, component by component.

1. **Equation tests:** each calculation (assembly R-value, window gain, infiltration conversion) checked against hand calculations written into the test suite.
2. **Reference comparison:** run OpenStudio-HPXML's sample house files through both engines and compare each load component. Tolerance: totals within 2%, components within 5%. Method error this small is far below the half-ton (6,000 Btu/h) equipment step and the uncertainty in inputs like ACH50 and window performance.
3. **Old-house stress cases:** uninsulated balloon-frame walls, single-pane windows with deep porches, raised floor over vented crawlspace, conditioned attic — built in both engines and compared.

Real users' houses are never committed to this repository.

## Architecture and repository

A static web app — files that run entirely in the user's browser, hosted on GitHub Pages — with no server and no user data leaving the device.

```
README.md        what it is, how to use it, limits
SPEC.md          this document
CLAUDE.md        working rules for AI coding agents
LICENSE          MIT
core/            Python calculation engine + tests
app/             TypeScript web interface (calls core via Pyodide)
data/            materials, windows, weather stations (each value sourced)
validation/      reference houses, comparison scripts, results
schema/          house file JSON Schema
docs/            format reference and LLM authoring guide
examples/        example house files (fictional or NREL samples only)
```

- **Core:** no screen code; testable and usable on its own.
- **Tests:** run automatically on every change through GitHub Actions.
- **Reference check:** a script that takes exported HPXML files and runs OpenStudio-HPXML for comparison.

## Naming, licensing, disclaimers

RightTon never uses "Manual J" in its name or claims. Manual J is an ACCA trademark, and only ACCA-approved software counts for code compliance ([ACCA](https://www.acca.org/approved-software)).

- **Findability:** so people searching for "Manual J" can find it, the README, the app's About text and the repository description may say, in exactly these words: "An open-source alternative to Manual J load calculation software. Not affiliated with or approved by ACCA; Manual J® is a registered trademark of ACCA." Repository topics may include `manual-j`. "Manual J" is never part of the product name, and RightTon is never described as Manual J "compliant", "certified" or "approved". A test checks the wording.

- **Description:** "residential heating and cooling load calculator" based on published open methods, with methods and sources cited in the app and README.
- **Table values:** the reference code contains factors NREL transcribed from Manual J 8th Edition tables, published under its BSD license. Every such value ported here is tagged with its origin so it can be replaced with an independently derived value if needed. Nothing is copied from the Manual J book itself.
- **License:** MIT. Code ported from OpenStudio-HPXML keeps its BSD-style copyright notice, as that license requires, and the OpenStudio name is not used for this project.
- **Disclaimer** on screen and on every report: a homeowner planning estimate, not a design for permits or rebates. Where those require an ACCA-approved calculation, a contractor must provide one.

## Build priorities

1. Calculation core (Python): rooms and zones, assemblies, windows, infiltration from ACH50, ducts, internal gains, latent load, zone-to-zone transfer.
2. Test suite with hand-calculation checks.
3. Reference comparison against OpenStudio-HPXML sample houses, results written to `validation/`.
4. House file format: schema, docs, LLM guide, validator, examples (see House file format).
5. Old-house stress cases built in both engines and compared; RightTon's own defaults with sources.
6. Web interface, polished: house editor (rooms, assemblies, surfaces, openings), results with component breakdown, scenario comparison, save/open house files.
7. Printable report, expanded old-house material library, DXF import.
