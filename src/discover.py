"""
Phase 0 — Data Discovery Script
================================
Loads the violations CSV into DuckDB and answers all open questions
from PROJECT_MEMORY.md before any ML work begins.

Outputs a structured report to stdout.
"""

import duckdb
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "jan to may police violation_anonymized791b166.csv"

# Bengaluru approximate bounding box (generous)
BLR_LAT_MIN, BLR_LAT_MAX = 12.7, 13.2
BLR_LON_MIN, BLR_LON_MAX = 77.3, 77.9


def main() -> None:
    print("=" * 70)
    print("  PARKING INTELLIGENCE — PHASE 0 DATA DISCOVERY")
    print("=" * 70)

    con = duckdb.connect()

    # ------------------------------------------------------------------
    # 1. Load CSV
    # ------------------------------------------------------------------
    print("\n[1] Loading CSV ...")
    con.execute(f"""
        CREATE TABLE violations AS
        SELECT * FROM read_csv_auto('{CSV_PATH.as_posix()}',
                                     all_varchar=false,
                                     header=true)
    """)
    row_count = con.execute("SELECT COUNT(*) FROM violations").fetchone()[0]
    col_count = con.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'violations'
    """).fetchone()[0]
    print(f"    Rows: {row_count:,}")
    print(f"    Columns: {col_count}")

    # Column names + types
    cols = con.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'violations'
        ORDER BY ordinal_position
    """).fetchall()
    print("\n    Column schema:")
    for name, dtype in cols:
        print(f"      {name:40s} {dtype}")

    # ------------------------------------------------------------------
    # 2. Date range (Q1)
    # ------------------------------------------------------------------
    print("\n[2] Date range (Q1) ...")
    # Note: closed_datetime and several other nullable datetime cols were
    # auto-inferred as VARCHAR by DuckDB due to high NULL rates. Cast them.
    date_range = con.execute("""
        SELECT
            MIN(created_datetime) AS min_created,
            MAX(created_datetime) AS max_created,
            MIN(TRY_CAST(closed_datetime AS TIMESTAMPTZ))  AS min_closed,
            MAX(TRY_CAST(closed_datetime AS TIMESTAMPTZ))  AS max_closed
        FROM violations
    """).fetchone()
    print(f"    created_datetime range: {date_range[0]}  ->  {date_range[1]}")
    print(f"    closed_datetime  range: {date_range[2]}  ->  {date_range[3]}")

    # Monthly distribution
    print("\n    Monthly distribution (created_datetime):")
    months = con.execute("""
        SELECT
            DATE_TRUNC('month', created_datetime) AS month,
            COUNT(*) AS cnt
        FROM violations
        WHERE created_datetime IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for month, cnt in months:
        print(f"      {month}: {cnt:>8,}")

    # ------------------------------------------------------------------
    # 3. NULL rates (Q2)
    # ------------------------------------------------------------------
    print("\n[3] NULL rates (Q2 — closed_datetime) ...")
    null_stats = con.execute("""
        SELECT
            COUNT(*)                                          AS total,
            COUNT(*) FILTER (WHERE closed_datetime IS NULL OR TRIM(closed_datetime) = '' OR closed_datetime = 'NULL') AS closed_null,
            COUNT(*) FILTER (WHERE action_taken_timestamp IS NULL OR TRIM(action_taken_timestamp) = '' OR action_taken_timestamp = 'NULL') AS action_null,
            COUNT(*) FILTER (WHERE validation_status IS NULL) AS validation_null,
            COUNT(*) FILTER (WHERE junction_name IS NULL)     AS junction_null,
            COUNT(*) FILTER (WHERE description IS NULL OR description = 'NULL') AS desc_null
        FROM violations
    """).fetchone()
    total = null_stats[0]
    print(f"    Total rows:                {total:,}")
    print(f"    closed_datetime NULL:      {null_stats[1]:,} ({null_stats[1]/total*100:.1f}%)")
    print(f"    action_taken_timestamp NULL:{null_stats[2]:,} ({null_stats[2]/total*100:.1f}%)")
    print(f"    validation_status NULL:    {null_stats[3]:,} ({null_stats[3]/total*100:.1f}%)")
    print(f"    junction_name NULL:        {null_stats[4]:,} ({null_stats[4]/total*100:.1f}%)")
    print(f"    description NULL/'NULL':   {null_stats[5]:,} ({null_stats[5]/total*100:.1f}%)")

    # ------------------------------------------------------------------
    # 4. Junction name sparsity (Q3)
    # ------------------------------------------------------------------
    print("\n[4] Junction name analysis (Q3) ...")
    junction_stats = con.execute("""
        SELECT
            junction_name,
            COUNT(*) AS cnt
        FROM violations
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 20
    """).fetchall()
    unique_junctions = con.execute(
        "SELECT COUNT(DISTINCT junction_name) FROM violations"
    ).fetchone()[0]
    print(f"    Unique junction_name values: {unique_junctions}")
    print("    Top 20:")
    for jname, cnt in junction_stats:
        pct = cnt / total * 100
        print(f"      {str(jname):40s} {cnt:>8,}  ({pct:.1f}%)")

    # ------------------------------------------------------------------
    # 5. Police station analysis (Q6)
    # ------------------------------------------------------------------
    print("\n[5] Police station analysis (Q6) ...")
    station_stats = con.execute("""
        SELECT police_station, COUNT(*) AS cnt
        FROM violations
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 30
    """).fetchall()
    unique_stations = con.execute(
        "SELECT COUNT(DISTINCT police_station) FROM violations"
    ).fetchone()[0]
    print(f"    Unique police_station values: {unique_stations}")
    print("    Top 30:")
    for stn, cnt in station_stats:
        pct = cnt / total * 100
        print(f"      {str(stn):35s} {cnt:>8,}  ({pct:.1f}%)")

    # ------------------------------------------------------------------
    # 6. Violation type taxonomy (Q4)
    # ------------------------------------------------------------------
    print("\n[6] Violation type taxonomy (Q4) ...")
    # violation_type is stored as a string like '["WRONG PARKING","NO PARKING"]'
    # Let's get the raw distinct values first
    vtype_raw = con.execute("""
        SELECT DISTINCT violation_type
        FROM violations
        WHERE violation_type IS NOT NULL
        LIMIT 50
    """).fetchall()
    # Parse all unique types from JSON arrays
    all_types = set()
    for (vt_str,) in vtype_raw:
        if vt_str and vt_str.strip():
            try:
                parsed = json.loads(vt_str)
                if isinstance(parsed, list):
                    all_types.update(parsed)
                else:
                    all_types.add(str(parsed))
            except (json.JSONDecodeError, TypeError):
                all_types.add(str(vt_str))

    print(f"    Unique violation types found (from first 50 distinct arrays): {len(all_types)}")
    for vt in sorted(all_types):
        print(f"      - {vt}")

    # Also get total unique violation_type array combinations
    unique_combos = con.execute(
        "SELECT COUNT(DISTINCT violation_type) FROM violations"
    ).fetchone()[0]
    print(f"    Total unique violation_type combinations: {unique_combos}")

    # ------------------------------------------------------------------
    # 7. Lat/Lon bounds & outliers (Q5)
    # ------------------------------------------------------------------
    print("\n[7] Lat/Lon bounds & outliers (Q5) ...")
    geo_stats = con.execute("""
        SELECT
            MIN(latitude)  AS lat_min,
            MAX(latitude)  AS lat_max,
            AVG(latitude)  AS lat_avg,
            MIN(longitude) AS lon_min,
            MAX(longitude) AS lon_max,
            AVG(longitude) AS lon_avg,
            COUNT(*) FILTER (WHERE latitude IS NULL OR longitude IS NULL) AS null_coords,
            COUNT(*) FILTER (WHERE latitude < 12.7 OR latitude > 13.2
                          OR longitude < 77.3 OR longitude > 77.9) AS outlier_coords
        FROM violations
    """).fetchone()
    print(f"    Latitude:  min={geo_stats[0]:.6f}  max={geo_stats[1]:.6f}  avg={geo_stats[2]:.6f}")
    print(f"    Longitude: min={geo_stats[3]:.6f}  max={geo_stats[4]:.6f}  avg={geo_stats[5]:.6f}")
    print(f"    NULL coordinates:    {geo_stats[6]:,}")
    print(f"    Outside Bengaluru:   {geo_stats[7]:,} ({geo_stats[7]/total*100:.2f}%)")

    # ------------------------------------------------------------------
    # 8. Vehicle type distribution
    # ------------------------------------------------------------------
    print("\n[8] Vehicle type distribution ...")
    vtypes = con.execute("""
        SELECT vehicle_type, COUNT(*) AS cnt
        FROM violations
        GROUP BY 1
        ORDER BY 2 DESC
    """).fetchall()
    print(f"    Unique vehicle types: {len(vtypes)}")
    for vtype, cnt in vtypes:
        pct = cnt / total * 100
        print(f"      {str(vtype):25s} {cnt:>8,}  ({pct:.1f}%)")

    # ------------------------------------------------------------------
    # 9. Clearance duration analysis (where closed_datetime is not null)
    # ------------------------------------------------------------------
    print("\n[9] Clearance duration analysis ...")
    clearance = con.execute("""
        WITH parsed AS (
            SELECT
                created_datetime,
                TRY_CAST(closed_datetime AS TIMESTAMPTZ) AS closed_ts
            FROM violations
            WHERE closed_datetime IS NOT NULL
              AND TRIM(closed_datetime) != ''
              AND closed_datetime != 'NULL'
        )
        SELECT
            COUNT(*) AS rows_with_close,
            AVG(EXTRACT(EPOCH FROM (closed_ts - created_datetime)) / 3600) AS avg_hours,
            MEDIAN(EXTRACT(EPOCH FROM (closed_ts - created_datetime)) / 3600) AS med_hours,
            MIN(EXTRACT(EPOCH FROM (closed_ts - created_datetime)) / 3600) AS min_hours,
            MAX(EXTRACT(EPOCH FROM (closed_ts - created_datetime)) / 3600) AS max_hours
        FROM parsed
        WHERE closed_ts IS NOT NULL
          AND closed_ts >= created_datetime
    """).fetchone()
    if clearance[0] > 0:
        print(f"    Rows with valid close: {clearance[0]:,}")
        print(f"    Avg clearance:  {clearance[1]:.1f} hours")
        print(f"    Median:         {clearance[2]:.1f} hours")
        print(f"    Min:            {clearance[3]:.1f} hours")
        print(f"    Max:            {clearance[4]:.1f} hours")
    else:
        print("    No rows with valid closed_datetime found.")

    # ------------------------------------------------------------------
    # 10. Hourly distribution (IST)
    # ------------------------------------------------------------------
    print("\n[10] Hourly distribution (converted to IST) ...")
    hourly = con.execute("""
        SELECT
            EXTRACT(HOUR FROM (created_datetime + INTERVAL '5 hours 30 minutes')) AS hour_ist,
            COUNT(*) AS cnt
        FROM violations
        WHERE created_datetime IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """).fetchall()
    for hour, cnt in hourly:
        bar = "#" * int(cnt / total * 200)
        print(f"      {int(hour):02d}:00  {cnt:>7,}  {bar}")

    # ------------------------------------------------------------------
    # 11. data_sent_to_scita distribution
    # ------------------------------------------------------------------
    print("\n[11] data_sent_to_scita distribution ...")
    scita = con.execute("""
        SELECT data_sent_to_scita, COUNT(*) AS cnt
        FROM violations
        GROUP BY 1
        ORDER BY 2 DESC
    """).fetchall()
    for val, cnt in scita:
        print(f"      {str(val):15s} {cnt:>8,}  ({cnt/total*100:.1f}%)")

    # ------------------------------------------------------------------
    # 12. validation_status distribution
    # ------------------------------------------------------------------
    print("\n[12] validation_status distribution ...")
    vstatus = con.execute("""
        SELECT validation_status, COUNT(*) AS cnt
        FROM violations
        GROUP BY 1
        ORDER BY 2 DESC
    """).fetchall()
    for val, cnt in vstatus:
        print(f"      {str(val):15s} {cnt:>8,}  ({cnt/total*100:.1f}%)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  PHASE 0 DISCOVERY COMPLETE")
    print("=" * 70)

    con.close()


if __name__ == "__main__":
    main()
