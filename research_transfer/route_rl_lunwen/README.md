# Liu/LRPHSD Route-RL Research Transfer

This folder is an isolated, review-oriented export of the local Liu/LRPHSD research project for an external assistant such as GrokBot. It is deliberately added under `research_transfer/route_rl_lunwen/`; the repository's existing `rl_research/` project and `rl_project_pack.tar.gz` are not modified.

## Read first

1. `GROK_CONTEXT_ZH.md` (Chinese research context)
2. `CURRENT_STATUS.md` (current, evidence-bounded status)
3. `RESULTS_SUMMARY.md` (reproduction and RL results)
4. `RESEARCH_PLAN.md` and `analysis_docs/RESEARCH_PLAN_ROUTE_RL.md`
5. `CODE_MAP.md` (source layout and entry points)
6. `GROKBOT_PROMPT_ZH.md` (copy/paste prompt)

The English context is in `GROK_CONTEXT_EN.md`. Full sanitized reports and state records are under `analysis_docs/`; selected runnable source is under `source/`.

## Important scientific status

The Liu/SEMFiX reproduction is complete and auditable. The later route-level RL studies are **not** a positive result: the current evidence does not show RL beating the strongest non-RL baseline or the Liu author method under the preregistered comparison rules. G0/G3/G4 and the final formal/posterior gates remain unpassed. No document in this export should be read as claiming a paper-ready RL advantage.

## Privacy and reproducibility boundary

The export contains no SSH keys, tokens, server addresses, raw server logs, compiled libraries, model checkpoints, or large trajectory/result dumps. Local and server paths have been sanitized. Reproduction of server-scale experiments requires reconstructing the environment and data independently; the included source and reports document the contracts and evidence without exposing private infrastructure.

## Quick local check

From this folder, run:

```bash
./source/run_syntax_check.sh
```

This checks Python syntax only. It does not recreate the private server experiments or certify scientific performance.

## Transfer transaction audit

`transfer_audit/` contains the changed-field fixture, diff, verification record and executable rollback script used to validate this export. The rollback test uses a separate copy and leaves the main `MODIFIED_FILE` changed.
