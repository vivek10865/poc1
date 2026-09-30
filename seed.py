"""POC-001: IRONMAN Relational Data Simulator - seed script.

Usage:
    python seed.py              # create schema in Snowflake + load data
    python seed.py --skip-schema  # reload data only (tables must exist; not recommended)
    python seed.py --dry-run    # no Snowflake; write CSVs to ./seed_output

Repeatable: fixed RNG seed + fixed reference date => identical data on every run.
"""
import argparse
import csv
import os
import random
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 42
REFERENCE_DATE = date(2026, 9, 1)      # events before this date are COMPLETED and have results
N_ATHLETES = 520
FIRST_EVENT_DATE = date(2025, 10, 5)
EVENT_SPACING_DAYS = 17
PRO_SHARE = 0.05

DATABASE = os.getenv("SNOWFLAKE_DATABASE", "IRONMAN_POC")
SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "CORE")
WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "IRONMAN_WH")

# (city, country, region) -> 34 locations => 34 events
LOCATIONS = [
    ("Kona", "United States", "North America"), ("Lake Placid", "United States", "North America"),
    ("Chattanooga", "United States", "North America"), ("Boulder", "United States", "North America"),
    ("Santa Rosa", "United States", "North America"), ("Mont-Tremblant", "Canada", "North America"),
    ("Cozumel", "Mexico", "Latin America"), ("Florianopolis", "Brazil", "Latin America"),
    ("Frankfurt", "Germany", "Europe"), ("Klagenfurt", "Austria", "Europe"),
    ("Vichy", "France", "Europe"), ("Nice", "France", "Europe"),
    ("Barcelona", "Spain", "Europe"), ("Tallinn", "Estonia", "Europe"),
    ("Cork", "Ireland", "Europe"), ("Copenhagen", "Denmark", "Europe"),
    ("Zurich", "Switzerland", "Europe"), ("Tampere", "Finland", "Europe"),
    ("Gdynia", "Poland", "Europe"), ("Cascais", "Portugal", "Europe"),
    ("Lanzarote", "Spain", "Europe"), ("Weymouth", "United Kingdom", "Europe"),
    ("Cairns", "Australia", "Asia-Pacific"), ("Busselton", "Australia", "Asia-Pacific"),
    ("Taupo", "New Zealand", "Asia-Pacific"), ("Melbourne", "Australia", "Asia-Pacific"),
    ("Subic Bay", "Philippines", "Asia-Pacific"), ("Da Nang", "Vietnam", "Asia-Pacific"),
    ("Kaohsiung", "Taiwan", "Asia-Pacific"), ("Langkawi", "Malaysia", "Asia-Pacific"),
    ("Goa", "India", "Asia-Pacific"), ("Cape Town", "South Africa", "Middle East & Africa"),
    ("Muscat", "Oman", "Middle East & Africa"), ("Dubai", "United Arab Emirates", "Middle East & Africa"),
]

# (faker locale, nationality, weight)
LOCALES = [
    ("en_US", "United States", 20), ("en_GB", "United Kingdom", 10), ("de_DE", "Germany", 10),
    ("fr_FR", "France", 8), ("es_ES", "Spain", 7), ("en_AU", "Australia", 8),
    ("it_IT", "Italy", 5), ("en_IN", "India", 6), ("pt_BR", "Brazil", 5),
    ("nl_NL", "Netherlands", 4), ("en_CA", "Canada", 5),
]

DISTANCES = {
    "FULL": dict(swim_km=3.8, bike_km=180.2, run_km=42.2, fee=850.0,
                 base=dict(swim=4200, t1=400, bike=22000, t2=300, run=16500)),
    "HALF": dict(swim_km=1.9, bike_km=90.0, run_km=21.1, fee=380.0,
                 base=dict(swim=2100, t1=300, bike=10800, t2=200, run=7500)),
}
REGION_FEE_FACTOR = {"North America": 1.0, "Europe": 0.95, "Asia-Pacific": 0.9,
                     "Latin America": 0.85, "Middle East & Africa": 0.9}

COLUMNS = {
    "LOCATIONS": ["location_id", "city", "country", "region"],
    "ATHLETES": ["athlete_id", "first_name", "last_name", "email", "gender", "birth_date",
                 "age_group", "nationality", "is_pro"],
    "EVENTS": ["event_id", "event_name", "event_type", "event_date", "location_id",
               "registration_open_date", "registration_close_date", "capacity", "status"],
    "RACES": ["race_id", "event_id", "race_name", "category", "distance_type", "swim_km",
              "bike_km", "run_km", "start_time"],
    "REGISTRATIONS": ["registration_id", "athlete_id", "race_id", "registration_date",
                      "bib_number", "status", "fee_usd"],
    "RESULTS": ["result_id", "registration_id", "result_status", "dnf_stage", "swim_seconds",
                "t1_seconds", "bike_seconds", "t2_seconds", "run_seconds", "total_seconds",
                "overall_rank", "gender_rank"],
}
LOAD_ORDER = ["LOCATIONS", "ATHLETES", "EVENTS", "RACES", "REGISTRATIONS", "RESULTS"]


