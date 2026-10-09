from backend.login_rate_limiter import LoginRateLimiter


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def test_allows_five_failures_and_blocks_sixth_attempt():
    clock = FakeClock()
    limiter = LoginRateLimiter(
        max_failures=5,
        window_seconds=60,
        clock=clock,
    )

    for _ in range(4):
        allowed, retry_after = limiter.record_failure("127.0.0.1")
        assert allowed is True
        assert retry_after == 0

    allowed, retry_after = limiter.record_failure("127.0.0.1")
    assert allowed is False
    assert retry_after == 60

    allowed, retry_after = limiter.check("127.0.0.1")
    assert allowed is False
    assert retry_after == 60


def test_window_expiry_allows_login_attempt_again():
    clock = FakeClock()
    limiter = LoginRateLimiter(
        max_failures=5,
        window_seconds=60,
        clock=clock,
    )

    for _ in range(5):
        limiter.record_failure("127.0.0.1")

    allowed, _ = limiter.check("127.0.0.1")
    assert allowed is False

    clock.advance(60)

    allowed, retry_after = limiter.check("127.0.0.1")
    assert allowed is True
    assert retry_after == 0


def test_successful_authentication_clears_failures():
    clock = FakeClock()
    limiter = LoginRateLimiter(
        max_failures=5,
        window_seconds=60,
        clock=clock,
    )

    for _ in range(5):
        limiter.record_failure("127.0.0.1")

    assert limiter.check("127.0.0.1")[0] is False

    limiter.clear("127.0.0.1")

    allowed, retry_after = limiter.check("127.0.0.1")
    assert allowed is True
    assert retry_after == 0


def test_clients_are_tracked_independently():
    clock = FakeClock()
    limiter = LoginRateLimiter(
        max_failures=2,
        window_seconds=60,
        clock=clock,
    )

    limiter.record_failure("10.0.0.1")
    limiter.record_failure("10.0.0.1")

    allowed, _ = limiter.check("10.0.0.1")
    assert allowed is False

    allowed, retry_after = limiter.check("10.0.0.2")
    assert allowed is True
    assert retry_after == 0


def test_stale_clients_are_pruned():
    clock = FakeClock()
    limiter = LoginRateLimiter(
        max_failures=2,
        window_seconds=60,
        max_clients=10,
        clock=clock,
    )

    limiter.record_failure("10.0.0.1")
    assert limiter.client_count() == 1

    clock.advance(60)

    assert limiter.client_count() == 0


def test_client_bound_is_enforced():
    clock = FakeClock()
    limiter = LoginRateLimiter(
        max_failures=2,
        window_seconds=60,
        max_clients=2,
        clock=clock,
    )

    limiter.record_failure("10.0.0.1")
    limiter.record_failure("10.0.0.2")
    limiter.record_failure("10.0.0.3")

    assert limiter.client_count() == 2
