import json
import os
from pathlib import Path

import pytest
from rlcore.joint_driver import consume, paired_rows, read_limit


def test_consumed_ticket_cannot_restart_across_outputs(tmp_path):
    lease = consume(tmp_path / "host-ledger", "test/one", {"output": "A"})
    with pytest.raises(FileExistsError):
        consume(tmp_path / "host-ledger", "test/one", {"output": "B"})
    assert lease.parent == tmp_path / "host-ledger" and json.loads(lease.read_text()) == {"output":"A"}


def row(eligible, m, arm="pg_m"):
    return dict(arm=arm,case_id="map-wind",result=dict(eligible=eligible,cost=10,M_return=m))


def test_paired_table_never_treats_partial_or_overspent_as_faster():
    inputs = {k:{"validation":[r]} for k,r in
              (("joint",row(False,1)),("serial",row(True,10)))}
    assert paired_rows(inputs)[0]["joint_minus_serial_min"] is None
    inputs["joint"]["validation"]=[row(True,7)]
    assert paired_rows(inputs)[0]["joint_minus_serial_min"] == -3
    inputs["serial"]["validation"] = []
    with pytest.raises(ValueError): paired_rows(inputs)


def test_duplicate_endpoint_rejected():
    a = row(True,1)
    with pytest.raises(ValueError): paired_rows({"joint":{"validation":[a,a]},"serial":{"validation":[a]}})


@pytest.mark.parametrize("value", [True, 0, -1, "1"])
def test_invalid_outer_limit(tmp_path,value):
    f=tmp_path/"ticket.json"
    f.write_text(json.dumps({"joint_training":{"config":{"wall_seconds":value},"valid_until":"2090-03-03T14:00:00Z"}}))
    with pytest.raises(ValueError):read_limit(f)
