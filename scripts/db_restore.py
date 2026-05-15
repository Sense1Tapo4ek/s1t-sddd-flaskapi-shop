#!/usr/bin/env python3
"""Restore a gzipped (or plain) mysqldump file into the configured database.

Usage:
    python scripts/db_restore.py data/dumps/shop-20260515-030000.sql.gz

WARNING: drops and recreates objects defined in the dump. Make a fresh
dump first if you need a rollback path.
"""

from __future__ import annotations

import gzip
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import get_database_url, parse_url


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    src = Path(sys.argv[1]).resolve()
    if not src.is_file():
        print(f"Not a file: {src}", file=sys.stderr)
        return 2

    creds = parse_url(get_database_url())
    print(
        f"Restoring {src.name} into {creds['database']}@{creds['host']}. "
        "Existing data WILL be overwritten."
    )

    cmd = [
        "mysql",
        f"--host={creds['host']}",
        f"--port={creds['port']}",
        f"--user={creds['user']}",
        f"--password={creds['password']}",
        "--default-character-set=utf8mb4",
        creds["database"],
    ]
    opener = gzip.open if src.suffix == ".gz" else open
    with opener(src, "rb") as fh:
        proc = subprocess.run(cmd, stdin=fh, check=False)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
