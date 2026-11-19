"""Paired exclusion intervention, using only hand-written engineering fixtures."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rlcore import paired_weather as paired, scen


def test_paired_engineering_counterfactual_changes_only_cell_rule_interface():
    receipt = paired.engineering_check()
    assert receipt["status"] == "PASS" and receipt["engineering_only"]
    assert receipt["identical_truth_queries"] == 24
    assert receipt["identical_forecast_queries"] == 22
    assert receipt["cell_outflow_retained_in_both"]
    assert receipt["cells_collision"] and not receipt["clear_collision"]
    assert not receipt["clear_cell_metadata_exposed"]


def test_clear_has_no_forwarded_hidden_geometry_and_is_pickle_safe():
    import pickle
    clear, cells = paired.make_paired_weather(75, (0, 1000, 0, 1000))
    rebuilt = pickle.loads(pickle.dumps(clear, protocol=4))
    assert rebuilt.pair_world_sha256 == cells.pair_world_sha256
    assert rebuilt.truth_wind(100, 200, 121) == cells.truth_wind(100, 200, 121)
    assert clear.ncell == 0 and clear.nowcast(120) == []
    for name in ("c_a", "c_b", "c_ang", "c_cx", "c_cy", "cells_meta", "_cell_list", "storm"):
        assert not hasattr(clear, name)
    with pytest.raises(ValueError, match="horizon"):
        clear.nowcast(901)


def test_scenario_registry_uses_same_world_and_different_interventions(monkeypatch):
    # No stored map or author plan is read: this is a one-station empty layout.
    layout = dict(stations=[dict(k=0, si=0, x=0.0, y=0.0, kind=1, R=4000.0, drones=[0])],
        drones=[dict(i=0, st=0, di=1, cap=.81, limit=480.0, trips=[])],
        assign={}, targets={}, fixed=27.8, n_open=1, n_dabs=0, types=[1])
    from types import SimpleNamespace
    monkeypatch.setattr(scen, "load_ins", lambda path: SimpleNamespace(sha256="1"*64))
    monkeypatch.setattr(scen, "plan_layout", lambda ins, solution: copy.deepcopy(layout))
    monkeypatch.setattr(scen, "bbox", lambda ins: (0, 1000, 0, 1000))
    row = dict(path="manual-pair-fixture.txt", solution={})
    clear = scen.make_env(row, 77, "weather_paired_clear")
    cells = scen.make_env(row, 77, "weather_paired_cells")
    assert clear.wx.pair_world_sha256 == cells.wx.pair_world_sha256
    assert clear.wx.truth_wind(100, 200, 120) == cells.wx.truth_wind(100, 200, 120)
    assert clear.wx.forecast_wind(120, 180) == cells.wx.forecast_wind(120, 180)
    assert clear.use_cells is False
    assert cells.use_cells == bool(cells.wx.ncell)
    assert clear.scenario_input_hash != cells.scenario_input_hash
    assert scen.SCENARIOS["weather_paired_clear"]["engineering_only"]
    assert scen.SCENARIOS["weather_paired_cells"]["engineering_only"]
