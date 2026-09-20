"""Run Section 1 normalization and write the clean row-oriented dataset.

Usage:
    python -m scripts.normalize_cli            # uses repo default paths
    python -m scripts.normalize_cli --print    # also dump a quality summary
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

# Allow running as a script or a module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.normalize import load_and_normalize  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_P1 = os.path.join(REPO, "data", "songs_part1.json")
DEFAULT_P2 = os.path.join(REPO, "data", "songs_part2.json")
DEFAULT_OUT = os.path.join(HERE, "..", "app", "data", "songs.normalized.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part1", default=DEFAULT_P1)
    ap.add_argument("--part2", default=DEFAULT_P2)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--print", action="store_true", dest="show")
    args = ap.parse_args()

    rows = load_and_normalize(args.part1, args.part2)
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(rows)} normalized rows -> {out}")

    if args.show:
        # No flag column anymore: dropped/untrustworthy values are simply null.
        # Summarize how many nulls landed in each field so the effect is visible.
        fields = [k for k in rows[0] if k not in ("index", "id", "title")]
        nulls = Counter()
        for r in rows:
            for f in fields:
                if r.get(f) is None:
                    nulls[f] += 1
        print("\nNull (dropped/missing) values per field:")
        for f, n in sorted(nulls.items(), key=lambda kv: -kv[1]):
            print(f"  {n:2}  {f}")
        clean = sum(1 for r in rows if all(r.get(f) is not None for f in fields))
        print(f"\n{clean}/{len(rows)} rows have no null fields")


if __name__ == "__main__":
    main()
