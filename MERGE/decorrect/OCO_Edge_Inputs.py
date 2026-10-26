# %% 04. 기존 선정 wafer에 대응하는 OCO edge 이력 조회
def oco_edge_lotinfo_sql(cfg, selected):
    """Keep the selected exposure in the SQL before choosing its latest edge history."""
    photos = selected["photo_transn_seq"].dropna().unique().tolist()
    lots = selected["lotid"].dropna().unique().tolist()
    recent_days = max(0, cfg.exclude_recent_days - 3)
    return f"""
WITH edge_lotinfo AS (
  SELECT {LOT_COLUMNS}, row_number() OVER (
    PARTITION BY l.lotid, l.slotid, l.photo_transn_seq ORDER BY l.impala_insert_time DESC
  ) AS rn
  FROM ees_ds_eai.apc_nautil_dat_lotinfo l
  WHERE l.impala_insert_time >= now() - interval {cfg.days + 5} days
    AND l.`timestamp` >= now() - interval {cfg.days + 5} days
    AND l.`timestamp` <= now() - interval {recent_days} days
    AND l.db_user = {quote(cfg.db_user)}
    {equals_filter('l.pstepseq', cfg.target_pstepseq)}
    {equals_filter('l.mstepseq', cfg.target_mstepseq_oco_edge)}
    {in_filter('l.lotid', lots)}
    {in_filter('l.photo_transn_seq', photos, True)}
)
SELECT * FROM edge_lotinfo WHERE rn = 1
"""


def select_oco_edge_history(edge, selected):
    keys = ["lotid", "slotid", "photo_transn_seq"]
    base, edge = selected.copy(), edge.copy()
    if base.empty:
        base = base.reindex(columns=list(dict.fromkeys(list(base.columns) + keys + ["lot_transn_seq"])))
    if edge.empty:
        edge = pd.DataFrame(columns=list(dict.fromkeys(list(base.columns) + list(edge.columns))))
    for frame in [base, edge]:
        require_columns(frame, keys + ["lot_transn_seq"], "OCO EDGE LOTINFO")
        frame["lotid"] = frame["lotid"].astype("string")
        for col in ["slotid", "photo_transn_seq", "lot_transn_seq"]:
            frame[col] = integer(frame[col])
    anchor = base[keys + ["lot_transn_seq"]].dropna(subset=keys).drop_duplicates(keys)
    anchor = anchor.rename(columns={"lot_transn_seq": "main_lot_transn_seq"})
    edge = edge.dropna(subset=keys + ["lot_transn_seq"]).merge(anchor[keys], on=keys, how="inner", validate="m:1")
    if "impala_insert_time" in edge:
        edge["_edge_order"] = pd.to_datetime(edge["impala_insert_time"], errors="coerce", format="mixed")
        edge = edge.sort_values("_edge_order", na_position="first").drop(columns="_edge_order")
    edge = edge.drop_duplicates(keys, keep="last").reset_index(drop=True)
    matched = anchor.merge(edge[keys + ["lot_transn_seq"]].rename(columns={"lot_transn_seq": "edge_lot_transn_seq"}), on=keys, how="left", validate="1:1")
    matched["edge_history_found"] = matched["edge_lot_transn_seq"].notna()
    matched["edge_history_status"] = np.where(matched["edge_history_found"], "matched", "missing_edge_history")
    return edge, matched


edge_query_parts = []
if cfg.include_oco_edge and not df_lotinfo_oco.empty:
    edge_photos = df_lotinfo_oco["photo_transn_seq"].dropna().unique().tolist()
    for offset in range(0, len(edge_photos), cfg.max_query_keys):
        subset = df_lotinfo_oco[df_lotinfo_oco["photo_transn_seq"].isin(edge_photos[offset:offset + cfg.max_query_keys])]
        sql_lotinfo_oco_edge = oco_edge_lotinfo_sql(cfg, subset)
        edge_query_parts.append(fetch_frame(f"lotinfo_oco_edge_{offset // cfg.max_query_keys}", sql_lotinfo_oco_edge))
df_lotinfo_oco_edge_query = pd.concat(edge_query_parts, ignore_index=True) if edge_query_parts else df_lotinfo_oco.iloc[:0].copy()
df_lotinfo_oco_edge, df_oco_edge_history_status = select_oco_edge_history(df_lotinfo_oco_edge_query, df_lotinfo_oco)
if not cfg.include_oco_edge:
    df_oco_edge_history_status["edge_history_status"] = "disabled"
oco_history_parts = [frame for frame in [df_lotinfo_oco, df_lotinfo_oco_edge] if not frame.empty]
df_lotinfo_oco_all = pd.concat(oco_history_parts, ignore_index=True) if oco_history_parts else df_lotinfo_oco_edge.copy()
if df_lotinfo_oco_all.duplicated(["lot_transn_seq", "slotid"]).any():
    raise ValueError("기존/edge LOTINFO의 lot_transn_seq + slotid가 중복됩니다. 별도 측정 이력인지 확인하세요.")
