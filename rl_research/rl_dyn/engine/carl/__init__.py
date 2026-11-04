"""CA-RL-TSALNS v1: coupling-aware joint neighborhoods for LRPHSD.

The package reuses the independent LRPHSD model/evaluator of ``lrphsd`` and
adds (i) an extended native kernel with explicit target removal, scoped
repair and 2-opt, (ii) coupling-aware joint macro-neighborhoods, (iii) a
state encoder, (iv) fixed/adaptive/rule/bandit/Q/PPO controllers and
(v) a same-budget experiment harness.
"""

__version__ = "1.0.0"
