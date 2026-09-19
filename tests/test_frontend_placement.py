"""P1-TC-PLC-FE-01 — 建築分頁建造 must enter startPlacement (same as shop).

WEAK (A): string/source assert on index.html. Catalog allows this for
frontend-only placement. Stronger E2E: TC-FE-PLACE-SHOP-01 / TC-FE-PLACE-BUILD-01
in tests/test_frontend.py. (B) manual — walk 商店 and 建築 tab once — still
required on a real device. Grep/source alone is not full UX (A).
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.phase1]

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "index.html"


@pytest.mark.case_id("P1-TC-PLC-FE-01")
def test_buildings_tab_build_button_calls_start_placement():
    """P1-TC-PLC-FE-01 建築 tab 撳建造後進入同商店一樣嘅放置態。

    WEAK (A): the available-buildings card template must call startPlacement,
    not only showToast('點擊下方空地…'). Stronger (A): TC-FE-PLACE-BUILD-01.
    (B) manual still required.
    """
    html = INDEX.read_text(encoding="utf-8")
    start = html.find("availContainer.innerHTML")
    end = html.find("function renderInventory")
    assert start != -1 and end != -1 and end > start, "could not isolate 建築分頁 template"
    chunk = html[start:end]
    assert "startPlacement" in chunk, (
        "建築分頁 建造 must call startPlacement(defId) like shopBuild(); "
        "STATUS: weak source assert — (B) click both entry points manually."
    )
    assert "showToast('點擊下方空地" not in chunk and 'showToast("點擊下方空地' not in chunk, (
        "建築分頁 建造 must not only toast '點擊下方空地' without entering placement"
    )
