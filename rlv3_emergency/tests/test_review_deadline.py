"""Handwritten control-flow fixtures only: no scientific map/solve/training."""
import importlib
import json
from pathlib import Path
import random
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def train(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("RLV3_ROOT", str(root))
    monkeypatch.syspath_prepend(str(root))
    return importlib.import_module("rlcore.train")


class Clock:
    now = 0.0
    def __call__(self):
        return self.now


class Handle:
    def __init__(self, value=None, error=None, ready=True, wait=None):
        self.value, self.error, self.is_ready, self.on_wait = value, error, ready, wait
    def ready(self):
        return self.is_ready
    def get(self):
        if self.error:
            raise self.error
        return self.value
    def wait(self, timeout):
        if self.on_wait:
            self.on_wait(timeout)


class Pool:
    def __init__(self, handles=()):
        self.handles, self.calls = list(handles), []
        self.closed = self.terminated = self.joined = False
    def apply_async(self, fun, args):
        self.calls.append((fun, args))
        return self.handles.pop(0)
    def close(self):
        self.closed = True
    def terminate(self):
        self.terminated = True
    def join(self):
        self.joined = True


def test_total_deadline_has_priority_and_dev_uses_same_clock(train):
    assert train.remaining_budget(20., 10., now=9.) == 1.
    with pytest.raises(train.PGDeadlineReached):
        train.remaining_budget(20., 10., now=10.)
    with pytest.raises(train.TotalBudgetExceeded):
        train.remaining_budget(10., 10., now=10.)
    # Development may finish under total, but never shifts the PG deadline.
    assert train.remaining_budget(20., None, now=12.) == 8.
    with pytest.raises(train.PGDeadlineReached):
        train.remaining_budget(20., 10., now=12.)


def test_partial_completed_jobs_are_retained_on_deadline(train):
    clock, retained, events = Clock(), [], []
    pending = Handle(ready=False, wait=lambda _: setattr(clock, "now", 2.))
    pool = Pool([Handle("finished"), pending])
    with pytest.raises(train.PGDeadlineReached):
        train.dispatch_jobs(pool, str, ["a", "b"],
                            lambda: train.remaining_budget(5., 1., now=clock()),
                            lambda i, x: retained.append((i, x)), events.append)
    assert retained == [(0, "finished")]
    assert events[-1] == dict(status="deadline", budget="pg", completed=1, issued=2, pending=[1])


def test_dispatch_expiration_stops_new_submissions(train):
    calls, events = 0, []
    def check():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise train.PGDeadlineReached()
        return 1.
    pool = Pool([Handle("retained")])
    with pytest.raises(train.PGDeadlineReached):
        train.dispatch_jobs(pool, str, ["a", "b"], check, on_event=events.append)
    assert len(pool.calls) == 1 and events[-1]["completed"] == 1


@pytest.mark.parametrize("error", [TimeoutError("worker-own-error"), RuntimeError("broken worker")])
def test_worker_exception_is_never_a_normal_pg_deadline(train, error):
    events = []
    with pytest.raises(type(error), match=str(error)):
        train.dispatch_jobs(Pool([Handle(error=error)]), str, ["a"], lambda: 1., on_event=events.append)
    assert events == [dict(status="worker_error", job=0, error_type=type(error).__name__, error=str(error))]


def test_worker_failure_ready_at_deadline_keeps_failure_identity(train):
    calls = 0
    def check():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise train.PGDeadlineReached()
        return 1.
    with pytest.raises(ValueError, match="bad result"):
        train.dispatch_jobs(Pool([Handle(error=ValueError("bad result"))]), str, ["a", "b"], check)


def test_successes_ready_after_another_worker_error_are_still_retained(train):
    completed = []
    with pytest.raises(ValueError, match="first job"):
        train.dispatch_jobs(Pool([Handle(error=ValueError("first job")), Handle("done")]),
                            str, ["a", "b"], lambda: 1.,
                            lambda i, value: completed.append((i, value)))
    assert completed == [(1, "done")]


def test_abrupt_worker_exit_is_not_pg_completion(train):
    pool = Pool([Handle(ready=False)])
    pool._pool = [SimpleNamespace(exitcode=1)]
    with pytest.raises(RuntimeError, match="worker process exited"):
        train.dispatch_jobs(pool, str, ["a"], lambda: 1.)


@pytest.mark.parametrize("budget_error", ["PGDeadlineReached", "TotalBudgetExceeded"])
def test_late_optimizer_transaction_restores_last_complete_state(train, budget_error):
    state = dict(parameter=5, moment=3, updates=7)
    saved = dict(state)
    count = 0
    def check():
        nonlocal count
        count += 1
        if count == 2:
            raise getattr(train, budget_error)()
    def step():
        state.update(parameter=99, moment=98)
    def rollback():
        state.clear(); state.update(saved)
    with pytest.raises(getattr(train, budget_error)):
        train.commit_pg_update(check, step, rollback)
    assert state == saved


def test_pre_step_expiration_never_calls_optimizer(train):
    calls = []
    def check():
        raise train.PGDeadlineReached()
    with pytest.raises(train.PGDeadlineReached):
        train.commit_pg_update(check, lambda: calls.append("step"), lambda: calls.append("rollback"))
    assert calls == []


def test_pool_is_terminated_joined_and_global_released(train, monkeypatch):
    pool = Pool()
    monkeypatch.setattr(train, "_POOL", pool)
    train._shutdown_pool()
    train._shutdown_pool()
    assert pool.terminated and pool.joined and train._POOL is None


def test_fixed_day_dedup_and_checkpoint_provenance(train):
    assert train.development_days("fixed_e4", [1, 2, 3]) == [1]
    assert train.development_days("nowind", [1, 2, 3]) == [1]
    assert train.development_days("emerg_low", [1, 2, 3]) == [1, 2, 3]
    assert [train.checkpoint_source(t) for t in ["bc", "init", "ri2", "it2"]] == ["bc", "initialization", "ri", "pg"]


def test_weather_author_cap_and_primary_selector(train):
    result = dict(J=1., cost=9., author_cost_cap=10., M_return=100., complete_strict=1,
                  physically_feasible=1, all_returned=1, timeout=0, failed=0)
    assert train.eligible_result(result, "fixed_e4")
    assert not train.eligible_result(dict(result, cost=10.000001), "fixed_e4")
    assert not train.eligible_result(dict(result, author_cost_cap=None), "fixed_e4")
    # Smaller J must not defeat the physical final-return endpoint.
    assert train.development_score([result, dict(result, J=1000., M_return=2.)], "fixed_e4") == 51.


def test_emergency_pools_every_release(train):
    rows = [dict(high_total=3, high_on_time=0), dict(high_total=2, high_on_time=2)]
    assert train.development_score(rows, "emerg_low") == -.4


def test_weather_jobs_attach_environment_cap_not_method_cost(train, monkeypatch):
    monkeypatch.setattr(train, "make_env", lambda *a: SimpleNamespace(L=dict(author_cost=31.)))
    monkeypatch.setattr(train.PO, "run_episode", lambda *a: dict(cost=1., author_cost_cap=-5.))
    monkeypatch.setattr(train.PO, "make", lambda *a: SimpleNamespace(name="hand"))
    monkeypatch.setattr(train, "_model_from", lambda *a: (None, "none", "none"))
    monkeypatch.setattr(train, "RLPolicy", lambda *a, **k: None)
    assert train.job_eval(({}, 1, "fixed_e4", "x", 1))["author_cost_cap"] == 31.
    assert train.job_eval(({}, 1, "nowind", "x", 1))["author_cost"] == 31.
    assert train.job_teacher(({}, 1, "fixed_e4", "hand", "none", False))[1]["author_cost_cap"] == 31.


def test_each_finished_rollout_is_journaled_before_next_failure(train, monkeypatch, tmp_path):
    monkeypatch.setattr(train, "_model_from", lambda *a: (None, "none", "none"))
    monkeypatch.setattr(train, "make_env", lambda *a: None)
    monkeypatch.setattr(train, "RLPolicy", lambda *a, **k: SimpleNamespace(buf=[]))
    calls = 0
    def episode(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("second hand-written episode failed")
        return dict(J=7., per_st_J={}, complete_strict=0, fallback=0, failed=1)
    monkeypatch.setattr(train.PO, "run_episode", episode)
    log = tmp_path / "attempts.jsonl"
    args = (dict(path="HAND_ONLY"), 1, "fixed_e4", "unused", 0, 2, 1., 0, "none", 0.,
            str(log), 4, 3)
    with pytest.raises(ValueError, match="second hand-written"):
        train.job_rollouts(args)
    row, = [json.loads(line) for line in log.read_text().splitlines()]
    assert row["rollout"] == 0 and row["failed"] == 1 and row["iteration"] == 4


@pytest.fixture
def hand_main(train, monkeypatch, tmp_path):
    """Run the real orchestration with hand-built plans and inert model/Adam."""
    import multiprocessing
    import torch
    model_module = importlib.import_module("rlcore.model")
    clock, pools, control = Clock(), [], dict(mode="rollout_deadline", backprops=0, steps=0)
    class Model:
        def __init__(self, **kwargs): self.marker = torch.tensor(5.)
        def to(self, dev): return self
        def parameters(self): return []
        def state_dict(self): return dict(marker=self.marker)
        def load_state_dict(self, saved): self.marker = saved.get("marker", self.marker).clone()
        def train(self): pass
        def eval(self): pass
        def __call__(self, tokens, context, mask):
            return torch.zeros((len(tokens), 2))
    class Adam:
        def __init__(self, *a, **k): self.moment = 3
        def state_dict(self): return dict(moment=self.moment)
        def load_state_dict(self, saved): self.moment = saved.get("moment", self.moment)
        def zero_grad(self, **kwargs): pass
        def step(self):
            self.moment = 99
            control["steps"] += 1
            if control["mode"] == "late_step":
                clock.now = 2.
    def backward(tensor, *args, **kwargs):
        # No autograd or model parameter update in orchestration fixtures.
        control["backprops"] += 1
        if control["mode"] == "gradient_deadline":
            clock.now = 2.
    class WorkPool(Pool):
        def apply_async(self, fun, args):
            self.calls.append((fun, args))
            if fun.__name__ == "job_rollouts":
                if control["mode"] in ("gradient_deadline", "late_step", "full_then_deadline"):
                    if control["mode"] != "full_then_deadline" or control["steps"] == 0:
                        import numpy as np
                        dec = (np.zeros((2, 34), np.float32), np.zeros(24, np.float32),
                               np.ones(2, bool), 0, 0)
                        n = 1025 if control["mode"] == "gradient_deadline" else 1
                        return Handle([dict(dec=[dec] * n, J=1., Jsh=1., ok=1),
                                       dict(dec=[dec], J=2., Jsh=2., ok=1)])
                return Handle(ready=False, wait=lambda _: setattr(clock, "now", 2.))
            return Handle(dict(J=10., M_return=10., cost=1., author_cost_cap=2., complete_strict=1,
                               physically_feasible=1, all_returned=1, timeout=0, failed=0,
                               fallback=0, inc_cell=0, inc_land=0, high_total=1, high_on_time=1,
                               routine_total=1, routine_done=1))
    def pool_factory(*args, **kwargs):
        pool = WorkPool(); pools.append(pool); return pool
    monkeypatch.setattr(multiprocessing, "get_context", lambda *a: SimpleNamespace(Pool=pool_factory))
    monkeypatch.setattr(model_module, "Policy", Model)
    monkeypatch.setattr(torch.optim, "Adam", Adam)
    monkeypatch.setattr(torch.Tensor, "backward", backward)
    monkeypatch.setattr(model_module, "collate", lambda rows, dev=None:
                        (torch.zeros((len(rows), 2, 34)), torch.zeros((len(rows), 24)),
                         torch.ones((len(rows), 2), dtype=torch.bool)))
    monkeypatch.setattr(train, "action_log_probs", lambda logits, mask, temp: torch.log_softmax(logits, -1))
    monkeypatch.setattr(train.time, "monotonic", clock)
    monkeypatch.setattr(train, "device", lambda *a: torch.device("cpu"))
    monkeypatch.setattr(train, "seed_all", lambda *a: None)
    monkeypatch.setattr(train, "load_plans", lambda p: [dict(path="HAND_TRAIN" if p == "t" else "HAND_DEV")])
    monkeypatch.setattr(train, "training_contract", lambda a: {"fixture": "inert"})
    args = ["hand", "--scen", "fixed_e4" if "rlv3_weather" in train.HERE else "emerg_low",
            "--plans", "t", "--dev_plans", "d", "--out", str(tmp_path), "--no_bc", "--no_base",
            "--no_ri", "--rl_iters", "2", "--rl_hours", str(1./3600),
            "--total_hours", str(10./3600), "--workers", "1", "--dev_days", "3"]
    def run(total_expiration=False, source="initialization", mode="rollout_deadline"):
        control["mode"] = mode
        if mode == "manifest_total_deadline":
            original_dump = json.dump
            def late_dump(*args, **kwargs):
                result = original_dump(*args, **kwargs)
                clock.now = 20.
                return result
            monkeypatch.setattr(train.json, "dump", late_dump)
        if source == "bc":
            best_score = 10. if "rlv3_weather" in train.HERE else -1.
            state = dict(stage="rl", it=0, best=dict(devJ=10., score=best_score, tag="bc", it=0,
                         source="bc", pg_optimizer_steps=0), ver=0, t_rl=0., t_ri=0., ri_it=0,
                         elapsed_wall=0., optimizer_steps=8, pg_optimizer_steps=0, model_source="bc",
                         pg_stop_reason=None, base="none", teacher="HAND_TEACHER")
            torch.save(dict(model={}, opt={}, state=state, contract={"fixture": "inert"},
                            rng=train.capture_rng(random.Random(0))), tmp_path / "state.pt")
        if total_expiration:
            args[args.index("--total_hours") + 1] = str(1./3600)
        monkeypatch.setattr(sys, "argv", args)
        return train.main()
    return SimpleNamespace(run=run, path=tmp_path, pools=pools, torch=torch, control=control)


def test_pg_dispatch_deadline_finishes_with_zero_pg_marked_explicitly(hand_main):
    hand_main.run()
    done = json.loads((hand_main.path / "done.json").read_text())
    assert done["status"] == "completed_without_pg_update" and done["pg_optimizer_steps"] == 0
    assert done["best_source"] == "initialization" and done["pg_stop_reason"] == "rl_hours_exhausted"
    assert hand_main.pools[0].terminated and hand_main.pools[0].joined
    assert hand_main.pools[1].closed and hand_main.pools[1].joined
    assert all(fun.__name__ != "job_rollouts" for fun, _ in hand_main.pools[1].calls)
    assert "continuous_phase_wall" in done["pg_clock"]


def test_bc_optimizer_steps_do_not_become_pg_evidence(hand_main):
    hand_main.run(source="bc")
    done = json.loads((hand_main.path / "done.json").read_text())
    assert done["optimizer_steps"] == 8 and done["pg_optimizer_steps"] == 0
    assert done["best_source"] == "bc" and done["status"] == "completed_without_pg_update"


def test_mid_microbatch_deadline_discards_gradient_and_never_steps(hand_main):
    hand_main.run(mode="gradient_deadline")
    done = json.loads((hand_main.path / "done.json").read_text())
    assert hand_main.control["backprops"] == 1 and hand_main.control["steps"] == 0
    assert done["pg_optimizer_steps"] == 0 and done["iters"] == 0
    interrupted = [json.loads(line) for line in (hand_main.path / "curve.jsonl").read_text().splitlines()
                   if json.loads(line).get("tag") == "pg_interrupted"]
    assert interrupted[-1]["phase"] == "gradient"


def test_late_step_rolls_back_adam_without_counting_pg(hand_main):
    hand_main.run(mode="late_step")
    saved = hand_main.torch.load(hand_main.path / "state.pt", weights_only=False)
    assert hand_main.control["steps"] == 1 and saved["opt"]["moment"] == 3
    assert saved["state"]["pg_optimizer_steps"] == 0 and saved["state"]["it"] == 0


def test_complete_update_survives_next_rollout_cutoff_and_bc_stays_best(hand_main):
    hand_main.run(source="bc", mode="full_then_deadline")
    done = json.loads((hand_main.path / "done.json").read_text())
    assert done["pg_optimizer_steps"] == 1 and done["iters"] == 1
    assert done["status"] == "completed_pg_updates" and done["best_source"] == "bc"
    assert all(fun.__name__ != "job_rollouts" for fun, _ in hand_main.pools[1].calls)
    saved = hand_main.torch.load(hand_main.path / "state.pt", weights_only=False)
    assert saved["opt"]["moment"] == 99 and saved["state"]["pg_optimizer_steps"] == 1


def test_total_expiration_fails_without_done_and_saves_failure(hand_main, train):
    with pytest.raises(train.TotalBudgetExceeded):
        hand_main.run(total_expiration=True)
    assert not (hand_main.path / "done.json").exists()
    saved = hand_main.torch.load(hand_main.path / "state.pt", weights_only=False)
    assert saved["state"]["failure"]["error_type"] == "TotalBudgetExceeded"
    assert hand_main.pools[0].terminated and hand_main.pools[0].joined


def test_total_deadline_during_final_manifest_cannot_publish_success(hand_main, train):
    with pytest.raises(train.TotalBudgetExceeded):
        hand_main.run(mode="manifest_total_deadline")
    assert not (hand_main.path / "done.json").exists()
    saved = hand_main.torch.load(hand_main.path / "state.pt", weights_only=False)
    assert saved["state"]["failure"]["error_type"] == "TotalBudgetExceeded"
