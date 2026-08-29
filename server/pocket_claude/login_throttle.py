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


# Gemeinsamer Eimer fuer unbekannte Absender, wenn jeder Platz von einer
# laufenden Sperre belegt ist. Kein gueltiges Ergebnis von _subject.
OVERFLOW_SUBJECT = "__overflow__"


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
    """IP-Backoff mit begrenztem Speicher und ohne dauerhafte Kontosperre.

    Der Speicher ist auf max_entries plus genau einen Platz fuer den
    gemeinsamen Ueberlauf-Eimer begrenzt. free_attempts ist die exakte Zahl
    freier Passwortpruefungen, der sperrausloesende Versuch wird selbst schon
    abgewiesen. Eine laufende Sperre wird niemals durch Verdraengung oder
    Verfall entfernt und auch nicht durch einen erfolgreichen Login aufgehoben.
    """

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
        """Reserviert atomar eine Passwortpruefung oder liefert die Wartezeit."""
        with self._lock:
            now = self._clock()
            self._remove_oldest_expired(now)
            subject = self._subject(source_ip)

            if subject not in self._entries and len(self._entries) >= self.max_entries:
                victim = self._evictable(now)
                if victim is not None:
                    # Verdraengt wird ausschliesslich ein Eintrag OHNE laufende
                    # Sperre. Eine aktive Sperre ist unantastbar, sonst koennte
                    # ein verteilter Flood den Angreifer selbst entsperren.
                    self._entries.pop(victim, None)
                else:
                    # Alles gesperrt: Der unbekannte Absender teilt sich den
                    # begrenzten Ueberlauf-Eimer. Das opfert keine Sperre und
                    # weist ihn auch nicht pauschal ab, er bekommt die freien
                    # Versuche des gemeinsamen Eimers.
                    subject = OVERFLOW_SUBJECT

            entry = self._entries.get(subject)
            if entry is not None and now < entry.blocked_until:
                # Eine laufende Sperre bleibt frisch, solange weiter geklopft
                # wird. Sonst rutscht sie in der LRU-Ordnung nach vorn und
                # wuerde beim naechsten Speicherdruck zuerst geprueft.
                entry.last_attempt = now
                self._entries.move_to_end(subject)
                return Attempt(
                    subject,
                    entry.reservation_id,
                    max(1, math.ceil(entry.blocked_until - now)),
                )

            if entry is None or now - entry.last_attempt > self.history_window:
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
            if now < entry.blocked_until:
                # Der sperrausloesende Versuch wird selbst schon abgewiesen,
                # damit free_attempts genau die Zahl freier Passwortpruefungen
                # ist und nicht eine mehr.
                return Attempt(
                    subject,
                    entry.reservation_id,
                    max(1, math.ceil(entry.blocked_until - now)),
                )
            return Attempt(subject, entry.reservation_id, 0)

    def record_success(self, attempt: Attempt) -> None:
        with self._lock:
            now = self._clock()
            entry = self._entries.get(attempt.subject)
            # Ein aelterer Erfolg darf eine neuere Reservierung nicht loeschen,
            # denn die kann bereits eine andere fehlgeschlagene Pruefung sein.
            if entry is None or entry.reservation_id != attempt.reservation_id:
                return
            if now < entry.blocked_until:
                # Ein Erfolg waehrend einer laufenden Sperre hebt sie nicht auf.
                # Sonst genuegt ein einziger gueltiger Zugang, um die Drossel
                # der IP fuer Rateversuche gegen andere Konten zuruecksetzen.
                return
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

    def _remove_oldest_expired(self, now: float, limit: int = 16) -> None:
        # Bewusst begrenzt: Ein voller Speicher darf pro Anfrage keinen
        # Volldurchlauf unter dem gemeinsamen Lock ausloesen.
        for _ in range(limit):
            if not self._entries:
                return
            bucket, entry = next(iter(self._entries.items()))
            if now - entry.last_attempt <= self.history_window:
                # Die Ordnung steigt nach last_attempt, ab hier ist alles jung.
                return
            if now < entry.blocked_until:
                # Eine laufende Sperre ueberlebt den Verfall auch dann, wenn
                # history_window kleiner als die Sperrdauer konfiguriert wurde.
                # Sie wandert ans Ende, damit der naechste Verfallslauf nicht
                # erneut an ihr haengenbleibt.
                entry.last_attempt = now
                self._entries.move_to_end(bucket)
                continue
            self._entries.pop(bucket, None)

    def _evictable(self, now: float, limit: int = 32) -> str | None:
        """Aeltester Eintrag OHNE laufende Sperre im begrenzten Suchfenster.

        Das Fenster ist bewusst gedeckelt, damit ein voller Speicher pro
        Anfrage keinen Volldurchlauf unter dem gemeinsamen Lock ausloest.
        """
        for index, (bucket, entry) in enumerate(self._entries.items()):
            if index >= limit:
                return None
            if bucket == OVERFLOW_SUBJECT:
                continue
            if now >= entry.blocked_until:
                return bucket
        return None

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
