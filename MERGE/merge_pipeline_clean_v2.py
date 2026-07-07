# -*- coding: utf-8 -*-
"""
Patched runner for merge_pipeline_clean.py.

Why this file exists
--------------------
`merge_pipeline_clean.py` can fail in `fetch_lot_hist_apc()` at `pd.merge_asof()`
when BDQ returns `tkin_tsdt` or merge-by columns as pandas Categorical dtype.
Pandas then raises a MergeError similar to:

    both sides category, but not equal ones

This file imports the clean pipeline, monkey-patches only `fetch_lot_hist_apc()`
with a dtype-hardened version, and then runs the same pipeline.

Run
---
python MERGE/merge_pipeline_clean_v2.py

Or in notebook:
    import runpy
    runpy.run_path("MERGE/merge_pipeline_clean_v2.py", run_name="__main__")
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import merge_pipeline_clean as base


def _force_plain_datetime(series: pd.Series) -> pd.Series:
    """Convert category/object/string datetime-like series to plain datetime64[ns]."""
    return pd.to_datetime(series.astype("string"), errors="coerce")


def _force_plain_string(series: pd.Series) -> pd.Series:
    """Convert category/object values to pandas string without category metadata."""
    return series.astype("string").str.strip()


def fetch_lot_hist_apc(df_lotinfo_adi: pd.DataFrame, cfg: base.PipelineConfig) -> pd.DataFrame:
    """Dtype-hardened replacement for base.fetch_lot_hist_apc.

    Main changes vs v1:
    - `event_tsdt`, `tkin_tsdt`, `event_tsdt_eexy` are converted via
      astype('string') before pd.to_datetime, removing Categorical metadata.
    - merge_asof key and by columns are explicitly copied, sorted, and reset-indexed.
    - `by` columns are forced to pandas string dtype on both sides.
    """
    if df_lotinfo_adi.empty:
        return pd.DataFrame()

    lotids = df_lotinfo_adi["lotid"].dropna().astype(str).unique().tolist()[:1000]
    if not lotids:
        return pd.DataFrame()

    lot_filter = base.sql_in_clause("lot_id", lotids)
    pstepseq_filter = f"AND step_seq = {base.sql_quote(cfg.target_pstepseq)}" if cfg.target_pstepseq else ""

    sql_main = f"""
    SELECT
        CAST(apc_hist_index_no AS BIGINT) AS apc_hist_index_no,
        apc_group_name, lot_id, step_seq, eqp_id, sub_eqp_id, ppid, reticle_id,
        run_type, event_tsdt, tkin_tsdt
    FROM ees_ds_eai.apc_apc_lot_hist
    WHERE db_user = {base.sql_quote(cfg.db_user_apc)}
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
    WHERE db_user = {base.sql_quote(cfg.db_user_apc)}
        AND event_tsdt >= now() - interval {cfg.days + 5} days
        AND event_tsdt <= now() - interval {cfg.exclude_recent_days} days
        AND apc_group_name = 'PHOTO_EEXY_GRP'
        AND save_type != 'A'
        {lot_filter}
        {pstepseq_filter}
    """

    base.log("[APC LOT HIST v2] main query start")
    main = base.bdq.getData(sql_main)
    base.log(f"[APC LOT HIST v2] main rows: {len(main)}")

    base.log("[APC LOT HIST v2] EEXY query start")
    eexy = base.bdq.getData(sql_eexy)
    base.log(f"[APC LOT HIST v2] EEXY rows: {len(eexy)}")

    if main.empty:
        return pd.DataFrame()

    if eexy.empty:
        main = main.copy()
        main["apc_trocs_hist_index_no"] = pd.NA
        return base.normalize_common_keys(main)

    merge_keys = ["lot_id", "step_seq", "eqp_id", "sub_eqp_id"]

    main = main.copy()
    eexy = eexy.copy()

    # Remove category metadata from all merge-by columns.
    for col in merge_keys:
        main[col] = _force_plain_string(main[col])
        eexy[col] = _force_plain_string(eexy[col])

    # Remove category metadata from datetime columns before merge_asof.
    main["tkin_tsdt"] = _force_plain_datetime(main["tkin_tsdt"])
    main["event_tsdt"] = _force_plain_datetime(main["event_tsdt"])
    eexy["tkin_tsdt"] = _force_plain_datetime(eexy["tkin_tsdt"])
    eexy["event_tsdt_eexy"] = _force_plain_datetime(eexy["event_tsdt_eexy"])

    main["apc_hist_index_no"] = pd.to_numeric(main["apc_hist_index_no"], errors="coerce").astype("Int64")
    eexy["apc_trocs_hist_index_no"] = pd.to_numeric(eexy["apc_trocs_hist_index_no"], errors="coerce").astype("Int64")

    main_valid = (
        main.dropna(subset=["tkin_tsdt"])
        .sort_values("tkin_tsdt", kind="mergesort")
        .reset_index(drop=True)
        .copy()
    )

    eexy_u = (
        eexy.dropna(subset=["tkin_tsdt"])
        .sort_values("event_tsdt_eexy", kind="mergesort")
        .drop_duplicates(merge_keys + ["tkin_tsdt"], keep="last")
        .sort_values("tkin_tsdt", kind="mergesort")
        .reset_index(drop=True)
        .copy()
    )

    # Final safety check: no category dtype should remain in merge_asof keys.
    for name, df_check in [("main_valid", main_valid), ("eexy_u", eexy_u)]:
        cat_cols = [c for c in ["tkin_tsdt"] + merge_keys if str(df_check[c].dtype) == "category"]
        if cat_cols:
            raise TypeError(f"{name} still has category dtype columns before merge_asof: {cat_cols}")

    if main_valid.empty:
        out = main.copy()
        out["apc_trocs_hist_index_no"] = pd.NA
        return base.normalize_common_keys(out)

    if eexy_u.empty:
        out = main.copy()
        out["apc_trocs_hist_index_no"] = pd.NA
        return base.normalize_common_keys(out)

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

    out = base.normalize_common_keys(out)

    # Safer dedup than original lot_id + sub_eqp_id only.
    dedup_keys = [c for c in ["lot_id", "step_seq", "eqp_id", "sub_eqp_id", "ppid", "reticle_id"] if c in out.columns]
    if dedup_keys:
        out = (
            out.sort_values("event_tsdt", kind="mergesort")
            .drop_duplicates(dedup_keys, keep="last")
            .reset_index(drop=True)
        )

    match_rate = out["apc_trocs_hist_index_no"].notna().mean() * 100 if len(out) else 0.0
    base.log(f"✅ APC LOT HIST v2 merged rows: {len(out)}, EEXY match rate: {match_rate:.1f}%")
    return out


# Monkey-patch the function used by base.run_pipeline().
base.fetch_lot_hist_apc = fetch_lot_hist_apc


if __name__ == "__main__":
    results = base.run_pipeline(base.CONFIG)
    base.log("\n===== PIPELINE DONE v2 =====")
    for key, value in results.items():
        if isinstance(value, pd.DataFrame):
            base.log(f"{key}: {value.shape}")
