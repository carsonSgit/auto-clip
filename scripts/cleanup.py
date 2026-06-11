"""Reclaim disk space from finished jobs.

Removes upload originals and stray work dirs for jobs that completed or failed
more than --keep-days ago. Final outputs are kept unless --outputs is passed.

    docker compose run --rm web python scripts/cleanup.py                 # dry run
    docker compose run --rm web python scripts/cleanup.py --apply
    docker compose run --rm web python scripts/cleanup.py --apply --keep-days 7 --outputs
"""

import argparse
import shutil
from datetime import datetime, timedelta, timezone

from autoclip.config import settings
from autoclip.db import SessionLocal, init_db
from autoclip.models import Job


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-days", type=int, default=14)
    parser.add_argument("--outputs", action="store_true", help="also delete final outputs")
    parser.add_argument("--apply", action="store_true", help="actually delete (default: dry run)")
    args = parser.parse_args()

    init_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.keep_days)
    with SessionLocal() as session:
        jobs = (
            session.query(Job)
            .filter(Job.status.in_(["complete", "failed"]), Job.updated_at < cutoff)
            .all()
        )
        known_ids = {j.id for j in session.query(Job).all()}

    targets = []
    for job in jobs:
        targets.append(settings.uploads_dir / job.id)
        targets.append(settings.work_dir / job.id)
        if args.outputs:
            targets.append(settings.output_dir / job.id)

    # Orphaned dirs with no DB row (e.g. from wiped databases)
    for root in (settings.uploads_dir, settings.work_dir):
        if root.is_dir():
            targets.extend(p for p in root.iterdir() if p.is_dir() and p.name not in known_ids)

    freed = 0
    for path in targets:
        if not path.is_dir():
            continue
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        freed += size
        print(f"{'DELETE' if args.apply else 'would delete'} {path}  ({size / 1e6:.0f} MB)")
        if args.apply:
            shutil.rmtree(path, ignore_errors=True)

    print(f"{'Freed' if args.apply else 'Would free'} {freed / 1e9:.2f} GB "
          f"({len(jobs)} finished jobs older than {args.keep_days}d)")


if __name__ == "__main__":
    main()
