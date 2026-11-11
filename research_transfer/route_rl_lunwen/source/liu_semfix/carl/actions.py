"""Versioned operator-level action vocabulary for CA-RL-TSALNS v5."""

FAMILY_NAMES = ("Location", "Assignment", "Routing", "Joint")
OPERATOR_NAMES = (
    "loc_open", "loc_close", "loc_upgrade", "loc_downgrade", "loc_swap",
    "asg_transfer", "asg_drone_reassign",
    "route_relocate", "route_two_opt", "route_cross_drone",
    "route_cross_trip", "route_classic",
    "joint_open_steal", "joint_close_shift", "joint_upgrade_absorb",
    "joint_downgrade_reallocate", "joint_swap_absorb",
)
OPERATOR_FAMILY = (
    0, 0, 0, 0, 0,
    1, 1,
    2, 2, 2, 2, 2,
    3, 3, 3, 3, 3,
)
N_FAMILIES = len(FAMILY_NAMES)
N_OPERATORS = len(OPERATOR_NAMES)
N_INTENSITIES = 3
N_ACTIONS = N_OPERATORS * N_INTENSITIES

# 2-opt has no destroy-size parameter; exposing three duplicate actions would
# create artificial action multiplicity. Other operators support all levels.
OPERATOR_INTENSITIES = tuple(
    (0,) if name == "route_two_opt" else (0, 1, 2)
    for name in OPERATOR_NAMES
)

def action_id(operator, intensity):
    if operator < 0 or operator >= N_OPERATORS:
        raise ValueError("operator out of range")
    if intensity not in OPERATOR_INTENSITIES[operator]:
        raise ValueError("unsupported intensity for operator")
    return operator * N_INTENSITIES + intensity

def action_universe_mask(families=(0, 1, 2, 3), intensities=(0, 1, 2),
                         operators=None):
    import numpy as np
    if not families or any(type(f) is not int or f not in range(N_FAMILIES)
                           for f in families):
        raise ValueError("families must be nonempty and contain only 0..3")
    if not intensities or any(type(i) is not int or i not in range(N_INTENSITIES)
                              for i in intensities):
        raise ValueError("intensities must be nonempty and contain only 0..2")
    selected = set(operators) if operators is not None else {
        op for op, family in enumerate(OPERATOR_FAMILY) if family in families
    }
    if not selected or any(type(op) is not int or op not in range(N_OPERATORS)
                           for op in selected):
        raise ValueError("operators must be nonempty and contain only valid operator IDs")
    mask = np.zeros(N_ACTIONS, dtype=bool)
    for op in selected:
        for intensity in intensities:
            if intensity in OPERATOR_INTENSITIES[op]:
                mask[action_id(op, intensity)] = True
    return mask
