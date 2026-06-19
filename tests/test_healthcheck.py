"""Tests for the healthcheck evaluation logic"""

import unittest
from datetime import datetime, timedelta

from vvm_to_signalk.healthcheck import is_healthy


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


if __name__ == "__main__":
    unittest.main()
