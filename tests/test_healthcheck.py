"""Tests for the healthcheck evaluation logic"""

import os
import tempfile
import unittest
import warnings
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from vvm_to_signalk.healthcheck import format_heartbeat, is_healthy, main


class TestHealthcheck(unittest.TestCase):
    """Test the is_healthy evaluation used by the Docker HEALTHCHECK"""

    def test_ok_and_fresh_is_healthy(self):
        """A recent OK heartbeat is healthy"""
        now = datetime(2026, 6, 19, 12, 0, 0)
        content = f"OK {now.isoformat()}\n"
        self.assertTrue(is_healthy(content, now=now, max_age_seconds=60))

    def test_ok_but_stale_is_unhealthy(self):
        """An OK heartbeat older than max_age is unhealthy (loop stalled/hung)"""
        now = datetime(2026, 6, 19, 12, 0, 0)
        written = now - timedelta(seconds=120)
        content = f"OK {written.isoformat()}\n"
        self.assertFalse(is_healthy(content, now=now, max_age_seconds=60))

    def test_device_absent_but_signalk_connected_is_healthy(self):
        """Scanning with no device found, SignalK connected, stays healthy"""
        now = datetime(2026, 6, 19, 12, 0, 0)
        content = f"OK {now.isoformat()}\n"
        self.assertTrue(is_healthy(content, now=now, max_age_seconds=60))

    def test_signalk_disconnected_is_unhealthy(self):
        """A BAD heartbeat (SignalK disconnected) is unhealthy even when fresh"""
        now = datetime(2026, 6, 19, 12, 0, 0)
        content = f"BAD SignalK Disconnected {now.isoformat()}\n"
        self.assertFalse(is_healthy(content, now=now, max_age_seconds=60))

    def test_empty_content_is_unhealthy(self):
        """Missing/empty heartbeat content is unhealthy"""
        now = datetime(2026, 6, 19, 12, 0, 0)
        self.assertFalse(is_healthy("", now=now, max_age_seconds=60))

    def test_malformed_content_is_unhealthy(self):
        """Unparseable heartbeat content is unhealthy"""
        now = datetime(2026, 6, 19, 12, 0, 0)
        self.assertFalse(is_healthy("garbage data", now=now, max_age_seconds=60))


class TestHeartbeatRoundTrip(unittest.TestCase):
    """The writer and checker must agree on the heartbeat format"""

    def test_ok_heartbeat_round_trips_to_healthy(self):
        """A heartbeat the writer produces for a connected state reads as healthy"""
        now = datetime(2026, 6, 19, 12, 0, 0)
        content = format_heartbeat(signalk_ok=True, now=now)
        self.assertTrue(is_healthy(content, now=now, max_age_seconds=60))

    def test_bad_heartbeat_round_trips_to_unhealthy(self):
        """A heartbeat the writer produces for a disconnected state reads as unhealthy"""
        now = datetime(2026, 6, 19, 12, 0, 0)
        content = format_heartbeat(signalk_ok=False, now=now)
        self.assertFalse(is_healthy(content, now=now, max_age_seconds=60))


class TestHealthcheckMain(unittest.TestCase):
    """Test the CLI entry point used by the Docker HEALTHCHECK"""

    def test_main_exits_zero_for_fresh_ok_file(self):
        """main() returns 0 when the heartbeat file is fresh and OK"""
        with tempfile.NamedTemporaryFile("w", suffix=".hc", delete=False) as f:
            f.write(format_heartbeat(signalk_ok=True, now=datetime.now(timezone.utc)))
            path = f.name
        try:
            with patch.dict(os.environ, {"APP_HEALTHCHECK_FILE": path}):
                self.assertEqual(main(), 0)
        finally:
            os.unlink(path)

    def test_main_exits_one_for_bad_file(self):
        """main() returns 1 when the heartbeat reports a fault"""
        with tempfile.NamedTemporaryFile("w", suffix=".hc", delete=False) as f:
            f.write(format_heartbeat(signalk_ok=False, now=datetime.now(timezone.utc)))
            path = f.name
        try:
            with patch.dict(os.environ, {"APP_HEALTHCHECK_FILE": path}):
                self.assertEqual(main(), 1)
        finally:
            os.unlink(path)

    def test_main_exits_one_for_missing_file(self):
        """main() returns 1 when the heartbeat file does not exist"""
        with patch.dict(os.environ, {"APP_HEALTHCHECK_FILE": "/nonexistent/hc_xyz"}):
            self.assertEqual(main(), 1)

    def test_main_does_not_use_deprecated_utcnow(self):
        """main() must not rely on the deprecated datetime.utcnow()."""
        with tempfile.NamedTemporaryFile("w", suffix=".hc", delete=False) as f:
            f.write(format_heartbeat(signalk_ok=True, now=datetime.now(timezone.utc)))
            path = f.name
        try:
            with patch.dict(os.environ, {"APP_HEALTHCHECK_FILE": path}):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    main()
            deprecations = [
                w for w in caught
                if issubclass(w.category, DeprecationWarning) and "utcnow" in str(w.message)
            ]
            self.assertEqual(deprecations, [])
        finally:
            os.unlink(path)


class TestTimezoneAwareHeartbeat(unittest.TestCase):
    """The healthcheck must work with timezone-aware timestamps"""

    def test_aware_ok_heartbeat_round_trips_to_healthy(self):
        """A timezone-aware OK heartbeat reads as healthy"""
        now = datetime(2026, 6, 19, 12, 0, 0, tzinfo=timezone.utc)
        content = format_heartbeat(signalk_ok=True, now=now)
        self.assertTrue(is_healthy(content, now=now, max_age_seconds=60))

    def test_naive_file_with_aware_now_does_not_crash(self):
        """A legacy naive heartbeat file evaluated against an aware now (the
        upgrade-transition case) must not raise and must read as healthy."""
        written = datetime(2026, 6, 19, 12, 0, 0)  # naive, legacy format
        now = datetime(2026, 6, 19, 12, 0, 0, tzinfo=timezone.utc)
        content = f"OK {written.isoformat()}\n"
        self.assertTrue(is_healthy(content, now=now, max_age_seconds=60))


if __name__ == "__main__":
    unittest.main()
