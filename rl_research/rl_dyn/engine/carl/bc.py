"""Behaviour-cloning warm start for the PPO macro controller.

A strong hand-tuned schedule (M1d) is rolled out on training instances and the
(state, action) pairs are used to pretrain the MLP policy.  PPO then fine-tunes
the pretrained policy.  The warm start is reported explicitly; it is *not* the
source of the RL claim (the claim is the PPO fine-tuned policy vs the same
schedule / fixed policy under the same budget).
"""
import torch
import numpy as np
import torch.nn as nn

from .ppo import PolicyNet


class RecordingScheduled:
    """Wraps ScheduledPolicy and records (feat, action, mask)."""

    name = "teacher_scheduled"

    def __init__(self):
        from .controllers import ScheduledPolicy
        self.inner = ScheduledPolicy()
        self.records = []

    def begin(self, ins, seed):
        self.inner.begin(ins, seed)
        self.records = []

    def act(self, feat, mask, step):
        a = self.inner.act(feat, mask, step)
        self.records.append((feat.copy(), int(a), mask.copy()))
        return a

    def observe(self, *args, **kwargs):
        pass

    def end_episode(self):
        pass


def collect_task(task):
    torch.set_num_threads(1)
    from lrphsd.problem import read_instance
    from .search import solve
    ins = read_instance(task["instance_path"])
    ctrl = RecordingScheduled()
    res = solve(ins, ctrl, seed=task["seed"], seconds=task["seconds"],
                max_steps=task.get("max_steps", 20000),
                intensities=tuple(task.get("intensities", (0, 1, 2))))
    if not res["feasible"]:
        raise ValueError("infeasible BC teacher episode")
    return {"records": ctrl.records, "cost": res["cost"],
            "initial_cost": res["initial_cost"], "steps": res["steps"],
            "solver_seconds": res["solver_seconds"], "feasible": res["feasible"],
            "instance": task["instance"], "seed": int(task["seed"]),
            "counters": res.get("counters", {})}


def train_bc(records, epochs=6, lr=1e-3, batch=4096, seed=0):
    if not records:
        raise ValueError("empty BC records")
    if any(not r[2][r[1]] for r in records):
        raise ValueError("masked BC label")
    torch.manual_seed(seed)
    feats = torch.from_numpy(np.asarray([r[0] for r in records], dtype=np.float32))
    actions = torch.as_tensor([r[1] for r in records], dtype=torch.long)
    masks = torch.from_numpy(np.asarray([r[2] for r in records], dtype=bool))
    model = PolicyNet()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    n = len(feats)
    gen = torch.Generator().manual_seed(seed)
    for ep in range(epochs):
        perm = torch.randperm(n, generator=gen)
        total = 0.0
        correct = 0
        for start in range(0, n, batch):
            mb = perm[start:start + batch]
            logits, _ = model(feats[mb])
            logits = logits.masked_fill(~masks[mb], -1e9)
            loss = nn.functional.cross_entropy(logits, actions[mb])
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            opt.step()
            total += float(loss.item()) * len(mb)
            correct += int((logits.argmax(-1) == actions[mb]).sum())
        print(f"[bc] epoch {ep + 1}: loss {total / n:.4f} acc {correct / n:.4f}", flush=True)
    return model
