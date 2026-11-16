# Reference comparison results

RightTon's design loads are compared, component by component, with NREL's
OpenStudio-HPXML (the "reference engine") on that project's own sample houses.

## Which route was used

**Route A: the reference engine was installed and run directly.** [CONFIRMED]

- OpenStudio 3.11.0 (`OpenStudio-3.11.0+241b8abb4d-Ubuntu-24.04-x86_64.deb`,
  from the NREL/OpenStudio GitHub release) installed and ran in the build
  environment (Ubuntu 24.04).
- OpenStudio-HPXML at commit `fb18723b7ee2f83b832b14916cb45be87879d5ba`
  (v1.13.0 development), run with `workflow/run_simulation.rb --skip-simulation`,
  which performs the design-load calculation without an annual simulation.
- The fallback (published results in `workflow/tests/base_results/results_simulations_hvac.csv`)
  was not needed and not used.

Date of run: 2026-11-15.

## Tolerance

From SPEC.md: totals within 2 %, components within 5 %. The reference reports
whole Btu/h, so a value also passes when it is within 1 Btu/h. Nothing else was
loosened.

## Result

- Sample houses run through the reference engine: 504 (one, `base-misc-multiple-buildings`,
  needs a building id and was not run) -> 503 with output
- **Compared: 441 sample houses plus 7 old-house stress cases = 448. Pass: 448. Fail: 0.**
- No building, zone or room value differed from the reference by more than
  1 Btu/h, so every difference is rounding of the reported numbers.
- Compared per house: 33 building-level values (13 heating, 15 sensible cooling,
  5 latent cooling components and totals). For the two houses that define zones
  and rooms, also every zone (3) and every room (8).
- Skipped: 62 houses that use something RightTon v1 does not model (table below).
  They are reported as skipped, not as passes.

The comparison covers detached houses and attached units, slab / crawlspace /
basement / walkout foundations, vented and unvented attics, cathedral roofs,
garages, all the reference's wall, window, shading, overhang, skylight and
storm-window variants, blower-door inputs in every unit, the default
tight/average/leaky table, exhaust/supply/balanced ventilation, duct location
and leakage variants, and weather files from Miami to Duluth plus one
southern-hemisphere file.

## Old-house stress cases

Seven houses built for both engines (`validation/stress/`, made by `make_stress_cases.py` from NREL's
vented-crawlspace sample house; fictional). Run through the reference on 2026-11-16; all pass, and no
value differs by more than 1 Btu/h.

| Case | What is changed | Reference heating / sensible / latent (Btu/h) |
| --- | --- | --- |
| `stress-balloon-frame-walls` | Walls R-4.7 (plaster on lath, empty cavity, board sheathing, siding), bare rim joists | see `validation/reference/design_loads.json` |
| `stress-single-pane-behind-porch` | Single-pane wood windows (U 0.89, SHGC 0.64), no blinds; south windows under an 8 ft porch roof | " |
| `stress-raised-floor-vented-crawlspace` | Bare wood floor (R-3.7) over the vented crawlspace, 11 ft ceilings | " |
| `stress-sealed-attic-with-ducts` | Unvented attic insulated at the roof deck (R-19.2) over a bare plaster ceiling, all ducts in the attic | " |
| `stress-leaky-14-ach50` | Blower door 14 ACH50 | " |
| `stress-old-house-all-denver` | All of the above, Denver weather | 62,154 / 32,542 / -1,473 |
| `stress-old-house-all-houston` | All of the above, Houston weather | 38,607 / 36,284 / 5,291 |

Two things these cases do **not** cover, because the reference has no equivalent:

- **A porch as a space.** The reference models a porch roof as a window overhang, and so do these cases.
  RightTon's house file can also describe an open porch as a space, which shades the wall and its
  windows completely; that path is checked by hand calculation only.
- **A sealed attic as conditioned space.** The reference treats a roof-insulated unvented attic as an
  unconditioned space with a calculated temperature, and so do these cases. RightTon's house file can
  instead declare the attic `conditioned` (inside the envelope), which removes duct losses entirely.
  The two descriptions give different answers by design; which one is right depends on whether the
  attic is really inside the air barrier.

The assembly R-values in these cases were worked out by RightTon's layer builder and then given to both
engines as numbers, so the layer builder itself is still checked only by hand calculation.

## What this comparison does and does not show

It shows that the Python port reproduces the reference's design-load method.

It does not show, and nobody should read it as showing:

1. **That the layer-by-layer assembly builder is right.** The reference takes a
   finished assembly R-value, so the comparison feeds RightTon the same R-value.
   `core/rightton/assemblies.py` is checked only by hand calculations.
2. **That RightTon's own defaults are right.** Inputs come from the reference's
   defaulted file (`in.xml`): duct areas, internal gains, occupants, shielding
   class and so on were filled in by the reference, not by RightTon.
