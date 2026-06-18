"""
src/ingest.py
=============
CSV → DuckDB loader with schema enforcement and basic cleaning.
"""

import json
import logging
from pathlib import Path

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = PROJECT_ROOT / "jan to may police violation_anonymized791b166.csv"


def load_csv(
    csv_path: Path | str = DEFAULT_CSV,
    *,
    con: duckdb.DuckDBPyConnection | None = None,
) -> pd.DataFrame:
    """Load violations CSV into a pandas DataFrame via DuckDB.

    DuckDB handles CSV parsing with correct type inference much faster
    than pure pandas on a 298K-row file.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")

    own_con = con is None
    if own_con:
        con = duckdb.connect()

    logger.info("Loading %s ...", csv_path.name)
    df: pd.DataFrame = con.execute(f"""
        SELECT * FROM read_csv_auto(
            '{csv_path.as_posix()}',
            all_varchar=false,
            header=true
        )
    """).fetchdf()

    if own_con:
        con.close()

    logger.info("Loaded %d rows × %d columns", len(df), len(df.columns))
    return df


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply minimal cleaning — parse JSON fields, fix timestamps."""
    df = df.copy()

    # ------------------------------------------------------------------
    # 1. Parse violation_type JSON arrays → list[str]
    # ------------------------------------------------------------------
    def _parse_json_array(val):
        if pd.isna(val) or val is None:
            return []
        if isinstance(val, list):
            return val
        try:
            parsed = json.loads(str(val))
            return parsed if isinstance(parsed, list) else [str(parsed)]
        except (json.JSONDecodeError, TypeError):
            return [str(val)]

    df["violation_type_list"] = df["violation_type"].apply(_parse_json_array)
    df["primary_violation"] = df["violation_type_list"].apply(
        lambda lst: lst[0] if lst else "UNKNOWN"
    )

    # ------------------------------------------------------------------
    # 2. Parse offence_code JSON arrays → list[int]
    # ------------------------------------------------------------------
    def _parse_offence_codes(val):
        if pd.isna(val) or val is None:
            return []
        if isinstance(val, list):
            return val
        try:
            parsed = json.loads(str(val))
            return parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, TypeError):
            return []

    df["offence_code_list"] = df["offence_code"].apply(_parse_offence_codes)

    # ------------------------------------------------------------------
    # 3. Ensure datetime columns are proper timestamps
    # ------------------------------------------------------------------
    dt_cols = [
        "created_datetime", "closed_datetime", "modified_datetime",
        "action_taken_timestamp", "data_sent_to_scita_timestamp",
        "validation_timestamp",
    ]
    for col in dt_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    # ------------------------------------------------------------------
    # 4. IST time features (from created_datetime)
    #    Note: timestamps are already in IST (+05:30) per Phase 0 discovery
    # ------------------------------------------------------------------
    if "created_datetime" in df.columns:
        # Timestamps are already IST but tz_convert ensures consistency
        try:
            ist = df["created_datetime"].dt.tz_convert("Asia/Kolkata")
        except TypeError:
            # If tz-naive, localize directly
            ist = df["created_datetime"].dt.tz_localize("Asia/Kolkata")
        df["hour_ist"] = ist.dt.hour
        df["day_of_week"] = ist.dt.dayofweek  # 0=Monday
        df["month"] = ist.dt.month
        df["date_ist"] = ist.dt.date

    # ------------------------------------------------------------------
    # 5. Clean junction_name
    # ------------------------------------------------------------------
    if "junction_name" in df.columns:
        df["junction_name"] = df["junction_name"].fillna("No Junction").str.strip()

    logger.info(
        "Cleaning done — added columns: violation_type_list, primary_violation, "
        "offence_code_list, hour_ist, day_of_week, month, date_ist"
    )
    return df
