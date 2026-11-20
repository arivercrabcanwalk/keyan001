"""Tiny synthetic optimizer/probability tests, with no map or scientific input."""
import copy
import importlib
import itertools
import json
import math
from pathlib import Path
import sys
import time

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
learning = importlib.import_module("rlcore.joint_learning")


class TinyRoute:
    """Two targets, two slots, real explicit close actions, arbitrary toy costs."""

    opened_rows = []

    def __init__(self, row, scenario, cap):
        self.row, self.cap = row, cap
        self.remaining = {10, 11}
        self.open = [False, False]
        self.previous = [None, None]
        self.duty = [0.0, 0.0]
        self.cost = 10.0
        self.trace = []
        self.done = bool(row.get("blocked"))
        self.opened_rows.append(row["id"])

    def options(self):
        if self.done:
            return []
        options = []
        for slot in range(2):
            for target in sorted(self.remaining):
                features = [0.0] * learning.FEAT_DIM
                features[:8] = [float(slot), float(target == 11), 0.0,
                                len(self.remaining)/2, self.duty[slot]/30,
                                self.cost/100, float(self.previous[slot] == 11),
                                float(self.open[slot])]
                options.append(((0, slot, target), features))
            if self.open[slot]:
                features = [0.0] * learning.FEAT_DIM
                features[:8] = [float(slot), 0.0, 1.0, len(self.remaining)/2,
                                self.duty[slot]/30, self.cost/100, 0.0, 1.0]
                options.append(((0, slot, -1), features))
        return options

    def teacher_action(self, options=None):
        choices = self.options() if options is None else options
        # A deterministic cost-oriented source; no action outside caller mask.
        return min(choices, key=lambda item: (item[0][2] == -1,
                                              item[0][1], item[0][2]))[0]

    greedy_action = teacher_action

    def step(self, action):
        assert action in [candidate for candidate, _ in self.options()]
        _, slot, target = action
        if target == -1:
            self.open[slot] = False
            self.duty[slot] += 1
            self.cost += 1
        else:
            increment = (8 if target == 10 else 6) if slot == 0 else 2
            increment += 6 if self.previous[slot] == 11 and target == 10 else 0
            self.duty[slot] += increment
            self.cost += increment * (1 if slot == 0 else 4)
            self.remaining.remove(target)
            self.previous[slot] = target
            self.open[slot] = True
        self.trace.append(action)
        self.done = not self.remaining and not any(self.open)

    def result(self):
        returned = not any(self.open)
        strict = not self.remaining and returned and not self.row.get("blocked", False)
        cost = self.cost + self.row.get("val_extra_cost", 0)
        return dict(cost=cost, J=cost+1000*len(self.remaining), M_return=max(self.duty) if returned else None,
                    complete_strict=strict, all_returned=returned, physically_feasible=not bool(self.remaining) and returned,
                    eligible=strict and cost<=self.cap+1e-7, fallback=False,
                    solution={"actions":copy.deepcopy(self.trace)}, unserved=len(self.remaining),
                    failed=0, routine_total=2, termination_reason="complete" if strict else "blocked")


@pytest.fixture(autouse=True)
def single_thread():
    before = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(before)


@pytest.fixture
def tiny(monkeypatch):
    monkeypatch.setattr(learning, "JointRoute", TinyRoute)
    TinyRoute.opened_rows = []
    return [({"id":"train"}, "fixed", 100.0)], [
        ({"id":"validation"}, "fixed", 100.0),
        ({"id":"validation_failure", "blocked":True}, "fixed", 100.0)]


def invoke(out, train, val, **overrides):
    parameters = dict(out=out, seed=19, bc_epochs=1, pg_steps=2, rollouts=12,
                      lr=.003, device="cpu", deadline=time.monotonic()+60)
    parameters.update(overrides)
    return learning.run_round(train, val, **parameters)


def test_actor_padding_permutation_and_action_conditioning():
    torch.manual_seed(3)
    actor = learning.JointActor(hidden_dim=8)
    first = [[.01*(j+1) for j in range(learning.FEAT_DIM)],
             [.03*(j+1) for j in range(learning.FEAT_DIM)],
             [-.02*(j+1) for j in range(learning.FEAT_DIM)]]
    second = [[.02] * learning.FEAT_DIM]
    features, mask = learning.collate_options([first, second])
    logits = actor(features, mask)
    assert torch.isneginf(logits[1, 1:]).all()
    alone, alone_mask = learning.collate_options([second])
    assert torch.allclose(logits[1, :1], actor(alone, alone_mask)[0], atol=1e-7)
    permutation = [2, 0, 1]
    shuffled, shuffled_mask = learning.collate_options([[first[i] for i in permutation]])
    assert torch.allclose(actor(shuffled, shuffled_mask)[0], logits[0, permutation], atol=1e-7)
    loss = -logits[0].log_softmax(-1)[1]
    loss.backward()
    assert any(parameter.grad is not None and parameter.grad.abs().sum()>0 for parameter in actor.parameters())
    with pytest.raises(ValueError, match="at least one"):
        learning.collate_options([[]])


