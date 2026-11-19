"""Finite public fault law, isolated from route policies and live simulators.

Every particle is a MODEL HYPOTHESIS supplied before this call. The API never
accepts an actual Scenario/Trace/event queue. Weather likelihoods must come from
a separately frozen common public observation model; this module does not fit
them. Each target has at most one candidate crossing within a particle.
"""
from dataclasses import dataclass
import math
import random


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('finite ' + name)
    return float(value)


@dataclass(frozen=True)
class FaultOpportunity:
    target_id: int
    exit_time: float
    fault_probability: float
    max_delay: float

    def __post_init__(self):
        if type(self.target_id) is not int or self.target_id < 0:
            raise ValueError('nonnegative integer target_id')
        for name in ('exit_time', 'fault_probability', 'max_delay'):
            _finite(getattr(self, name), name)
        if self.exit_time < 0 or not 0 <= self.fault_probability <= 1 or self.max_delay <= 0:
            raise ValueError('nonnegative exit, probability in [0,1], positive delay support')
        if not math.isfinite(self.exit_time + self.max_delay) or self.exit_time + self.max_delay <= self.exit_time:
            raise ValueError('finite representable release support required')

    def release_fraction(self, now):
        return max(0., min(1., (now - self.exit_time) / self.max_delay))


@dataclass(frozen=True)
class StormParticle:
    particle_id: str
    weight: float
    opportunities: tuple

    def __post_init__(self):
        if type(self.particle_id) is not str or not self.particle_id:
            raise ValueError('particle id required')
        if _finite(self.weight, 'weight') <= 0:
            raise ValueError('strictly positive prior weight')
        object.__setattr__(self, 'opportunities', tuple(self.opportunities))
        if not all(isinstance(x, FaultOpportunity) for x in self.opportunities):
            raise TypeError('FaultOpportunity required')
        ids = [x.target_id for x in self.opportunities]
        if len(ids) != len(set(ids)):
            raise ValueError('repeated-target crossing semantics not defined')


@dataclass(frozen=True)
class PublicAlarm:
    target_id: int
    released_at: float


@dataclass(frozen=True)
class PublicPrefix:
    now: float
    alarms: tuple = ()
    # After-release means ALL alarms at now are public, including those which
    # have since been served. This ledger must not be only the pending queue.
    phase: str = 'AFTER_RELEASE'

    def __post_init__(self):
        if _finite(self.now, 'now') < 0 or self.phase != 'AFTER_RELEASE':
            raise ValueError('nonnegative after-release frontier required')
        object.__setattr__(self, 'alarms', tuple(self.alarms))
        ids = []
        for alarm in self.alarms:
            if not isinstance(alarm, PublicAlarm):
                raise TypeError('PublicAlarm required')
            if type(alarm.target_id) is not int or alarm.target_id < 0:
                raise ValueError('alarm target_id')
            if not 0 <= _finite(alarm.released_at, 'released_at') <= self.now:
                raise ValueError('published alarm after current frontier')
            ids.append(alarm.target_id)
        if len(ids) != len(set(ids)):
            raise ValueError('one alarm per target in this law')


@dataclass(frozen=True)
class FutureSample:
    particle_id: str
    releases: tuple
    beyond_horizon_target_ids: tuple
    no_future_fault_target_ids: tuple
    # Horizon is a rollout observation boundary, not evidence of no fault.
    horizon: float


class IncompatiblePublicHistory(ValueError):
    pass


