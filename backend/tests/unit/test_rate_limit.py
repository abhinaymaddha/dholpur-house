import pytest

from app.errors import RateLimited
from app.services.rate_limit import RateLimiter


class Clock:
    def __init__(self, t=1_800_000_000.0):   # 2027-01-15, mid-day UTC
        self.t = t

    def __call__(self):
        return self.t


def test_per_minute_limit_slides():
    clock = Clock()
    rl = RateLimiter(per_minute=2, per_day=100, daily_budget=100, clock=clock)
    rl.check("a")
    rl.check("a")
    with pytest.raises(RateLimited, match="a bit fast"):
        rl.check("a")
    rl.check("b")                       # other visitors are unaffected
    clock.t += 61
    rl.check("a")                       # the window moved on


def test_per_day_limit_resets_at_utc_midnight():
    clock = Clock()
    rl = RateLimiter(per_minute=100, per_day=2, daily_budget=100, clock=clock)
    rl.check("a")
    rl.check("a")
    with pytest.raises(RateLimited, match="today's limit"):
        rl.check("a")
    clock.t += 24 * 3600
    rl.check("a")


def test_site_budget_counts_only_ai_calls_and_refusals_cost_nothing():
    clock = Clock()
    rl = RateLimiter(per_minute=100, per_day=100, daily_budget=2, clock=clock)
    rl.check("a")
    rl.check("b")
    rl.check("c", uses_ai=False)        # real past questions don't reach the model
    with pytest.raises(RateLimited, match="The site has reached"):
        rl.check("d")
    with pytest.raises(RateLimited):
        rl.check("d")
    assert rl._daily.get("d") is None   # refused requests aren't counted against the visitor


def test_idle_visitors_are_forgotten():
    clock = Clock()
    rl = RateLimiter(per_minute=5, per_day=10**6, daily_budget=10**6, clock=clock)
    for i in range(10_001):
        rl.check(f"v{i}")
    clock.t += 120
    rl.check("fresh")
    assert set(rl._recent) == {"fresh"}


def test_a_request_counts_every_model_call_it_leads_to():
    rl = RateLimiter(per_minute=100, per_day=100, daily_budget=4, clock=Clock())
    rl.check("a", ai_calls=3)
    with pytest.raises(RateLimited, match="site has reached"):
        rl.check("b", ai_calls=2)                # counted nothing: a smaller request still fits
    rl.check("b", ai_calls=1)
    with pytest.raises(RateLimited, match="site has reached"):
        rl.check("c")
