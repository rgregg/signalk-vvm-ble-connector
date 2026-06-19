"""SmartCraft data dictionary: decode VVM notifications into engineering values."""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).resolve().parent / "data" / "smartcraft_data_items.json"

# type name -> (byte width, signed)
_TYPE_SIZES = {
    "uint1": (1, False), "uint2": (2, False), "uint3": (3, False),
    "uint4": (4, False), "uint8": (8, False),
    "sint1": (1, True), "sint2": (2, True), "sint3": (3, True),
    "sint4": (4, True), "sint8": (8, True),
    "boolean": (1, False), "Flag": (1, False), "8bit": (1, False),
    "16bit": (2, False), "string": (0, False), "null": (0, False),
}


class DataItemType:
    """Helpers for the SmartCraft type strings."""

    @staticmethod
    def size(type_str: str) -> int:
        return _TYPE_SIZES.get(type_str, (0, False))[0]

    @staticmethod
    def signed(type_str: str) -> bool:
        return _TYPE_SIZES.get(type_str, (0, False))[1]


class DataItem:
    """A single SmartCraft data item and how to decode its value(s)."""

    def __init__(self, record: dict):
        self.id = record["id"]
        self.name = record["name"]
        self.type = record["type"]
        self.gain = record.get("gain", 1.0)
        self.units = record.get("units", "")
        self.access = record.get("access", "")
        self.enum = record.get("enum")
        self.bits = record.get("bits")

    def __str__(self):
        return f"DataItem(id={self.id}, name={self.name!r}, type={self.type}, units={self.units})"

    @property
    def value_size(self) -> int:
        return DataItemType.size(self.type)

    @property
    def signed(self) -> bool:
        return DataItemType.signed(self.type)

    @property
    def is_vessel(self) -> bool:
        return self.access.endswith("Vessel")

    def decode_values(self, payload: bytes, max_engines: int = 4) -> list[float]:
        """Decode the per-engine values that follow the 2-byte ID.

        Vessel items carry a single value; engine items carry one value per engine
        (the device sends a slot for every engine up to max_engines). Each value is
        little-endian, signed per type, then multiplied by gain.
        """
        size = self.value_size
        if size == 0:
            return []
        count = 1 if self.is_vessel else min(max_engines, len(payload) // size)
        values = []
        for i in range(count):
            chunk = payload[i * size:(i + 1) * size]
            if len(chunk) < size:
                break
            raw = int.from_bytes(chunk, byteorder="little", signed=self.signed)
            values.append(raw * self.gain)
        return values


class DataDictionary:
    """Lookup table of DataItem by ID, loaded from the bundled JSON."""

    def __init__(self, items: dict[int, DataItem]):
        self._items = items

    @classmethod
    def load(cls, path: Path = _DATA_FILE) -> "DataDictionary":
        records = json.loads(Path(path).read_text())
        return cls({r["id"]: DataItem(r) for r in records})

    def by_id(self, item_id: int) -> DataItem | None:
        return self._items.get(item_id)


def decode_notification(data: bytes, dictionary: DataDictionary,
                        max_engines: int = 4) -> tuple[DataItem | None, list[float]]:
    """Decode a channel notification into (DataItem, per-engine values)."""
    if data is None or len(data) < 2:
        return None, []
    item_id = int.from_bytes(data[:2], byteorder="little")
    item = dictionary.by_id(item_id)
    if item is None:
        logger.debug("Unknown data-item ID %s in notification %s", item_id, data.hex())
        return None, []
    return item, item.decode_values(data[2:], max_engines)
