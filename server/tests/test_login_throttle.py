"""Tests fuer das Modul login_throttle."""
from __future__ import annotations

import ipaddress
import threading
import unittest
from types import SimpleNamespace
from typing import List

from fastapi import HTTPException, status

from pocket_claude.login_throttle import (
    OVERFLOW_SUBJECT,
    Attempt,
    LoginThrottler,
    _valid_ip,
    client_ip,
    throttle_error,
)


class FakeClock:
    """Kontrollierbare Uhr fuer deterministische Zeitspruenge in Tests."""

    def __init__(self, initial_time: float = 1000.0) -> None:
        self.time = initial_time

    def __call__(self) -> float:
        return self.time

    def advance(self, seconds: float) -> None:
        self.time += seconds


class TestLoginThrottlerFreeAttempts(unittest.TestCase):
    """Prueft das Verhalten der anfaenglichen Freiversuche."""

    def test_free_attempts_return_retry_after_zero(self) -> None:
        # Die ersten free_attempts Versuche liefern retry_after 0.
        clock = FakeClock(100.0)
        throttler = LoginThrottler(free_attempts=4, clock=clock)

        for attempt_index in range(1, 5):
            attempt = throttler.reserve("192.0.2.1")
            self.assertEqual(attempt.retry_after, 0)
            self.assertEqual(attempt.reservation_id, attempt_index)
            self.assertEqual(attempt.subject, "192.0.2.1")


class TestLoginThrottlerBackoff(unittest.TestCase):
    """Prueft das exponentielle Wachstum der Sperre und deren Deckelung."""

    def test_exponential_growth_and_max_delay_cap(self) -> None:
        # Pruefung der exponentiellen Verzoegerung und der Deckelung bei max_delay.
        clock = FakeClock(1000.0)
        base_delay = 5.0
        max_delay = 35.0
        throttler = LoginThrottler(
            free_attempts=2,
            base_delay=base_delay,
            max_delay=max_delay,
            clock=clock,
        )

        # Versuch 1 und 2: Freiversuche ohne Sperre
        att1 = throttler.reserve("192.0.2.1")
        self.assertEqual(att1.retry_after, 0)
        att2 = throttler.reserve("192.0.2.1")
        self.assertEqual(att2.retry_after, 0)

        # Versuch 3 loest die Sperre aus und wird selbst schon abgewiesen,
        # damit free_attempts genau zwei freie Pruefungen bedeutet.
        # Verzoegerung base_delay * 2^0 = 5.0s
        att3 = throttler.reserve("192.0.2.1")
        self.assertEqual(att3.retry_after, 5)

        # Sperre aktiv: Bei t=1001.0 betraegt die Restzeit ceil(1005.0 - 1001.0) = 4s
        clock.advance(1.0)
        blocked_att = throttler.reserve("192.0.2.1")
        self.assertEqual(blocked_att.retry_after, 4)

        # Uhr auf Ende der Sperre vorstellen (t=1005.0)
        clock.advance(4.0)

        # Versuch 4: Verzoegerung base_delay * 2^1 = 10.0s (Sperre bis 1015.0)
        att4 = throttler.reserve("192.0.2.1")
        self.assertEqual(att4.retry_after, 10)

        # Uhr auf Ende der Sperre vorstellen (t=1015.0)
        clock.advance(10.0)

        # Versuch 5: Verzoegerung base_delay * 2^2 = 20.0s (Sperre bis 1035.0)
        att5 = throttler.reserve("192.0.2.1")
        self.assertEqual(att5.retry_after, 20)

        # Uhr auf Ende der Sperre vorstellen (t=1035.0)
        clock.advance(20.0)

        # Versuch 6: Wuerde rechnerisch 40.0s ergeben, wird auf max_delay = 35.0s gedeckelt
        att6 = throttler.reserve("192.0.2.1")
        self.assertEqual(att6.retry_after, 35)

        # Pruefung der Deckelung: Nach 30s ist die Sperre noch aktiv mit Restzeit 5s
        clock.advance(30.0)
        blocked_cap = throttler.reserve("192.0.2.1")
        self.assertEqual(blocked_cap.retry_after, 5)

        # Nach weiteren 5s ist die alte Sperre abgelaufen. Der naechste
        # Versuch setzt sofort die naechste, weiterhin gedeckelte Sperre.
        clock.advance(5.0)
        att7 = throttler.reserve("192.0.2.1")
        self.assertEqual(att7.retry_after, 35)


