"""One-off backfill for memories saved before the `category` field existed.

`category` is now a required, closed-vocabulary field on every `remember`
call (see tools.CATEGORIES) - the broad grand-topic a memory's `topic`
belongs under (e.g. "Gear" -> "Mechanics"), one level above topic itself.
New scans set it automatically. This script retroactively categorizes old
data by matching its `topic` against the known topics from past Wikipedia
scans (see the queue example in README.md), so it groups into the same
category-globe clusters new data produces automatically.

Run once after pulling the category-field change, from the project root:

    python scripts/backfill_categories.py

Safe to run more than once - it only touches memories where category is
still empty, and only for topics listed in TOPIC_TO_CATEGORY below.
Anything else (a topic not listed here, or already categorized) is left
alone - it just stays uncategorized and orbits the main globe directly,
same as before this field existed. Add more entries here as needed, or set
a category by hand for one-off cases.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db  # noqa: E402

TOPIC_TO_CATEGORY = {
    "Classical mechanics": "Mechanics",
    "Newton's laws of motion": "Mechanics",
    "Mechanical engineering": "Mechanics",
    "Simple machine": "Mechanics",
    "Kinematics": "Mechanics",
    "Thermodynamics": "Mechanics",
    "Fluid mechanics": "Mechanics",
    "Gear": "Mechanics",
    "Algorithm": "Coding",
    "Data structure": "Coding",
    "Object-oriented programming": "Coding",
    "Version control": "Coding",
    "Compiler": "Coding",
    "Software design pattern": "Coding",
    "Machine learning": "Coding",
}


def main() -> None:
    db.init_db()
    updated = 0
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, topic FROM memories WHERE category = '' OR category IS NULL"
        ).fetchall()
        for row in rows:
            category = TOPIC_TO_CATEGORY.get(row["topic"])
            if category:
                conn.execute("UPDATE memories SET category = ? WHERE id = ?", (category, row["id"]))
                updated += 1

    print(f"Backfilled category on {updated} memories.")
    print(
        "Anything left uncategorized wasn't in TOPIC_TO_CATEGORY - add it there and "
        "re-run, or set a category by hand, to pull it into a category globe."
    )


if __name__ == "__main__":
    main()
