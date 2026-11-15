"""The committed snapshot of reference-engine results must keep matching.

See validation/RESULTS.md. Tolerances come from SPEC.md: totals within 2 %,
components within 5 %.
"""

import argparse
import sys
from pathlib import Path

VALIDATION = Path(__file__).resolve().parents[2] / "validation"
sys.path.insert(0, str(VALIDATION))

import compare  # noqa: E402


def test_tolerances_are_the_spec_values():
    assert compare.TOTAL_TOL == 0.02
    assert compare.COMPONENT_TOL == 0.05
    assert compare.ABS_TOL_BTUH == 1.0


def test_snapshot_houses_match_reference_engine():
    results = compare.run(argparse.Namespace(reference_dir=None, epw_dir=None, snapshot=False))
    assert len(results) >= 121
    not_passing = {name: r["reason"] for name, r in results.items() if r["status"] != "pass"}
    assert not not_passing


def test_base_house_reference_values():
    """Spot check against numbers printed by the reference engine for its base
    house (results_design_load_details.csv): infiltration 80 cfm heating and
    41 cfm cooling; totals 41,543 / 27,993 / 265 Btu/h."""
    import hpxml_reader
    from rightton.engine import calculate

    res = calculate(hpxml_reader.load(compare.HOUSES_DIR / "base.xml.gz", compare.EPW_DIR))
    assert round(res.infiltration.heating_cfm) == 80
    assert round(res.infiltration.cooling_cfm) == 41
    assert round(res.building.heat_total) == 41543
    assert round(res.building.cool_sensible) == 27993
    assert round(res.building.cool_latent) == 265
