# 14

# ─────────────────────────────────────────────────────────────────────
# 섹션 11b-1: 핵심 함수 정의 (_is_edge, _mark_sel_all)
# ─────────────────────────────────────────────────────────────────────

# 웨이퍼 유효 반경 (단위: um)
WAFER_LIMIT_RADIUS = 147000


def normalize_apc_id(series):
    return pd.to_numeric(series, errors='coerce').astype('Int64')


def format_coord_key(series):
    s = pd.to_numeric(series, errors='coerce').round(2)
    return s.map(lambda v: f"{v:.2f}" if pd.notna(v) else "<NA>")


def build_match_key(apc_series, x_series, y_series):
    apc = normalize_apc_id(apc_series).astype('string')
    x = format_coord_key(x_series)
    y = format_coord_key(y_series)
    return apc + "_" + x + "_" + y


def _is_edge(center, pitch, limit_radius):
    """
    Shot 네 모서리 중
      - 하나라도 반경 밖이면 1
      - 전부 밖이면 2
      - 전부 안이면 0
    """
    corners = np.array([
        [center[0] - pitch[0] / 2, center[1] - pitch[1] / 2],
        [center[0] - pitch[0] / 2, center[1] + pitch[1] / 2],
        [center[0] + pitch[0] / 2, center[1] + pitch[1] / 2],
        [center[0] + pitch[0] / 2, center[1] - pitch[1] / 2],
    ])
    r = np.sqrt(np.sum(corners ** 2, axis=1))
    if np.max(r) > limit_radius:
        return 1 if np.min(r) <= limit_radius else 2
    return 0


def _mark_sel_all(test_inf, shot_layout, limit_radius):
    """
    웨이퍼 반경 내 계측 가능한 모든 (shot, mark) 조합을 생성합니다.

    Parameters
    ----------
    test_inf    : (test_n, step_n*2) ndarray
                  각 Test 마크의 상대 좌표 [coord_x_step0, coord_y_step0, ...] (um)
    shot_layout : [pitch_x, pitch_y, shift_x, shift_y] (um)
    limit_radius: 웨이퍼 유효 반경 (um)

    Returns
    -------
    DataFrame:
        Test_ID, Shot_X, Shot_Y, Coordinate_X, Coordinate_Y,
        Wafer_X, Wafer_Y, Radius, Inside_Radius
    """
    test_n = test_inf.shape[0]
    step_n = test_inf.shape[1] // 2

    # Shot 후보 생성
    shot_list = []
    for ix in range(-10, 11):
        for iy in range(-10, 11):
            cx = ix * shot_layout[0] + shot_layout[2]
            cy = iy * shot_layout[1] + shot_layout[3]
            if _is_edge([cx, cy], shot_layout[:2], limit_radius) != 2:
                shot_list.append([ix, iy])

    if len(shot_list) == 0:
        return pd.DataFrame(columns=[
            "Test_ID", "Shot_X", "Shot_Y",
            "Coordinate_X", "Coordinate_Y",
            "Wafer_X", "Wafer_Y", "Radius", "Inside_Radius"
        ])

    shot_arr = np.array(shot_list)
    shot_n = len(shot_arr)

    n_total = shot_n * test_n
    test_all = np.zeros((n_total, 3 + step_n * 2))
    wafer_x = np.zeros(n_total)
    wafer_y = np.zeros(n_total)
    coord_x = np.zeros(n_total)
    coord_y = np.zeros(n_total)

    # Shot × Test 조합 배열 초기화
    for i, (sx, sy) in enumerate(shot_arr):
        s = i * test_n
        e = s + test_n
        test_all[s:e, 0] = np.arange(1, test_n + 1)
        test_all[s:e, 1] = sx
        test_all[s:e, 2] = sy

    # 각 step의 wafer 절대좌표 계산
    for step in range(step_n):
        for ii in range(n_total):
            tid = int(test_all[ii, 0]) - 1
            rx = test_inf[tid, step * 2]
            ry = test_inf[tid, step * 2 + 1]
            cx = test_all[ii, 1] * shot_layout[0] + shot_layout[2]
            cy = test_all[ii, 2] * shot_layout[1] + shot_layout[3]

            test_all[ii, 3 + step * 2] = cx + rx
            test_all[ii, 3 + step * 2 + 1] = cy + ry

            # 첫 번째 step 좌표를 대표 mark 좌표로 사용
            if step == 0:
                wafer_x[ii] = cx + rx
                wafer_y[ii] = cy + ry
                coord_x[ii] = rx
                coord_y[ii] = ry

    # 대표 mark 기준 반경 판정
    radius = np.sqrt(wafer_x**2 + wafer_y**2)
    inside = radius < limit_radius

    df_out = pd.DataFrame({
        "Test_ID": test_all[:, 0].astype(int),
        "Shot_X": test_all[:, 1].astype(int),
        "Shot_Y": test_all[:, 2].astype(int),
        "Coordinate_X": coord_x,
        "Coordinate_Y": coord_y,
        "Wafer_X": wafer_x,
        "Wafer_Y": wafer_y,
        "Radius": radius,
        "Inside_Radius": inside,
    })

    # 실제 fitting에 쓸 것은 inside인 mark만
    df_out = df_out[df_out["Inside_Radius"]].copy()

    return df_out


