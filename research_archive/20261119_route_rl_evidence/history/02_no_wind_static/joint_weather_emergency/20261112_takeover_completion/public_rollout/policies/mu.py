"""Deterministic frozen base policies (non-learning).

mu_lpt: nearest legal OPEN target for this slot's station, else RETURN.
No randomness, no wall-clock branch, so T2 can compare two runs bit for bit.
"""
from __future__ import annotations


def make_mu(kind: str = "lpt", static=None):
    if kind not in ("lpt", "nearest", "idle"):
        raise ValueError("unknown base policy")

    def mu(frame, key, engine):
        if kind == "idle":
            return None
        legal = engine.legal_actions(key)
        targets = [(a, t) for (a, t) in legal if a == "TARGET"]
        if targets:
            slot = engine.slots[key]
            nodes = engine.static.nodes
            targets.sort(key=lambda at: (round(
                ((nodes[at[1]].x - slot.x) ** 2 + (nodes[at[1]].y - slot.y) ** 2), 9),
                at[1]))
            return targets[0]
        returns = [(a, t) for (a, t) in legal if a == "RETURN"]
        if returns:
            return returns[0]
        return None

    return mu
