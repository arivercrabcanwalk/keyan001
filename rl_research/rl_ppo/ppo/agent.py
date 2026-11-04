"""PPO / A2C / REINFORCE for segment-level DAC of the LRPHSD ALNS.
Policy: obs-normalised MLP (NOBS->64->64) with factored categorical heads (T, M, fam, inten, restart);
separate value MLP. Workers run whole episodes with a numpy copy of the policy (CPU, no torch in workers).
Reward per segment = relative improvement of the best objective (x100 / init); optional paired
baseline (CRN): terminal bonus = (obj_base - obj)/init*100 where obj_base is the tuned static NoRL with
the same instance & seed  -> removes instance/seed noise from the return."""
import sys, os, json, math, time, random, argparse
sys.path.insert(0, '/workspace/rl_ppo')
import numpy as np

HEADS = None
def heads_from(spec):  # e.g. "T,M,I,R" -> active heads ; inactive heads fixed to default
    names = ['T', 'M', 'F', 'I', 'R']
    return [n in spec.split(',') for n in names]

class NPPolicy:
    def __init__(self, P, active, defaults, mu, sd, greedy=False, rng=None):
        self.P = P; self.active = active; self.defaults = defaults; self.mu = mu; self.sd = sd
        self.greedy = greedy; self.rng = rng or np.random.default_rng(); self.log = []
    def __call__(self, o, k, S):
        from ppo import dac
        x = np.clip((o - self.mu) / self.sd, -5, 5)
        h = np.tanh(self.P['w1'] @ x + self.P['b1']); h = np.tanh(self.P['w2'] @ h + self.P['b2'])
        cfg = []; lp = 0.0; acts = []
        for j, n in enumerate(dac.NHEAD):
            if not self.active[j]:
                v = self.defaults[j](k, S) if callable(self.defaults[j]) else self.defaults[j]
                cfg.append(v); acts.append(-1); continue
            z = self.P[f'h{j}w'] @ h + self.P[f'h{j}b']; z = z - z.max(); p = np.exp(z); p /= p.sum()
            a = int(p.argmax()) if self.greedy else int(self.rng.choice(n, p=p))
            lp += math.log(p[a] + 1e-12); cfg.append(a); acts.append(a)
        self.log.append((x.astype(np.float32), acts, lp))
        return tuple(cfg)

def fam_default(k, S): return 0 if k < 0.3 * S else 1

def episode(args):
    P, active, mu, sd, inst, lam, sec, seed, greedy, defaults_spec, base_obj, eseed = args
    from ppo import dac, specs, common
    defaults = [defaults_spec[0], defaults_spec[1], fam_default, defaults_spec[3], 0]
    pol = NPPolicy(P, active, defaults, mu, sd, greedy, np.random.default_rng(eseed))
    ins = common.load(inst)
    r = dac.solve_dac(ins, pol, specs.units(sec, len(ins.targets)), seed=seed, lam=lam)
    init = r['init_obj']; at = r['anytime']; prev = init; rew = []
    for b in at:
        rew.append((prev - b) / init * 100); prev = b
    return dict(obs=[l[0] for l in pol.log], acts=[l[1] for l in pol.log], logp=[l[2] for l in pol.log],
                rew=rew, obj=r['objective'], init=init, base=base_obj, inst=inst, lam=lam, sec=sec, seed=seed,
                cost=r['cost'], mk=r['makespan'], feasible=r['feasible'])