def shot_fitting_all_marks(
    df_final,
    df_trocs_input,
    limit_radius=WAFER_LIMIT_RADIUS,
    k_col_prefix="rk",
    result_prefix="trocs_fit"
):
    """
    계측 가능한 모든 마크에 TROCS Fitting을 적용합니다.
    df_final의 메타데이터(LOT_ID, Wafer, GROUP 등)를 결과에 함께 포함합니다.

    Parameters
    ----------
    df_final       : 계측 데이터
                     (UNIQUE_ID, STEP_PITCH_X/Y, MAP_SHIFT_X/Y,
                      TEST, coordinate_X/Y, apc_hist_index_no 포함)
    df_trocs_input : RK K값 데이터
                     (apc_hist_index_no, pos_x/y_valn[um], rk1~72_valn 포함)
    limit_radius   : 웨이퍼 유효 반경 (um)
    k_col_prefix   : K값 컬럼 접두사 (기본 "rk")
    result_prefix  : 결과 컬럼 접두사 (기본 "trocs_fit")

    Returns
    -------
    DataFrame
    """
    if df_final.empty or df_trocs_input.empty:
        print("데이터가 없습니다.")
        return pd.DataFrame()

    k_cols = [f"{k_col_prefix}{i}_valn" for i in range(1, 73)]

    # df_trocs_input 내부 key 생성
    trocs_w = df_trocs_input.copy()
    trocs_w["apc_hist_index_no"] = normalize_apc_id(trocs_w["apc_hist_index_no"])
    trocs_w["pos_x_valn"] = pd.to_numeric(trocs_w["pos_x_valn"], errors='coerce')
    trocs_w["pos_y_valn"] = pd.to_numeric(trocs_w["pos_y_valn"], errors='coerce')

    trocs_w["_fcp_xr"] = trocs_w["pos_x_valn"].round(2)
    trocs_w["_fcp_yr"] = trocs_w["pos_y_valn"].round(2)
    trocs_w["_mk"] = build_match_key(
        trocs_w["apc_hist_index_no"],
        trocs_w["_fcp_xr"],
        trocs_w["_fcp_yr"]
    )

    if 'event_tsdt' in trocs_w.columns:
        trocs_w['event_tsdt'] = pd.to_datetime(trocs_w['event_tsdt'], errors='coerce')
    if 'tkin_tsdt' in trocs_w.columns:
        trocs_w['tkin_tsdt'] = pd.to_datetime(trocs_w['tkin_tsdt'], errors='coerce')

    sort_cols = [c for c in ['event_tsdt', 'tkin_tsdt'] if c in trocs_w.columns]
    if sort_cols:
        trocs_w = trocs_w.sort_values(sort_cols, ascending=True)

    trocs_w = trocs_w.dropna(subset=["_mk"]).drop_duplicates(subset=["_mk"], keep="last")
    trocs_idx = trocs_w.set_index("_mk")

    meta_cols_avail = [c for c in _META_COLS if c in df_final.columns]

    results = []
    n_uid = df_final["UNIQUE_ID"].nunique()
    ok, skip = 0, 0

    for uid, grp in df_final.groupby("UNIQUE_ID"):
        # shot layout
        try:
            pitch_x = float(grp["STEP_PITCH_X"].iloc[0])
            pitch_y = float(grp["STEP_PITCH_Y"].iloc[0])
            shift_x = float(grp["MAP_SHIFT_X"].iloc[0])
            shift_y = float(grp["MAP_SHIFT_Y"].iloc[0])
        except (KeyError, ValueError, IndexError):
            skip += 1
            continue

        shot_layout = [pitch_x, pitch_y, shift_x, shift_y]

        # apc_hist_index_no
        if "apc_hist_index_no" not in grp.columns:
            skip += 1
            continue

        grp = grp.copy()
        grp["apc_hist_index_no"] = normalize_apc_id(grp["apc_hist_index_no"])
        valid_apc = grp["apc_hist_index_no"].dropna().unique()
        if len(valid_apc) == 0:
            skip += 1
            continue

        # UNIQUE_ID 내 apc가 여러 개면 첫 번째 사용하되 경고
        apc_idx_no = valid_apc[0]
        if len(valid_apc) > 1:
            print(f"⚠️ UNIQUE_ID={uid} 에 apc_hist_index_no가 {len(valid_apc)}개 있습니다. 첫 번째 값 사용: {apc_idx_no}")

        # test mark 좌표 추출
        if "TEST" in grp.columns:
            unique_tests = sorted(grp["TEST"].dropna().unique())
            marks = []
            for t in unique_tests:
                sub = grp[grp["TEST"] == t][["coordinate_X", "coordinate_Y"]].dropna()
                if len(sub) > 0:
                    marks.append(sub.iloc[0].values)
            test_inf = np.array(marks) if marks else np.empty((0, 2))
        else:
            test_inf = grp[["coordinate_X", "coordinate_Y"]].drop_duplicates().dropna().values

        if len(test_inf) == 0:
            skip += 1
            continue

        # 전체 mark 생성
        df_marks = _mark_sel_all(test_inf, shot_layout, limit_radius)
        if df_marks.empty:
            skip += 1
            continue

        df_marks = df_marks.reset_index(drop=True)

        # FCP 좌표 / key 추가
        df_marks["fcp_x"] = df_marks["Shot_X"] * pitch_x + shift_x
        df_marks["fcp_y"] = df_marks["Shot_Y"] * pitch_y + shift_y
        df_marks["apc_hist_index_no"] = apc_idx_no
        df_marks["UNIQUE_ID"] = uid

        df_marks["apc_hist_index_no"] = normalize_apc_id(df_marks["apc_hist_index_no"])
        df_marks["_mk"] = build_match_key(
            df_marks["apc_hist_index_no"],
            df_marks["fcp_x"],
            df_marks["fcp_y"]
        )

        # 메타데이터 추가
        for mc in meta_cols_avail:
            vals = grp[mc].dropna()
            df_marks[mc] = vals.iloc[0] if len(vals) > 0 else None

        # fitting
        fit_x = np.full(len(df_marks), np.nan)
        fit_y = np.full(len(df_marks), np.nan)

        matched_mk = 0
        missing_mk = 0
        nan_k = 0

        for mk, mk_grp in df_marks.groupby("_mk"):
            if mk not in trocs_idx.index:
                missing_mk += len(mk_grp)
                continue

            row = trocs_idx.loc[mk]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]

            try:
                k_vals = row[k_cols].values.astype(float)
            except (KeyError, ValueError):
                missing_mk += len(mk_grp)
                continue

            if np.isnan(k_vals).all():
                nan_k += len(mk_grp)
                continue

            k_vals = np.nan_to_num(k_vals, nan=0.0)
            Y_dx = k_vals[::2]
            Y_dy = k_vals[1::2]

            rx = mk_grp["Coordinate_X"].values.astype(float)
            ry = mk_grp["Coordinate_Y"].values.astype(float)
            X_dx, X_dy = cpe_k_to_fit(rx, ry)

            fit_x[mk_grp.index] = X_dx.dot(Y_dx)
            fit_y[mk_grp.index] = X_dy.dot(Y_dy)
            matched_mk += len(mk_grp)

        df_marks[f"{result_prefix}_all_x"] = fit_x
        df_marks[f"{result_prefix}_all_y"] = fit_y
        df_marks.drop(columns=["_mk"], inplace=True)

        print(f"\n[{uid}] generated marks = {len(df_marks)}")
        print(f"[{uid}] matched marks   = {matched_mk}")
        print(f"[{uid}] missing mk      = {missing_mk}")
        print(f"[{uid}] nan k marks     = {nan_k}")

        results.append(df_marks)
        ok += 1

    print(f"\n전체 마크 TROCS Fitting 완료")
    print(f"  총 UNIQUE_ID : {n_uid}")
    print(f"  처리 성공   : {ok}")
    print(f"  건너뜀      : {skip}")

    if not results:
        return pd.DataFrame()

    df_all = pd.concat(results, ignore_index=True)
    col_x = f"{result_prefix}_all_x"
    print(f"  유효 마크   : {df_all[col_x].notna().sum():,} / {len(df_all):,}")

    return df_all