class TestLoginThrottlerActiveLock(unittest.TestCase):
    """Prueft das Verhalten von reserve waehrend einer aktiven Sperre."""

    def test_reserve_during_active_lock_returns_retry_after_greater_zero(self) -> None:
        # Waehrend einer aktiven Sperre muss retry_after strikt groesser 0 sein.
        clock = FakeClock(100.0)
        throttler = LoginThrottler(
            free_attempts=1,
            base_delay=10.0,
            clock=clock,
        )

        # Versuch 1: Freiversuch
        att1 = throttler.reserve("192.0.2.10")
        self.assertEqual(att1.retry_after, 0)
        self.assertEqual(att1.reservation_id, 1)

        # Versuch 2: Loest Sperre fuer 10s aus (blocked_until = 110.0) und
        # wird selbst bereits mit der vollen Wartezeit abgewiesen.
        att2 = throttler.reserve("192.0.2.10")
        self.assertEqual(att2.retry_after, 10)
        self.assertEqual(att2.reservation_id, 2)

        # Versuch 3 bei t=102.5: Sperre aktiv, Wartezeit ceil(110.0 - 102.5) = 8
        clock.advance(2.5)
        blocked1 = throttler.reserve("192.0.2.10")
        self.assertGreater(blocked1.retry_after, 0)
        self.assertEqual(blocked1.retry_after, 8)
        self.assertEqual(blocked1.reservation_id, att2.reservation_id)

        # Versuch 4 bei t=109.8: Restzeit 0.2s liefert aufgerundet 1 Sekunde
        clock.advance(7.3)
        blocked2 = throttler.reserve("192.0.2.10")
        self.assertGreater(blocked2.retry_after, 0)
        self.assertEqual(blocked2.retry_after, 1)


class TestLoginThrottlerRecordSuccess(unittest.TestCase):
    """Prueft die Entsperrung durch record_success."""

    def test_record_success_removes_only_current_reservation(self) -> None:
        # record_success loescht den Eintrag bei uebereinstimmender reservation_id.
        clock = FakeClock(100.0)
        throttler = LoginThrottler(free_attempts=2, clock=clock)

        attempt = throttler.reserve("192.0.2.20")
        self.assertEqual(throttler.entry_count(), 1)

        throttler.record_success(attempt)
        self.assertEqual(throttler.entry_count(), 0)

    def test_record_success_older_attempt_does_not_remove_newer_reservation(self) -> None:
        # Ein aelterer Erfolg darf eine neuere Reservierung nicht loeschen.
        clock = FakeClock(100.0)
        throttler = LoginThrottler(free_attempts=5, clock=clock)

        att1 = throttler.reserve("192.0.2.20")
        att2 = throttler.reserve("192.0.2.20")

        self.assertNotEqual(att1.reservation_id, att2.reservation_id)
        self.assertEqual(throttler.entry_count(), 1)

        # Veralteter Erfolg fuer att1 wird ignoriert
        throttler.record_success(att1)
        self.assertEqual(throttler.entry_count(), 1)

        # Aktueller Erfolg fuer att2 raeumt den Eintrag auf
        throttler.record_success(att2)
        self.assertEqual(throttler.entry_count(), 0)

    def test_record_success_unknown_subject_is_safely_ignored(self) -> None:
        # Erfolg fuer einen unbekannten Eintrag fuehrt nicht zu Fehlern.
        throttler = LoginThrottler()
        dummy_attempt = Attempt(subject="192.0.2.99", reservation_id=999, retry_after=0)
        throttler.record_success(dummy_attempt)
        self.assertEqual(throttler.entry_count(), 0)


