"""Check or intentionally update the persisted-contract compatibility snapshot."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from photonic_workflow.maintenance import contract_surface_snapshot  # noqa: E402
from photonic_workflow.models.io import atomic_write_text  # noqa: E402


def rendered_snapshot() -> str:
    return (
        json.dumps(
            contract_surface_snapshot(),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update",
        action="store_true",
        help="Write an intentional new snapshot instead of checking it.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "tests"
            / "fixtures"
            / "contract_surface_v1.json"
        ),
    )
    args = parser.parse_args()
    actual = rendered_snapshot()
    if args.update:
        atomic_write_text(args.snapshot, actual)
        print(f"Updated {args.snapshot}")
        return 0
    try:
        expected = args.snapshot.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Missing compatibility snapshot: {args.snapshot}")
        return 1
    if expected == actual:
        print("Contract compatibility snapshot verified.")
        return 0
    print(
        "".join(
            difflib.unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile=str(args.snapshot),
                tofile="current contract surface",
            )
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
