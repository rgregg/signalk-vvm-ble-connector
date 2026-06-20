from vvm_to_signalk.config_decoder import ConfigDecoder

# Reassembled config response. Layout matches ConfigDecoder.parse_params:
#   byte0 = 0x28; byte1 = payload length (1 byte); byte2 = 0x00;
#   bytes3.. = payload = magic(2) + 4-byte (slot, id) pairs; id is little-endian.
# 6 pairs (24B) + magic (2B) = 26B payload -> length byte = 0x1a.
# Pairs (LE id): slot0->1(RPM) slot1->210 slot2->232 slot3->6000 slot4->150 slot5->10
RAW = bytes.fromhex(
    "28" "1a" "00"   # header: marker, length=26, spacer
    "0100"           # magic (discarded)
    "0000" "0100"    # slot 0 -> id 0x0001 = 1
    "0100" "d200"    # slot 1 -> id 0x00d2 = 210
    "0200" "e800"    # slot 2 -> id 0x00e8 = 232
    "0300" "7017"    # slot 3 -> id 0x1770 = 6000
    "0400" "9600"    # slot 4 -> id 0x0096 = 150
    "0500" "0a00"    # slot 5 -> id 0x000a = 10
)

def _packetize(raw: bytes) -> list[bytes]:
    # Re-create the indication chunks: each prefixed with a sequence byte,
    # as ConfigDecoder.combine_and_parse_data expects (sorts by, then strips, byte 0).
    chunks = [raw[i:i + 19] for i in range(0, len(raw), 19)]
    return [bytes([i]) + c for i, c in enumerate(chunks)]

def test_active_ids_parsed_little_endian():
    dec = ConfigDecoder()
    dec.add(_packetize(RAW))
    assert dec.has_all_data
    assert dec.active_data_item_ids() == [1, 210, 232, 6000, 150, 10]


def test_zero_id_slots_dropped():
    # Unused slots carry id 0 (e.g. inactive engine placeholders) and must be dropped.
    # payload = magic(2) + 3 pairs(12) = 14 bytes -> length byte 0x0e.
    raw = bytes.fromhex(
        "28" "0e" "00"   # header: marker, length=14, spacer
        "0100"           # magic (discarded)
        "0000" "0100"    # slot 0 -> id 1
        "0100" "0000"    # slot 1 -> id 0 (dropped)
        "0200" "e800"    # slot 2 -> id 232
    )
    dec = ConfigDecoder()
    dec.add(_packetize(raw))
    assert dec.has_all_data
    assert dec.active_data_item_ids() == [1, 232]