class TestValidIpHelper(unittest.TestCase):
    """Prueft die IP-Validierungsfunktion _valid_ip."""

    def test_valid_ip_length_limit(self) -> None:
        # Eingaben laenger als 45 Zeichen werden abgewiesen.
        long_str = "192.168.1.1" + "a" * 35  # 46 Zeichen
        self.assertIsNone(_valid_ip(long_str))
        self.assertIsNone(_valid_ip("2001:0db8:0000:0000:0000:0000:0000:0001extra_long_suffix"))

    def test_valid_ip_rejects_scope_id(self) -> None:
        # IPv6 Scope IDs mit Prozentzeichen werden abgewiesen.
        self.assertIsNone(_valid_ip("fe80::1%eth0"))
        self.assertIsNone(_valid_ip("fe80::1%1"))
        self.assertIsNone(_valid_ip("::1%lo0"))
        self.assertIsNone(_valid_ip("192.168.1.1%eth0"))

    def test_valid_ip_accepts_valid_ipv4_and_ipv6(self) -> None:
        # Gueltige IPv4 und IPv6 Adressen werden normalisiert akzeptiert.
        self.assertEqual(_valid_ip("192.168.1.1"), "192.168.1.1")
        self.assertEqual(_valid_ip("  10.0.0.1  "), "10.0.0.1")
        self.assertEqual(_valid_ip("127.0.0.1"), "127.0.0.1")
        self.assertEqual(_valid_ip("::1"), "::1")
        self.assertEqual(_valid_ip("2001:db8::1"), "2001:db8::1")
        self.assertEqual(_valid_ip("fe80::200:f8ff:fe21:67cf"), "fe80::200:f8ff:fe21:67cf")

    def test_valid_ip_rejects_invalid_inputs(self) -> None:
        # Leere oder syntaktisch ungueltige Werte liefern None.
        self.assertIsNone(_valid_ip(""))
        self.assertIsNone(_valid_ip("   "))
        self.assertIsNone(_valid_ip("invalid_host"))
        self.assertIsNone(_valid_ip("999.999.999.999"))
        self.assertIsNone(_valid_ip("1.2.3.4.5"))


class TestIpNormalizationAndAggregation(unittest.TestCase):
    """Prueft die Normalisierung von IPv6-Netzen und IPv4-mapped Adressen."""

    def test_ipv6_grouped_to_slash_64(self) -> None:
        # IPv6 Adressen werden auf das /64 Netzwerk zusammengefasst.
        ip1 = "2001:db8:abcd:0012:0000:0000:0000:0001"
        ip2 = "2001:db8:abcd:0012:ffff:ffff:ffff:ffff"
        subject1 = LoginThrottler._subject(ip1)
        subject2 = LoginThrottler._subject(ip2)
        self.assertEqual(subject1, "2001:db8:abcd:12::/64")
        self.assertEqual(subject2, "2001:db8:abcd:12::/64")
        self.assertEqual(subject1, subject2)

    def test_ipv4_mapped_ipv6_normalized_to_ipv4(self) -> None:
        # IPv4-mapped IPv6 wird zur reinen IPv4 normalisiert.
        mapped_ip = "::ffff:192.0.2.128"
        subject = LoginThrottler._subject(mapped_ip)
        self.assertEqual(subject, "192.0.2.128")

    def test_subject_shares_bucket_across_ipv6_in_same_prefix(self) -> None:
        # Verschiedene IPv6-Adressen im selben /64-Netz teilen sich das Throttling-Konto.
        clock = FakeClock(100.0)
        throttler = LoginThrottler(free_attempts=2, clock=clock)

        att1 = throttler.reserve("2001:db8:1:2::1")
        att2 = throttler.reserve("2001:db8:1:2::2")
        self.assertEqual(att1.subject, "2001:db8:1:2::/64")
        self.assertEqual(att2.subject, "2001:db8:1:2::/64")
        self.assertEqual(throttler.entry_count(), 1)

    def test_subject_shares_bucket_between_ipv4_mapped_and_ipv4(self) -> None:
        # IPv4-mapped IPv6 und die IPv4 teilen sich dasselbe Konto.
        clock = FakeClock(100.0)
        throttler = LoginThrottler(free_attempts=2, clock=clock)

        att1 = throttler.reserve("::ffff:198.51.100.1")
        att2 = throttler.reserve("198.51.100.1")
        self.assertEqual(att1.subject, "198.51.100.1")
        self.assertEqual(att2.subject, "198.51.100.1")
        self.assertEqual(throttler.entry_count(), 1)


