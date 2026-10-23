# %% 00. 기존 동일 번호 코드 셀 교체
@dataclass
class PipelineConfig:
    days: int = 8
    exclude_recent_days: int = 1
    expo_days: int = 10
    target_lotid: list[str] | str | None = None
    target_pstepseq: str | None = "VC075030"
    target_mstepseq: str | None = "VC075040"
    target_mstepseq_oco: str | None = "VC077251"
    include_oco_edge: bool = True
    target_mstepseq_oco_edge: str | None = "VC077252"
    oco_edge_scale: float = 0.6
    db_user: str = "SIMAXP2"
    db_user_apc: str = "EAPCP2"
    slot_min: int = 9
    slot_max: int = 14
    rawdata_gap_seconds: int = 60
    apc_match_seconds: int = 60
    wafer_radius_um: float = 147000.0
    max_query_keys: int = 1000
    rawdata_row_limit: int = 10000000
    reference_date: str | None = None  # Python 측 ADI 날짜 필터용. SQL의 now()는 DB 기준.
    output_dir: str = "output_decorrect_notebook"
    save_parquet: bool = True
    save_excel: bool = False
    max_excel_rows: int = 1048575

    def __post_init__(self):
        if not np.isfinite(self.oco_edge_scale) or self.oco_edge_scale < 0:
            raise ValueError("oco_edge_scale은 유한한 0 이상의 수여야 합니다.")
        if self.include_oco_edge and (not self.target_mstepseq_oco_edge or self.target_mstepseq_oco_edge == self.target_mstepseq_oco):
            raise ValueError("Edge 측정 step은 기존 OCO step과 다른 값으로 지정하세요.")
        if self.days <= 0 or not 0 <= self.exclude_recent_days < self.days:
            raise ValueError("days > exclude_recent_days >= 0 이어야 합니다.")
        if self.slot_min > self.slot_max or self.max_query_keys <= 0 or self.rawdata_row_limit <= 0:
            raise ValueError("wafer 범위와 조회 제한을 확인하세요.")
        if self.rawdata_gap_seconds < 0 or self.apc_match_seconds < 0:
            raise ValueError("시간 간격은 0 이상이어야 합니다.")

OUTPUT_DIR = Path.cwd() / "output_decorrect_notebook"
SAVE_PARQUET = True
SAVE_EXCEL = True
EXCEL_PREVIEW_ROWS = 10000  # 이보다 큰 테이블은 Excel 샘플 + 전체 Parquet을 저장
PREVIEW_ROWS = 10

cfg = PipelineConfig()
cfg.days = 8
cfg.exclude_recent_days = 1
cfg.expo_days = 10
cfg.target_lotid = None  # 예: ["B0K486.1", "B0K271.1"]
cfg.target_pstepseq = "VC075030"
cfg.target_mstepseq = "VC075040"
cfg.target_mstepseq_oco = "VC077251"
cfg.include_oco_edge = True  # False이면 기존 OCO만 사용
cfg.target_mstepseq_oco_edge = "VC077252"
cfg.oco_edge_scale = 0.6  # Edge RAWDATA의 value_x/value_y에만 조회 직후 적용
cfg.slot_min = 9
cfg.slot_max = 14
cfg.reference_date = None  # Python ADI 날짜 필터. SQL now()의 날짜를 바꾸지는 않음
cfg.output_dir = str(OUTPUT_DIR)
cfg.save_parquet = SAVE_PARQUET
cfg.save_excel = SAVE_EXCEL
cfg.__post_init__()
if EXCEL_PREVIEW_ROWS < 1 or PREVIEW_ROWS < 1:
    raise ValueError("미리보기 행 수는 1 이상이어야 합니다.")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print("중간 결과 저장 폴더:", OUTPUT_DIR.resolve())


