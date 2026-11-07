"""Build tests/fixtures/rahma_punches.csv from docs/rahma.txt.

docs/rahma.txt holds psql output where `system_day`/`system_time` are the stored
punch_time values rendered in the DB server time zone (Asia/Shanghai, +08).
The CSV keeps those raw +08 timestamps so the tests exercise the conversion.
"""
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "rahma.txt"
DST = ROOT / "tests" / "fixtures" / "rahma_punches.csv"
ROW = re.compile(r"^\s*(\d{4}-\d{2}-\d{2}) \w{3} \| (\d{2}:\d{2} [AP]M)\s*\|")


def main() -> int:
    rows = []
    for line in SRC.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if not m:
            continue
        stamp = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %I:%M %p")
        rows.append(stamp.strftime("%Y-%m-%dT%H:%M:00+08:00"))
    with DST.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["emp_code", "punch_time"])
        for value in rows:
            writer.writerow(["302", value])
    print(f"{len(rows)} punches written to {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
