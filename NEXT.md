# Next steps

State on 2026-11-15: build priorities 1-3 of SPEC.md are done and passing.
`python -m pytest core` (187 tests) and `python validation/compare.py`
(121 snapshot houses) both pass. The interface (priority 4) has not been started.

## Before or alongside the interface (priority 4)

1. **Old-house stress cases (SPEC validation step 3).** Write HPXML files for:
   uninsulated balloon-frame walls, single-pane windows behind a deep porch,
   raised floor over a vented crawlspace, conditioned (roof-insulated unvented)
   attic with ducts in it. Run them through `validation/run_reference.sh` and add
   them to the snapshot. This is the first test of the cases the tool exists for.
2. **HPXML export** (SPEC outputs): the reverse of `validation/hpxml_reader.py`,
   so any RightTon project can be checked against the reference engine.
3. **Project file (JSON) load/save** for `rightton.model.Building`, with the
   per-input default / source / confidence flags SPEC.md asks for. The model
   currently carries values only.
4. **Defaults RightTon must own**, since the comparison used the reference's:
   internal gains (the reference uses 2400 Btu/h, or 3600 with more than one refrigerator/freezer),
   occupants (bedrooms + 1), duct surface areas and effective R-value, shielding
   class, infiltration height and volume.
5. **Pyodide check**: the core has no dependencies beyond the standard library,
   but `weather.py` finds `data/ashrae622_wsf.csv` by file path; package the data
   file with the wheel before loading it in the browser.
6. **A results-to-report layer**: ranked component list, sensible heat ratio,
   tons, and the ACH50 -> design airflow steps (already in `Results.infiltration`).

## Method gaps to close (each is listed in validation/RESULTS.md)

- ERV/HRV: port `Airflow.calc_hrv_erv_effectiveness` so rated efficiencies can be entered (5 skipped houses).
- Ventilation through the air handler (CFIS): port `apply_hvac_cfis_loads` (14 skipped houses).
- More than one heating or cooling system per zone, and systems serving part of the load (22 skipped houses).
- User-assigned infiltration share per zone (SPEC inputs table).
- Dehumidifier heat as its own reported line (today it is entered as room internal sensible gain).
- Roof interior air film by pitch in `assemblies.py` ([CONFIRM]).
- Sensitivity ranges for the "input confidence" output.

## Housekeeping

- `.github/workflows/tests.yml` runs the tests and the snapshot comparison on every push.
- The reference clone and OpenStudio install live outside the repo; nothing from them is needed to run the tests.
