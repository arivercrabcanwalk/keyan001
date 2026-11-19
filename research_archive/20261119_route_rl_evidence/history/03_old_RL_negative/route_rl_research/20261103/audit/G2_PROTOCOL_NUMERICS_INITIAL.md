# Independent initial review: frozen G2 station-DP protocol

Date: 2026-11-03. Reviewer: route_mechanism_g4. Scope is a read-only review of `joint_route_env/G2_STATION_SPLIT_DP_PROTOCOL.md` for the numerical semantics, 1e-7/1e-8 tolerance contract, and status names. This initial is prepared before receiving peer replies to this protocol review. No code, solver, evaluator, DP, test, quality, training, or server job was run.

## Initial decision

The draft materially improves the earlier plan: it uses the evaluator's `1e-7` feasibility allowance, explicitly makes DABS both slots share the large-station radius and duration while retaining slot-specific battery, keeps all 24 maps/stations, preserves unresolved stations, and separates the historical oracle diagnostic from 6s/12s solver comparison. These parts are consistent with the frozen evaluator inspected in `STATION_SPLIT_DP_NUMERICS_INITIAL.md`.

The numerical contract and terminology still need clarification before execution. The current DP is a floating-point reference whose reconstructed witnesses can be independently checked as evaluator-feasible; that alone does not certify that its DP scalar is the exact minimum over every evaluator-admitted IEEE-feasible route. The protocol should not let a coverage-status label imply that stronger claim.

## Findings

### 1. Geometry and accumulation semantics remain unspecified

The formulation says to use the shortest closed tour and `tour_length/speed`, but does not freeze whether edges use `hypot` or `sqrt(dx**2+dy**2)`, whether travel is divided by speed edge-by-edge or after summing route length, and the accumulation order for service, target energy, trip times, and station/map objective. The inspected current `exact.py` differs from `evaluator.py` on these operations. Matching the evaluator's `1e-7` thresholds does not resolve those arithmetic differences.

Required clarification: freeze a deterministic distance and accumulation contract for the DP and witness reconstruction; independently rescore every witness using the evaluator; keep DP objective, evaluator objective, their residual, and resource slacks separately. Any feasibility-sensitive or cost-ranking case within a declared numerical ambiguity band remains unresolved. Passing a scalar agreement threshold is not an optimality certificate.

### 2. Separate the feasibility epsilon from cost and regression tolerances

The draft correctly states that `1e-7` is a feasibility allowance rather than a cost-rounding tolerance. However, the phrase “candidate cost regression beyond the predeclared `1e-8` absolute map-cost reconciliation tolerance” leaves unclear whether `1e-8` compares (a) the DP's scalar predicted map cost against the full evaluator's map cost, or (b) the candidate map cost against its parent. Those are different checks.

Required clarification: name separate fields, for example `EPS_FEAS=1e-7` only for coverage/battery/duty predicates and `EPS_COST_RECON=1e-8` only for a specified DP-vs-evaluator objective reconciliation. Define candidate-versus-parent regression/tie classification independently. A route witness can pass `EPS_COST_RECON` and still provide only a feasible upper bound; the cost tolerance must never relax feasibility or establish optimality.

### 3. Full-reference status should not imply a certified IEEE optimum

The labels “Exact station formulation” and `FULL_STATION_DOMAIN_REFERENCE` combine complete-domain enumeration language with a floating implementation that has no independently checked evaluator-semantic lower bound. A full map whose station runs finish and whose reconstructed candidate passes evaluation supports the statement “the predeclared station DP completed and its returned full candidate is evaluator-feasible.” It does not by itself prove an exact optimum under the evaluator's floating predicates or a lower bound on remaining opportunity.

Required clarification: define the status as coverage/completion, not proof strength. Prefer a name such as `FULL_STATION_DP_REFERENCE_WITNESS_VERIFIED`; explicitly say it is the DP result under the frozen recurrence/arithmetic plus a feasible witness, and not a formal IEEE/real-arithmetic optimality certificate. If the project intends an exact optimum claim, it needs an independently justified lower-bound/certification method with the same feasible domain; tiny-fixture exhaustive checks alone do not certify larger stations.

### 4. The new station cutoff is not the old exact solver's validated station cutoff

The draft sets station-union `n<=12`, “fixed from the existing small-instance exact-DP limit.” The existing `exact.py` guard counts all targets in the complete instance, not targets at an individual station. Thus 12 may be selected as a new conservative station-level cap, but it is not an already validated per-station capability or a direct coverage guarantee. Label it as a newly predeclared G2 resource cutoff, without implying station-level performance has been tested.

## Correct details confirmed

- Frozen evaluator coverage uses station-type radius with `1e-7`; its energy and cumulative-duty checks also admit `+1e-7`.
- For SABS, the only active slot is SD slot 1 and its duration is `small_duration`.
- For DABS, both slots use `large_duration` and the large station radius; LD slot 0 uses large battery and SD slot 1 uses small battery.
- `1e-8` is much smaller than and conceptually separate from `1e-7`; the draft must preserve that distinction and not convert it into a feasibility epsilon.
- Full-map witness validation, unresolved retention, and separation from later 6s/12s method comparisons are required and appropriately stated.

## Execution boundary

This is a review only. It does not edit or freeze the root protocol, implement the DP, run the tiny fixture verifier, start the 24-map diagnostic, or authorize any solver/quality/training work. All G2 results remain pending.