save_stage("04_LOTINFO_OCO_EDGE_QUERY", df_lotinfo_oco_edge_query)
save_stage("04_LOTINFO_OCO_EDGE_SELECTED", df_lotinfo_oco_edge)
save_stage("04_LOTINFO_OCO_WITH_EDGE", df_lotinfo_oco_all)
save_stage("04_OCO_EDGE_HISTORY_STATUS", df_oco_edge_history_status)

# %% 05. 조회 직후 edge RAWDATA X/Y 배율 적용 및 기존 OCO와 결합
def prepare_oco_raw_source(raw, source_name, mstepseq, scale=1.0):
    """Scale only RAWDATA.value_x/y once, retaining the original values and source history."""
    out = raw.copy()
    if out.empty:
        out = out.reindex(columns=list(dict.fromkeys(list(out.columns) + ["lot_transn_seq", "slot_id", "transn_occur_date", "data_kind", "test_point_no", "coordinate_x", "coordinate_y", "value_x", "value_y", "mrc_x_valn", "mrc_y_valn"])))
    require_columns(out, ["lot_transn_seq", "data_kind", "value_x", "value_y"], "OCO RAW SOURCE")
    if not np.isfinite(scale) or scale < 0:
        raise ValueError("OCO edge 배율은 유한한 0 이상의 수여야 합니다.")
    measured = out["data_kind"].eq("RAWDATA")
    out["measurement_source"], out["source_mstepseq"] = source_name, mstepseq
    out["source_lot_transn_seq"] = integer(out["lot_transn_seq"])
    out["measurement_scale"] = np.where(measured, float(scale), 1.0)
    for axis in ["x", "y"]:
        col, original = f"value_{axis}", f"value_{axis}_original"
        # DB results may be categorical or nullable integer; use float before replacement.
        current = pd.to_numeric(out[col], errors="coerce").astype(float)
        # Reusing an already-prepared frame never applies the factor a second time.
        values = pd.to_numeric(out[original], errors="coerce").astype(float) if original in out else current
        out[original] = values.where(measured)
        out[col] = current.where(~measured, values * scale)
    return out


sql_rawdata_oco = rawdata_sql(cfg, df_lotinfo_oco) if not df_lotinfo_oco.empty else None
sql_rawdata_adi = rawdata_sql(cfg, df_lotinfo_adi) if not df_lotinfo_adi.empty else None
sql_rawdata_oco_edge = rawdata_sql(cfg, df_lotinfo_oco_edge) if not df_lotinfo_oco_edge.empty else None
df_rawdata_oco_main_query = fetch_frame("rawdata_oco", sql_rawdata_oco, reuse=False) if sql_rawdata_oco else pd.DataFrame()
df_rawdata_oco_main_query = prepare_oco_raw_source(df_rawdata_oco_main_query, "oco_main", cfg.target_mstepseq_oco)
df_rawdata_oco_edge_query = fetch_frame("rawdata_oco_edge", sql_rawdata_oco_edge, reuse=False) if sql_rawdata_oco_edge else pd.DataFrame()
df_rawdata_oco_edge_query = prepare_oco_raw_source(df_rawdata_oco_edge_query, "oco_edge", cfg.target_mstepseq_oco_edge, cfg.oco_edge_scale)
oco_raw_parts = [frame for frame in [df_rawdata_oco_main_query, df_rawdata_oco_edge_query] if not frame.empty]
df_rawdata_oco_query = pd.concat(oco_raw_parts, ignore_index=True) if oco_raw_parts else df_rawdata_oco_main_query.copy()
df_rawdata_adi_query = fetch_frame("rawdata_adi", sql_rawdata_adi, reuse=False) if sql_rawdata_adi else pd.DataFrame()
save_stage("05_RAWDATA_OCO_MAIN_QUERY", df_rawdata_oco_main_query)
save_stage("05_RAWDATA_OCO_EDGE_SCALED", df_rawdata_oco_edge_query)
save_stage("05_RAWDATA_OCO_QUERY", df_rawdata_oco_query)
save_stage("05_RAWDATA_ADI_QUERY", df_rawdata_adi_query)

# %% 08. E2 선택 후 기존/edge point 수 확인
def oco_edge_coverage(measured, history_status):
    keys = ["LOT_ID", "Wafer", "photo_transn_seq"]
    result = history_status.rename(columns={"lotid": "LOT_ID", "slotid": "Wafer"}).copy()
    for source_name, count_col in [("oco_main", "n_main_points"), ("oco_edge", "n_edge_points")]:
        subset = measured[measured["measurement_source"].eq(source_name)]
        counts = subset.groupby(keys, observed=True, dropna=False).size().rename(count_col).reset_index()
        result = result.merge(counts, on=keys, how="left", validate="1:1")
        result[count_col] = result[count_col].fillna(0).astype(int)
    result["edge_point_status"] = np.where(result["n_edge_points"].gt(0), "included", np.where(result["edge_history_found"], "no_points_after_group_filter", result["edge_history_status"]))
    return result


df_oco_edge_coverage = oco_edge_coverage(df_oco_measured, df_oco_edge_history_status)
save_stage("08_OCO_EDGE_COVERAGE", df_oco_edge_coverage)