# ─────────────────────────────────────────────────────────────────────
# df_final에서 가져올 메타데이터 컬럼 목록
# ─────────────────────────────────────────────────────────────────────
_META_COLS = [
    'STEPSEQ', 'LOT_ID', 'Wafer', 'GROUP',
    'P_EQPID', 'Photo_PPID', 'P_TIME', 'M_TIME',
    'ChuckID', 'ReticleID', 'Base_EQP1', 'MMO_MRC_EQP',
    'M_STEPSEQ',
    'STEP_PITCH_X', 'STEP_PITCH_Y', 'MAP_SHIFT_X', 'MAP_SHIFT_Y',
    'photo_transn_seq', 'apc_trocs_hist_index_no',
]


# ─────────────────────────────────────────────────────────────────────
# lot_hist 메타데이터 + RK값 추출
# ─────────────────────────────────────────────────────────────────────
trocs_meta_cols = [
    'event_tsdt', 'tkin_tsdt', 'apc_hist_index_no', 'lot_id', 'step_seq', 'eqp_id',
    'sub_eqp_id', 'ppid', 'reticle_id', 'run_type',
    'pos_x_valn', 'pos_y_valn'
]
rk_col_list = [f'rk{i}_valn' for i in range(1, 73)]
trocs_final_cols = trocs_meta_cols + rk_col_list

