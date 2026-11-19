"""Mutation check: a test that cannot fail proves nothing.

Each mutant deliberately breaks one property and we record which acceptance
test catches it.  A mutant that no test catches means that test is vacuous.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import platform
import sys
import time

from env import causal_engine, forecast_book, latent_phase
from env.causal_engine import CausalEngine
from env.core import ReleasedTarget as latent_phase_released
from env.forecast_book import ForecastBook
from tests import run_all


def _rerun(name, model):
    rec = run_all.TESTS[name](None, model)
    return rec["status"]


def mutant_leak(out, model):
    """Engine consults a private truth handle -> T2 must fail."""
    orig = CausalEngine.run_with_frozen_mu

    def leaky(self, mu, **kw):
        truth = getattr(self, "truth_handle", None)
        if truth is not None:
            # leak: jitter the decision by a truth-dependent amount
            self._leak = truth.seed
            self.frontier_id += 0 if truth.seed % 2 == 0 else 0
        return orig(self, mu, **kw)

    CausalEngine.run_with_frozen_mu = leaky
    # make the leak observable: advance an extra frontier when truth seed is odd
    def leaky2(self, mu, **kw):
        truth = getattr(self, "truth_handle", None)
        if truth is not None and truth.seed % 2 == 1:
            self.frontier_id += 1
        return orig(self, mu, **kw)
    CausalEngine.run_with_frozen_mu = leaky2
    try:
        return _rerun("T2", model)
    finally:
        CausalEngine.run_with_frozen_mu = orig


def mutant_return_keeps_energy(out, model):
    """RETURN no longer resets the trip battery -> T6-A1 must fail."""
    orig = CausalEngine.apply_physical

    def bad(self, key, action):
        before = self.slots[key].trip_energy
        orig(self, key, action)
        if action[0] == "RETURN":
            self.slots[key].trip_energy = before
    CausalEngine.apply_physical = bad
    try:
        return _rerun("T6", model)
    finally:
        CausalEngine.apply_physical = orig


def mutant_forecast_ignores_time(out, model):
    """visible() returns the newest version regardless of publication time."""
    orig = ForecastBook.visible

    def bad(self, t):
        return self._published[-1] if self._published else None
    ForecastBook.visible = bad
    try:
        return _rerun("T5", model)
    finally:
        ForecastBook.visible = orig


def mutant_unique_phase(out, model):
    """Sampler returns a point phase -> T3-A2 must fail."""
    orig = latent_phase.FrozenParticleModel._one

    def bad(self, static, prefix, rng, idx):
        p = orig(self, static, prefix, rng, idx)
        fixed = tuple(latent_phase.SlotPhase(ph.station, ph.slot, ph.target, 1.0)
                      for ph in p.hidden_phases)
        return latent_phase.Particle(
            particle_id=p.particle_id, seed=p.seed,
            hidden_past_wind=p.hidden_past_wind, hidden_phases=fixed,
            future=p.future, weight=p.weight)
    latent_phase.FrozenParticleModel._one = bad
    try:
        return _rerun("T3", model)
    finally:
        latent_phase.FrozenParticleModel._one = orig


def mutant_reveal_unreleased(out, model):
    """Publish unreleased background requests -> T8-A1 must fail."""
    orig = CausalEngine._released

    def bad(self):
        got = orig(self)
        have = {r.target for r in got}
        for tid in self.static.target_ids:
            if tid not in have:
                got.append(latent_phase_released(tid, "UNRELEASED"))
        return got
    CausalEngine._released = bad
    try:
        return _rerun("T8", model)
    finally:
        CausalEngine._released = orig


def mutant_ignore_nfz(out, model):
    """Drop the no-fly geometry -> T8-A3/A5 must fail."""
    orig_init = CausalEngine.__init__

    def bad(self, *a, **kw):
        orig_init(self, *a, **kw)
        self.nfz = ()
    CausalEngine.__init__ = bad
    try:
        return _rerun("T8", model)
    finally:
        CausalEngine.__init__ = orig_init


def mutant_alarm_early(out, model):
    """Publish an alarm before its time -> T9-A1 must fail."""
    orig = CausalEngine._reveal_alarms

    def bad(self):
        for t_at, tid in self.particle.future.faults:
            if tid not in self.alarm_seen:
                self.alarm_seen.add(tid)
                self.alarm_open.add(tid)
        return []
    CausalEngine._reveal_alarms = bad
    try:
        return _rerun("T9", model)
    finally:
        CausalEngine._reveal_alarms = orig


def mutant_ignore_alarm(out, model):
    """Drop the alarm law -> T9-A2 must fail."""
    orig = CausalEngine._reveal_alarms

    def bad(self):
        return []
    CausalEngine._reveal_alarms = bad
    try:
        return _rerun("T9", model)
    finally:
        CausalEngine._reveal_alarms = orig


MUTANTS = [
    ("alarm_revealed_before_its_time", "T9", mutant_alarm_early),
    ("alarm_law_ignored", "T9", mutant_ignore_alarm),
    ("reveal_unreleased_requests", "T8", mutant_reveal_unreleased),
    ("ignore_nfz_geometry", "T8", mutant_ignore_nfz),

    ("leak_truth_handle", "T2", mutant_leak),
    ("return_keeps_trip_energy", "T6", mutant_return_keeps_energy),
    ("forecast_ignores_publication_time", "T5", mutant_forecast_ignores_time),
    ("sampler_returns_point_phase", "T3", mutant_unique_phase),
]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="receipts")
    args = ap.parse_args(argv)
    model = latent_phase.FrozenParticleModel(latent_phase.FrozenModelParams())
    rows = []
    for name, target, fn in MUTANTS:
        status = fn(args.out, model)
        rows.append({"mutant": name, "expected_failing_test": target,
                     "observed_status": status,
                     "caught": status == "FAIL" or status == "ERROR"})
        print(f"{name:36s} -> {target} {status:6s} caught={rows[-1]['caught']}")
    ok = all(r["caught"] for r in rows)
    rec = {"schema": "public_rollout_mutation_check_v1",
           "status": "PASS" if ok else "FAIL",
           "note": "A mutant that no acceptance test catches means that test is vacuous.",
           "rows": rows, "host": platform.node(),
           "python": sys.version.split()[0],
           "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    pathlib.Path(args.out).mkdir(parents=True, exist_ok=True)
    (pathlib.Path(args.out) / "MUTATION.json").write_text(
        json.dumps(rec, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print("MUTATION_CHECK", rec["status"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())