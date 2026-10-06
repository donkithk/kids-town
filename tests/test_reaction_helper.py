"""Reader self-check for tap reactions. No browser and no product database.

``_map_reaction`` stores the selected cell under ``acted``. ``_reaction_blame``
used to read only ``chosen`` and ``preview``, so a real selection was reported
as None and a reverse probe failed. These cases lock the shared reader.
"""
from __future__ import annotations

from tests.test_warehouse_e2e import (
    _reaction_blame,
    reaction_happened,
    selection_of,
)


def test_acted_selection_is_that_cell_not_none():
    reaction = {
        "acted": (0, 6),
        "toast": "",
        "sheet": False,
        "scene": "場景 2 · 選擇建築",
        "ready": "",
    }
    assert selection_of(reaction) == (0, 6)
    assert reaction_happened(reaction)
    bucket, detail = _reaction_blame((0, 6), "select", reaction, False)
    assert bucket is None, detail
    assert detail == ""


def test_acted_mismatch_names_the_cell():
    reaction = {"acted": (0, 6), "toast": "", "scene": "場景 2 · 選擇建築"}
    bucket, detail = _reaction_blame((1, 1), "select", reaction, False)
    assert bucket == "neighbor"
    assert "(0, 6)" in detail
    assert "None" not in detail


def test_chosen_and_preview_still_count_without_acted():
    chosen = {"chosen": [[3, 3]], "preview": [], "toast": "", "scene": "場景 2"}
    assert selection_of(chosen) == (3, 3)
    assert reaction_happened(chosen)
    bucket, detail = _reaction_blame((3, 3), "select", chosen, False)
    assert bucket is None, detail

    preview = {"preview": [[2, 4]], "chosen": [], "toast": "", "scene": "場景 3 · 放置"}
    assert selection_of(preview) == (2, 4)
    assert reaction_happened(preview)


def test_toast_and_sheet_count_as_reactions_without_a_cell():
    assert selection_of({"toast": "這個位置放不下這座建築物。"}) is None
    assert reaction_happened({"toast": "這個位置放不下這座建築物。"})
    assert reaction_happened({"sheet": True, "toast": ""})
    assert reaction_happened({"scene": "場景 3 · 放置", "toast": ""})
    assert reaction_happened({"ready": "已選擇空地。", "toast": ""})
    assert not reaction_happened({"toast": "", "sheet": False, "scene": "場景 2", "ready": ""})
    assert not reaction_happened({"toast": "探針", "scene": "場景 2"}, ignore_toast="探針")


def test_already_open_sheet_is_not_a_new_reaction():
    from tests.test_warehouse_e2e import _sheet_opened_by_tap

    assert _sheet_opened_by_tap(True, True) is False
    assert _sheet_opened_by_tap(False, True) is True
    assert not reaction_happened({
        "toast": "",
        "sheet": False,
        "scene": "場景 2 · 選擇建築",
        "ready": "請點選金色空地，或打開清單選擇要興建的建築物。",
    })


def test_empty_chosen_does_not_hide_acted():
    reaction = {"acted": (0, 6), "chosen": [], "preview": [], "toast": "", "scene": "場景 2"}
    assert selection_of(reaction) == (0, 6)
    assert reaction_happened(reaction)
