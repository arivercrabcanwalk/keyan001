"""Small pointer actor-critic for the physical weather-route action space."""
from __future__ import annotations

import torch
from torch import nn


class WeatherPointerActorCritic(nn.Module):
    """Scores variable target/RETURN candidates; it never selects an operator."""

    def __init__(self, global_dim=17, candidate_dim=9, hidden_dim=64):
        super().__init__()
        if min(global_dim, candidate_dim, hidden_dim) <= 0:
            raise ValueError("network dimensions must be positive")
        self.global_encoder = nn.Sequential(nn.Linear(global_dim, hidden_dim), nn.Tanh(),
                                            nn.Linear(hidden_dim, hidden_dim), nn.Tanh())
        self.candidate_encoder = nn.Sequential(nn.Linear(candidate_dim, hidden_dim), nn.Tanh(),
                                               nn.Linear(hidden_dim, hidden_dim), nn.Tanh())
        self.query = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.key = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.score_bias = nn.Linear(hidden_dim, 1)
        self.value_head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.Tanh(),
                                        nn.Linear(hidden_dim, 1))
        self.hidden_dim = hidden_dim

    def forward(self, global_features, candidates, mask):
        global_features = torch.as_tensor(global_features, dtype=torch.float32)
        candidates = torch.as_tensor(candidates, dtype=torch.float32,
                                     device=global_features.device)
        mask = torch.as_tensor(mask, dtype=torch.bool, device=global_features.device).reshape(-1)
        if global_features.ndim != 1 or candidates.ndim != 2:
            raise ValueError("one global vector and a candidate matrix are required")
        if candidates.shape[0] != mask.numel() or candidates.shape[1] != self.candidate_encoder[0].in_features:
            raise ValueError("candidate/mask dimensions mismatch")
        if global_features.numel() != self.global_encoder[0].in_features:
            raise ValueError("global feature dimension mismatch")
        g = self.global_encoder(global_features)
        c = self.candidate_encoder(candidates)
        logits = (self.key(c) * self.query(g).unsqueeze(0)).sum(dim=-1) / (self.hidden_dim ** 0.5)
        logits = logits + self.score_bias(c).reshape(-1)
        logits = logits.masked_fill(~mask, -torch.inf)
        return logits, self.value_head(g).reshape(())


def greedy_action(model, observation):
    """Choose the max-logit legal physical action deterministically."""
    from rl_algorithms import masked_policy_distribution
    model.eval()
    with torch.no_grad():
        dist, value = masked_policy_distribution(model, observation)
        action = int(torch.argmax(dist.logits).item())
        return action, float(dist.log_prob(torch.tensor(action, device=dist.logits.device))), float(value)