# %% 04. 기존 동일 번호 코드 셀 교체
def select_lot_pair(adi, oco, cfg):
    if adi.empty or oco.empty:
        return adi.iloc[:0].copy(), oco.iloc[:0].copy(), pd.DataFrame()
    adi, oco = adi.copy(), oco.copy()
    for frame in (adi, oco):
        require_columns(frame, ["photo_transn_seq", "slotid", "lot_transn_seq", "lotid", "timestamp"], "LOTINFO")
        frame["photo_transn_seq"], frame["slotid"] = integer(frame["photo_transn_seq"]), integer(frame["slotid"])
    adi["timestamp"] = pd.to_datetime(adi["timestamp"], errors="coerce")
    today = pd.Timestamp(cfg.reference_date).normalize() if cfg.reference_date else pd.Timestamp.today().normalize()
    start, end = today - pd.Timedelta(days=cfg.days), today - pd.Timedelta(days=cfg.exclude_recent_days)
    adi = adi[adi["timestamp"].ge(start) & adi["timestamp"].lt(end)].copy()
    keys = ["photo_transn_seq", "slotid"]
    common = oco[keys].dropna().drop_duplicates().merge(adi[keys].dropna().drop_duplicates(), on=keys, how="inner")
    adi, oco = [frame.merge(common, on=keys, how="inner").sort_values(keys).reset_index(drop=True) for frame in (adi, oco)]
    adi, oco = [frame[frame["slotid"].between(cfg.slot_min, cfg.slot_max)].copy() for frame in (adi, oco)]
    for frame in (adi, oco):
        frame["slotid"] = frame["slotid"].astype(int)
    oco_extra = oco[keys + ["lot_transn_seq", "timestamp", "mstepseq"]].drop_duplicates(keys)
    oco_extra = oco_extra.rename(columns={"lot_transn_seq": "lot_transn_seq_oco", "timestamp": "timestamp_oco", "mstepseq": "mstepseq_oco"})
    saved = adi.merge(oco_extra, on=keys, how="left")
    if "per_shot_mrc_id" in saved:
        parts = saved["per_shot_mrc_id"].astype(str).str.split("/").str[-1].str.split("_")
        saved["base_eqpid"] = parts.str[0]
        saved["psm_update_time"] = parts.str[1].astype("string").str.replace(r"^20", "", regex=True).str[:10]
    return adi, oco, saved

df_lotinfo_adi, df_lotinfo_oco, df_lotinfo_save = select_lot_pair(df_lotinfo_adi_query, df_lotinfo_oco_query, cfg)
save_stage("04_LOTINFO_ADI_SELECTED", df_lotinfo_adi)
save_stage("04_LOTINFO_OCO_SELECTED", df_lotinfo_oco)
save_stage("04_LOTINFO_PAIRED", df_lotinfo_save)

# OCO edge input extension: matched to the selected main wafers
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


# %% 05. 기존 동일 번호 코드 셀 교체
def rawdata_sql(cfg, lots):
    ids = limited_keys(lots["lot_transn_seq"], cfg.max_query_keys, "RAWDATA")
    return f"""
SELECT r.lot_transn_seq,r.slot_id,r.transn_occur_date,r.data_kind,r.test_point_no,r.coordinate_x,r.coordinate_y,r.value_x,r.value_y,r.mrc_x_valn,r.mrc_y_valn
FROM ees_ds_eai.apc_nautil_dat_rawdata r
WHERE r.impala_insert_time >= now() - interval {cfg.days + 10} days AND r.db_user = {quote(cfg.db_user)}
  {in_filter('r.lot_transn_seq', ids, True)} AND r.data_kind IN ('RAWDATA','TESTDATA','PERSHOT')
LIMIT {cfg.rawdata_row_limit}
"""

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
        # Reusing an already-prepared frame never applies the factor a second time.
        values = pd.to_numeric(out[original] if original in out else out[col], errors="coerce")
        out[original] = values.where(measured)
        out[col] = out[col].where(~measured, values * scale)
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


