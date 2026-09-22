"""One-off backfill for memories saved before the `topic` field existed.

Every Wikipedia scan has always tagged facts as
["wikipedia", "<the topic>", ...extra keywords]. This script reads that old
convention back out of `tags` and fills in `topic` for any memory that
doesn't have one yet, so old data groups into the same one-globe-per-topic
clusters that new scans produce automatically.

Run once after pulling the topic-field fix, from the project root:

    python scripts/backfill_topics.py

Safe to run more than once - it only touches memories where topic is still
empty, and does nothing to memories that don't match the old
["wikipedia", "<topic>", ...] tag shape (those are left alone; add a topic
for them by hand via POST /memory or leave them unclustered).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db  # noqa: E402


def main() -> None:
    db.init_db()
    updated = 0
    skipped = 0
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, tags FROM memories WHERE topic = '' OR topic IS NULL"
        ).fetchall()
        for row in rows:
            tags = [t for t in row["tags"].split(",") if t]
            if len(tags) >= 2 and tags[0] == "wikipedia":
                conn.execute("UPDATE memories SET topic = ? WHERE id = ?", (tags[1], row["id"]))
                updated += 1
            else:
                skipped += 1

    print(f"Backfilled topic on {updated} memories.")
    print(f"Left {skipped} memories untouched (didn't match the old wikipedia-scan tag shape).")


if __name__ == "__main__":
    main()