class TestMaxEntriesEviction(unittest.TestCase):
    """Prueft die Begrenzung des Speichers und die Verdraengung aeltester Eintraege."""

    def test_max_entries_never_exceeded_and_oldest_evicted(self) -> None:
        # Die Anzahl der Eintraege ueberschreitet max_entries nie, der aelteste Eintrag verfaellt.
        clock = FakeClock(100.0)
        throttler = LoginThrottler(max_entries=3, free_attempts=2, clock=clock)

        throttler.reserve("192.0.2.1")
        throttler.reserve("192.0.2.2")
        throttler.reserve("192.0.2.3")
        self.assertEqual(throttler.entry_count(), 3)

        # Ein vierter Eintrag verdraengt den aeltesten Eintrag (192.0.2.1)
        throttler.reserve("192.0.2.4")
        self.assertEqual(throttler.entry_count(), 3)

        # 192.0.2.1 war verdraengt und startet bei Neuankunft frisch mit Versuch 1
        fresh_att = throttler.reserve("192.0.2.1")
        self.assertEqual(fresh_att.retry_after, 0)
        self.assertEqual(throttler.entry_count(), 3)

    def test_lru_order_updated_on_access(self) -> None:
        # Ein Zugriff aktualisiert die Position, sodass der nicht genutzte Eintrag verdraengt wird.
        clock = FakeClock(100.0)
        throttler = LoginThrottler(max_entries=3, free_attempts=5, clock=clock)

        throttler.reserve("192.0.2.1")
        throttler.reserve("192.0.2.2")
        throttler.reserve("192.0.2.3")

        # 192.0.2.1 erneut ansprechen, damit wird 192.0.2.2 zum aeltesten Eintrag
        clock.advance(1.0)
        throttler.reserve("192.0.2.1")

        # 192.0.2.4 hinzufuegen: verdraengt 192.0.2.2
        throttler.reserve("192.0.2.4")
        self.assertEqual(throttler.entry_count(), 3)


class TestHistoryWindowExpiration(unittest.TestCase):
    """Prueft das automatische Verfallen alter Eintraege."""

    def test_expired_entry_resets_attempt_count(self) -> None:
        # Eintraege aelter als history_window verfallen und Versuche starten neu.
        clock = FakeClock(100.0)
        throttler = LoginThrottler(
            free_attempts=1,
            base_delay=10.0,
            history_window=300.0,
            clock=clock,
        )

        throttler.reserve("192.0.2.5")  # Versuch 1 (Freiversuch)
        throttler.reserve("192.0.2.5")  # Versuch 2 (loest Sperre bis 110.0 aus)

        # Zeit um mehr als history_window nach vorne bewegen (Differenz 350s > 300s)
        clock.advance(350.0)

        # Der naechste Aufruf erkennt den verfallenen Verlauf und gewaehrt wieder einen Freiversuch
        att = throttler.reserve("192.0.2.5")
        self.assertEqual(att.retry_after, 0)

    def test_remove_oldest_expired_cleans_up_old_entries(self) -> None:
        # Alte Eintraege werden bei Aufruf von reserve automatisch bereinigt.
        clock = FakeClock(100.0)
        throttler = LoginThrottler(history_window=200.0, clock=clock)

        throttler.reserve("192.0.2.1")
        self.assertEqual(throttler.entry_count(), 1)

        # Zeit ueberschreitet das Zeitfenster
        clock.advance(250.0)

        # Reservierung fuer eine neue IP bereinigt den alten Eintrag
        throttler.reserve("192.0.2.2")
        self.assertEqual(throttler.entry_count(), 1)


