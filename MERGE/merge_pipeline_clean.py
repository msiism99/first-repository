# -*- coding: utf-8 -*-
"""
Clean refactor of MERGE/001.py~013.py.

Purpose
-------
- Keep the original ADI/OCO data flow, but remove notebook-style global sprawl.
- Standardize key dtypes before every important merge.
- Guard empty DataFrames and optional columns.
- Keep raw/KMRC/PSM/TROCS/WK-RK decomposition in one runnable pipeline.

Run
---
1) Edit CONFIG at the bottom.
2) Run this file in the same environment where `bigdataquery` is available.

Notes
-----
- Original files are intentionally left untouched.
- PSM/TROCS convention follows the existing code:
    raw_x = X_reg_demrc - PSM_X or psm_fit_x
    raw_y = Y_reg_demrc - PSM_Y or psm_fit_y
  Re-check this sign convention against APC/PSM definition before using final coefficients.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import bigdataquery as bdq


# =============================================================================
# 0. Config
# =============================================================================

@dataclass
class PipelineConfig:
    days: int = 8
    exclude_recent_days: int = 1
    expo_days: int = 10
    max_excel_rows: int = 1_048_575

    # Use a list/tuple, not SQL text. Example: ["B0K486.1", "B0K271.1"]
    target_lotid: Optional[Sequence[str] | str] = None
    target_pstepseq: Optional[str] = "VC075030"
    target_mstepseq: Optional[str] = "VC075040"
    target_mstepseq_oco: Optional[str] = "VC077251"

    db_user_apc: str = "EAPCP2"
    db_user: str = "SIMAXP2"

    rawdata_gap_seconds: int = 60
    max_lot_transn_seq: int = 1_000
    max_photo_transn_seq: int = 1_000
    limit_rawdata_rows: int = 10_000_000

    slot_min: int = 9
    slot_max: int = 14
    wafer_radius_um: float = 147_000.0

    output_dir: str = "output_clean"
    save_intermediate_excel: bool = True
    save_final_parquet: bool = True
    run_apc_psm_trocs: bool = True
    run_wk_rk_regression: bool = True


# =============================================================================
# 1. Small utilities
# =============================================================================

def log(msg: str) -> None:
    print(msg, flush=True)


def ensure_output_dir(cfg: PipelineConfig) -> Path:
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out


def normalize_lotid_list(value: Optional[Sequence[str] | str]) -> list[str]:
    """Accept None/list/tuple/string and return clean lot list.

    Backward compatibility:
    - "('A','B')" is parsed into ["A", "B"] approximately.
    - plain "A" becomes ["A"].
    """
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        if s.startswith("(") and s.endswith(")"):
            s = s[1:-1]
        parts = [p.strip().strip("'").strip('"') for p in s.split(",")]
        return [p for p in parts if p]
    return [str(x).strip() for x in value if str(x).strip()]


def sql_quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def sql_in_clause(column: str, values: Sequence[object], numeric: bool = False) -> str:
    vals = [v for v in values if pd.notna(v)]
    if not vals:
        return ""
    if numeric:
        text = ",".join(str(int(float(v))) for v in vals)
    else:
        text = ",".join(sql_quote(v) for v in vals)
    return f"AND {column} IN ({text})"


def to_int64_nullable(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def to_int_plain_if_possible(s: pd.Series) -> pd.Series:
    out = pd.to_numeric(s, errors="coerce")
    return out.astype("Int64")


def clean_str_series(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip()


def remove_duplicated_columns(df: pd.DataFrame, name: str = "df") -> pd.DataFrame:
    if df.empty:
        return df.copy()
    dup_cols = df.columns[df.columns.duplicated()].tolist()
    if dup_cols:
        log(f"⚠️ {name} duplicated columns removed: {dup_cols}")
        df = df.loc[:, ~df.columns.duplicated()].copy()
    return df


def require_columns(df: pd.DataFrame, cols: Sequence[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing required columns: {missing}")


def pick_existing(df: pd.DataFrame, cols: Sequence[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


def normalize_common_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common join keys without assuming all columns exist."""
    df = df.copy()
    for col in ["photo_transn_seq", "apc_hist_index_no", "apc_trocs_hist_index_no", "lot_transn_seq"]:
        if col in df.columns:
            df[col] = to_int64_nullable(df[col])
    for col in ["slotid", "slot_id", "Wafer"]:
        if col in df.columns:
            df[col] = to_int64_nullable(df[col])
    for col in ["lotid", "LOT_ID", "lot_id"]:
        if col in df.columns:
            df[col] = clean_str_series(df[col])
    return df


def normalize_match_key_columns(df: pd.DataFrame, lot_col: str, wafer_col: str, photo_col: str = "photo_transn_seq") -> pd.DataFrame:
    df = df.copy()
    df["_lot_key"] = clean_str_series(df[lot_col]) if lot_col in df.columns else pd.Series(pd.NA, index=df.index, dtype="string")
    df["_wafer_key"] = to_int64_nullable(df[wafer_col]).astype("string") if wafer_col in df.columns else pd.Series(pd.NA, index=df.index, dtype="string")
    df["_photo_key"] = to_int64_nullable(df[photo_col]).astype("string") if photo_col in df.columns else pd.Series(pd.NA, index=df.index, dtype="string")
    return df


def save_excel_if_small(df: pd.DataFrame, path: Path, max_rows: int) -> None:
    if df.empty:
        log(f"skip save empty: {path}")
        return
    if len(df) > max_rows:
        sample_path = path.with_name(path.stem + "_sample100000" + path.suffix)
        df.head(100_000).to_excel(sample_path, index=False)
        log(f"⚠️ {path.name}: Excel row limit risk. saved sample -> {sample_path}")
    else:
        df.to_excel(path, index=False)
        log(f"saved: {path}")


# =============================================================================
# 2. LOTINFO / RAWDATA / metadata queries
# =============================================================================

