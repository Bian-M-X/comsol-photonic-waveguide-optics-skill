from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Keep direct script loading compatible with an uninstalled source checkout.
SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from photonic_workflow.adapters.comsol.recipes import (  # noqa: E402
    CIRCULAR_BEND_JAVA_HELPER,
)
from photonic_workflow.recipes.geometry import (  # noqa: E402
    compute_circular_bend,
    compute_circular_route,
)

HELPER = CIRCULAR_BEND_JAVA_HELPER

__all__ = ["HELPER", "compute_circular_bend", "compute_circular_route"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Emit a COMSOL Java helper skeleton for analytic annular-sector bends."
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        parser.error(
            "--output is retired because it did not enforce project-root or no-overwrite "
            "policy; use 'photonic recipe render' with --project-root instead"
        )
    else:
        print(HELPER)


if __name__ == "__main__":
    main()