def ascii_slug(text):
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if c.isalnum() and ord(c) < 128).lower()


def age_on(birth, on):
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def age_group_label(gender, age):
    band = "18-24" if age < 25 else f"{age // 5 * 5}-{age // 5 * 5 + 4}"
    return f"{gender}{band}"


def generate():
    from faker import Faker

    Faker.seed(SEED)
    rng = random.Random(SEED)
    fakers = {loc: Faker(loc) for loc, _, _ in LOCALES}

    # ---- locations
    locations = [dict(location_id=i + 1, city=c, country=co, region=r)
                 for i, (c, co, r) in enumerate(LOCATIONS)]

    # ---- athletes
    athletes, ability, age_of = [], {}, {}
    used_emails = set()
    for aid in range(1, N_ATHLETES + 1):
        loc, nat, _ = rng.choices(LOCALES, weights=[w for _, _, w in LOCALES])[0]
        fk = fakers[loc]
        gender = "M" if rng.random() < 0.62 else "F"
        first = fk.first_name_male() if gender == "M" else fk.first_name_female()
        last = fk.last_name()
        age = int(min(74, max(18, rng.gauss(41, 10))))
        birth = REFERENCE_DATE - timedelta(days=age * 365 + rng.randint(0, 364))
        age = age_on(birth, REFERENCE_DATE)
        is_pro = rng.random() < PRO_SHARE
        email = f"{ascii_slug(first)}.{ascii_slug(last)}{aid}@example.com"
        assert email not in used_emails
        used_emails.add(email)
        athletes.append(dict(athlete_id=aid, first_name=first, last_name=last, email=email,
                             gender=gender, birth_date=birth,
                             age_group=age_group_label(gender, age), nationality=nat, is_pro=is_pro))
        ability[aid] = min(1.5, max(0.75, rng.gauss(1.0, 0.12)))
        age_of[aid] = age
    gender_of = {a["athlete_id"]: a["gender"] for a in athletes}
    pro_of = {a["athlete_id"]: a["is_pro"] for a in athletes}
    age_pool = [a["athlete_id"] for a in athletes if not a["is_pro"]]
    pro_pool = [a["athlete_id"] for a in athletes if a["is_pro"]]

    # ---- events and races
    events, races = [], []
    event_factor = {}
    for i, loc in enumerate(locations):
        d = FIRST_EVENT_DATE + timedelta(days=i * EVENT_SPACING_DAYS)
        d += timedelta(days=(6 - d.weekday()) % 7)  # align to Sunday
        etype = "IRONMAN" if i % 2 == 0 else "IRONMAN 70.3"
        dist = "FULL" if etype == "IRONMAN" else "HALF"
        eid = i + 1
        name = f"{etype} {loc['city']}"
        events.append(dict(event_id=eid, event_name=name, event_type=etype, event_date=d,
                           location_id=loc["location_id"],
                           registration_open_date=d - timedelta(days=365),
                           registration_close_date=d - timedelta(days=14),
                           capacity=rng.randint(1500, 2500) if dist == "FULL" else rng.randint(1200, 2000),
                           status="COMPLETED" if d < REFERENCE_DATE else "UPCOMING"))
        event_factor[eid] = rng.uniform(0.96, 1.08)
        dd = DISTANCES[dist]
        for cat, label, start in (("AGE_GROUP", "Age Group", 6 * 60 + 30), ("PRO", "Pro", 6 * 60 + 25)):
            races.append(dict(race_id=len(races) + 1, event_id=eid, race_name=f"{name} - {label}",
                              category=cat, distance_type=dist, swim_km=dd["swim_km"],
                              bike_km=dd["bike_km"], run_km=dd["run_km"],
                              start_time=datetime(d.year, d.month, d.day, start // 60, start % 60)))
    event_by_id = {e["event_id"]: e for e in events}
    loc_by_id = {l["location_id"]: l for l in locations}

    # ---- registrations
    registrations = []
    for race in races:
        ev = event_by_id[race["event_id"]]
        if race["category"] == "AGE_GROUP":
            chosen = rng.sample(age_pool, rng.randint(60, 110))
        else:
            chosen = rng.sample(pro_pool, min(len(pro_pool), rng.randint(5, 12)))
        base_fee = DISTANCES[race["distance_type"]]["fee"]
        region = loc_by_id[ev["location_id"]]["region"]
        rows = []
        for aid in chosen:
            reg_date = ev["event_date"] - timedelta(days=rng.randint(21, 330))
            cancelled = rng.random() < 0.05
            fee = 0.0 if race["category"] == "PRO" else round(
                base_fee * REGION_FEE_FACTOR[region] * rng.choice([1.0, 1.0, 1.0, 1.05, 1.1]), 2)
            rows.append(dict(athlete_id=aid, race_id=race["race_id"], registration_date=reg_date,
                             status="CANCELLED" if cancelled else "CONFIRMED", fee_usd=fee))
        rows.sort(key=lambda r: (r["registration_date"], r["athlete_id"]))
        bib = 0
        for r in rows:
            if r["status"] == "CONFIRMED":
                bib += 1
                r["bib_number"] = bib
            else:
                r["bib_number"] = None
            r["registration_id"] = len(registrations) + 1
            registrations.append(r)
    race_by_id = {r["race_id"]: r for r in races}

    # ---- results (completed events only, confirmed registrations only)
    results, tmp = [], {}
    for reg in registrations:
        race = race_by_id[reg["race_id"]]
        ev = event_by_id[race["event_id"]]
        if ev["status"] != "COMPLETED" or reg["status"] != "CONFIRMED":
            continue
        aid = reg["athlete_id"]
        base = DISTANCES[race["distance_type"]]["base"]
        scale = ability[aid] * (1 + max(0, age_of[aid] - 35) * 0.004) * (0.82 if pro_of[aid] else 1.0)
        ef = event_factor[ev["event_id"]]

        def split(key, factor=1.0):
            return int(round(base[key] * scale * factor * rng.gauss(1, 0.04)))

        draw = rng.random()
        row = dict(result_id=len(results) + 1, registration_id=reg["registration_id"],
                   result_status="FINISHED", dnf_stage=None, swim_seconds=None, t1_seconds=None,
                   bike_seconds=None, t2_seconds=None, run_seconds=None, total_seconds=None,
                   overall_rank=None, gender_rank=None)
        if draw < 0.04:
            row["result_status"] = "DNS"
        elif draw < 0.12:
            row["result_status"] = "DNF"
            row["dnf_stage"] = rng.choice(["SWIM", "BIKE", "RUN"])
            if row["dnf_stage"] in ("BIKE", "RUN"):
                row["swim_seconds"], row["t1_seconds"] = split("swim"), split("t1")
            if row["dnf_stage"] == "RUN":
                row["bike_seconds"], row["t2_seconds"] = split("bike", ef), split("t2")
        else:
            row["swim_seconds"], row["t1_seconds"] = split("swim"), split("t1")
            row["bike_seconds"], row["t2_seconds"] = split("bike", ef), split("t2")
            row["run_seconds"] = split("run", ef)
            row["total_seconds"] = sum(row[k] for k in ("swim_seconds", "t1_seconds", "bike_seconds",
                                                        "t2_seconds", "run_seconds"))
        tmp[row["result_id"]] = (race["race_id"], gender_of[aid], reg["registration_id"])
        results.append(row)

    # ranks per race (overall) and per race + gender
    by_race = {}
    for r in results:
        if r["result_status"] == "FINISHED":
            by_race.setdefault(tmp[r["result_id"]][0], []).append(r)
    for rows in by_race.values():
        rows.sort(key=lambda r: (r["total_seconds"], r["registration_id"]))
        gcount = {}
        for n, r in enumerate(rows, 1):
            g = tmp[r["result_id"]][1]
            gcount[g] = gcount.get(g, 0) + 1
            r["overall_rank"], r["gender_rank"] = n, gcount[g]

    return {"LOCATIONS": locations, "ATHLETES": athletes, "EVENTS": events, "RACES": races,
            "REGISTRATIONS": registrations, "RESULTS": results}


def write_csvs(data, out_dir="seed_output"):
    Path(out_dir).mkdir(exist_ok=True)
    for table in LOAD_ORDER:
        with open(Path(out_dir) / f"{table.lower()}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS[table])
            for row in data[table]:
                w.writerow([row[c] for c in COLUMNS[table]])
    print(f"CSV files written to ./{out_dir}")


def connect():
    import snowflake.connector
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    kwargs = dict(account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
                  password=os.environ["SNOWFLAKE_PASSWORD"])
    if os.getenv("SNOWFLAKE_ROLE"):
        kwargs["role"] = os.environ["SNOWFLAKE_ROLE"]
    return snowflake.connector.connect(**kwargs)


def load(data, skip_schema=False):
    conn = connect()
    try:
        cur = conn.cursor()
        if not skip_schema:
            with open(Path(__file__).with_name("schema.sql"), encoding="utf-8") as f:
                conn.execute_string(f.read())
            print("Schema created.")
        cur.execute(f"USE WAREHOUSE {WAREHOUSE}")
        cur.execute(f"USE DATABASE {DATABASE}")
        cur.execute(f"USE SCHEMA {SCHEMA}")
        for table in LOAD_ORDER:
            cols = COLUMNS[table]
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})"
            rows = [tuple(r[c] for c in cols) for r in data[table]]
            for i in range(0, len(rows), 2000):
                cur.executemany(sql, rows[i:i + 2000])
            print(f"Loaded {len(rows):>6} rows into {table}")
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="write CSVs instead of loading Snowflake")
    ap.add_argument("--skip-schema", action="store_true")
    args = ap.parse_args()
    data = generate()
    for t in LOAD_ORDER:
        print(f"Generated {len(data[t]):>6} {t}")
    if args.dry_run:
        write_csvs(data)
    else:
        load(data, args.skip_schema)
        print("Done. Next: python validate.py")