def fetch_lotinfo_pair(cfg: PipelineConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lotids = normalize_lotid_list(cfg.target_lotid)
    lotid_filter = sql_in_clause("l.lotid", lotids)
    pstepseq_filter = f"AND l.pstepseq = {sql_quote(cfg.target_pstepseq)}" if cfg.target_pstepseq else ""
    mstepseq_filter_adi = f"AND l.mstepseq = {sql_quote(cfg.target_mstepseq)}" if cfg.target_mstepseq else ""
    mstepseq_filter_oco = f"AND l.mstepseq = {sql_quote(cfg.target_mstepseq_oco)}" if cfg.target_mstepseq_oco else ""

    sql_lotinfo_oco = f"""
    WITH lotinfo_raw AS (
      SELECT *
      FROM (
        SELECT
          l.lot_transn_seq,l.photo_transn_seq,l.impala_insert_time,
          l.db_user,l.`timestamp`,l.lotid,l.slotid,
          l.pstepseq,l.mstepseq,l.ppid,l.peqpid,l.chuckid,l.reticleid,
          l.steppitch_x,l.steppitch_y,l.mapshift_x,l.mapshift_y,
          l.dmargin_x,l.dmargin_y,l.outlr_resdl_spec_ratio,l.chip_x_qty,l.chip_y_qty,
          l.psm_mmo_ref_eqp_id,l.per_shot_mrc_id,
          row_number() OVER (
            PARTITION BY l.lotid, l.slotid
            ORDER BY l.impala_insert_time DESC
          ) AS rn
        FROM ees_ds_eai.apc_nautil_dat_lotinfo l
        WHERE l.impala_insert_time >= now() - interval {cfg.days + 5} days
          AND l.`timestamp` >= now() - interval {cfg.days + 5} days
          AND l.`timestamp` <= now() - interval {max(0, cfg.exclude_recent_days - 3)} days
          AND l.db_user = {sql_quote(cfg.db_user)}
          {lotid_filter}
          {pstepseq_filter}
          {mstepseq_filter_oco}
      ) t
      WHERE t.rn = 1
    )
    SELECT * FROM lotinfo_raw
    LIMIT 1000
    """

    log("[LOTINFO] OCO query start")
    df_lotinfo_oco = bdq.getData(sql_lotinfo_oco)
    df_lotinfo_oco = normalize_common_keys(df_lotinfo_oco)
    log(f"[LOTINFO] OCO rows: {len(df_lotinfo_oco)}")

    if df_lotinfo_oco.empty or "photo_transn_seq" not in df_lotinfo_oco.columns:
        log("⚠️ OCO lotinfo is empty. ADI lotinfo cannot be linked by photo_transn_seq.")
        return pd.DataFrame(), df_lotinfo_oco, pd.DataFrame()

    photo_values = df_lotinfo_oco["photo_transn_seq"].dropna().unique().tolist()[: cfg.max_photo_transn_seq]
    if not photo_values:
        log("⚠️ No valid photo_transn_seq in OCO lotinfo.")
        return pd.DataFrame(), df_lotinfo_oco, pd.DataFrame()

    photo_filter = sql_in_clause("l.photo_transn_seq", photo_values, numeric=True)
    sql_lotinfo_adi = f"""
    WITH lotinfo_raw AS (
      SELECT *
      FROM (
        SELECT
          l.lot_transn_seq,l.photo_transn_seq,l.impala_insert_time,
          l.db_user,l.`timestamp`,l.lotid,l.slotid,
          l.pstepseq,l.mstepseq,l.ppid,l.peqpid,l.chuckid,l.reticleid,
          l.steppitch_x,l.steppitch_y,l.mapshift_x,l.mapshift_y,
          l.dmargin_x,l.dmargin_y,l.outlr_resdl_spec_ratio,l.chip_x_qty,l.chip_y_qty,
          l.psm_mmo_ref_eqp_id,l.per_shot_mrc_id,
          row_number() OVER (
            PARTITION BY l.lotid, l.slotid
            ORDER BY l.impala_insert_time DESC
          ) AS rn
        FROM ees_ds_eai.apc_nautil_dat_lotinfo l
        WHERE l.impala_insert_time >= now() - interval {cfg.days + 10} days
          AND l.`timestamp` >= now() - interval {cfg.days + 10} days
          AND l.`timestamp` <= now() - interval {cfg.exclude_recent_days} days
          AND l.db_user = {sql_quote(cfg.db_user)}
          {photo_filter}
          {pstepseq_filter}
          {mstepseq_filter_adi}
      ) t
      WHERE t.rn = 1
    )
    SELECT * FROM lotinfo_raw
    LIMIT 100000
    """

    log("[LOTINFO] ADI query start")
    df_lotinfo_adi = bdq.getData(sql_lotinfo_adi)
    df_lotinfo_adi = normalize_common_keys(df_lotinfo_adi)
    log(f"[LOTINFO] ADI query rows: {len(df_lotinfo_adi)}")

    if df_lotinfo_adi.empty:
        return df_lotinfo_adi, df_lotinfo_oco, pd.DataFrame()

    # Date filter at Python side, as in the original code.
    df_lotinfo_adi["timestamp"] = pd.to_datetime(df_lotinfo_adi["timestamp"], errors="coerce")
    today = pd.Timestamp.today().normalize()
    start_date = today - pd.Timedelta(days=cfg.days)
    end_date_exclusive = today - pd.Timedelta(days=cfg.exclude_recent_days)
    df_lotinfo_adi = df_lotinfo_adi[
        (df_lotinfo_adi["timestamp"] >= start_date) &
        (df_lotinfo_adi["timestamp"] < end_date_exclusive)
    ].copy()

    # Keep only common photo_transn_seq + slotid between ADI/OCO.
    oco_keys = df_lotinfo_oco[["photo_transn_seq", "slotid"]].dropna().drop_duplicates()
    adi_keys = df_lotinfo_adi[["photo_transn_seq", "slotid"]].dropna().drop_duplicates()
    common_keys = oco_keys.merge(adi_keys, on=["photo_transn_seq", "slotid"], how="inner")

    df_lotinfo_oco = df_lotinfo_oco.merge(common_keys, on=["photo_transn_seq", "slotid"], how="inner")
    df_lotinfo_adi = df_lotinfo_adi.merge(common_keys, on=["photo_transn_seq", "slotid"], how="inner")

    df_lotinfo_oco = df_lotinfo_oco[df_lotinfo_oco["slotid"].between(cfg.slot_min, cfg.slot_max)].copy()
    df_lotinfo_adi = df_lotinfo_adi[df_lotinfo_adi["slotid"].between(cfg.slot_min, cfg.slot_max)].copy()

    sort_cols = ["photo_transn_seq", "slotid"]
    df_lotinfo_oco = df_lotinfo_oco.sort_values(sort_cols).reset_index(drop=True)
    df_lotinfo_adi = df_lotinfo_adi.sort_values(sort_cols).reset_index(drop=True)

    log(f"✅ ADI LOTINFO rows: {len(df_lotinfo_adi)}")
    log(f"✅ OCO LOTINFO rows: {len(df_lotinfo_oco)}")

    df_lotinfo_save = df_lotinfo_adi.copy()
    oco_add_cols = (
        df_lotinfo_oco[["photo_transn_seq", "slotid", "lot_transn_seq", "timestamp", "mstepseq"]]
        .drop_duplicates(subset=["photo_transn_seq", "slotid"])
        .rename(columns={
            "lot_transn_seq": "lot_transn_seq_oco",
            "timestamp": "timestamp_oco",
            "mstepseq": "mstepseq_oco",
        })
    )
    df_lotinfo_save = df_lotinfo_save.merge(oco_add_cols, on=["photo_transn_seq", "slotid"], how="left")

    if "per_shot_mrc_id" in df_lotinfo_save.columns:
        last_part = df_lotinfo_save["per_shot_mrc_id"].astype(str).str.split("/").str[-1]
        df_lotinfo_save["base_eqpid"] = last_part.str.split("_").str[0]
        df_lotinfo_save["psm_update_time"] = (
            last_part.str.split("_").str[1]
            .astype("string")
            .str.replace(r"^20", "", regex=True)
            .str[:10]
        )

    return df_lotinfo_adi, df_lotinfo_oco, df_lotinfo_save


def filter_latest_batch_by_gap_per_kind(df_rawdata: pd.DataFrame, gap_seconds: int = 60) -> pd.DataFrame:
    if df_rawdata.empty:
        return df_rawdata.copy()
    required = ["lot_transn_seq", "slot_id", "data_kind", "transn_occur_date"]
    require_columns(df_rawdata, required, "filter_latest_batch_by_gap_per_kind")

    df = df_rawdata.copy()
    df["transn_occur_date"] = pd.to_datetime(df["transn_occur_date"].astype(str), errors="coerce")
    before = len(df)
    df = df.dropna(subset=["transn_occur_date"]).copy()
    if before != len(df):
        log(f"⚠️ transn_occur_date NaT removed: {before - len(df)} rows")

    group_cols = ["lot_transn_seq", "slot_id", "data_kind"]
    df = df.sort_values(group_cols + ["transn_occur_date"]).reset_index(drop=True)
    df["prev_time"] = df.groupby(group_cols)["transn_occur_date"].shift(1)
    df["gap_sec"] = (df["transn_occur_date"] - df["prev_time"]).dt.total_seconds()
    df["new_batch"] = (df["prev_time"].isna() | (df["gap_sec"] > gap_seconds)).astype(int)
    df["batch_id"] = df.groupby(group_cols)["new_batch"].cumsum()
    last_batch = (
        df.groupby(group_cols, dropna=False)["batch_id"].max().reset_index().rename(columns={"batch_id": "last_batch_id"})
    )
    df = df.merge(last_batch, on=group_cols, how="inner")
    df = df[df["batch_id"] == df["last_batch_id"]].copy()
    df = df.drop(columns=["prev_time", "gap_sec", "new_batch", "batch_id", "last_batch_id"])
    return df.reset_index(drop=True)


def fetch_rawdata_from_lotinfo(
    df_lotinfo: pd.DataFrame,
    cfg: PipelineConfig,
    label: str,
) -> pd.DataFrame:
    if df_lotinfo.empty:
        log(f"⚠️ {label}: empty LOTINFO. RAWDATA query skipped.")
        return pd.DataFrame()
    require_columns(df_lotinfo, ["lot_transn_seq", "slotid"], f"{label} lotinfo")

    lot_transn_seqs = (
        to_int64_nullable(df_lotinfo["lot_transn_seq"])
        .dropna().astype("int64").unique().tolist()[: cfg.max_lot_transn_seq]
    )
    if not lot_transn_seqs:
        log(f"⚠️ {label}: no valid lot_transn_seq.")
        return pd.DataFrame()

    lot_filter = sql_in_clause("r.lot_transn_seq", lot_transn_seqs, numeric=True)
    sql_rawdata = f"""
    SELECT
      r.lot_transn_seq,
      r.slot_id,
      r.transn_occur_date,
      r.data_kind,
      r.test_point_no,
      r.coordinate_x,
      r.coordinate_y,
      r.value_x,
      r.value_y,
      r.mrc_x_valn,
      r.mrc_y_valn
    FROM ees_ds_eai.apc_nautil_dat_rawdata r
    WHERE r.impala_insert_time >= now() - interval {cfg.days + 10} days
      AND r.db_user = {sql_quote(cfg.db_user)}
      {lot_filter}
      AND r.data_kind IN ('RAWDATA', 'TESTDATA', 'PERSHOT')
    LIMIT {cfg.limit_rawdata_rows}
    """

    log(f"[{label}] RAWDATA query start")
    df_rawdata = bdq.getData(sql_rawdata)
    if df_rawdata.empty:
        log(f"⚠️ {label}: RAWDATA query returned 0 rows.")
        return df_rawdata

    df_rawdata = normalize_common_keys(df_rawdata)
    df_rawdata["transn_occur_date"] = pd.to_datetime(df_rawdata["transn_occur_date"].astype(str), errors="coerce")

    key = df_lotinfo[["lot_transn_seq", "slotid"]].drop_duplicates().copy()
    key = normalize_common_keys(key)

    before = len(df_rawdata)
    df_rawdata = df_rawdata.merge(
        key,
        left_on=["lot_transn_seq", "slot_id"],
        right_on=["lot_transn_seq", "slotid"],
        how="inner",
    ).reset_index(drop=True)
    log(f"[{label}] after lotinfo merge rows: {len(df_rawdata)} (drop {before - len(df_rawdata)})")
    log(f"[{label}] data_kind before batch filter:\n{df_rawdata['data_kind'].value_counts(dropna=False)}")

    before_batch = len(df_rawdata)
    df_rawdata = filter_latest_batch_by_gap_per_kind(df_rawdata, gap_seconds=cfg.rawdata_gap_seconds)
    log(f"[{label}] after latest-batch filter rows: {len(df_rawdata)} (drop {before_batch - len(df_rawdata)})")
    log(f"[{label}] data_kind after batch filter:\n{df_rawdata['data_kind'].value_counts(dropna=False)}")
    return df_rawdata


def fetch_expo_overlay(df_lotinfo_adi: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
    if df_lotinfo_adi.empty:
        log("⚠️ empty LOTINFO. EXPO_OVERLAY_LOT skipped.")
        return pd.DataFrame()
    lotids = df_lotinfo_adi["lotid"].dropna().astype(str).unique().tolist()[:1000]
    if not lotids:
        return pd.DataFrame()
    lot_filter = sql_in_clause("e.lot_id", lotids)
    pstepseq_filter = f"AND e.photo_step_seq = {sql_quote(cfg.target_pstepseq)}" if cfg.target_pstepseq else ""

    sql_expo = f"""
    SELECT
      CAST(e.apc_hist_index_no AS BIGINT) AS apc_hist_index_no,
      e.apc_trocs_hist_index_no,
      e.impala_insert_time,
      e.seq_no,
      e.lot_id,
      e.slot_id,
      e.photo_step_seq,
      e.metro_step_seq,
      e.photo_date,
      e.photo_transn_seq,
      e.mmo_mrc_ref_eqp_id
    FROM ees_ds_eai.apc_expo_overlay_lot e
    WHERE e.impala_insert_time >= now() - interval {cfg.expo_days + 5} days
      AND e.db_user = {sql_quote(cfg.db_user)}
      {lot_filter}
      {pstepseq_filter}
    LIMIT 100000
    """
    log("[EXPO] query start")
    df = bdq.getData(sql_expo)
    if df.empty:
        log("⚠️ EXPO_OVERLAY_LOT returned 0 rows")
        return df
    df = normalize_common_keys(df.rename(columns={"lot_id": "lotid", "photo_date": "P_TIME"}))
    df["P_TIME"] = pd.to_datetime(df["P_TIME"], errors="coerce")
    df = df.sort_values("P_TIME").drop_duplicates(["lotid", "slot_id"], keep="last")

    key = df_lotinfo_adi[["lotid", "slotid"]].drop_duplicates().copy()
    key = normalize_common_keys(key)
    df = df.merge(key, left_on=["lotid", "slot_id"], right_on=["lotid", "slotid"], how="inner")
    df = df.sort_values(["photo_transn_seq", "slotid"]).reset_index(drop=True)
    log(f"✅ EXPO rows: {len(df)}")
    return df


def fetch_paramdata_f1(df_lotinfo_adi: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
    if df_lotinfo_adi.empty:
        log("⚠️ empty LOTINFO. NAUTIL_PARAMDATA F1 skipped.")
        return pd.DataFrame()
    photo_values = df_lotinfo_adi["photo_transn_seq"].dropna().unique().tolist()[: cfg.max_photo_transn_seq]
    if not photo_values:
        log("⚠️ no photo_transn_seq. NAUTIL_PARAMDATA F1 skipped.")
        return pd.DataFrame()
    photo_filter = sql_in_clause("p.photo_transn_seq", photo_values, numeric=True)
    mstepseq_filter = f"AND p.mstepseq = {sql_quote(cfg.target_mstepseq)}" if cfg.target_mstepseq else ""
    sql_param = f"""
    SELECT
      p.photo_transn_seq,
      p.lotid,
      p.slotid,
      p.base_eqp_id1,
      p.impala_insert_time
    FROM ees_ds_eai.apc_nautil_paramdata p
    WHERE p.impala_insert_time >= now() - interval {cfg.days + 5} days
      AND p.db_user = {sql_quote(cfg.db_user)}
      {photo_filter}
      AND p.subname = 'F1'
      {mstepseq_filter}
    LIMIT 1000000
    """
    log("[PARAMDATA F1] query start")
    df = bdq.getData(sql_param)
    if df.empty:
        log("⚠️ PARAMDATA F1 returned 0 rows")
        return df
    df = normalize_common_keys(df)
    key = normalize_common_keys(df_lotinfo_adi[["photo_transn_seq", "slotid"]].drop_duplicates())
    df = df.merge(key, on=["photo_transn_seq", "slotid"], how="inner")
    df = df.sort_values(["photo_transn_seq", "slotid"]).reset_index(drop=True)
    log(f"✅ PARAMDATA F1 rows: {len(df)}")
    return df


# =============================================================================
# 3. Build ADI/OCO final measured DataFrames
# =============================================================================

def split_rawdata(df_rawdata: pd.DataFrame, include_pershot: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if df_rawdata.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    df = df_rawdata.copy()

    raw = df[df["data_kind"] == "RAWDATA"].copy().rename(columns={
        "test_point_no": "TEST",
        "coordinate_x": "DieX",
        "coordinate_y": "DieY",
        "value_x": "X_reg",
        "value_y": "Y_reg",
    })
    raw = remove_duplicated_columns(raw, "raw")

    test = df[df["data_kind"] == "TESTDATA"].copy().rename(columns={
        "test_point_no": "TEST",
        "value_x": "coordinate_X",
        "value_y": "coordinate_Y",
        "mrc_x_valn": "MRC_RX",
        "mrc_y_valn": "MRC_RY",
    })
    test_cols = ["lot_transn_seq", "slot_id", "TEST", "coordinate_X", "coordinate_Y", "MRC_RX", "MRC_RY"]
    test = test[pick_existing(test, test_cols)].drop_duplicates(["lot_transn_seq", "slot_id", "TEST"], keep="last")

    if include_pershot:
        pershot = df[df["data_kind"] == "PERSHOT"].copy().rename(columns={
            "test_point_no": "TEST",
            "coordinate_x": "DieX",
            "coordinate_y": "DieY",
            "value_x": "PSM_X",
            "value_y": "PSM_Y",
        })
        pcols = ["lot_transn_seq", "slot_id", "TEST", "DieX", "DieY", "PSM_X", "PSM_Y"]
        pershot = pershot[pick_existing(pershot, pcols)].drop_duplicates(
            ["lot_transn_seq", "slot_id", "TEST", "DieX", "DieY"], keep="last"
        )
    else:
        pershot = pd.DataFrame()

    return raw, test, pershot


def build_measurement_result(
    df_rawdata: pd.DataFrame,
    df_lotinfo: pd.DataFrame,
    df_expo: pd.DataFrame,
    df_param_f1: pd.DataFrame,
    label: str,
    include_pershot: bool,
) -> pd.DataFrame:
    raw, test, pershot = split_rawdata(df_rawdata, include_pershot=include_pershot)
    if raw.empty:
        log(f"⚠️ {label}: no RAWDATA rows. build skipped.")
        return pd.DataFrame()

    result = raw.copy()
    result = remove_duplicated_columns(result, f"{label}_result_init")

    lotinfo_u = normalize_common_keys(df_lotinfo.copy()).drop_duplicates(["lot_transn_seq", "slotid"], keep="last")
    result = result.merge(
        lotinfo_u,
        left_on=["lot_transn_seq", "slot_id"],
        right_on=["lot_transn_seq", "slotid"],
        how="left",
        validate="m:1",
        suffixes=("", "_lotinfo"),
    )
    result = remove_duplicated_columns(result, f"{label}_after_lotinfo")
    log(f"✅ {label}: LOTINFO joined -> {len(result)} rows")

    if not test.empty:
        result = result.merge(
            normalize_common_keys(test),
            on=["lot_transn_seq", "slot_id", "TEST"],
            how="left",
            validate="m:1",
            suffixes=("", "_test"),
        )
        result = remove_duplicated_columns(result, f"{label}_after_test")
        log(f"✅ {label}: TESTDATA joined")

    if include_pershot and not pershot.empty:
        result = result.merge(
            normalize_common_keys(pershot),
            on=["lot_transn_seq", "slot_id", "TEST", "DieX", "DieY"],
            how="left",
            validate="m:1",
            suffixes=("", "_psm"),
        )
        result = remove_duplicated_columns(result, f"{label}_after_pershot")
        log(f"✅ {label}: PERSHOT joined")

    if not df_expo.empty:
        expo_cols = [
            "lotid", "slot_id", "P_TIME", "apc_hist_index_no", "apc_trocs_hist_index_no", "mmo_mrc_ref_eqp_id"
        ]
        expo_u = normalize_common_keys(df_expo[pick_existing(df_expo, expo_cols)].copy())
        expo_u = expo_u.drop_duplicates(["lotid", "slot_id"], keep="last")
        result = result.merge(
            expo_u,
            on=["lotid", "slot_id"],
            how="left",
            validate="m:1",
        )
        log(f"✅ {label}: EXPO joined")

    if not df_param_f1.empty and "photo_transn_seq" in result.columns:
        result = normalize_common_keys(result)
        param = df_param_f1[["photo_transn_seq", "lotid", "slotid", "base_eqp_id1"]].copy()
        param = normalize_common_keys(param).drop_duplicates(["photo_transn_seq", "lotid", "slotid"], keep="last")
        result = result.merge(
            param,
            on=["photo_transn_seq", "lotid", "slotid"],
            how="left",
            validate="m:1",
        ).rename(columns={"base_eqp_id1": "Base_EQP1"})
        log(f"✅ {label}: PARAMDATA F1 joined")

    rename_map = {
        "pstepseq": "STEPSEQ",
        "lotid": "LOT_ID",
        "slotid": "Wafer",
        "peqpid": "P_EQPID",
        "ppid": "Photo_PPID",
        "chuckid": "ChuckID",
        "reticleid": "ReticleID",
        "steppitch_x": "STEP_PITCH_X",
        "steppitch_y": "STEP_PITCH_Y",
        "mapshift_x": "MAP_SHIFT_X",
        "mapshift_y": "MAP_SHIFT_Y",
        "dmargin_x": "Dmargin_X",
        "dmargin_y": "Dmargin_Y",
        "outlr_resdl_spec_ratio": "Outlier_Spec_Ratio",
        "chip_x_qty": "CHIP_X_NUM",
        "chip_y_qty": "CHIP_Y_NUM",
        "mmo_mrc_ref_eqp_id": "MMO_MRC_EQP",
        "mstepseq": "M_STEPSEQ",
        "timestamp": "M_TIME",
    }
    result = result.rename(columns=rename_map)
    result = result.drop(columns=["psm_mmo_ref_eqp_id"], errors="ignore")
    result = remove_duplicated_columns(result, f"{label}_after_rename")

    numeric_cols = [
        "TEST", "DieX", "DieY", "X_reg", "Y_reg", "MRC_RX", "MRC_RY", "PSM_X", "PSM_Y",
        "STEP_PITCH_X", "STEP_PITCH_Y", "MAP_SHIFT_X", "MAP_SHIFT_Y", "coordinate_X", "coordinate_Y",
    ]
    for col in numeric_cols:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    result = normalize_common_keys(result)
    log(f"🎯 {label}: measurement result -> {result.shape}")
    return result


def add_geometry_group_ids(df: pd.DataFrame, cfg: PipelineConfig, label: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df = df.copy()
    require_columns(df, ["TEST", "DieX", "DieY", "STEP_PITCH_X", "STEP_PITCH_Y", "MAP_SHIFT_X", "MAP_SHIFT_Y", "coordinate_X", "coordinate_Y"], f"{label} geometry")

    df["GROUP"] = pd.cut(df["TEST"], bins=[0, 80, 160, 240], labels=["E1", "E2", "E3"])
    if label.upper() == "OCO":
        # Original rule. Keep it explicit and easy to change.
        keep_group = "E2" if (cfg.target_mstepseq_oco or "")[2:5] == "077" else "E1"
        before = len(df)
        df = df[df["GROUP"] == keep_group].copy()
        log(f"[{label}] GROUP filter {keep_group}: {before} -> {len(df)}")

    for c in ["DieX", "DieY", "STEP_PITCH_X", "STEP_PITCH_Y", "MAP_SHIFT_X", "MAP_SHIFT_Y", "coordinate_X", "coordinate_Y"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["fcp_x"] = df["DieX"] * df["STEP_PITCH_X"] + df["MAP_SHIFT_X"]
    df["fcp_y"] = df["DieY"] * df["STEP_PITCH_Y"] + df["MAP_SHIFT_Y"]
    df["wf_x"] = df["fcp_x"] + df["coordinate_X"]
    df["wf_y"] = df["fcp_y"] + df["coordinate_Y"]
    df["radius"] = np.sqrt(df["wf_x"] ** 2 + df["wf_y"] ** 2)

    # UNIQUE_IDs. Missing columns are filled with empty strings to avoid runtime failure.
    base_cols = ["STEPSEQ", "P_EQPID", "Photo_PPID", "MMO_MRC_EQP", "P_TIME", "M_TIME", "LOT_ID", "Wafer"]
    for c in base_cols:
        if c not in df.columns:
            df[c] = ""
    base = df[base_cols].astype("string").fillna("").agg("_".join, axis=1)
    df["UNIQUE_ID3"] = base
    df["UNIQUE_ID"] = base + "_" + df["GROUP"].astype("string").fillna("")
    df["UNIQUE_ID2"] = base + "_" + df["TEST"].astype("string") + "_" + df["DieX"].astype("string") + "_" + df["DieY"].astype("string") + "_" + df["GROUP"].astype("string")
    df["UNIQUE_ID4"] = base + "_" + df["DieX"].astype("string") + "_" + df["DieY"].astype("string") + "_" + df["GROUP"].astype("string")

    sx = df["STEP_PITCH_X"].to_numpy(dtype=float) / 2.0
    sy = df["STEP_PITCH_Y"].to_numpy(dtype=float) / 2.0
    x = df["fcp_x"].to_numpy(dtype=float)
    y = df["fcp_y"].to_numpy(dtype=float)
    d2 = np.maximum.reduce([
        (x - sx) ** 2 + (y - sy) ** 2,
        (x + sx) ** 2 + (y - sy) ** 2,
        (x - sx) ** 2 + (y + sy) ** 2,
        (x + sx) ** 2 + (y + sy) ** 2,
    ])
    df["Max_Corner_Distance"] = np.sqrt(d2)
    df["Is_Edge_Shot"] = df["Max_Corner_Distance"] > cfg.wafer_radius_um

    desired = [
        "UNIQUE_ID", "UNIQUE_ID2", "UNIQUE_ID3", "UNIQUE_ID4",
        "STEPSEQ", "LOT_ID", "Wafer", "P_EQPID", "Photo_PPID", "P_TIME", "M_TIME",
        "ChuckID", "ReticleID", "Base_EQP1", "MMO_MRC_EQP",
        "GROUP", "TEST", "DieX", "DieY",
        "STEP_PITCH_X", "STEP_PITCH_Y", "MAP_SHIFT_X", "MAP_SHIFT_Y", "coordinate_X", "coordinate_Y",
        "fcp_x", "fcp_y", "wf_x", "wf_y", "radius", "CHIP_X_NUM", "CHIP_Y_NUM",
        "Outlier_Spec_Ratio", "Dmargin_X", "Dmargin_Y",
        "X_reg", "Y_reg", "MRC_RX", "MRC_RY", "PSM_X", "PSM_Y",
        "Is_Edge_Shot", "Max_Corner_Distance", "M_STEPSEQ", "photo_transn_seq",
        "apc_hist_index_no", "apc_trocs_hist_index_no",
    ]
    df = df[pick_existing(df, desired)].copy()
    df = normalize_common_keys(df)
    log(f"✅ {label}: geometry/group/ID done -> {df.shape}")
    return df


# =============================================================================
# 4. KMRC decorrection
# =============================================================================

def osr_wk20p_rk20p(x, y, rx, ry) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    rx = np.asarray(rx, dtype=float)
    ry = np.asarray(ry, dtype=float)
    X_dx = np.vstack([
        np.ones(len(x)),
        x / 1e6, -y / 1e6,
        (x ** 2) / 1e12, (x * y) / 1e12, (y ** 2) / 1e12,
        (x ** 3) / 1e15, (x ** 2 * y) / 1e15, (x * y ** 2) / 1e15, (y ** 3) / 1e15,
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12,
    ]).T
    X_dy = np.vstack([
        np.ones(len(y)),
        y / 1e6, x / 1e6,
        (y ** 2) / 1e12, (y * x) / 1e12, (x ** 2) / 1e12,
        (y ** 3) / 1e15, (y ** 2 * x) / 1e15, (y * x ** 2) / 1e15, (x ** 3) / 1e15,
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12, (rx ** 3) / 1e12,
    ]).T
    return X_dx, X_dy


COEFF_KEYS_DX = [
    "WK1", "WK3", "WK5", "WK7", "WK9", "WK11", "WK13", "WK15", "WK17", "WK19",
    "RK3", "RK5", "RK7", "RK9", "RK11", "RK13", "RK15", "RK17", "RK19",
]
COEFF_KEYS_DY = [
    "WK2", "WK4", "WK6", "WK8", "WK10", "WK12", "WK14", "WK16", "WK18", "WK20",
    "RK4", "RK6", "RK8", "RK10", "RK12", "RK14", "RK16", "RK18", "RK20",
]
KPARA_TO_COL = {**{f"WK{i}": f"wk{i}" for i in range(1, 21)}, **{f"RK{i}": f"rk{i}" for i in range(3, 21)}}


def fetch_kmrc(df_final: pd.DataFrame, cfg: PipelineConfig, label: str) -> pd.DataFrame:
    if df_final.empty or "photo_transn_seq" not in df_final.columns:
        log(f"⚠️ {label}: df_final empty or no photo_transn_seq. KMRC skipped.")
        return pd.DataFrame()
    photo_values = df_final["photo_transn_seq"].dropna().unique().tolist()[: cfg.max_photo_transn_seq]
    if not photo_values:
        return pd.DataFrame()
    photo_filter = sql_in_clause("p.photo_transn_seq", photo_values, numeric=True)
    mstepseq_filter = f"AND p.mstepseq = {sql_quote(cfg.target_mstepseq)}" if cfg.target_mstepseq else ""
    wk_cols = ", ".join([f"p.wk{i}" for i in range(1, 21)])
    rk_cols = ", ".join([f"p.rk{i}" for i in range(3, 21)])
    sql_kmrc = f"""
    SELECT
      p.photo_transn_seq,
      p.lotid,
      p.slotid,
      p.subname,
      {wk_cols},
      {rk_cols},
      p.impala_insert_time
    FROM ees_ds_eai.apc_nautil_paramdata p
    WHERE p.impala_insert_time >= now() - interval {cfg.days + 10} days
      AND p.db_user = {sql_quote(cfg.db_user)}
      {photo_filter}
      AND p.subname = 'CMP'
      {mstepseq_filter}
    LIMIT 100000
    """
    log(f"[{label}] KMRC query start")
    df = bdq.getData(sql_kmrc)
    if df.empty:
        log(f"⚠️ {label}: KMRC returned 0 rows")
        return df
    df = normalize_common_keys(df)
    df = df.sort_values("impala_insert_time").drop_duplicates(["photo_transn_seq", "lotid", "slotid"], keep="last")
    log(f"✅ {label}: KMRC rows after dedup: {len(df)}")
    return df


def apply_kmrc_decorrection(df_final: pd.DataFrame, df_kmrc: pd.DataFrame, label: str) -> pd.DataFrame:
    if df_final.empty or df_kmrc.empty:
        log(f"⚠️ {label}: KMRC decorrection skipped.")
        return df_final.copy()

    required_k_cols = [KPARA_TO_COL[k] for k in COEFF_KEYS_DX + COEFF_KEYS_DY]
    missing = [c for c in sorted(set(required_k_cols)) if c not in df_kmrc.columns]
    if missing:
        log(f"❌ {label}: KMRC missing columns: {missing}")
        return df_final.copy()

    df = normalize_match_key_columns(normalize_common_keys(df_final), lot_col="LOT_ID", wafer_col="Wafer")
    kmrc = normalize_match_key_columns(normalize_common_keys(df_kmrc), lot_col="lotid", wafer_col="slotid")
    kmrc_idx = kmrc.set_index(["_photo_key", "_lot_key", "_wafer_key"])

    mrc_fit_x = pd.Series(np.nan, index=df.index, dtype=float)
    mrc_fit_y = pd.Series(np.nan, index=df.index, dtype=float)
    success = 0
    skip = 0

    for key, grp in df.groupby(["_photo_key", "_lot_key", "_wafer_key"], dropna=False):
        if key not in kmrc_idx.index:
            skip += 1
            continue
        row = kmrc_idx.loc[key]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        try:
            kx = np.array([float(row[KPARA_TO_COL[k]]) for k in COEFF_KEYS_DX], dtype=float)
            ky = np.array([float(row[KPARA_TO_COL[k]]) for k in COEFF_KEYS_DY], dtype=float)
        except Exception as exc:
            log(f"⚠️ {label} {key}: K extraction failed: {exc}")
            skip += 1
            continue
        if np.isnan(kx).any() or np.isnan(ky).any():
            skip += 1
            continue
        X_dx, X_dy = osr_wk20p_rk20p(grp["fcp_x"], grp["fcp_y"], grp["coordinate_X"], grp["coordinate_Y"])
        mrc_fit_x.loc[grp.index] = X_dx.dot(kx) * -1
        mrc_fit_y.loc[grp.index] = X_dy.dot(ky) * -1
        success += 1

    df["mrc_fit_x"] = mrc_fit_x
    df["mrc_fit_y"] = mrc_fit_y
    df["X_reg_demrc"] = pd.to_numeric(df["X_reg"], errors="coerce") - df["mrc_fit_x"]
    df["Y_reg_demrc"] = pd.to_numeric(df["Y_reg"], errors="coerce") - df["mrc_fit_y"]

    if "PSM_X" in df.columns and "PSM_Y" in df.columns:
        df["raw_x"] = df["X_reg_demrc"] - pd.to_numeric(df["PSM_X"], errors="coerce")
        df["raw_y"] = df["Y_reg_demrc"] - pd.to_numeric(df["PSM_Y"], errors="coerce")

    df = df.drop(columns=["_photo_key", "_lot_key", "_wafer_key"], errors="ignore")
    log(f"✅ {label}: KMRC decorrection done. success groups={success}, skipped groups={skip}, valid rows={df['mrc_fit_x'].notna().sum()}/{len(df)}")
    return df


# =============================================================================
# 5. APC shot input, PSM/TROCS fitting at measured points
# =============================================================================

def fetch_lot_hist_apc(df_lotinfo_adi: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
    if df_lotinfo_adi.empty:
        return pd.DataFrame()
    lotids = df_lotinfo_adi["lotid"].dropna().astype(str).unique().tolist()[:1000]
    if not lotids:
        return pd.DataFrame()
    lot_filter = sql_in_clause("lot_id", lotids)
    pstepseq_filter = f"AND step_seq = {sql_quote(cfg.target_pstepseq)}" if cfg.target_pstepseq else ""

    sql_main = f"""
    SELECT
        CAST(apc_hist_index_no AS BIGINT) AS apc_hist_index_no,
        apc_group_name, lot_id, step_seq, eqp_id, sub_eqp_id, ppid, reticle_id,
        run_type, event_tsdt, tkin_tsdt
    FROM ees_ds_eai.apc_apc_lot_hist
    WHERE db_user = {sql_quote(cfg.db_user_apc)}
        AND event_tsdt >= now() - interval {cfg.days + 5} days
        AND event_tsdt <= now() - interval {cfg.exclude_recent_days} days
        AND apc_group_name != 'PHOTO_EEXY_GRP'
        AND save_type != 'A'
        {lot_filter}
        {pstepseq_filter}
    """
    sql_eexy = f"""
    SELECT
        CAST(apc_hist_index_no AS BIGINT) AS apc_trocs_hist_index_no,
        lot_id, step_seq, eqp_id, sub_eqp_id, tkin_tsdt, event_tsdt AS event_tsdt_eexy
    FROM ees_ds_eai.apc_apc_lot_hist
    WHERE db_user = {sql_quote(cfg.db_user_apc)}
        AND event_tsdt >= now() - interval {cfg.days + 5} days
        AND event_tsdt <= now() - interval {cfg.exclude_recent_days} days
        AND apc_group_name = 'PHOTO_EEXY_GRP'
        AND save_type != 'A'
        {lot_filter}
        {pstepseq_filter}
    """
    log("[APC LOT HIST] main query start")
    main = bdq.getData(sql_main)
    log(f"[APC LOT HIST] main rows: {len(main)}")
    log("[APC LOT HIST] EEXY query start")
    eexy = bdq.getData(sql_eexy)
    log(f"[APC LOT HIST] EEXY rows: {len(eexy)}")

    if main.empty:
        return pd.DataFrame()
    if eexy.empty:
        main["apc_trocs_hist_index_no"] = pd.NA
        return normalize_common_keys(main)

    merge_keys = ["lot_id", "step_seq", "eqp_id", "sub_eqp_id"]
    for col in merge_keys:
        main[col] = clean_str_series(main[col])
        eexy[col] = clean_str_series(eexy[col])
    main["tkin_tsdt"] = pd.to_datetime(main["tkin_tsdt"], errors="coerce")
    main["event_tsdt"] = pd.to_datetime(main["event_tsdt"], errors="coerce")
    eexy["tkin_tsdt"] = pd.to_datetime(eexy["tkin_tsdt"], errors="coerce")
    eexy["event_tsdt_eexy"] = pd.to_datetime(eexy["event_tsdt_eexy"], errors="coerce")

    main_valid = main.dropna(subset=["tkin_tsdt"]).sort_values("tkin_tsdt")
    eexy_u = (
        eexy.dropna(subset=["tkin_tsdt"])
        .sort_values("event_tsdt_eexy")
        .drop_duplicates(merge_keys + ["tkin_tsdt"], keep="last")
        .sort_values("tkin_tsdt")
    )
    out = pd.merge_asof(
        main_valid,
        eexy_u[merge_keys + ["tkin_tsdt", "apc_trocs_hist_index_no"]],
        on="tkin_tsdt",
        by=merge_keys,
        tolerance=pd.Timedelta("60s"),
        direction="nearest",
    )

    invalid = main[main["tkin_tsdt"].isna()].copy()
    if not invalid.empty:
        invalid["apc_trocs_hist_index_no"] = pd.NA
        out = pd.concat([out, invalid], ignore_index=True)

    out = normalize_common_keys(out)
    # Safer than original lot_id+sub_eqp_id only: keep latest per richer process key.
    dedup_keys = [c for c in ["lot_id", "step_seq", "eqp_id", "sub_eqp_id", "ppid", "reticle_id"] if c in out.columns]
    out = out.sort_values("event_tsdt").drop_duplicates(dedup_keys, keep="last").reset_index(drop=True)
    log(f"✅ APC LOT HIST merged rows: {len(out)}, EEXY match rate: {out['apc_trocs_hist_index_no'].notna().mean() * 100:.1f}%")
    return out


def fetch_shot_input_apc(df_lot_hist_apc: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
    if df_lot_hist_apc.empty or "apc_trocs_hist_index_no" not in df_lot_hist_apc.columns:
        return pd.DataFrame()
    idxs = df_lot_hist_apc["apc_trocs_hist_index_no"].dropna().astype("int64").unique().tolist()
    if not idxs:
        log("⚠️ no apc_trocs_hist_index_no. shot_input skipped.")
        return pd.DataFrame()
    idx_filter = sql_in_clause("CAST(apc_hist_index_no AS BIGINT)", idxs, numeric=True)
    mrc_cols = ", ".join([f"mrc_k{i}_valn" for i in range(1, 73)])
    rk_cols = ", ".join([f"rk{i}_valn" for i in range(1, 73)])
    sql_shot = f"""
    SELECT
        CAST(apc_hist_index_no AS BIGINT) AS apc_hist_index_no,
        pos_x_valn,
        pos_y_valn,
        {mrc_cols},
        {rk_cols}
    FROM ees_ds_eai.apc_apc_photo_shot_input_hist
    WHERE db_user = {sql_quote(cfg.db_user_apc)}
        AND impala_insert_time >= now() - interval {cfg.days + 10} days
        {idx_filter}
    """
    log("[SHOT INPUT HIST] query start")
    shot = bdq.getData(sql_shot)
    if shot.empty:
        return shot
    shot = normalize_common_keys(shot)
    num_cols = ["pos_x_valn", "pos_y_valn"] + [f"mrc_k{i}_valn" for i in range(1, 73)] + [f"rk{i}_valn" for i in range(1, 73)]
    for c in num_cols:
        if c in shot.columns:
            shot[c] = pd.to_numeric(shot[c], errors="coerce")

    lot_cols = ["apc_hist_index_no", "apc_trocs_hist_index_no", "lot_id", "step_seq", "eqp_id", "sub_eqp_id", "ppid", "reticle_id", "run_type", "event_tsdt", "tkin_tsdt"]
    lot_subset = normalize_common_keys(df_lot_hist_apc[pick_existing(df_lot_hist_apc, lot_cols)].copy())
    lot_subset = lot_subset.dropna(subset=["apc_trocs_hist_index_no"]).sort_values(["event_tsdt", "tkin_tsdt"])
    lot_subset = lot_subset.drop_duplicates(["apc_trocs_hist_index_no"], keep="last")

    joined = shot.merge(
        lot_subset,
        left_on="apc_hist_index_no",
        right_on="apc_trocs_hist_index_no",
        how="left",
        suffixes=("_shot", "_lot"),
        validate="many_to_one",
    )
    joined = joined.rename(columns={"apc_hist_index_no_lot": "apc_hist_index_no"})
    joined = joined.drop(columns=["apc_hist_index_no_shot", "apc_trocs_hist_index_no"], errors="ignore")
    joined = normalize_common_keys(joined)
    joined["pos_x_valn"] = pd.to_numeric(joined["pos_x_valn"], errors="coerce") * 1000.0
    joined["pos_y_valn"] = pd.to_numeric(joined["pos_y_valn"], errors="coerce") * 1000.0
    log(f"✅ SHOT INPUT joined rows: {len(joined)}, matched lot rows: {joined['lot_id'].notna().sum()}")
    return joined


def format_coord_key(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").round(2)
    return s.map(lambda v: f"{v:.2f}" if pd.notna(v) else "<NA>")


def build_psm_match_key(lot_series, sub_eqp_series, x_series, y_series) -> pd.Series:
    lot = lot_series.astype(str).str.strip()
    sub = sub_eqp_series.astype(str).str.strip()
    return lot + "_" + sub + "_" + format_coord_key(x_series) + "_" + format_coord_key(y_series)


def cpe_k_to_fit(rx, ry) -> tuple[np.ndarray, np.ndarray]:
    rx = np.asarray(rx, dtype=float)
    ry = np.asarray(ry, dtype=float)
    X_dx = np.vstack([
        np.ones(len(rx)),
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12,
        (rx ** 4) / 1e19, (rx ** 3 * ry) / 1e19, (rx ** 2 * ry ** 2) / 1e19, (rx * ry ** 3) / 1e19, (ry ** 4) / 1e19,
        (rx ** 5) / 1e23, (rx ** 4 * ry) / 1e23, (rx ** 3 * ry ** 2) / 1e23, (rx ** 2 * ry ** 3) / 1e23, (rx * ry ** 4) / 1e23, (ry ** 5) / 1e23,
        (rx ** 6) / 1e27, (rx ** 5 * ry) / 1e27, (rx ** 4 * ry ** 2) / 1e27, (rx ** 3 * ry ** 3) / 1e27, (rx ** 2 * ry ** 4) / 1e27, (rx * ry ** 5) / 1e27, (ry ** 6) / 1e27,
        (rx ** 7) / 1e31, (rx ** 6 * ry) / 1e31, (rx ** 5 * ry ** 2) / 1e31, (rx ** 4 * ry ** 3) / 1e31, (rx ** 3 * ry ** 4) / 1e31, (rx ** 2 * ry ** 5) / 1e31, (rx * ry ** 6) / 1e31, (ry ** 7) / 1e31,
    ]).T
    X_dy = np.vstack([
        np.ones(len(ry)),
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12, (rx ** 3) / 1e12,
        (ry ** 4) / 1e19, (ry ** 3 * rx) / 1e19, (ry ** 2 * rx ** 2) / 1e19, (ry * rx ** 3) / 1e19, (rx ** 4) / 1e19,
        (ry ** 5) / 1e23, (ry ** 4 * rx) / 1e23, (ry ** 3 * rx ** 2) / 1e23, (ry ** 2 * rx ** 3) / 1e23, (ry * rx ** 4) / 1e23, (rx ** 5) / 1e23,
        (ry ** 6) / 1e27, (ry ** 5 * rx) / 1e27, (ry ** 4 * rx ** 2) / 1e27, (ry ** 3 * rx ** 3) / 1e27, (ry ** 2 * rx ** 4) / 1e27, (ry * rx ** 5) / 1e27, (rx ** 6) / 1e27,
        (ry ** 7) / 1e31, (ry ** 6 * rx) / 1e31, (ry ** 5 * rx ** 2) / 1e31, (ry ** 4 * rx ** 3) / 1e31, (ry ** 3 * rx ** 4) / 1e31, (ry ** 2 * rx ** 5) / 1e31, (ry * rx ** 6) / 1e31, (rx ** 7) / 1e31,
    ]).T
    return X_dx, X_dy


def prepare_shot_input_for_matching(df_shot_input: pd.DataFrame, df_lotinfo_adi: pd.DataFrame) -> pd.DataFrame:
    if df_shot_input.empty:
        return df_shot_input.copy()
    df = df_shot_input.copy()
    df["lot_id"] = clean_str_series(df["lot_id"])
    df["sub_eqp_id"] = clean_str_series(df["sub_eqp_id"])
    df["match_key"] = build_psm_match_key(df["lot_id"], df["sub_eqp_id"], df["pos_x_valn"], df["pos_y_valn"])

    # Keep only lot/sub_eqp combinations present in target wafers.
    if not df_lotinfo_adi.empty:
        keys = df_lotinfo_adi[["lotid", "slotid"]].copy()
        keys = normalize_common_keys(keys)
        keys["sub_eqp_id"] = np.where(keys["slotid"].astype("Int64") % 2 == 1, "EX1", "EX2")
        keys = keys.rename(columns={"lotid": "lot_id"})[["lot_id", "sub_eqp_id"]].drop_duplicates()
        df = df.merge(keys, on=["lot_id", "sub_eqp_id"], how="inner")
    return df


def add_final_match_key(df_final: pd.DataFrame) -> pd.DataFrame:
    if df_final.empty:
        return df_final.copy()
    df = df_final.copy()
    df["_slot_key"] = to_int64_nullable(df["Wafer"])
    df["sub_eqp_id"] = np.where(df["_slot_key"] % 2 == 1, "EX1", "EX2")
    df["match_key"] = build_psm_match_key(df["LOT_ID"], df["sub_eqp_id"], df["fcp_x"], df["fcp_y"])
    return df.drop(columns=["_slot_key"], errors="ignore")


def shot_fitting_from_input(
    df_final: pd.DataFrame,
    df_input: pd.DataFrame,
    k_col_prefix: str,
    result_prefix: str,
    n_k: int = 72,
) -> pd.DataFrame:
    if df_final.empty or df_input.empty:
        return df_final.copy()
    if "match_key" not in df_final.columns:
        df_final = add_final_match_key(df_final)
    if "match_key" not in df_input.columns:
        raise ValueError("df_input must have match_key. Run prepare_shot_input_for_matching first.")

    k_cols = [f"{k_col_prefix}{i}_valn" for i in range(1, n_k + 1)]
    missing = [c for c in k_cols if c not in df_input.columns]
    if missing:
        log(f"⚠️ {result_prefix}: missing K columns count={len(missing)}, first={missing[:5]}")
        return df_final.copy()

    inp = df_input.copy()
    for c in ["event_tsdt", "tkin_tsdt"]:
        if c in inp.columns:
            inp[c] = pd.to_datetime(inp[c], errors="coerce")
    sort_cols = [c for c in ["event_tsdt", "tkin_tsdt"] if c in inp.columns]
    if sort_cols:
        inp = inp.sort_values(sort_cols)
    inp = inp.dropna(subset=["match_key"]).drop_duplicates("match_key", keep="last")
    inp_idx = inp.set_index("match_key")

    out = df_final.copy()
    fit_x = pd.Series(np.nan, index=out.index, dtype=float)
    fit_y = pd.Series(np.nan, index=out.index, dtype=float)
    success = 0
    skip = 0

    for mk, grp in out.groupby("match_key", dropna=False):
        if pd.isna(mk) or mk not in inp_idx.index:
            skip += 1
            continue
        row = inp_idx.loc[mk]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        try:
            kv = row[k_cols].values.astype(float)
        except Exception:
            skip += 1
            continue
        if np.isnan(kv).all():
            skip += 1
            continue
        kv = np.nan_to_num(kv, nan=0.0)
        kx = kv[::2]
        ky = kv[1::2]
        rx = pd.to_numeric(grp["coordinate_X"], errors="coerce").values.astype(float)
        ry = pd.to_numeric(grp["coordinate_Y"], errors="coerce").values.astype(float)
        if np.isnan(rx).any() or np.isnan(ry).any():
            skip += 1
            continue
        X_dx, X_dy = cpe_k_to_fit(rx, ry)
        fit_x.loc[grp.index] = X_dx.dot(kx)
        fit_y.loc[grp.index] = X_dy.dot(ky)
        success += 1

    out[f"{result_prefix}_x"] = fit_x
    out[f"{result_prefix}_y"] = fit_y
    log(f"✅ {result_prefix}: fitting done. success groups={success}, skipped={skip}, valid rows={fit_x.notna().sum()}/{len(out)}")
    return out


def add_raw_from_psm_fit_if_needed(df: pd.DataFrame, label: str) -> pd.DataFrame:
    df = df.copy()
    if "raw_x" not in df.columns and {"X_reg_demrc", "psm_fit_x"}.issubset(df.columns):
        df["raw_x"] = pd.to_numeric(df["X_reg_demrc"], errors="coerce") - pd.to_numeric(df["psm_fit_x"], errors="coerce")
    if "raw_y" not in df.columns and {"Y_reg_demrc", "psm_fit_y"}.issubset(df.columns):
        df["raw_y"] = pd.to_numeric(df["Y_reg_demrc"], errors="coerce") - pd.to_numeric(df["psm_fit_y"], errors="coerce")
    if {"raw_x", "raw_y"}.issubset(df.columns):
        log(f"✅ {label}: raw_x/raw_y available rows X/Y = {df['raw_x'].notna().sum()}/{df['raw_y'].notna().sum()}")
    return df


# =============================================================================
# 6. Wafer-level WK/RK joint regression
# =============================================================================

def fit_lstsq(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coef, X @ coef


def run_company_joint_regression(df: pd.DataFrame, label: str = "ADI", min_points: int = 30) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df.copy(), pd.DataFrame(), pd.DataFrame()
    required = ["LOT_ID", "Wafer", "raw_x", "raw_y", "fcp_x", "fcp_y", "coordinate_X", "coordinate_Y"]
    require_columns(df, required, f"{label} joint regression")
    out = df.copy()
    for c in required[2:]:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    result_cols = ["wk_fit_x", "wk_fit_y", "rk_fit_x", "rk_fit_y", "total_fit_x", "total_fit_y", "raw_minus_total_fit_x", "raw_minus_total_fit_y"]
    for c in result_cols:
        out[c] = np.nan
    coef_rows = []
    summary_rows = []

    for (lot, wafer), grp in out.groupby(["LOT_ID", "Wafer"], dropna=False):
        mask = grp[["raw_x", "raw_y", "fcp_x", "fcp_y", "coordinate_X", "coordinate_Y"]].notna().all(axis=1)
        work = grp.loc[mask].copy()
        n = len(work)
        if n < min_points:
            summary_rows.append({"LOT_ID": lot, "Wafer": wafer, "n_total": len(grp), "n_valid": n, "status": "skip_too_few_points"})
            continue
        X_dx, X_dy = osr_wk20p_rk20p(work["fcp_x"], work["fcp_y"], work["coordinate_X"], work["coordinate_Y"])
        raw_x = work["raw_x"].to_numpy(dtype=float)
        raw_y = work["raw_y"].to_numpy(dtype=float)
        coef_x, pred_x = fit_lstsq(X_dx, raw_x)
        coef_y, pred_y = fit_lstsq(X_dy, raw_y)
        wk_x = X_dx[:, :10] @ coef_x[:10]
        rk_x = X_dx[:, 10:] @ coef_x[10:]
        wk_y = X_dy[:, :10] @ coef_y[:10]
        rk_y = X_dy[:, 10:] @ coef_y[10:]
        res_x = raw_x - pred_x
        res_y = raw_y - pred_y
        idx = work.index
        out.loc[idx, "wk_fit_x"] = wk_x
        out.loc[idx, "rk_fit_x"] = rk_x
        out.loc[idx, "total_fit_x"] = pred_x
        out.loc[idx, "raw_minus_total_fit_x"] = res_x
        out.loc[idx, "wk_fit_y"] = wk_y
        out.loc[idx, "rk_fit_y"] = rk_y
        out.loc[idx, "total_fit_y"] = pred_y
        out.loc[idx, "raw_minus_total_fit_y"] = res_y

        coef_row = {"LOT_ID": lot, "Wafer": wafer, "n_total": len(grp), "n_valid": n}
        for name, val in zip(COEFF_KEYS_DX, coef_x):
            coef_row[f"{name}_X"] = val
        for name, val in zip(COEFF_KEYS_DY, coef_y):
            coef_row[f"{name}_Y"] = val
        coef_rows.append(coef_row)
        summary_rows.append({
            "LOT_ID": lot, "Wafer": wafer, "n_total": len(grp), "n_valid": n,
            "rms_raw_x": float(np.sqrt(np.nanmean(raw_x ** 2))),
            "rms_raw_y": float(np.sqrt(np.nanmean(raw_y ** 2))),
            "rms_residual_x": float(np.sqrt(np.nanmean(res_x ** 2))),
            "rms_residual_y": float(np.sqrt(np.nanmean(res_y ** 2))),
            "status": "ok",
        })

    coef_df = pd.DataFrame(coef_rows)
    summary_df = pd.DataFrame(summary_rows)
    log(f"✅ {label}: joint regression done. coef rows={len(coef_df)}, summary rows={len(summary_df)}")
    return out, coef_df, summary_df


# =============================================================================
# 7. Pipeline orchestration
# =============================================================================

def run_pipeline(cfg: PipelineConfig) -> dict[str, pd.DataFrame]:
    out_dir = ensure_output_dir(cfg)

    df_lotinfo_adi, df_lotinfo_oco, df_lotinfo_save = fetch_lotinfo_pair(cfg)
    if cfg.save_intermediate_excel and not df_lotinfo_save.empty:
        save_excel_if_small(df_lotinfo_save, out_dir / "NAUTIL_DAT_LOTINFO_clean.xlsx", cfg.max_excel_rows)

    df_rawdata_oco = fetch_rawdata_from_lotinfo(df_lotinfo_oco, cfg, label="OCO")
    df_rawdata_adi = fetch_rawdata_from_lotinfo(df_lotinfo_adi, cfg, label="ADI")

    df_expo = fetch_expo_overlay(df_lotinfo_adi, cfg)
    df_param_f1 = fetch_paramdata_f1(df_lotinfo_adi, cfg)
    if cfg.save_intermediate_excel:
        save_excel_if_small(df_expo, out_dir / "EXPO_OVERLAY_LOT_clean.xlsx", cfg.max_excel_rows)
        save_excel_if_small(df_param_f1, out_dir / "NAUTIL_PARAMDATA_F1_clean.xlsx", cfg.max_excel_rows)

    df_result_adi = build_measurement_result(df_rawdata_adi, df_lotinfo_adi, df_expo, df_param_f1, label="ADI", include_pershot=True)
    df_result_oco = build_measurement_result(df_rawdata_oco, df_lotinfo_oco, df_expo, df_param_f1, label="OCO", include_pershot=False)

    df_final_adi = add_geometry_group_ids(df_result_adi, cfg, label="ADI")
    df_final_oco = add_geometry_group_ids(df_result_oco, cfg, label="OCO")

    df_kmrc_adi = fetch_kmrc(df_final_adi, cfg, label="ADI")
    df_kmrc_oco = fetch_kmrc(df_final_oco, cfg, label="OCO")
    df_final_adi = apply_kmrc_decorrection(df_final_adi, df_kmrc_adi, label="ADI")
    df_final_oco = apply_kmrc_decorrection(df_final_oco, df_kmrc_oco, label="OCO")

    if cfg.save_intermediate_excel:
        save_excel_if_small(df_kmrc_adi, out_dir / "df_kmrc_adi_clean.xlsx", cfg.max_excel_rows)
        save_excel_if_small(df_kmrc_oco, out_dir / "df_kmrc_oco_clean.xlsx", cfg.max_excel_rows)

    df_lot_hist_apc = pd.DataFrame()
    df_shot_input = pd.DataFrame()
    if cfg.run_apc_psm_trocs:
        df_lot_hist_apc = fetch_lot_hist_apc(df_lotinfo_adi, cfg)
        df_shot_input = fetch_shot_input_apc(df_lot_hist_apc, cfg)
        df_shot_input = prepare_shot_input_for_matching(df_shot_input, df_lotinfo_adi)
        if cfg.save_intermediate_excel:
            save_excel_if_small(df_shot_input, out_dir / "df_shot_input_clean.xlsx", cfg.max_excel_rows)

        df_final_adi = add_final_match_key(df_final_adi)
        df_final_oco = add_final_match_key(df_final_oco)
        df_final_adi = shot_fitting_from_input(df_final_adi, df_shot_input, k_col_prefix="mrc_k", result_prefix="psm_fit")
        df_final_oco = shot_fitting_from_input(df_final_oco, df_shot_input, k_col_prefix="mrc_k", result_prefix="psm_fit")
        df_final_adi = shot_fitting_from_input(df_final_adi, df_shot_input, k_col_prefix="rk", result_prefix="trocs_fit")
        df_final_oco = shot_fitting_from_input(df_final_oco, df_shot_input, k_col_prefix="rk", result_prefix="trocs_fit")
        df_final_adi = add_raw_from_psm_fit_if_needed(df_final_adi, label="ADI")
        df_final_oco = add_raw_from_psm_fit_if_needed(df_final_oco, label="OCO")

        # Same filter as original: keep rows with valid MMO_MRC_EQP.
        for name, frame in [("ADI", df_final_adi), ("OCO", df_final_oco)]:
            if "MMO_MRC_EQP" in frame.columns:
                before = len(frame)
                frame2 = frame[frame["MMO_MRC_EQP"].notna() & (frame["MMO_MRC_EQP"].astype(str).str.strip() != "")].copy()
                log(f"[{name}] MMO_MRC_EQP filter: {before} -> {len(frame2)}")
                if name == "ADI":
                    df_final_adi = frame2
                else:
                    df_final_oco = frame2

    coef_adi = pd.DataFrame()
    coef_oco = pd.DataFrame()
    summary_adi = pd.DataFrame()
    summary_oco = pd.DataFrame()
    if cfg.run_wk_rk_regression:
        df_final_adi, coef_adi, summary_adi = run_company_joint_regression(df_final_adi, label="ADI", min_points=30)
        df_final_oco, coef_oco, summary_oco = run_company_joint_regression(df_final_oco, label="OCO", min_points=30)

    if cfg.save_final_parquet:
        if not df_final_adi.empty:
            df_final_adi.to_parquet(out_dir / "ADI_clean.parquet", index=False)
            log(f"saved: {out_dir / 'ADI_clean.parquet'}")
        if not df_final_oco.empty:
            df_final_oco.to_parquet(out_dir / "OCO_clean.parquet", index=False)
            log(f"saved: {out_dir / 'OCO_clean.parquet'}")
    if cfg.save_intermediate_excel:
        save_excel_if_small(coef_adi, out_dir / "coef_adi_global_clean.xlsx", cfg.max_excel_rows)
        save_excel_if_small(coef_oco, out_dir / "coef_oco_global_clean.xlsx", cfg.max_excel_rows)
        save_excel_if_small(summary_adi, out_dir / "summary_adi_clean.xlsx", cfg.max_excel_rows)
        save_excel_if_small(summary_oco, out_dir / "summary_oco_clean.xlsx", cfg.max_excel_rows)

    return {
        "df_lotinfo_adi": df_lotinfo_adi,
        "df_lotinfo_oco": df_lotinfo_oco,
        "df_rawdata_adi": df_rawdata_adi,
        "df_rawdata_oco": df_rawdata_oco,
        "df_expo": df_expo,
        "df_param_f1": df_param_f1,
        "df_kmrc_adi": df_kmrc_adi,
        "df_kmrc_oco": df_kmrc_oco,
        "df_lot_hist_apc": df_lot_hist_apc,
        "df_shot_input": df_shot_input,
        "df_final_adi": df_final_adi,
        "df_final_oco": df_final_oco,
        "coef_adi": coef_adi,
        "coef_oco": coef_oco,
        "summary_adi": summary_adi,
        "summary_oco": summary_oco,
    }


# =============================================================================
# 8. Entrypoint
# =============================================================================

CONFIG = PipelineConfig(
    days=8,
    exclude_recent_days=1,
    expo_days=10,
    target_lotid=None,
    # Example: target_lotid=["B0K486.1", "B0K271.1"],
    target_pstepseq="VC075030",
    target_mstepseq="VC075040",
    target_mstepseq_oco="VC077251",
    db_user_apc="EAPCP2",
    db_user="SIMAXP2",
    output_dir="output_clean",
)


if __name__ == "__main__":
    results = run_pipeline(CONFIG)
    log("\n===== PIPELINE DONE =====")
    for key, value in results.items():
        if isinstance(value, pd.DataFrame):
            log(f"{key}: {value.shape}")
