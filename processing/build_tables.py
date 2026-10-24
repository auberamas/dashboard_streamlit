"""Run once after the cleaning: reads the big csv and saves the tables used by the dashboard.

    python -m processing.build_tables

Only needed when data/effectifs_clean.csv changes without running cleaning_analysis/clean.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.tables import build_tables  # noqa: E402
from utils.config import TABLES_PATH  # noqa: E402

if __name__ == "__main__":
    tables = build_tables()
    size_mb = Path(TABLES_PATH).stat().st_size / 1e6
    print(f"{TABLES_PATH} written ({size_mb:.1f} MB)")
    for name, value in tables.items():
        shape = getattr(value, "shape", None)
        print(f"  {name:<12} {shape if shape is not None else type(value).__name__}")
