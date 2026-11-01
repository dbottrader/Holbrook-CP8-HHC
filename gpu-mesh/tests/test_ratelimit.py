from gpumesh.ratelimit import RateLimiter


def test_sliding_window_rejects_then_admits():
    now = [0.0]
    limiter = RateLimiter(clock=lambda: now[0])
    assert limiter.allow("ip", 2, 60)[0] is True
    assert limiter.allow("ip", 2, 60)[0] is True
    ok, remaining = limiter.allow("ip", 2, 60)
    assert ok is False
    assert remaining == 0
    now[0] = 61
    assert limiter.allow("ip", 2, 60)[0] is True
