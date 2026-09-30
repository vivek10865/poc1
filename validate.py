"""POC-001: integration / validation script.

Run after seed.py:
    python validate.py            # validate + export CSV/JSON to ./export
    python validate.py --no-export

1. Checks acceptance criteria (>=500 athletes, >=30 events) and referential integrity.
2. Checks business rules (unique bibs, split sums, contiguous ranks, ...).
3. Prints a content fingerprint per table so repeatability can be confirmed (run seed twice, compare).
4. Exports every table as CSV + JSON for downstream components / agent testing.
Exit code is 1 if any check fails.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from seed import DATABASE, SCHEMA, WAREHOUSE, LOAD_ORDER, REFERENCE_DATE, connect

# (name, SQL returning one number, predicate on that number)
CHECKS = [
    ("Athletes >= 500", "SELECT COUNT(*) FROM ATHLETES", lambda v: v >= 500),
    ("Events >= 30", "SELECT COUNT(*) FROM EVENTS", lambda v: v >= 30),
    ("Locations populated", "SELECT COUNT(*) FROM LOCATIONS", lambda v: v > 0),
    ("Races populated", "SELECT COUNT(*) FROM RACES", lambda v: v > 0),
    ("Registrations populated", "SELECT COUNT(*) FROM REGISTRATIONS", lambda v: v > 0),
    ("Results populated", "SELECT COUNT(*) FROM RESULTS", lambda v: v > 0),

    ("FK orphans: EVENTS.LOCATION_ID",
     "SELECT COUNT(*) FROM EVENTS e LEFT JOIN LOCATIONS l ON e.LOCATION_ID = l.LOCATION_ID "
     "WHERE l.LOCATION_ID IS NULL", lambda v: v == 0),
    ("FK orphans: RACES.EVENT_ID",
     "SELECT COUNT(*) FROM RACES r LEFT JOIN EVENTS e ON r.EVENT_ID = e.EVENT_ID "
     "WHERE e.EVENT_ID IS NULL", lambda v: v == 0),
    ("FK orphans: REGISTRATIONS.ATHLETE_ID",
     "SELECT COUNT(*) FROM REGISTRATIONS g LEFT JOIN ATHLETES a ON g.ATHLETE_ID = a.ATHLETE_ID "
     "WHERE a.ATHLETE_ID IS NULL", lambda v: v == 0),
    ("FK orphans: REGISTRATIONS.RACE_ID",
     "SELECT COUNT(*) FROM REGISTRATIONS g LEFT JOIN RACES r ON g.RACE_ID = r.RACE_ID "
     "WHERE r.RACE_ID IS NULL", lambda v: v == 0),
    ("FK orphans: RESULTS.REGISTRATION_ID",
     "SELECT COUNT(*) FROM RESULTS s LEFT JOIN REGISTRATIONS g ON s.REGISTRATION_ID = g.REGISTRATION_ID "
     "WHERE g.REGISTRATION_ID IS NULL", lambda v: v == 0),

    ("Duplicate PKs (all tables)",
     "SELECT (SELECT COUNT(*) - COUNT(DISTINCT LOCATION_ID) FROM LOCATIONS) "
     "+ (SELECT COUNT(*) - COUNT(DISTINCT ATHLETE_ID) FROM ATHLETES) "
     "+ (SELECT COUNT(*) - COUNT(DISTINCT EVENT_ID) FROM EVENTS) "
     "+ (SELECT COUNT(*) - COUNT(DISTINCT RACE_ID) FROM RACES) "
     "+ (SELECT COUNT(*) - COUNT(DISTINCT REGISTRATION_ID) FROM REGISTRATIONS) "
     "+ (SELECT COUNT(*) - COUNT(DISTINCT RESULT_ID) FROM RESULTS)", lambda v: v == 0),
    ("Duplicate registrations (athlete + race)",
     "SELECT COUNT(*) FROM (SELECT ATHLETE_ID, RACE_ID FROM REGISTRATIONS "
     "GROUP BY 1, 2 HAVING COUNT(*) > 1)", lambda v: v == 0),
    ("Duplicate bib numbers within a race",
     "SELECT COUNT(*) FROM (SELECT RACE_ID, BIB_NUMBER FROM REGISTRATIONS "
     "WHERE BIB_NUMBER IS NOT NULL GROUP BY 1, 2 HAVING COUNT(*) > 1)", lambda v: v == 0),
    ("Registered on/before event date",
     "SELECT COUNT(*) FROM REGISTRATIONS g JOIN RACES r ON g.RACE_ID = r.RACE_ID "
     "JOIN EVENTS e ON r.EVENT_ID = e.EVENT_ID WHERE g.REGISTRATION_DATE > e.EVENT_DATE",
     lambda v: v == 0),
    ("Results only for CONFIRMED registrations",
     "SELECT COUNT(*) FROM RESULTS s JOIN REGISTRATIONS g ON s.REGISTRATION_ID = g.REGISTRATION_ID "
     "WHERE g.STATUS <> 'CONFIRMED'", lambda v: v == 0),
    ("Results only for completed events",
     "SELECT COUNT(*) FROM RESULTS s JOIN REGISTRATIONS g ON s.REGISTRATION_ID = g.REGISTRATION_ID "
     "JOIN RACES r ON g.RACE_ID = r.RACE_ID JOIN EVENTS e ON r.EVENT_ID = e.EVENT_ID "
     f"WHERE e.EVENT_DATE >= '{REFERENCE_DATE}'", lambda v: v == 0),
    ("FINISHED total = sum of splits",
     "SELECT COUNT(*) FROM RESULTS WHERE RESULT_STATUS = 'FINISHED' AND TOTAL_SECONDS <> "
     "SWIM_SECONDS + T1_SECONDS + BIKE_SECONDS + T2_SECONDS + RUN_SECONDS", lambda v: v == 0),
    ("FINISHED rows have times and ranks",
     "SELECT COUNT(*) FROM RESULTS WHERE RESULT_STATUS = 'FINISHED' AND "
     "(TOTAL_SECONDS IS NULL OR OVERALL_RANK IS NULL OR GENDER_RANK IS NULL)", lambda v: v == 0),
    ("Non-finishers have no total/rank",
     "SELECT COUNT(*) FROM RESULTS WHERE RESULT_STATUS <> 'FINISHED' AND "
     "(TOTAL_SECONDS IS NOT NULL OR OVERALL_RANK IS NOT NULL)", lambda v: v == 0),
    ("Overall ranks contiguous per race",
     "SELECT COUNT(*) FROM (SELECT g.RACE_ID FROM RESULTS s JOIN REGISTRATIONS g "
     "ON s.REGISTRATION_ID = g.REGISTRATION_ID WHERE s.RESULT_STATUS = 'FINISHED' "
     "GROUP BY g.RACE_ID HAVING MAX(s.OVERALL_RANK) <> COUNT(*) "
     "OR COUNT(DISTINCT s.OVERALL_RANK) <> COUNT(*))", lambda v: v == 0),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-export", action="store_true")
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()
    cur.execute(f"USE WAREHOUSE {WAREHOUSE}")
    cur.execute(f"USE DATABASE {DATABASE}")
    cur.execute(f"USE SCHEMA {SCHEMA}")

    failed = 0
    print("== Validation ==")
    for name, sql, ok in CHECKS:
        value = cur.execute(sql).fetchone()[0]
        passed = ok(value)
        failed += 0 if passed else 1
        print(f"[{'PASS' if passed else 'FAIL'}] {name}  (value={value})")

    print("\n== Row counts and fingerprints (compare across seed runs to confirm repeatability) ==")
    fp_file = Path("fingerprint.json")
    old = json.loads(fp_file.read_text()) if fp_file.exists() else {}
    new = {}
    for t in LOAD_ORDER:
        count = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        fp = str(cur.execute(f"SELECT HASH_AGG(*) FROM {t}").fetchone()[0])
        new[t] = fp
        note = "first run" if t not in old else ("MATCH" if old[t] == fp else "CHANGED")
        print(f"{t:<14} rows={count:<7} fingerprint={fp}  [{note}]")
    fp_file.write_text(json.dumps(new, indent=2))

    if not args.no_export:
        out = Path("export")
        out.mkdir(exist_ok=True)
        for t in LOAD_ORDER:
            cur.execute(f"SELECT * FROM {t} ORDER BY 1")
            cols = [c[0].lower() for c in cur.description]
            rows = cur.fetchall()
            with open(out / f"{t.lower()}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                w.writerows(rows)
            with open(out / f"{t.lower()}.json", "w", encoding="utf-8") as f:
                json.dump([dict(zip(cols, r)) for r in rows], f, default=str, indent=1)
        print(f"\nExported CSV + JSON for {len(LOAD_ORDER)} tables to ./export")

    conn.close()
    print(f"\n{'ALL CHECKS PASSED' if not failed else str(failed) + ' CHECK(S) FAILED'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