def test_exact_loo_variable_length_terminal_gradient():
    theta, step = -.3, 1e-6
    def law(value):
        p = 1/(1+math.exp(-value))
        return [(1-p, 8.0, -p), (p*(1-p), 3.0, 1-2*p), (p*p, 1.0, 2*(1-p))]
    gradient = 0.0
    for (p1, cost1, score1), (p2, cost2, score2) in itertools.product(law(theta), repeat=2):
        advantages = learning.loo_advantages([cost1, cost2])
        gradient += p1*p2*(advantages[0]*score1+advantages[1]*score2)/2
    objective = lambda value: -sum(probability*cost for probability,cost,_ in law(value))/1000
    assert gradient == pytest.approx((objective(theta+step)-objective(theta-step))/(2*step), rel=1e-8)


def test_frozen_L_tiers_and_fixed_wind_J_are_exact():
    good = dict(cost=30.0, J=30.0, M_return=42.0, complete_strict=True,
                all_returned=True, physically_feasible=True, eligible=True,
                fallback=False, unserved=0, failed=0, routine_total=4)
    over = {**good, "cost":32.0, "J":32.0, "eligible":False}
    missing = {**good, "complete_strict":False, "eligible":False, "unserved":1, "J":1030.0}
    assert learning.terminal_score(good,"j",30)==30
    assert learning.terminal_score(missing,"j",30)==1030
    assert learning.terminal_score(good,"m",30)==42
    violation = (32-30)/30
    assert learning.terminal_score(over,"m",30)==pytest.approx(601+600*violation/(1+violation))
    assert learning.terminal_score(missing,"m",30)==1352
    assert learning.terminal_score(good,"m",30) < learning.terminal_score(over,"m",30) < learning.terminal_score(missing,"m",30)
    assert not learning.result_eligible({**good,"cost":30.1},30)
    with pytest.raises(ValueError,match="legacy formula"):
        learning.terminal_score({**good,"J":42},"j",30)
    with pytest.raises(ValueError,match="outside frozen"):
        learning.terminal_score({**good,"M_return":601},"m",30)
    assert learning.json_safe({"x":math.inf,"y":math.nan})=={"x":None,"y":None}


def test_full_pair_clones_BC_retains_failure_and_never_trains_on_validation(tiny,tmp_path):
    train,val = tiny
    before = copy.deepcopy([train,val])
    summary = invoke(tmp_path/"round",train,val)
    assert summary["status"]=="completed_fixed_endpoints"
    assert summary["counts"]==dict(bc_updates=1,pg_j_updates=2,pg_m_updates=2,
                                   teacher_episodes=1,pg_episodes=48,validation_episodes=8)
    checkpoints = summary["checkpoints"]
    bc_hash = checkpoints["bc"]["weight_sha256"]
    assert checkpoints["frozen_bc"]["weight_sha256"]==bc_hash
    assert checkpoints["pg_j"]["source_weight_sha256"]==bc_hash
    assert checkpoints["pg_m"]["source_weight_sha256"]==bc_hash
    assert checkpoints["initial"]["weight_sha256"]!=bc_hash
    assert any(checkpoints[arm]["weight_sha256"]!=bc_hash for arm in ("pg_j","pg_m"))
    assert all(arm["cases"]==2 and arm["failure_count"]==1 for arm in summary["arms"].values())
    # The failed validation row remains in both all-case objectives.
    assert all(arm["mean_L_all"]>=901 for arm in summary["arms"].values())
    assert all(row["result"]["solution"] is not None for row in summary["validation"])
    assert [train,val]==before
    first_val = next(i for i,value in enumerate(TinyRoute.opened_rows) if value.startswith("validation"))
    assert all(value=="train" for value in TinyRoute.opened_rows[:first_val])
    assert first_val==49
    receipts = [json.loads(line) for line in (tmp_path/"round"/"receipts.jsonl").read_text().splitlines()]
    starts = [row for row in receipts if row["tag"]=="pg_start"]
    assert len(starts)==2 and all(row["source_weight_sha256"]==bc_hash for row in starts)
    j_seeds = [row["seed"] for row in receipts if row["tag"]=="episode_started" and row["stage"]=="pg_j"]
    m_seeds = [row["seed"] for row in receipts if row["tag"]=="episode_started" and row["stage"]=="pg_m"]
    assert j_seeds==m_seeds
    assert summary["frozen_bc_unchanged"] and summary["legacy_unchanged"] and summary["input_unchanged"]
    for arm in ("pg_j", "pg_m"):
        evidence = summary["learning_evidence"][arm]
        assert evidence["optimizer_steps"]==2
        assert evidence["changed_updates"]+evidence["zero_parameter_change_updates"]==2
        assert evidence["parameter_changed_from_source"] == (checkpoints[arm]["weight_sha256"]!=bc_hash)
    json.dumps(summary, allow_nan=False)