# %% 06. 기존 동일 번호 코드 셀 교체
def latest_raw_batch(raw, lots, gap_seconds=60):
    if raw.empty or lots.empty:
        return raw.iloc[:0].copy()
    require_columns(raw, ["lot_transn_seq", "slot_id", "data_kind", "transn_occur_date"], "RAWDATA")
    df = raw.copy()
    df["transn_occur_date"] = pd.to_datetime(df["transn_occur_date"].astype(str), errors="coerce")
    df["slot_id"] = integer(df["slot_id"])
    df = df.dropna(subset=["slot_id", "transn_occur_date"]).copy()
    df["slot_id"] = df["slot_id"].astype(int)
    keys = lots[["lot_transn_seq", "slotid"]].drop_duplicates().copy()
    keys["lot_transn_seq"], keys["slotid"] = integer(keys["lot_transn_seq"]), integer(keys["slotid"])
    df["lot_transn_seq"] = integer(df["lot_transn_seq"])
    df = df.merge(keys.dropna(), left_on=["lot_transn_seq", "slot_id"], right_on=["lot_transn_seq", "slotid"], how="inner")
    groups = ["lot_transn_seq", "slot_id", "data_kind"]
    df = df.sort_values(groups + ["transn_occur_date"]).reset_index(drop=True)
    previous = df.groupby(groups)["transn_occur_date"].shift()
    starts = previous.isna() | (df["transn_occur_date"] - previous).dt.total_seconds().gt(gap_seconds)
    df["_batch"] = starts.astype(int).groupby([df[col] for col in groups]).cumsum()
    # transform으로 최대 batch를 붙이면 원본 merge와 같은 행 선택을 중간 테이블 없이 수행합니다.
    last = df.groupby(groups)["_batch"].transform("max")
    return df[df["_batch"].eq(last)].drop(columns="_batch").reset_index(drop=True)

df_rawdata_oco = latest_raw_batch(df_rawdata_oco_query, df_lotinfo_oco_all, cfg.rawdata_gap_seconds)
df_rawdata_adi = latest_raw_batch(df_rawdata_adi_query, df_lotinfo_adi, cfg.rawdata_gap_seconds)
save_stage("06_RAWDATA_OCO_LATEST", df_rawdata_oco)
save_stage("06_RAWDATA_ADI_LATEST", df_rawdata_adi)
source.release_cache()


# %% 08. 기존 동일 번호 코드 셀 교체
RENAME = {
    "pstepseq": "STEPSEQ", "lotid": "LOT_ID", "slotid": "Wafer", "peqpid": "P_EQPID", "ppid": "Photo_PPID",
    "chuckid": "ChuckID", "reticleid": "ReticleID", "steppitch_x": "STEP_PITCH_X", "steppitch_y": "STEP_PITCH_Y",
    "mapshift_x": "MAP_SHIFT_X", "mapshift_y": "MAP_SHIFT_Y", "dmargin_x": "Dmargin_X", "dmargin_y": "Dmargin_Y",
    "outlr_resdl_spec_ratio": "Outlier_Spec_Ratio", "chip_x_qty": "CHIP_X_NUM", "chip_y_qty": "CHIP_Y_NUM",
    "mmo_mrc_ref_eqp_id": "MMO_MRC_EQP", "mstepseq": "M_STEPSEQ", "timestamp": "M_TIME",
}

OCO_PROVENANCE_COLUMNS = ["measurement_source", "source_mstepseq", "source_lot_transn_seq", "measurement_scale", "X_reg_original", "Y_reg_original"]

FINAL_COLUMNS = [
    "UNIQUE_ID", "UNIQUE_ID2", "UNIQUE_ID3", "UNIQUE_ID4", "STEPSEQ", "LOT_ID", "Wafer",
    "P_EQPID", "Photo_PPID", "P_TIME", "M_TIME", "ChuckID", "ReticleID", "Base_EQP1", "MMO_MRC_EQP", "GROUP", "TEST", "DieX", "DieY",
    "STEP_PITCH_X", "STEP_PITCH_Y", "MAP_SHIFT_X", "MAP_SHIFT_Y", "coordinate_X", "coordinate_Y",
    "fcp_x", "fcp_y", "wf_x", "wf_y", "radius", "CHIP_X_NUM", "CHIP_Y_NUM", "Outlier_Spec_Ratio", "Dmargin_X", "Dmargin_Y",
    "X_reg", "Y_reg", "MRC_RX", "MRC_RY", "PSM_X", "PSM_Y", "Is_Edge_Shot", "Max_Corner_Distance",
    "M_STEPSEQ", "photo_transn_seq", "apc_hist_index_no", "apc_trocs_hist_index_no",
] + OCO_PROVENANCE_COLUMNS

