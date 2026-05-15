#!/usr/bin/env python3
"""Seed demo data via the catalog facade. Idempotent.

Invoked from Dockerfile CMD and from `scripts/bootstrap_cpanel.sh`.
The use case keys off stable slugs/titles, so re-runs do not create
duplicates.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PYTHONPATH", str(ROOT / "src"))


def main() -> int:
    from root.container import build_container
    from catalog.ports.driving.facade import CatalogFacade

    container = build_container()
    facade = container.get(CatalogFacade)
    result = facade.create_demo_data()
    print(f"Seed OK: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