3. **That the method itself is accurate for a given real house.** Both engines
   share one method and its tables.

## Known differences from the reference (by design)

| Difference | Effect on the comparison |
| --- | --- |
| Rooms get latent loads and a share of ventilation load. The reference gives rooms sensible loads only and keeps ventilation at zone level. | Room ventilation is left out when comparing room totals; zone and building totals are unaffected. |
| Partitions between rooms in zones with different setpoints carry a zone-to-zone transfer load. The reference has one setpoint for the house and no such load. | None: sample houses have one setpoint, so the transfer is zero. Tested by hand calculation only. |
| Wetbulb temperature is solved by bisection, the reference uses its own iteration. | Only used for weather files without a design-conditions header; results agree to rounding. |
| Infiltration is shared among rooms by exposed wall area, as in the reference, unless the user assigns shares. | None: sample houses assign no shares. Tested by hand calculation only. |
| A window in a wall that faces a porch, garage or other buffer space gets a load (shaded-glass value under an open porch, conduction only otherwise). The reference gives such windows no load at all. | One sample house has such a window (`base-bldgtype-mf-unit-adjacent-to-multiple-hvac-none`); the comparison leaves that window out on the RightTon side so both engines see the same inputs. With it, RightTon's heating total is 4.9 % higher. Tested by hand calculation only. |
| Heat from equipment such as a dehumidifier is its own result line. The reference has no such input. | None. |

## Not ported in v1 (the skipped houses)

### Skipped, by reason

| Reason | Houses | Examples |
| --- | --- | --- |
| more than one heating or cooling system in a zone | 21 | `base-bldgtype-mf-unit-shared-boiler-chiller-water-loop-heat-pump`, `base-bldgtype-mf-unit-shared-boiler-cooling-tower-water-loop-heat-pump`, `base-bldgtype-mf-unit-shared-boiler-only-fan-coil-fireplace-elec` |
| central-fan-integrated ventilation (CFIS) | 14 | `base-hvac-ptac-cfis`, `base-hvac-pthp-cfis`, `base-mechvent-cfis` |
| file holds more than one dwelling unit | 7 | `base-bldgtype-mf-whole-building`, `base-bldgtype-mf-whole-building-common-spaces`, `base-bldgtype-mf-whole-building-detailed-electric-panel` |
| ERV/HRV (rated-efficiency to effectiveness conversion not ported) | 5 | `base-mechvent-erv`, `base-mechvent-erv-atre-asre`, `base-mechvent-hrv` |
| shared ventilation system | 3 | `base-bldgtype-mf-unit-shared-mechvent`, `base-bldgtype-mf-unit-shared-mechvent-multiple`, `base-bldgtype-mf-unit-shared-mechvent-preconditioning` |
| evaporative cooler | 3 | `base-hvac-evap-cooler-furnace-gas`, `base-hvac-evap-cooler-only`, `base-hvac-evap-cooler-only-ducted` |
| cooling system with integrated heating | 3 | `base-hvac-ptac-with-heating-electricity`, `base-hvac-ptac-with-heating-natural-gas`, `base-hvac-room-ac-with-heating` |
| location 'manufactured home underbelly' | 2 | `base-foundation-belly-wing-no-skirt`, `base-foundation-belly-wing-skirt` |
| unit multiplier (reference reports loads for all identical units together) | 2 | `base-misc-unit-multiplier`, `base-misc-unit-multiplier-detailed-electric-panel` |
| duct location 'roof deck' | 1 | `base-bldgtype-mf-unit-adjacent-to-multiple` |
| HVAC system serving part of the load | 1 | `base-hvac-room-ac-only-partial-conditioning` |
Also not ported (per the v1 scope): heat pump sizing adjustments, geothermal loop
sizing, equipment capacity selection, and the tabulated default duct loads.

## Open items marked [CONFIRM] in the code

- `core/rightton/assemblies.py`: the interior air film for a sloped roof is taken
  as the horizontal-surface average; the reference varies it with pitch.
- `core/rightton/airflow.py`: ERV/HRV effectiveness is a direct input; the
  reference derives it from rated recovery efficiency and fan power.

## How to reproduce

Without the reference engine (what the test suite and CI do), using the committed
snapshot of 129 distinct houses and their reference loads:

```bash
python validation/compare.py
```

With the reference engine:

```bash
validation/run_reference.sh /path/to/OpenStudio-HPXML /tmp/refout 4
```

```bash
python validation/compare.py --reference-dir /tmp/refout --epw-dir /path/to/OpenStudio-HPXML/weather --snapshot
```

A change to load math is not done until this still passes. If it cannot pass,
record the gap and its cause here; do not loosen the tolerance.