def assemble_measurements(raw, lots, expo, f1, mode, cfg):
    if raw.empty:
        return pd.DataFrame(columns=FINAL_COLUMNS)
    df = raw[raw["data_kind"].eq("RAWDATA")].rename(columns={"test_point_no": "TEST", "coordinate_x": "DieX", "coordinate_y": "DieY", "value_x": "X_reg", "value_y": "Y_reg", "value_x_original": "X_reg_original", "value_y_original": "Y_reg_original"}).copy()
    if df.empty:
        return pd.DataFrame(columns=FINAL_COLUMNS)
    df = clean_columns(df).merge(lots, left_on=["lot_transn_seq", "slot_id"], right_on=["lot_transn_seq", "slotid"], how="left", validate="m:1", suffixes=("", "_lotinfo"))
    test = raw[raw["data_kind"].eq("TESTDATA")].rename(columns={"test_point_no": "TEST", "value_x": "coordinate_X", "value_y": "coordinate_Y", "mrc_x_valn": "MRC_RX", "mrc_y_valn": "MRC_RY"})
    if not test.empty:
        columns = ["lot_transn_seq", "slot_id", "TEST", "coordinate_X", "coordinate_Y", "MRC_RX", "MRC_RY"]
        df = df.merge(test[columns], on=columns[:3], how="left", validate="m:1", suffixes=("", "_test"))
    for col in ["coordinate_X", "coordinate_Y", "MRC_RX", "MRC_RY"]:
        if col not in df:
            df[col] = np.nan
    if mode == "ADI":
        pershot = raw[raw["data_kind"].eq("PERSHOT")].rename(columns={"test_point_no": "TEST", "coordinate_x": "DieX", "coordinate_y": "DieY", "value_x": "PSM_X", "value_y": "PSM_Y"})
        columns = ["lot_transn_seq", "slot_id", "TEST", "DieX", "DieY", "PSM_X", "PSM_Y"]
        if not pershot.empty:
            df = df.merge(pershot[columns], on=columns[:5], how="left", validate="m:1", suffixes=("", "_psm"))
        for col in ["PSM_X", "PSM_Y"]:
            if col not in df:
                df[col] = np.nan
    if not expo.empty:
        columns = ["lotid", "slot_id", "photo_transn_seq", "photo_date", "apc_hist_index_no", "apc_trocs_hist_index_no", "mmo_mrc_ref_eqp_id"]
        df = df.merge(expo[columns].rename(columns={"photo_date": "P_TIME", "photo_transn_seq": "photo_transn_seq_expo"}), on=["lotid", "slot_id"], how="left", validate="m:1")
    else:
        for col in ["P_TIME", "apc_hist_index_no", "apc_trocs_hist_index_no", "mmo_mrc_ref_eqp_id"]:
            df[col] = pd.NA
    # 원본의 photo_transn_seq_x/y 충돌 때문에 빠지던 F1 메타데이터만 명시적으로 연결합니다.
    if not f1.empty:
        f1 = f1.copy()
        f1["photo_transn_seq"], f1["slotid"] = integer(f1["photo_transn_seq"]), integer(f1["slotid"])
        f1["_f1_lot_key"] = f1["lotid"].astype(str).str.strip()
        df["_f1_lot_key"] = df["lotid"].astype(str).str.strip()
        keys = ["photo_transn_seq", "_f1_lot_key", "slotid"]
        f1 = f1.sort_values("impala_insert_time").drop_duplicates(keys, keep="last") if "impala_insert_time" in f1 else f1.drop_duplicates(keys, keep="last")
        df = df.merge(f1[keys + ["base_eqp_id1"]], on=keys, how="left", validate="m:1").rename(columns={"base_eqp_id1": "Base_EQP1"})
        df = df.drop(columns="_f1_lot_key")
    df = clean_columns(df.rename(columns=RENAME)).reset_index(drop=True)
    numeric(df, ["TEST", "X_reg", "Y_reg", "PSM_X", "PSM_Y", "MRC_RX", "MRC_RY"])
    df["GROUP"] = pd.cut(df["TEST"], bins=[0, 80, 160, 240], labels=["E1", "E2", "E3"])
    if mode == "OCO":
        group = "E2" if (cfg.target_mstepseq_oco or "")[2:5] == "077" else "E1"
        df = df[df["GROUP"].eq(group)].copy()
    return add_geometry_and_ids(df, cfg)