class PublicFaultLaw:
    def __init__(self, model_id, particles):
        if type(model_id) is not str or not model_id:
            raise ValueError('frozen model_id required')
        self.model_id = model_id
        self.particles = tuple(particles)
        if not self.particles or not all(isinstance(x, StormParticle) for x in self.particles):
            raise TypeError('nonempty finite model particles required')
        ids = [x.particle_id for x in self.particles]
        if len(ids) != len(set(ids)):
            raise ValueError('unique particle ids required')
        target_sets = [{x.target_id for x in p.opportunities} for p in self.particles]
        if any(x != target_sets[0] for x in target_sets):
            raise ValueError('identical public target universe required; use p=0 for no crossing')
        self.target_ids = frozenset(target_sets[0])

    def weights(self, prefix, weather_log_likelihood=None, *, mode='public_history'):
        """Conditional probabilities over supplied model particles.

        prior_fixture is a declared synthetic verification mode that rejects
        nonempty alarm history. It is never a candidate scientific baseline.
        """
        if not isinstance(prefix, PublicPrefix):
            raise TypeError('PublicPrefix required')
        if mode not in {'public_history', 'prior_fixture'}:
            raise ValueError('explicit conditioning mode')
        observed = {x.target_id: x.released_at for x in prefix.alarms}
        if not set(observed) <= self.target_ids:
            raise ValueError('alarm outside public target universe')
        if mode == 'prior_fixture' and observed:
            raise ValueError('prior fixture does not process released alarms')
        weather = (0.,) * len(self.particles) if weather_log_likelihood is None else tuple(weather_log_likelihood)
        if len(weather) != len(self.particles):
            raise ValueError('one public weather likelihood per model particle')
        for value in weather:
            if type(value) not in (int, float) or math.isnan(value) or value == math.inf:
                raise ValueError('finite or negative-infinite log likelihood')
        logs = []
        for particle, weather_log in zip(self.particles, weather):
            value = math.log(particle.weight) + weather_log
            if mode == 'public_history':
                for item in particle.opportunities:
                    if item.target_id in observed:
                        release = observed[item.target_id]
                        if (item.fault_probability == 0 or release < item.exit_time or
                                release >= item.exit_time + item.max_delay):
                            value = -math.inf
                            break
                        value += math.log(item.fault_probability) - math.log(item.max_delay)
                    else:
                        occurred_probability = item.fault_probability * item.release_fraction(prefix.now)
                        if occurred_probability >= 1.:
                            value = -math.inf
                            break
                        value += math.log1p(-occurred_probability)
            logs.append(value)
        maximum = max(logs)
        if maximum == -math.inf:
            raise IncompatiblePublicHistory('zero model support; no uniform reset or hidden-future access')
        scaled = [math.exp(value - maximum) for value in logs]
        total = math.fsum(scaled)
        if not math.isfinite(total) or total <= 0:
            raise ArithmeticError('invalid conditional weight normalization')
        return tuple(value / total for value in scaled)

    def future_probability(self, particle_id, target_id, prefix):
        """Probability of a future alarm conditional on this particle and history.

        Call weights first to establish particle compatibility. This local
        probability alone does not condition a particle on other targets.
        """
        if not isinstance(prefix, PublicPrefix):
            raise TypeError('PublicPrefix required')
        particle = next((x for x in self.particles if x.particle_id == particle_id), None)
        if particle is None:
            raise ValueError('unknown model particle')
        item = next((x for x in particle.opportunities if x.target_id == target_id), None)
        if item is None:
            raise ValueError('unknown public target')
        if target_id in {x.target_id for x in prefix.alarms}:
            return 0.
        f = item.release_fraction(prefix.now)
        survival = 1. - item.fault_probability * f
        if survival <= 0:
            raise IncompatiblePublicHistory('no-alarm history impossible in this particle')
        return item.fault_probability * (1. - f) / survival

    def sample_future(self, prefix, seed, *, horizon, weather_log_likelihood=None):
        if type(seed) is not int or seed < 0:
            raise ValueError('explicit nonnegative integer sample seed')
        horizon = _finite(horizon, 'horizon')
        if not isinstance(prefix, PublicPrefix) or horizon < prefix.now:
            raise ValueError('horizon cannot precede public frontier')
        weights = self.weights(prefix, weather_log_likelihood, mode='public_history')
        rng = random.Random(seed)
        # One shared storm particle for the WHOLE target set. Independent
        # per-target particle selection would destroy latent correlation.
        draw = rng.random()
        cumulative = 0.
        selected = None
        for particle, weight in zip(self.particles, weights):
            cumulative += weight
            if weight > 0 and draw < cumulative:
                selected = particle
                break
        if selected is None:
            selected = next(p for p, weight in reversed(tuple(zip(self.particles, weights))) if weight > 0)
        observed = {x.target_id for x in prefix.alarms}
        releases, beyond, absent = [], [], []
        for item in sorted(selected.opportunities, key=lambda x: x.target_id):
            if item.target_id in observed:
                continue
            probability = self.future_probability(selected.particle_id, item.target_id, prefix)
            if rng.random() >= probability:
                absent.append(item.target_id)
                continue
            low = max(prefix.now, item.exit_time)
            high = item.exit_time + item.max_delay
            # Uniform on the remaining delay support. A sampled endpoint may
            # round to low; fail explicitly rather than silently shift time.
            release = low + (high - low) * rng.random()
            if release <= prefix.now or release >= high:
                raise ArithmeticError('sampled release does not advance representable clock')
            if release <= horizon:
                releases.append(PublicAlarm(item.target_id, release))
            else:
                beyond.append(item.target_id)
        releases.sort(key=lambda x: (x.released_at, x.target_id))
        return FutureSample(selected.particle_id, tuple(releases), tuple(beyond), tuple(absent), horizon)