df_trocs_input = df_joined_apc[trocs_final_cols].copy()

# FCP 단위 변환: pos_x/y_valn mm → um
df_trocs_input['pos_x_valn'] = pd.to_numeric(df_trocs_input['pos_x_valn'], errors='coerce') * 1000
df_trocs_input['pos_y_valn'] = pd.to_numeric(df_trocs_input['pos_y_valn'], errors='coerce') * 1000
df_trocs_input['apc_hist_index_no'] = normalize_apc_id(df_trocs_input['apc_hist_index_no'])

print(f"[df_trocs_input] 생성 완료: {df_trocs_input.shape}")
print(f"  - 메타데이터 컬럼: {len(trocs_meta_cols)}개")
print(f"  - RK값 컬럼: {len(rk_col_list)}개")
print(f"  - pos_x/y_valn 단위 변환 완료 (mm → um, x1000)")
print(df_trocs_input.head())

df_trocs_input.to_excel('df_trocs_input.xlsx', index=False)


# ─────────────────────────────────────────────────────────────────────
# df_trocs_input key 생성 / df_final key 비교
# ─────────────────────────────────────────────────────────────────────
if len(df_trocs_input) > 0:
    df_trocs_input['fcp_x_round'] = pd.to_numeric(df_trocs_input['pos_x_valn'], errors='coerce').round(2)
    df_trocs_input['fcp_y_round'] = pd.to_numeric(df_trocs_input['pos_y_valn'], errors='coerce').round(2)

    df_trocs_input['match_key'] = build_match_key(
        df_trocs_input['apc_hist_index_no'],
        df_trocs_input['fcp_x_round'],
        df_trocs_input['fcp_y_round']
    )

    trocs_keys = set(df_trocs_input['match_key'].dropna().unique())
    final_keys_adi = set(df_final_adi['match_key'].dropna().unique()) if 'match_key' in df_final_adi.columns else set()
    final_keys_oco = set(df_final_oco['match_key'].dropna().unique()) if 'match_key' in df_final_oco.columns else set()

    matched_keys_adi = trocs_keys & final_keys_adi
    matched_keys_oco = trocs_keys & final_keys_oco

    print(f"df_trocs_input 고유 키: {len(trocs_keys)}")
    print(f"df_final_adi 고유 키: {len(final_keys_adi)}")
    print(f"매칭된 키(ADI): {len(matched_keys_adi)}")
    print(f"df_final_oco 고유 키: {len(final_keys_oco)}")
    print(f"매칭된 키(OCO): {len(matched_keys_oco)}")
