#!/usr/bin/env python3
"""Create a gzipped mysqldump under data/dumps/<timestamp>.sql.gz.

Usage:
    python scripts/db_dump.py [--keep N]

  --keep N   Retain only the N most recent dumps (default: 14).

On CPanel schedule this from "Cron Jobs":
    0 3 * * * cd ~/app && /home/USER/virtualenv/app/3.11/bin/python scripts/db_dump.py
"""

from __future__ import annotations

import argparse
import gzip
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import ensure_dumps_dir, get_database_url, parse_url


MYSQLDUMP_CANDIDATES = (
    "mysqldump",
    "/usr/bin/mysqldump",
    "/usr/local/bin/mysqldump",
    "/usr/local/mysql/bin/mysqldump",
)


def _find_mysqldump() -> str:
    for candidate in MYSQLDUMP_CANDIDATES:
        path = shutil.which(candidate) or (
            candidate if Path(candidate).is_file() else None
        )
        if path:
            return path
    print(
        "mysqldump binary not found. Set PATH or install mysql-client.",
        file=sys.stderr,
    )
    sys.exit(2)


def _prune(directory: Path, keep: int) -> None:
    dumps = sorted(directory.glob("*.sql.gz"), key=lambda p: p.stat().st_mtime)
    for stale in dumps[:-keep] if keep > 0 else []:
        stale.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=int, default=14)
    args = parser.parse_args()

    creds = parse_url(get_database_url())
    target_dir = ensure_dumps_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"shop-{timestamp}.sql.gz"

    mysqldump = _find_mysqldump()
    cmd = [
        mysqldump,
        f"--host={creds['host']}",
        f"--port={creds['port']}",
        f"--user={creds['user']}",
        f"--password={creds['password']}",
        "--single-transaction",
        "--quick",
        "--default-character-set=utf8mb4",
        "--no-tablespaces",
        creds["database"],
    ]

    print(f"Dumping {creds['database']}@{creds['host']} -> {target}")
    with gzip.open(target, "wb") as gz:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdout is not None
        for chunk in iter(lambda: proc.stdout.read(65536), b""):
            gz.write(chunk)
        _, err = proc.communicate()

    if proc.returncode != 0:
        target.unlink(missing_ok=True)
        sys.stderr.write(err.decode("utf-8", errors="replace"))
        return proc.returncode

    _prune(target_dir, args.keep)
    print(f"OK: {target.relative_to(Path.cwd())} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