def test_validation_content_cannot_change_training_and_runs_reproduce(tiny,tmp_path):
    train,val = tiny
    first = invoke(tmp_path/"a",train,val)
    other_val = [({"id":"different_validation", "val_extra_cost":5},"fixed",100.0)]
    second = invoke(tmp_path/"b",train,other_val)
    assert first["deterministic_weight_hashes"]==second["deterministic_weight_hashes"]
    assert first["counts"]["pg_episodes"]==second["counts"]["pg_episodes"]


def test_serial_is_explicit_fixed_slot_representation(tiny,tmp_path):
    train,val = tiny
    summary = invoke(tmp_path/"serial",train,val,mode="serial",pg_steps=1,rollouts=4)
    assert summary["status"]=="completed_fixed_endpoints"
    contract = json.loads((tmp_path/"serial"/"contract.json").read_text())
    assert "fixed cyclic" in contract["representation"]
    for row in summary["validation"]:
        current = None
        returned = True
        for action in row["actions"]:
            if not returned:
                assert tuple(action[:2])==current
            current,returned = tuple(action[:2]), action[2]==-1
    assert contract["legacy_reference"]["status"]=="read_only_unexecuted_not_matched_comparison"


def test_deadline_retains_all_validation_rows_and_no_updates(tiny,tmp_path):
    train,val = tiny
    summary = invoke(tmp_path/"late",train,val,deadline=time.monotonic()-1)
    assert summary["status"]=="deadline_interrupted"
    assert summary["counts"]["bc_updates"]==summary["counts"]["pg_j_updates"]==summary["counts"]["pg_m_updates"]==0
    assert len(summary["validation"])==4*len(val)
    assert all(not row["result"]["eligible"] for row in summary["validation"])
    assert all(arm["mean_L_all"] is None for arm in summary["arms"].values())
    assert not summary["fixed_endpoints_complete"]


def test_late_optimizer_update_restores_weights_and_adam(monkeypatch):
    model = learning.JointActor(hidden_dim=8)
    optimizer = torch.optim.Adam(model.parameters(),lr=.01)
    for parameter in model.parameters():
        parameter.grad = torch.ones_like(parameter)
    before = learning.weight_hash(model)
    original = optimizer.step
    def late_step():
        original()
        raise learning.DeadlineReached("synthetic post-mutation deadline")
    monkeypatch.setattr(optimizer,"step",late_step)
    with pytest.raises(learning.DeadlineReached):
        learning._commit_step(model,optimizer,torch.device("cpu"),time.monotonic()+10)
    assert learning.weight_hash(model)==before
    assert optimizer.state_dict()["state"]=={}
    assert all(parameter.grad is None for parameter in model.parameters())


def test_zero_score_updates_report_no_parameter_change(tiny,tmp_path,monkeypatch):
    train,val = tiny
    class SingleOptionRoute(TinyRoute):
        def options(self):
            return super().options()[:1]
    monkeypatch.setattr(learning,"JointRoute",SingleOptionRoute)
    summary = invoke(tmp_path/"singleton",train,val,pg_steps=1,rollouts=2)
    assert summary["status"]=="completed_fixed_endpoints"
    for arm in ("pg_j","pg_m"):
        evidence = summary["learning_evidence"][arm]
        assert evidence["optimizer_steps"]==1
        assert evidence["changed_updates"]==0
        assert evidence["zero_parameter_change_updates"]==1
        assert not evidence["parameter_changed_from_source"]


def test_split_overlap_and_artifact_overwrite_are_explicit(tiny,tmp_path):
    train,val = tiny
    with pytest.raises(ValueError,match="overlap"):
        invoke(tmp_path/"bad",train,train)
    invoke(tmp_path/"one",train,val,bc_epochs=0,pg_steps=0)
    with pytest.raises(FileExistsError,match="already exist"):
        invoke(tmp_path/"one",train,val)