def add_geometry_and_ids(df, cfg):
    if df.empty:
        return pd.DataFrame(columns=FINAL_COLUMNS)
    df = df.reset_index(drop=True)
    columns = ["DieX", "DieY", "STEP_PITCH_X", "STEP_PITCH_Y", "MAP_SHIFT_X", "MAP_SHIFT_Y", "coordinate_X", "coordinate_Y"]
    require_columns(df, columns, "좌표 계산")
    for col in columns:
        df[col] = pd.to_numeric(df[col].astype(str).str.strip(), errors="coerce")
    df["fcp_x"] = df["DieX"] * df["STEP_PITCH_X"] + df["MAP_SHIFT_X"]
    df["fcp_y"] = df["DieY"] * df["STEP_PITCH_Y"] + df["MAP_SHIFT_Y"]
    df["wf_x"], df["wf_y"] = df["fcp_x"] + df["coordinate_X"], df["fcp_y"] + df["coordinate_Y"]
    df["radius"] = np.sqrt(df["wf_x"] ** 2 + df["wf_y"] ** 2)
    fields = ["STEPSEQ", "P_EQPID", "Photo_PPID", "MMO_MRC_EQP", "P_TIME", "M_TIME", "LOT_ID", "Wafer"]
    text = {col: df[col].astype("string").fillna("") for col in fields + ["GROUP", "TEST", "DieX", "DieY"]}
    base = text[fields[0]]
    for col in fields[1:]:
        base = base + "_" + text[col]
    df["UNIQUE_ID3"], df["UNIQUE_ID"] = base, base + "_" + text["GROUP"]
    df["UNIQUE_ID2"] = base + "_" + text["TEST"] + "_" + text["DieX"] + "_" + text["DieY"] + "_" + text["GROUP"]
    df["UNIQUE_ID4"] = base + "_" + text["DieX"] + "_" + text["DieY"] + "_" + text["GROUP"]
    if "measurement_source" in df:
        edge = df["measurement_source"].eq("oco_edge")
        suffix = "_OCO_EDGE_" + integer(df["source_lot_transn_seq"]).astype("string").fillna("unknown")
        for col in ["UNIQUE_ID", "UNIQUE_ID2", "UNIQUE_ID3", "UNIQUE_ID4"]:
            df.loc[edge, col] = df.loc[edge, col] + suffix.loc[edge]
    x, y = df["fcp_x"].to_numpy(float), df["fcp_y"].to_numpy(float)
    sx, sy = df["STEP_PITCH_X"].to_numpy(float) / 2, df["STEP_PITCH_Y"].to_numpy(float) / 2
    distances = [(x + dx * sx) ** 2 + (y + dy * sy) ** 2 for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]]
    df["Max_Corner_Distance"] = np.sqrt(np.maximum.reduce(distances))
    df["Is_Edge_Shot"] = df["Max_Corner_Distance"].gt(cfg.wafer_radius_um)
    return df[[col for col in FINAL_COLUMNS if col in df]].copy()

df_adi_measured = assemble_measurements(df_rawdata_adi, df_lotinfo_adi, df_expo_overlay, df_paramdata, "ADI", cfg)
df_oco_measured = assemble_measurements(df_rawdata_oco, df_lotinfo_oco_all, df_expo_overlay, df_paramdata, "OCO", cfg)
save_stage("08_ADI_MEASURED", df_adi_measured)
save_stage("08_OCO_MEASURED", df_oco_measured)

# OCO edge coverage after the existing group filter
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
