"""Generate deterministic, illustrative daily forcing for the notebook."""

import csv
import math
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "educational_forcing.csv"
RAIN_EVENTS_MM = {
    1: 10.0,
    2: 5.0,
    12: 18.0,
    13: 6.0,
    21: 10.0,
    34: 24.0,
    35: 12.0,
    47: 7.0,
    60: 30.0,
    61: 8.0,
    77: 15.0,
    78: 10.0,
}


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(("date", "precipitation_mm", "mean_temp_c", "pet_mm"))
        start_day = date(2026, 3, 1)
        for day_index in range(90):
            mean_temp_c = (
                -2.0
                + 0.19 * day_index
                + 3.0 * math.sin(2 * math.pi * day_index / 14)
            )
            writer.writerow(
                (
                    (start_day + timedelta(days=day_index)).isoformat(),
                    f"{RAIN_EVENTS_MM.get(day_index, 0.0):.1f}",
                    f"{mean_temp_c:.2f}",
                    f"{max(0.0, 0.12 * (mean_temp_c + 3.0)):.2f}",
                )
            )

    print(f"Wrote 90 synthetic daily records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
