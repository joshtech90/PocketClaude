"""Bounded process-local throttling for password logins."""
from __future__ import annotations

import ipaddress
import math
import threading
import time
from collections import OrderedDict, deque
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


# Feste, bewusst NICHT eskalierende Bremse fuer unbekannte Absender, wenn
# jeder Platz von einer laufenden Sperre belegt ist. Absichtlich ohne
# gemeinsamen Zaehler und ohne eigenen Eintrag: Ein gemeinsamer Eimer liesse
# sich vergiften und vom Angreifer auf Minuten hochschaukeln, diese Bremse
# bleibt konstant kurz und faellt weg, sobald ein Platz frei wird.
OVERFLOW_DELAY_SECONDS = 1.0

# Wie viele Verdraengungskandidaten ein Durchlauf auf Vorrat sammelt.
_VICTIM_BATCH = 64


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

    Der Speicher ist hart auf max_entries begrenzt. free_attempts ist die exakte Zahl
    freier Passwortpruefungen, der sperrausloesende Versuch wird selbst schon
    abgewiesen. Eine laufende Sperre wird niemals durch Verdraengung oder
    Verfall entfernt und auch nicht durch einen erfolgreichen Login aufgehoben.

    Sind alle Plaetze gesperrt, bekommt ein unbekannter Absender eine feste
    kurze Bremse ohne eigenen Eintrag. Das bleibt eine Beeintraechtigung unter
    einem verteilten Angriff, ist aber nicht eskalierbar und endet sofort,
    sobald ein Platz frei wird.
    """

    def __init__(
        self,
        *,
        max_entries: int = 8_192,
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
        self._victims: deque[str] = deque()
        self._no_victim_until = 0.0
        # Nur fuer Tests und Diagnose: Zahl der Volldurchlaeufe.
        self._scan_count = 0
        self._lock = threading.Lock()

    def reserve(self, source_ip: str) -> Attempt:
        """Reserviert atomar eine Passwortpruefung oder liefert die Wartezeit."""
        with self._lock:
            now = self._clock()
            self._remove_oldest_expired(now)
            subject = self._subject(source_ip)

            if subject not in self._entries and len(self._entries) >= self.max_entries:
                victim = self._pick_victim(now)
                if victim is not None:
                    # Verdraengt wird ausschliesslich ein Eintrag OHNE laufende
                    # Sperre. Eine aktive Sperre ist unantastbar, sonst koennte
                    # ein verteilter Flood den Angreifer selbst entsperren.
                    self._entries.pop(victim, None)
                else:
                    # Wirklich jeder Platz ist gesperrt. Der unbekannte
                    # Absender wird kurz gebremst, bekommt aber KEINEN Eintrag
                    # und teilt sich keinen Zaehler. Damit laesst sich diese
                    # Bremse weder vergiften noch hochschaukeln, sie bleibt bei
                    # OVERFLOW_DELAY_SECONDS und endet, sobald ein Platz frei
                    # wird.
                    return Attempt(
                        subject,
                        0,
                        max(1, math.ceil(OVERFLOW_DELAY_SECONDS)),
                    )

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
            if now >= entry.blocked_until and len(self._victims) < _VICTIM_BATCH:
                # Ohne laufende Sperre ist dieser Eintrag ab sofort ein
                # Verdraengungskandidat. Ihn hier vorzumerken macht den
                # Volldurchlauf im Normalbetrieb ueberfluessig. Der Vorrat ist
                # eine Kandidatenmenge, keine strenge LRU-Ordnung; die Reihung
                # ist eine Heuristik, die Sicherheitszusage ist allein, dass
                # eine laufende Sperre nie verdraengt wird.
                self._victims.append(subject)
                self._no_victim_until = 0.0
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

    def _pick_victim(self, now: float) -> str | None:
        """Naechster verdraengbarer Eintrag, amortisiert konstant.

        Ein Durchlauf sammelt bis zu _VICTIM_BATCH Kandidaten auf Vorrat, die
        danach einzeln abgetragen werden. Findet ein Durchlauf gar kein Opfer,
        wird das bis zum Ablauf der fruehesten Sperre gemerkt. Ohne diese
        Sperre wuerde bei voller Tabelle JEDE Anfrage einen Volldurchlauf
        unter dem gemeinsamen Lock ausloesen.
        """
        while self._victims:
            bucket = self._victims.popleft()
            entry = self._entries.get(bucket)
            # Ein vorgemerkter Kandidat kann inzwischen entfernt oder erneut
            # gesperrt worden sein. Beides macht ihn unantastbar.
            if entry is not None and now >= entry.blocked_until:
                return bucket

        if now < self._no_victim_until:
            return None

        frueheste = math.inf
        for bucket, entry in self._entries.items():
            if now >= entry.blocked_until:
                self._victims.append(bucket)
                if len(self._victims) >= _VICTIM_BATCH:
                    break
            elif entry.blocked_until < frueheste:
                frueheste = entry.blocked_until
        self._scan_count += 1

        if len(self._victims) < _VICTIM_BATCH:
            # Der Durchlauf hat die Tabelle vollstaendig gesehen, er wurde also
            # nicht vorzeitig abgebrochen. Vor Ablauf der fruehesten Sperre
            # kann kein weiterer Kandidat auftauchen, den nicht schon das
            # Vormerken beim Entstehen erfasst haette. Ohne diese Merkzeit
            # wuerde ein einziger Kandidat pro Anfrage einen Volldurchlauf
            # ausloesen.
            self._no_victim_until = frueheste if frueheste < math.inf else now
        if not self._victims:
            return None
        return self._victims.popleft()

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
