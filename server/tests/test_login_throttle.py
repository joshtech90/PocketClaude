import threading
from types import SimpleNamespace

from pocket_claude.login_throttle import (
    LoginThrottler,
    _valid_ip,
    client_ip,
    throttle_error,
)


def _request(peer: str, headers: dict[str, str] | None = None):
    return SimpleNamespace(
        client=SimpleNamespace(host=peer),
        headers=headers or {},
    )


def test_lan_peer_cannot_spoof_forwarded_headers():
    request = _request(
        "192.168.31.50",
        {"x-forwarded-for": "203.0.113.10", "forwarded": "for=203.0.113.11"},
    )
    assert client_ip(request) == "192.168.31.50"


def test_route_does_not_parse_forwarded_headers_itself():
    request = _request("127.0.0.1", {"x-forwarded-for": "198.51.100.7, 203.0.113.10"})
    assert client_ip(request) == "127.0.0.1"


def test_invalid_proxy_header_falls_back_to_loopback_peer():
    request = _request("127.0.0.1", {"x-forwarded-for": "not-an-ip"})
    assert client_ip(request) == "127.0.0.1"


def test_ipv6_scope_and_oversized_values_are_rejected():
    assert _valid_ip("fe80::1%eth0") is None
    assert _valid_ip("1" * 10_000) is None


def test_cooldown_recovers_and_success_clears_history():
    now = [100.0]
    throttle = LoginThrottler(
        free_attempts=1,
        base_delay=5.0,
        max_delay=30.0,
        clock=lambda: now[0],
    )
    first = throttle.reserve("192.0.2.1")
    second = throttle.reserve("192.0.2.1")
    assert first.retry_after == 0
    assert second.retry_after == 0
    assert throttle.reserve("192.0.2.1").retry_after == 5
    now[0] += 5.0
    successful = throttle.reserve("192.0.2.1")
    assert successful.retry_after == 0
    throttle.record_success(successful)
    assert throttle.entry_count() == 0


def test_parallel_reservations_cannot_burst_past_the_limit():
    throttle = LoginThrottler(free_attempts=4, base_delay=30.0)
    barrier = threading.Barrier(20)
    results: list[int] = []
    result_lock = threading.Lock()

    def reserve():
        barrier.wait()
        wait = throttle.reserve("192.0.2.1").retry_after
        with result_lock:
            results.append(wait)

    threads = [threading.Thread(target=reserve) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(0) == 5
    assert len([wait for wait in results if wait > 0]) == 15


def test_capacity_evicts_oldest_exact_subject_without_collateral_block():
    throttle = LoginThrottler(
        max_entries=1,
        free_attempts=0,
        base_delay=30.0,
    )
    throttle.reserve("192.0.2.1")
    assert throttle.reserve("192.0.2.1").retry_after == 30

    other = throttle.reserve("192.0.2.2")

    assert other.retry_after == 0
    assert other.subject == "192.0.2.2"
    assert throttle.entry_count() == 1


def test_capacity_remains_bounded_under_many_sources():
    throttle = LoginThrottler(max_entries=8)

    for third_octet in range(10):
        for last_octet in range(1, 255):
            throttle.reserve(f"198.51.{third_octet}.{last_octet}")

    assert throttle.entry_count() == 8


def test_old_success_cannot_clear_a_newer_reservation():
    throttle = LoginThrottler(free_attempts=1, base_delay=30.0)
    older = throttle.reserve("192.0.2.1")
    newer = throttle.reserve("192.0.2.1")
    assert older.retry_after == 0
    assert newer.retry_after == 0

    throttle.record_success(older)

    assert throttle.entry_count() == 1
    assert throttle.reserve("192.0.2.1").retry_after == 30


def test_expired_slot_is_reused_after_saturation():
    now = [100.0]
    throttle = LoginThrottler(
        max_entries=1,
        history_window=10.0,
        clock=lambda: now[0],
    )
    throttle.reserve("192.0.2.1")
    assert throttle.reserve("192.0.2.2").retry_after == 0

    now[0] += 11.0
    admitted = throttle.reserve("192.0.2.2")

    assert admitted.subject == "192.0.2.2"
    assert throttle.entry_count() == 1


def test_ipv6_privacy_addresses_share_one_64_subject():
    throttle = LoginThrottler(
        max_entries=32,
        free_attempts=0,
        base_delay=30.0,
    )

    first = throttle.reserve("2001:db8:abcd:1234::1")
    second = throttle.reserve("2001:db8:abcd:1234:ffff::99")

    assert first.subject == "2001:db8:abcd:1234::/64"
    assert second.subject == first.subject
    assert second.retry_after == 30


def test_ipv4_mapped_ipv6_is_tracked_as_its_ipv4_address():
    throttle = LoginThrottler(free_attempts=0, base_delay=30.0)

    first = throttle.reserve("::ffff:192.0.2.1")
    second = throttle.reserve("192.0.2.1")

    assert first.subject == "192.0.2.1"
    assert second.subject == first.subject
    assert second.retry_after == 30


def test_old_success_cannot_clear_a_recreated_subject():
    throttle = LoginThrottler(max_entries=1, free_attempts=4)
    older = throttle.reserve("192.0.2.1")
    throttle.reserve("192.0.2.2")
    newer = throttle.reserve("192.0.2.1")

    throttle.record_success(older)

    assert throttle.entry_count() == 1
    assert newer.reservation_id != older.reservation_id


def test_throttle_error_has_429_and_retry_after():
    error = throttle_error(7)
    assert error.status_code == 429
    assert error.headers == {"Retry-After": "7"}
    assert "7 Sekunden" in error.detail
