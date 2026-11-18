"""How RightTon may mention Manual J (issue #9; SPEC "Naming, licensing, disclaimers")."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SENTENCE = ("An open-source alternative to Manual J load calculation software, for informational purposes only. "
            "Not affiliated with or approved by ACCA; Manual J® is a registered trademark of ACCA.")
PUBLIC = [ROOT / "README.md", ROOT / "app" / "index.html", *sorted((ROOT / "app" / "src").rglob("*.ts*")),
          *sorted((ROOT / "docs").glob("*.md"))]


def test_alternative_wording_is_in_readme_and_app():
    assert SENTENCE in (ROOT / "README.md").read_text(encoding="utf-8")
    assert SENTENCE in (ROOT / "app" / "src" / "App.tsx").read_text(encoding="utf-8")


def test_never_claims_compliance_or_uses_the_name():
    claim = re.compile(r"Manual J®?[^.;]*\b(compliant|compliance|certified|approved)\b", re.I)
    for path in PUBLIC:
        text = path.read_text(encoding="utf-8")
        assert not claim.search(text), f"{path.relative_to(ROOT)}: {claim.search(text).group(0)}"
    title = re.search(r"<title>(.*?)</title>", (ROOT / "app" / "index.html").read_text(encoding="utf-8")).group(1)
    assert "Manual J" not in title
