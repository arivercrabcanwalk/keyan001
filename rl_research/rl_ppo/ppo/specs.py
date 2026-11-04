"""Method spec strings -> controllers.
  norl:M          rl_v3 NoRL emulation: T 0.01->0.001 exponential over run, NoRL fam/intensity phase (30%), best-of-M
  s:T,M,I         static: T level idx, M idx, intensity idx; fam = NoRL phase (struct k<0.3S, route after)
  p:A/B[@f]       two-phase: A,B are 'T,M,I' ; switch at fraction f (default .5)
  r:T,M,I         reactive rule: like s: but restart-to-best + high intensity when last segment had no improvement
"""
from ppo import dac
def _fam(k, S): return 0 if k < 0.3 * S else 1
def make(spec):
    kind, _, arg = spec.partition(':')
    if kind == 'norl':
        mi = dac.M_LEVELS.index(int(arg))
        def c(o, k, S):
            return (0.01 * 0.1 ** (k / S), mi, _fam(k, S), 1 if k < 0.3 * S else 0, 0, 0.1 ** (1 / S))
        return c
    if kind == 's':
        t, m, i = map(int, arg.split(','))
        return lambda o, k, S: (t, m, _fam(k, S), i, 0)
    if kind == 'p':
        f = 0.5
        if '@' in arg: arg, f = arg.split('@'); f = float(f)
        A, B = [tuple(map(int, x.split(','))) for x in arg.split('/')]
        def c(o, k, S):
            t, m, i = A if k < f * S else B
            return (t, m, _fam(k, S), i, 0)
        return c
    if kind == 'r':
        t, m, i = map(int, arg.split(','))
        def c(o, k, S):
            stuck = k > 0 and o[8] <= 1e-9
            return (t, m, _fam(k, S), 2 if stuck else i, 1 if stuck else 0)
        return c
    if kind in ('rr', 'ri'):
        t, m, i = map(int, arg.split(','))
        def c(o, k, S):
            stuck = k > 0 and o[8] <= 1e-9
            if kind == 'rr': return (t, m, _fam(k, S), i, 1 if stuck else 0)
            return (t, m, _fam(k, S), 2 if stuck else i, 0)
        return c
    raise ValueError(spec)
def units(sec, n_t):
    """work units equivalent to `sec` seconds of wall clock (calibrated, us/unit ~ 45+0.7n)."""
    return sec * 1e6 / (45.0 + 0.7 * n_t)