class TestConcurrency(unittest.TestCase):
    """Prueft die Thread-Sicherheit bei gleichzeitigen Reservierungen."""

    def test_concurrent_reserve_unique_reservation_ids_and_no_lost_attempts(self) -> None:
        # Mehrere Threads rufen gleichzeitig reserve fuer verschiedene IP-Adressen auf.
        throttler = LoginThrottler(max_entries=200, free_attempts=10)
        num_threads = 40
        results: List[Attempt] = []
        threads: List[threading.Thread] = []
        collector_lock = threading.Lock()

        def worker(ip: str) -> None:
            attempt = throttler.reserve(ip)
            with collector_lock:
                results.append(attempt)

        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(f"198.51.100.{i}",))
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(results), num_threads)
        reservation_ids = [attempt.reservation_id for attempt in results]
        self.assertEqual(len(reservation_ids), len(set(reservation_ids)))
        self.assertEqual(throttler.entry_count(), num_threads)

    def test_concurrent_reserve_same_ip(self) -> None:
        # Mehrere Threads rufen gleichzeitig reserve fuer dieselbe IP auf.
        clock = FakeClock(100.0)
        throttler = LoginThrottler(max_entries=50, free_attempts=50, clock=clock)
        num_threads = 30
        results: List[Attempt] = []
        threads: List[threading.Thread] = []
        collector_lock = threading.Lock()

        def worker() -> None:
            attempt = throttler.reserve("203.0.113.1")
            with collector_lock:
                results.append(attempt)

        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(results), num_threads)
        reservation_ids = [attempt.reservation_id for attempt in results]
        self.assertEqual(len(reservation_ids), len(set(reservation_ids)))
        self.assertEqual(throttler.entry_count(), 1)


