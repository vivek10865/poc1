# POC-001 Data Dictionary — IRONMAN Relational Data Simulator

Database `IRONMAN_POC`, schema `CORE`. All data is synthetic (Faker, fixed seed 42, reference date 2026-09-01).
Snowflake does not enforce PK/FK constraints; integrity is guaranteed by `seed.py` and verified by `validate.py`.

## Relationships
LOCATIONS 1—N EVENTS 1—N RACES 1—N REGISTRATIONS N—1 ATHLETES; REGISTRATIONS 1—0..1 RESULTS

## LOCATIONS
| Column | Type | Description |
|---|---|---|
| LOCATION_ID | NUMBER PK | Location identifier |
| CITY | VARCHAR | Host city |
| COUNTRY | VARCHAR | Host country |
| REGION | VARCHAR | North America, Latin America, Europe, Asia-Pacific, Middle East & Africa |

## ATHLETES
| Column | Type | Description |
|---|---|---|
| ATHLETE_ID | NUMBER PK | Athlete identifier |
| FIRST_NAME, LAST_NAME | VARCHAR | Synthetic name (locale-based) |
| EMAIL | VARCHAR UNIQUE | Synthetic email at example.com |
| GENDER | VARCHAR(1) | M or F |
| BIRTH_DATE | DATE | Date of birth |
| AGE_GROUP | VARCHAR | Age group as of 2026-09-01, e.g. M40-44 |
| NATIONALITY | VARCHAR | Country of the athlete |
| IS_PRO | BOOLEAN | Professional athlete (~5%) |

## EVENTS
| Column | Type | Description |
|---|---|---|
| EVENT_ID | NUMBER PK | Event identifier |
| EVENT_NAME | VARCHAR | e.g. IRONMAN Frankfurt |
| EVENT_TYPE | VARCHAR | IRONMAN or IRONMAN 70.3 |
| EVENT_DATE | DATE | Race day (Sundays) |
| LOCATION_ID | NUMBER FK → LOCATIONS | Host location |
| REGISTRATION_OPEN_DATE / REGISTRATION_CLOSE_DATE | DATE | Registration window |
| CAPACITY | NUMBER | Participant capacity |
| STATUS | VARCHAR | COMPLETED (before 2026-09-01) or UPCOMING |

## RACES
| Column | Type | Description |
|---|---|---|
| RACE_ID | NUMBER PK | Race identifier |
| EVENT_ID | NUMBER FK → EVENTS | Parent event (2 races per event) |
| RACE_NAME | VARCHAR | e.g. IRONMAN Frankfurt - Age Group |
| CATEGORY | VARCHAR | AGE_GROUP or PRO |
| DISTANCE_TYPE | VARCHAR | FULL or HALF |
| SWIM_KM, BIKE_KM, RUN_KM | NUMBER | Discipline distances |
| START_TIME | TIMESTAMP_NTZ | Local start time |

## REGISTRATIONS
| Column | Type | Description |
|---|---|---|
| REGISTRATION_ID | NUMBER PK | Registration identifier |
| ATHLETE_ID | NUMBER FK → ATHLETES | Registered athlete |
| RACE_ID | NUMBER FK → RACES | Race entered (unique per athlete + race) |
| REGISTRATION_DATE | DATE | On or before event date |
| BIB_NUMBER | NUMBER | Unique per race; NULL if cancelled |
| STATUS | VARCHAR | CONFIRMED or CANCELLED |
| FEE_USD | NUMBER(8,2) | Entry fee (0 for pros; varies by region) |

## RESULTS
Only for CONFIRMED registrations in COMPLETED events.
| Column | Type | Description |
|---|---|---|
| RESULT_ID | NUMBER PK | Result identifier |
| REGISTRATION_ID | NUMBER FK → REGISTRATIONS, UNIQUE | One result per registration |
| RESULT_STATUS | VARCHAR | FINISHED, DNF, DNS |
| DNF_STAGE | VARCHAR | SWIM, BIKE or RUN (DNF only) |
| SWIM_SECONDS, T1_SECONDS, BIKE_SECONDS, T2_SECONDS, RUN_SECONDS | NUMBER | Split times; NULL for stages not completed |
| TOTAL_SECONDS | NUMBER | Sum of splits (FINISHED only) |
| OVERALL_RANK | NUMBER | Rank within race (FINISHED only) |
| GENDER_RANK | NUMBER | Rank within race and gender (FINISHED only) |
