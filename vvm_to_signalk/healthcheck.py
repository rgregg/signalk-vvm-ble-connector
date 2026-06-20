"""Healthcheck evaluation for the Docker HEALTHCHECK.

The application writes a heartbeat line to a file on each loop iteration in the
form ``OK <iso-timestamp>`` (or ``BAD <reason> <iso-timestamp>``). The container
is healthy only when the most recent heartbeat reports ``OK`` and is recent
enough to prove the loop is still alive. A device that is simply absent (engine
off / out of range) keeps reporting ``OK`` while SignalK is connected, so it
stays healthy.
"""

import os
import sys
from datetime import datetime, timezone

DEFAULT_HEALTHCHECK_FILE = "/tmp/healthcheck"
DEFAULT_MAX_AGE_SECONDS = 60


def format_heartbeat(signalk_ok: bool, now: datetime) -> str:
    """Produce a heartbeat line for the given state.

    This is the single source of truth for the heartbeat format shared by the
    writer (``write_healthcheck``) and the checker (``is_healthy``) so the two
    cannot drift apart.
    """
    if signalk_ok:
        return f"OK {now.isoformat()}\n"
    return f"BAD SignalK Disconnected {now.isoformat()}\n"


def is_healthy(content: str, now: datetime, max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS) -> bool:
    """Return True when the heartbeat content reports OK and is fresh.

    ``content`` is the raw heartbeat file content. ``now`` is the current time;
    naive values are treated as UTC. Heartbeats written by older versions used a
    naive UTC timestamp, so both sides are normalised to timezone-aware UTC
    before comparison to stay compatible across an upgrade.
    """
    line = content.strip()
    if not line:
        return False

    tokens = line.split()
    if len(tokens) < 2:
        return False

    status = tokens[0]
    if status != "OK":
        return False

    try:
        written = datetime.fromisoformat(tokens[-1])
    except ValueError:
        return False

    now = _as_utc(now)
    written = _as_utc(written)

    age = (now - written).total_seconds()
    return 0 <= age <= max_age_seconds


def _as_utc(value: datetime) -> datetime:
    """Treat a naive datetime as UTC; leave aware datetimes unchanged."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def main() -> int:
    """Read the heartbeat file and exit 0 (healthy) or 1 (unhealthy)."""
    path = os.getenv("APP_HEALTHCHECK_FILE", DEFAULT_HEALTHCHECK_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return 1

    return 0 if is_healthy(content, now=datetime.now(timezone.utc)) else 1


if __name__ == "__main__":
    sys.exit(main())