class TestThrottleError(unittest.TestCase):
    """Prueft die Erzeugung der HTTP-Exception fuer Throttling-Fehler."""

    def test_throttle_error_status_and_header(self) -> None:
        # throttle_error liefert HTTP 429 mit passendem Retry-After Header.
        exc = throttle_error(60)
        self.assertIsInstance(exc, HTTPException)
        self.assertEqual(exc.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(exc.status_code, 429)
        self.assertEqual(exc.headers, {"Retry-After": "60"})
        self.assertIn("60 Sekunden", exc.detail)

    def test_throttle_error_minimum_retry_after(self) -> None:
        # Kleinere Werte als 1 werden auf 1 aufgerundet.
        exc_zero = throttle_error(0)
        self.assertEqual(exc_zero.headers, {"Retry-After": "1"})
        self.assertIn("1 Sekunden", exc_zero.detail)

        exc_neg = throttle_error(-5)
        self.assertEqual(exc_neg.headers, {"Retry-After": "1"})


class TestClientIpAndLimits(unittest.TestCase):
    """Prueft die client_ip Hilfsfunktion und Limits im Konstruktor."""

    def test_client_ip_extraction(self) -> None:
        # client_ip extrahiert die bereinigte IP oder liefert unknown.
        req_valid = SimpleNamespace(client=SimpleNamespace(host="  192.0.2.1  "))
        self.assertEqual(client_ip(req_valid), "192.0.2.1")

        req_none = SimpleNamespace(client=None)
        self.assertEqual(client_ip(req_none), "unknown")

        req_invalid = SimpleNamespace(client=SimpleNamespace(host="invalid_host"))
        self.assertEqual(client_ip(req_invalid), "unknown")

        req_scoped = SimpleNamespace(client=SimpleNamespace(host="fe80::1%eth0"))
        self.assertEqual(client_ip(req_scoped), "unknown")

    def test_invalid_constructor_limits(self) -> None:
        # Ungueltige Grenzen im Konstruktor loesen einen ValueError aus.
        with self.assertRaises(ValueError):
            LoginThrottler(max_entries=0)
        with self.assertRaises(ValueError):
            LoginThrottler(free_attempts=-1)


class TestSolFindings(unittest.TestCase):
    """Regression fuer die Findings aus den Sol-Reviews."""

    def test_eviction_never_drops_an_active_block(self) -> None:
        # Finding 1: Ein Flood neuer Quellen darf eine laufende Sperre nicht
        # aus dem Speicher draengen und den Angreifer damit entsperren.
        # Geprueft wird ueber reservation_id und Restzeit, nicht nur ueber
        # retry_after groesser 0. Eine geloeschte und neu angelegte Sperre
        # haette eine neue ID und die volle Frist.
        clock = FakeClock(1000.0)
        throttler = LoginThrottler(
            max_entries=3,
            free_attempts=0,
            base_delay=600.0,
            max_delay=600.0,
            clock=clock,
        )
        gesperrt = throttler.reserve("192.0.2.1")
        self.assertEqual(gesperrt.retry_after, 600)

        for i in range(2, 40):
            clock.advance(1.0)
            throttler.reserve(f"198.51.100.{i}")

        # max_entries plus genau ein Platz fuer den Ueberlauf-Eimer.
        self.assertLessEqual(throttler.entry_count(), 4)
        erneut = throttler.reserve("192.0.2.1")
        self.assertEqual(erneut.reservation_id, gesperrt.reservation_id)
        self.assertLess(erneut.retry_after, 600)
        self.assertGreater(erneut.retry_after, 0)

    def test_full_table_routes_newcomers_to_the_overflow_bucket(self) -> None:
        # Finding N1: Ist jeder Platz gesperrt, wird weder eine Sperre geopfert
        # noch der neue Absender pauschal abgewiesen. Er landet im gemeinsamen,
        # begrenzten Ueberlauf-Eimer und behaelt dessen freie Versuche.
        clock = FakeClock(1000.0)
        throttler = LoginThrottler(
            max_entries=2, free_attempts=0, base_delay=100.0, clock=clock
        )
        alt1 = throttler.reserve("192.0.2.1")
        clock.advance(10.0)
        alt2 = throttler.reserve("192.0.2.2")

        neu = throttler.reserve("192.0.2.3")
        self.assertEqual(neu.subject, OVERFLOW_SUBJECT)

        # Beide bestehenden Sperren leben unveraendert weiter.
        self.assertEqual(
            throttler.reserve("192.0.2.1").reservation_id, alt1.reservation_id
        )
        self.assertEqual(
            throttler.reserve("192.0.2.2").reservation_id, alt2.reservation_id
        )

    def test_overflow_bucket_grants_its_free_attempts(self) -> None:
        # Finding N1: Der Ueberlauf-Eimer sperrt unbekannte Absender nicht
        # sofort aus, sie bekommen die konfigurierten Freiversuche.
        clock = FakeClock(1000.0)
        throttler = LoginThrottler(
            max_entries=2, free_attempts=2, base_delay=100.0, clock=clock
        )
        for _ in range(3):
            throttler.reserve("192.0.2.1")
        for _ in range(3):
            throttler.reserve("192.0.2.2")

        erster = throttler.reserve("192.0.2.50")
        self.assertEqual(erster.subject, OVERFLOW_SUBJECT)
        self.assertEqual(erster.retry_after, 0)

    def test_unblocked_entry_is_evicted_before_any_block(self) -> None:
        # Finding 1, Mischfall: Bei vollem Speicher wird der ungesperrte
        # Eintrag geopfert, nicht die laufende Sperre.
        clock = FakeClock(1000.0)
        throttler = LoginThrottler(
            max_entries=2, free_attempts=1, base_delay=300.0, clock=clock
        )
        frei = throttler.reserve("192.0.2.20")
        self.assertEqual(frei.retry_after, 0)
        clock.advance(1.0)
        throttler.reserve("192.0.2.21")
        gesperrt = throttler.reserve("192.0.2.21")
        self.assertGreater(gesperrt.retry_after, 0)

        clock.advance(1.0)
        throttler.reserve("192.0.2.22")

        # Die Sperre lebt mit unveraenderter ID weiter.
        weiter = throttler.reserve("192.0.2.21")
        self.assertEqual(weiter.reservation_id, gesperrt.reservation_id)

    def test_success_during_active_block_does_not_reset_it(self) -> None:
        # Finding 2: Ein gueltiger Login darf die laufende Sperre der IP nicht
        # aufheben, sonst setzt ein bekanntes Konto die Drossel zurueck.
        clock = FakeClock(1000.0)
        throttler = LoginThrottler(free_attempts=2, base_delay=30.0, clock=clock)
        throttler.reserve("192.0.2.7")
        throttler.reserve("192.0.2.7")
        sperrend = throttler.reserve("192.0.2.7")
        self.assertGreater(sperrend.retry_after, 0)

        throttler.record_success(sperrend)
        self.assertEqual(throttler.entry_count(), 1)
        weiter = throttler.reserve("192.0.2.7")
        self.assertEqual(weiter.reservation_id, sperrend.reservation_id)
        self.assertGreater(weiter.retry_after, 0)

    def test_success_without_block_still_clears_the_entry(self) -> None:
        # Gegenprobe: Ohne laufende Sperre raeumt ein Erfolg wie bisher auf.
        clock = FakeClock(1000.0)
        throttler = LoginThrottler(free_attempts=2, base_delay=30.0, clock=clock)
        versuch = throttler.reserve("192.0.2.8")
        self.assertEqual(versuch.retry_after, 0)
        throttler.record_success(versuch)
        self.assertEqual(throttler.entry_count(), 0)

    def test_expiry_never_drops_an_active_block(self) -> None:
        # Finding 3: Ist history_window kleiner als die Sperrdauer, darf der
        # Verfall die laufende Sperre trotzdem nicht entfernen. Geprueft wird
        # die exakte Restzeit, damit ein Neuanlegen der Sperre auffaellt.
        clock = FakeClock(1000.0)
        throttler = LoginThrottler(
            free_attempts=0,
            base_delay=1200.0,
            max_delay=1200.0,
            history_window=10.0,
            clock=clock,
        )
        gesperrt = throttler.reserve("192.0.2.9")
        self.assertEqual(gesperrt.retry_after, 1200)

        clock.advance(11.0)
        erneut = throttler.reserve("192.0.2.9")
        self.assertEqual(erneut.reservation_id, gesperrt.reservation_id)
        self.assertEqual(erneut.retry_after, 1189)

    def test_blocked_hit_keeps_entry_at_the_end_of_the_order(self) -> None:
        # Finding N2 und die Ordnungsannahme: Ein geblockter Treffer frischt
        # last_attempt auf und wandert ans Ende, sonst haengt der Verfallslauf
        # bei jedem Aufruf an derselben Sperre fest.
        clock = FakeClock(1000.0)
        throttler = LoginThrottler(
            max_entries=4, free_attempts=0, base_delay=300.0, clock=clock
        )
        gesperrt = throttler.reserve("192.0.2.30")
        clock.advance(5.0)
        throttler.reserve("192.0.2.31")

        clock.advance(5.0)
        throttler.reserve("192.0.2.30")
        letzter = next(reversed(throttler._entries))
        self.assertEqual(letzter, "192.0.2.30")
        self.assertEqual(
            throttler._entries[letzter].reservation_id,
            gesperrt.reservation_id,
        )

    def test_scans_stay_bounded_when_table_is_full_of_blocks(self) -> None:
        # Finding N2: Der Verfalls- und der Verdraengungslauf sind begrenzt.
        clock = FakeClock(1000.0)
        throttler = LoginThrottler(
            max_entries=64,
            free_attempts=0,
            base_delay=600.0,
            max_delay=600.0,
            clock=clock,
        )
        for i in range(64):
            throttler.reserve(f"203.0.113.{i}")
        self.assertEqual(throttler.entry_count(), 64)

        for i in range(200):
            ergebnis = throttler.reserve(f"198.51.100.{i % 200}")
            self.assertGreater(ergebnis.retry_after, 0)
        # Der Speicher bleibt hart begrenzt: max_entries plus Ueberlauf-Eimer.
        self.assertLessEqual(throttler.entry_count(), 65)


if __name__ == "__main__":
    unittest.main()