"""Decode VVM Fault Alert (0x201) indications. See docs/protocol-map.md §3."""
import logging

logger = logging.getLogger(__name__)

_FAULT_TYPES = {0: "Unknown", 1: "Universal", 2: "Legacy"}


class Fault:
    """A decoded engine fault event."""

    def __init__(self, fault_type, engine_position, is_active, fault_id,
                 failure_type_id=None, severity=None, action_id=None):
        self.fault_type = fault_type
        self.engine_position = engine_position
        self.is_active = is_active
        self.fault_id = fault_id
        self.failure_type_id = failure_type_id
        self.severity = severity
        self.action_id = action_id

    def __str__(self):
        return (f"Fault(type={self.fault_type}, engine={self.engine_position}, "
                f"active={self.is_active}, key={self.fault_key})")

    @property
    def fault_key(self) -> str:
        if self.fault_type == "Universal":
            return f"{self.fault_id}-{self.failure_type_id}"
        return f"{self.fault_id}-Legacy"


def _common_header(data: bytes):
    fault_type = _FAULT_TYPES.get(data[0] & 0x0F, "Unknown")
    engine_position = data[0] >> 4
    is_active = bool(data[1] & 0x01)
    return fault_type, engine_position, is_active


def parse_fault(data: bytes) -> Fault | None:
    """Parse a Fault Alert payload (4 bytes = Legacy, 9 bytes = Universal)."""
    if data is None:
        return None
    if len(data) == 4:
        fault_type, engine, active = _common_header(data)
        fault_id = int.from_bytes(data[2:4], byteorder="little")
        return Fault(fault_type, engine, active, fault_id)
    if len(data) == 9:
        fault_type, engine, active = _common_header(data)
        body = data[2:9].ljust(8, b"\x00")
        num = int.from_bytes(body, byteorder="little")
        severity = num & 0x7
        action_id = (num & 0xFF8) >> 3
        # long_id = (num & 0x7FF000) >> 12  # not currently published
        # short_id = (num & 0x7FF800000) >> 23
        failure_type_id = (num & 0x3F800000000) >> 35
        fault_id = (num & 0xFFFC0000000000) >> 42
        return Fault(fault_type, engine, active, fault_id,
                     failure_type_id=failure_type_id, severity=severity, action_id=action_id)
    logger.warning("Unexpected fault payload length %s: %s", len(data), data.hex())
    return None