else:
    print("df_trocs_input이 비어있습니다.")


# ─────────────────────────────────────────────────────────────────────
# TROCS Fitting 실행
# ─────────────────────────────────────────────────────────────────────
if len(df_final_adi) > 0 and len(df_trocs_input) > 0:
    print("TROCS Fitting 시작...")
    df_final_adi2 = shot_fitting(df_final_adi, df_trocs_input, k_col_prefix="rk", result_prefix="trocs_fit")
    df_final_oco2 = shot_fitting(df_final_oco, df_trocs_input, k_col_prefix="rk", result_prefix="trocs_fit")
    print("TROCS Fitting 완료!")
else:
    print("데이터가 없어 TROCS Fitting을 수행할 수 없습니다.")
    df_final_adi2 = pd.DataFrame()
    df_final_oco2 = pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────
# 전체 마크 TROCS Fitting
# ─────────────────────────────────────────────────────────────────────
if len(df_final_adi2) > 0 and len(df_trocs_input) > 0:
    print("전체 마크 TROCS Fitting 시작... (ADI)")
    df_trocs_allmarks_adi = shot_fitting_all_marks(df_final_adi2, df_trocs_input)
else:
    print("df_final_adi2 또는 df_trocs_input이 비어 있어 ADI 건너뜁니다.")
    df_trocs_allmarks_adi = pd.DataFrame()

if len(df_final_oco2) > 0 and len(df_trocs_input) > 0:
    print("전체 마크 TROCS Fitting 시작... (OCO)")
    df_trocs_allmarks_oco = shot_fitting_all_marks(df_final_oco2, df_trocs_input)
else:
    print("df_final_oco2 또는 df_trocs_input이 비어 있어 OCO 건너뜁니다.")
    df_trocs_allmarks_oco = pd.DataFrame()











# ─────────────────────────────────────────────────────────────────────
# trocs_fit이 하나도 없는 shot 제거
# 기준: (UNIQUE_ID, Shot_X, Shot_Y) 단위로
#      trocs_fit_all_x / trocs_fit_all_y 가 모두 NaN인 shot은 통째로 제거
# ─────────────────────────────────────────────────────────────────────

# ADI
if len(df_trocs_allmarks_adi) > 0:
    before_rows = len(df_trocs_allmarks_adi)
    before_shots = (
        df_trocs_allmarks_adi[['UNIQUE_ID', 'Shot_X', 'Shot_Y']]
        .drop_duplicates()
        .shape[0]
    )

    valid_shots_adi = (
        df_trocs_allmarks_adi
        .groupby(['UNIQUE_ID', 'Shot_X', 'Shot_Y'])[['trocs_fit_all_x', 'trocs_fit_all_y']]
        .apply(lambda g: g['trocs_fit_all_x'].notna().any() or g['trocs_fit_all_y'].notna().any())
        .reset_index(name='is_valid_shot')
    )

    df_trocs_allmarks_adi = df_trocs_allmarks_adi.merge(
        valid_shots_adi,
        on=['UNIQUE_ID', 'Shot_X', 'Shot_Y'],
        how='left'
    )

    df_trocs_allmarks_adi = df_trocs_allmarks_adi[
        df_trocs_allmarks_adi['is_valid_shot']
    ].drop(columns=['is_valid_shot']).copy()

    after_rows = len(df_trocs_allmarks_adi)
    after_shots = (
        df_trocs_allmarks_adi[['UNIQUE_ID', 'Shot_X', 'Shot_Y']]
        .drop_duplicates()
        .shape[0]
    )

    print(f"ADI: invalid shot 제거 완료")
    print(f"  rows : {before_rows} -> {after_rows} (제거 {before_rows - after_rows})")
    print(f"  shots: {before_shots} -> {after_shots} (제거 {before_shots - after_shots})")


