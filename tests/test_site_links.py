"""Pages links and the volunteer landing section."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_site_links_resolve():
    script = ROOT / "scripts" / "check_site_links.py"
    done = subprocess.run([sys.executable, str(script)], check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr or done.stdout


def test_landing_section_is_a_simulated_credit_invitation():
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    start = html.index('id="run"')
    section = html[start:html.index("</section>", start)]
    assert "Run one command, do verified work for open AI" in section
    assert 'href="human/"' in section
    assert 'href="console/"' in section
    assert 'href="join/"' in section
    lowered = section.lower()
    for banned in ("token sale", "returns", "yield", "investor", "airdrop", "mint"):
        assert banned not in lowered
    assert "utility credit for verified contribution" in lowered
    assert "0xdffe664d23e30baff7ad4d16831ad625cc90bcca" in lowered
