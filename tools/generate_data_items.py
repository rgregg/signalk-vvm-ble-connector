"""Generate vvm_to_signalk/data/smartcraft_data_items.json from docs/protocol-map.md §7."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "protocol-map.md"
OUT = ROOT / "vvm_to_signalk" / "data" / "smartcraft_data_items.json"

def parse_enum(cell: str):
    cell = cell.strip()
    if not (cell.startswith("{") and ":" in cell):
        return None, None
    inner = cell.strip("{}")
    # bits look like "0-1:Name" (start-length); enums look like "0:Name"
    is_bits = bool(re.match(r"\s*\d+\s*-\s*\d+\s*:", inner))
    if is_bits:
        return None, cell
    enum = {}
    for pair in inner.split(","):
        if ":" in pair:
            k, v = pair.split(":", 1)
            enum[k.strip()] = v.strip()
    return (enum or None), None

def main():
    rows = []
    in_table = False
    for line in DOC.read_text().splitlines():
        if line.startswith("| Id | Name |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            if set(line.replace("|", "").strip()) <= {"-"}:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 7 or cells[0] == "Id":
                continue
            enum, bits = parse_enum(cells[5])
            rows.append({
                "id": int(cells[0]),
                "name": cells[1],
                "type": cells[2],
                "gain": float(cells[3]) if cells[3] not in ("-", "") else 1.0,
                "units": cells[4],
                "enum": enum,
                "bits": bits,
                "access": cells[6],
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"wrote {len(rows)} items to {OUT}")

if __name__ == "__main__":
    sys.exit(main())