# OCO
if len(df_trocs_allmarks_oco) > 0:
    before_rows = len(df_trocs_allmarks_oco)
    before_shots = (
        df_trocs_allmarks_oco[['UNIQUE_ID', 'Shot_X', 'Shot_Y']]
        .drop_duplicates()
        .shape[0]
    )

    valid_shots_oco = (
        df_trocs_allmarks_oco
        .groupby(['UNIQUE_ID', 'Shot_X', 'Shot_Y'])[['trocs_fit_all_x', 'trocs_fit_all_y']]
        .apply(lambda g: g['trocs_fit_all_x'].notna().any() or g['trocs_fit_all_y'].notna().any())
        .reset_index(name='is_valid_shot')
    )

    df_trocs_allmarks_oco = df_trocs_allmarks_oco.merge(
        valid_shots_oco,
        on=['UNIQUE_ID', 'Shot_X', 'Shot_Y'],
        how='left'
    )

    df_trocs_allmarks_oco = df_trocs_allmarks_oco[
        df_trocs_allmarks_oco['is_valid_shot']
    ].drop(columns=['is_valid_shot']).copy()

    after_rows = len(df_trocs_allmarks_oco)
    after_shots = (
        df_trocs_allmarks_oco[['UNIQUE_ID', 'Shot_X', 'Shot_Y']]
        .drop_duplicates()
        .shape[0]
    )

    print(f"OCO: invalid shot 제거 완료")
    print(f"  rows : {before_rows} -> {after_rows} (제거 {before_rows - after_rows})")
    print(f"  shots: {before_shots} -> {after_shots} (제거 {before_shots - after_shots})")

# ─────────────────────────────────────────────────────────────────────
# 저장 및 요약
# ─────────────────────────────────────────────────────────────────────
import os

if len(df_trocs_allmarks_adi) > 0:
    os.makedirs("output", exist_ok=True)
    out_path = "output/BDQ_trocs_allmarks_adi.xlsx"
    df_trocs_allmarks_adi.to_excel(out_path, index=False)

    col_x = "trocs_fit_all_x"
    valid_n = df_trocs_allmarks_adi[col_x].notna().sum() if col_x in df_trocs_allmarks_adi.columns else 0

    print(f"✅ 저장 완료: {out_path}")
    print(f"   총 마크 수   : {len(df_trocs_allmarks_adi):,}")
    print(f"   유효 Fitting : {valid_n:,}")
    print(f"\n[컬럼 목록]")
    print(df_trocs_allmarks_adi.columns.tolist())

    show_cols = [
        "UNIQUE_ID", "Test_ID", "Shot_X", "Shot_Y",
        "Coordinate_X", "Coordinate_Y",
        "Wafer_X", "Wafer_Y", "Radius",
        "fcp_x", "fcp_y",
        "trocs_fit_all_x", "trocs_fit_all_y"
    ]
    avail = [c for c in show_cols if c in df_trocs_allmarks_adi.columns]
    print(f"\n[샘플 데이터]")
    display(df_trocs_allmarks_adi[avail].head(10))
else:
    print("df_trocs_allmarks_adi 비어 있습니다 — 저장 건너뜀")

if len(df_trocs_allmarks_oco) > 0:
    os.makedirs("output", exist_ok=True)
    out_path = "output/BDQ_trocs_allmarks_oco.xlsx"
    df_trocs_allmarks_oco.to_excel(out_path, index=False)

    col_x = "trocs_fit_all_x"
    valid_n = df_trocs_allmarks_oco[col_x].notna().sum() if col_x in df_trocs_allmarks_oco.columns else 0

    print(f"✅ 저장 완료: {out_path}")
    print(f"   총 마크 수   : {len(df_trocs_allmarks_oco):,}")
    print(f"   유효 Fitting : {valid_n:,}")
    print(f"\n[컬럼 목록]")
    print(df_trocs_allmarks_oco.columns.tolist())

    show_cols = [
        "UNIQUE_ID", "Test_ID", "Shot_X", "Shot_Y",
        "Coordinate_X", "Coordinate_Y",
        "Wafer_X", "Wafer_Y", "Radius",
        "fcp_x", "fcp_y",
        "trocs_fit_all_x", "trocs_fit_all_y"
    ]
    avail = [c for c in show_cols if c in df_trocs_allmarks_oco.columns]
    print(f"\n[샘플 데이터]")
    display(df_trocs_allmarks_oco[avail].head(10))
else:
    print("df_trocs_allmarks_oco 비어 있습니다 — 저장 건너뜀")
