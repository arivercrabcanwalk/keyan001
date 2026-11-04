import sys
import tempfile
from pathlib import Path
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carl.ppo import compute_gae, load_model, save_model, PolicyNet, ppo_update
from carl.state import N_FEATURES
from carl.actions import N_ACTIONS
from carl.controllers import PPOController


def test_numpy_policy_matches_torch():
    model = PolicyNet()
    controller = PPOController(model, deterministic=True)
    rng = np.random.default_rng(42)
    for feat in rng.normal(size=(100, N_FEATURES)).astype(np.float32):
        logits_np, value_np = controller._numpy_forward(feat)
        with torch.no_grad():
            logits_t, value_t = model(torch.as_tensor(feat).unsqueeze(0))
        assert np.allclose(logits_np, logits_t.numpy()[0], atol=2e-5, rtol=2e-5)
        assert abs(value_np - float(value_t.item())) < 2e-5
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "model.pt"
        save_model(model, p)
        loaded = load_model(p)
        assert loaded.training is False
        legacy = Path(d) / "legacy.pt"
        torch.save(model.state_dict(), legacy)
        try:
            load_model(legacy)
        except ValueError:
            pass
        else:
            raise AssertionError("legacy checkpoint accepted")


def test_semimarkov_gae_uses_elapsed_time():
    rewards = np.asarray([0.0, 1.0], dtype=np.float32)
    values = np.asarray([0.0, 0.0], dtype=np.float32)
    dones = np.asarray([0.0, 1.0], dtype=np.float32)
    durations = np.asarray([0.5, 1.5], dtype=np.float32)
    adv, ret = compute_gae(rewards, values, dones, durations, 2.0,
                           gamma=0.99, lam=0.95)
    expected = (0.99 ** 0.25) * (0.95 ** 0.25)
    assert abs(float(adv[0]) - expected) < 1e-6
    assert abs(float(adv[1]) - 1.0) < 1e-6
    assert np.allclose(ret, adv)


def test_singleton_minibatch_is_finite_and_masked_actions_rejected():
    model = PolicyNet()
    opt = torch.optim.Adam(model.parameters(), lr=0.001)
    n = 2
    batch = dict(
        feat=np.zeros((n, N_FEATURES), np.float32),
        mask=np.ones((n, N_ACTIONS), bool),
        action=np.zeros(n, np.int64),
        logp=np.full(n, -np.log(N_ACTIONS), np.float32),
        ret=np.ones(n, np.float32),
        adv=np.asarray([0.0, 1.0], np.float32),
    )
    stats = ppo_update(model, opt, batch, epochs=1, minibatch=1)
    assert all(np.isfinite(v) for v in stats.values())
    assert all(torch.isfinite(p).all() for p in model.parameters())
    bad = dict(batch)
    bad["mask"] = batch["mask"].copy()
    bad["mask"][0, 0] = False
    try:
        ppo_update(model, opt, bad, epochs=1, minibatch=1)
    except ValueError:
        pass
    else:
        raise AssertionError("masked action was accepted")


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name, flush=True)
            except Exception as exc:
                failures += 1
                print("FAIL", name, repr(exc), flush=True)
    print("RESULT", 3 - failures, "/3", flush=True)
    raise SystemExit(bool(failures))
