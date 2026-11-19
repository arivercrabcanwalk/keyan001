import sys
sys.path.insert(0, "<EXECUTION_PATH>")
from fixtures.build import f02_3s_6t
from env.core import PublicPrefix
from env.causal_engine import CausalEngine, EngineConfig
from env.forecast_book import ForecastBook, ErrorModel
from env.latent_phase import FrozenParticleModel, FrozenModelParams
from tests.run_all import _truth_particle, _publish
static = f02_3s_6t()
rel = ((0.0,1),(0.0,2),(0.0,6))
cfg = EngineConfig(horizon_min=240.0)
prefix = PublicPrefix(static_sha256=static.sha256, t_min=0.0, frontier_id=0, releases=rel)
p = _truth_particle(static, rel, 240.0, seed=7)
fb = ForecastBook([0.0,60.0,120.0,180.0], 180.0, error_model=ErrorModel(0.05,0.05))
_publish(fb, p, 240.0)
eng = CausalEngine(static, prefix, p, cfg, fb)
print("slots", list(eng.slots))
print("released", eng._released())
for k in sorted(eng.slots):
    print(k, "legal:", eng.legal_actions(k))
