"""Bounded process-local throttling for password logins."""
from __future__ import annotations

import ipaddress
import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from fastapi import Request


def _valid_ip(value: str) -> str | None:
    candidate = value.strip()
    if not candidate or len(candidate) > 45 or "%" in candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def client_ip(request: Request) -> str:
    """Return the IP normalized by Uvicorn's loopback-only proxy middleware."""
    peer = request.client.host.strip() if request.client and request.client.host else ""
    return _valid_ip(peer) or "unknown"


@dataclass
class _Entry:
    attempts: int
    last_attempt: float
    blocked_until: float
    reservation_id: int


@dataclass(frozen=True)
class Attempt:
    subject: str
    reservation_id: int
    retry_after: int


class LoginThrottler:
    """IP-based backoff with bounded memory and no persistent account lock."""

    def __init__(
        self,
        *,
        max_entries: int = 2_048,
        free_attempts: int = 4,
        base_delay: float = 5.0,
        max_delay: float = 300.0,
        history_window: float = 900.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1 or free_attempts < 0:
            raise ValueError("invalid throttler limits")
        self.max_entries = max_entries
        self.free_attempts = free_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.history_window = history_window
        self._clock = clock
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._next_reservation_id = 0
        self._lock = threading.Lock()

    def reserve(self, source_ip: str) -> Attempt:
        """Atomically reserve one password check or return a wait time."""
        with self._lock:
            now = self._clock()
            self._remove_oldest_expired(now)
            subject = self._subject(source_ip)
            entry = self._entries.get(subject)
            if entry is not None and now < entry.blocked_until:
                return Attempt(
                    subject,
                    entry.reservation_id,
                    max(1, math.ceil(entry.blocked_until - now)),
                )

            if entry is None or now - entry.last_attempt > self.history_window:
                if entry is None and len(self._entries) >= self.max_entries:
                    # A distributed source flood already defeats the security
                    # premise of any per-IP limiter. Evicting the oldest exact
                    # subject keeps every arriving source tracked and avoids
                    # both a global collision lockout and a fail-open client.
                    self._entries.popitem(last=False)
                entry = _Entry(
                    attempts=0,
                    last_attempt=now,
                    blocked_until=0.0,
                    reservation_id=0,
                )

            entry.attempts += 1
            entry.last_attempt = now
            self._next_reservation_id += 1
            entry.reservation_id = self._next_reservation_id
            if entry.attempts > self.free_attempts:
                exponent = entry.attempts - self.free_attempts - 1
                delay = min(self.max_delay, self.base_delay * (2 ** min(exponent, 16)))
                entry.blocked_until = now + delay

            self._entries[subject] = entry
            self._entries.move_to_end(subject)
            return Attempt(subject, entry.reservation_id, 0)

    def record_success(self, attempt: Attempt) -> None:
        with self._lock:
            entry = self._entries.get(attempt.subject)
            # A successful older request must not erase a newer reservation,
            # which may already represent another failed password check.
            if (
                entry is not None
                and entry.reservation_id == attempt.reservation_id
            ):
                self._entries.pop(attempt.subject, None)

    @staticmethod
    def _subject(source_ip: str) -> str:
        """Collapse IPv6 privacy addresses to the network normally delegated."""
        try:
            address = ipaddress.ip_address(source_ip)
        except ValueError:
            return source_ip
        if isinstance(address, ipaddress.IPv6Address):
            if address.ipv4_mapped is not None:
                return str(address.ipv4_mapped)
            network = ipaddress.ip_network(f"{address}/64", strict=False)
            return f"{network.network_address}/64"
        return str(address)

    def _remove_oldest_expired(self, now: float) -> None:
        while self._entries:
            bucket, entry = next(iter(self._entries.items()))
            if now - entry.last_attempt <= self.history_window:
                return
            self._entries.pop(bucket, None)

    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)


def throttle_error(retry_after: int) -> HTTPException:
    wait = max(1, int(retry_after))
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Zu viele Fehlversuche. Bitte in {wait} Sekunden erneut versuchen.",
        headers={"Retry-After": str(wait)},
    )


login_throttler = LoginThrottler()
