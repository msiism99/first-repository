# 14

# ─────────────────────────────────────────────────────────────────────
# 섹션 11b-1: 핵심 함수 정의 (_is_edge, _mark_sel_all)
# all_marks.py 로직을 노트북 내에 인라인으로 정의합니다.
# ─────────────────────────────────────────────────────────────────────

# 웨이퍼 유효 반경 (단위: um) — 300mm 웨이퍼 기준
WAFER_LIMIT_RADIUS = 147000

def _is_edge(center, pitch, limit_radius):
    """Shot 네 모서리 중 하나라도 반경 밖이면 1, 전부 밖이면 2, 전부 안이면 0 반환"""
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
    DataFrame: Test_ID, Shot_X, Shot_Y, Coordinate_X, Coordinate_Y,
               Wafer_X, Wafer_Y, Radius
    """
    test_n = test_inf.shape[0]
    step_n = test_inf.shape[1] // 2

    # Shot 후보 생성 (X/Y 방향 각 -10 ~ 10)
    shot_list = []
    for ix in range(-10, 11):
        for iy in range(-10, 11):
            cx = ix * shot_layout[0] + shot_layout[2]
            cy = iy * shot_layout[1] + shot_layout[3]
            if _is_edge([cx, cy], shot_layout[:2], limit_radius) != 2:
                shot_list.append([ix, iy])
    shot_arr = np.array(shot_list)
    shot_n   = len(shot_arr)

    n_total  = shot_n * test_n
    test_all = np.zeros((n_total, 3 + step_n * 2))  # [test_id, sx, sy, step coords...]
    wafer_x  = np.zeros(n_total)
    wafer_y  = np.zeros(n_total)
    coord_x  = np.zeros(n_total)
    coord_y  = np.zeros(n_total)

    # Shot × Test 조합 배열 초기화
    for i, (sx, sy) in enumerate(shot_arr):
        s = i * test_n
        e = s + test_n
        test_all[s:e, 0] = np.arange(1, test_n + 1)
        test_all[s:e, 1] = sx
        test_all[s:e, 2] = sy

    # 각 step의 wafer 절대 좌표 계산
    for step in range(step_n):
        for ii in range(n_total):
            tid = int(test_all[ii, 0]) - 1
            rx  = test_inf[tid, step * 2]
            ry  = test_inf[tid, step * 2 + 1]
            cx  = test_all[ii, 1] * shot_layout[0] + shot_layout[2]
            cy  = test_all[ii, 2] * shot_layout[1] + shot_layout[3]
            test_all[ii, 3 + step * 2]     = cx + rx
            test_all[ii, 3 + step * 2 + 1] = cy + ry
            if step == 0:                 # 첫 번째 step 좌표를 대표값으로 기록
                wafer_x[ii] = cx + rx
                wafer_y[ii] = cy + ry
                coord_x[ii] = rx
                coord_y[ii] = ry

    # 모든 step의 마크가 반경 내에 있는 행만 선택
    in_rad = np.column_stack([
        np.sqrt(test_all[:, 3 + s*2]**2 + test_all[:, 4 + s*2]**2) < limit_radius
        for s in range(step_n)
    ])
    f = np.all(in_rad, axis=1)

    return pd.DataFrame({
        "Test_ID"      : test_all[f, 0].astype(int),
        "Shot_X"       : test_all[f, 1].astype(int),
        "Shot_Y"       : test_all[f, 2].astype(int),
        "Coordinate_X" : coord_x[f],
        "Coordinate_Y" : coord_y[f],
        "Wafer_X"      : wafer_x[f],
        "Wafer_Y"      : wafer_y[f],
        "Radius"       : np.sqrt(wafer_x[f]**2 + wafer_y[f]**2),
    })

def shot_fitting_all_marks(df_final, df_trocs_input,
                           limit_radius=WAFER_LIMIT_RADIUS,
                           k_col_prefix="rk",
                           result_prefix="trocs_fit"):
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
    limit_radius   : 웨이퍼 유효 반경 (um), 기본 150000
    k_col_prefix   : K값 컬럼 접두사 (기본 "rk")
    result_prefix  : 결과 컬럼 접두사 (기본 "trocs_fit")

    Returns
    -------
    DataFrame: UNIQUE_ID, 메타데이터, Test_ID, Shot_X/Y, Coordinate_X/Y,
               Wafer_X/Y, Radius, fcp_x/y, apc_hist_index_no,
               {result_prefix}_all_x, {result_prefix}_all_y
    """
    if df_final.empty or df_trocs_input.empty:
        print("데이터가 없습니다.")
        return pd.DataFrame()

    k_cols = [f"{k_col_prefix}{i}_valn" for i in range(1, 73)]

    # df_trocs_input에 내부 match_key 생성 (pos_x/y_valn은 이미 um 단위)
    trocs_w = df_trocs_input.copy()
    trocs_w["_fcp_xr"] = trocs_w["pos_x_valn"].round(2)
    trocs_w["_fcp_yr"] = trocs_w["pos_y_valn"].round(2)
    trocs_w["_mk"] = (
        trocs_w["apc_hist_index_no"].astype(str) + "_" +
        trocs_w["_fcp_xr"].astype(str) + "_" +
        trocs_w["_fcp_yr"].astype(str)
    )
    trocs_idx = trocs_w.set_index("_mk")

    # df_final에서 실제 존재하는 메타 컬럼만 사용
    meta_cols_avail = [c for c in _META_COLS if c in df_final.columns]

    results = []
    n_uid   = df_final["UNIQUE_ID"].nunique()
    ok, skip = 0, 0

    for uid, grp in df_final.groupby("UNIQUE_ID"):

        # ── shot layout 추출 ──────────────────────────────────
        try:
            pitch_x = float(grp["STEP_PITCH_X"].iloc[0])
            pitch_y = float(grp["STEP_PITCH_Y"].iloc[0])
            shift_x = float(grp["MAP_SHIFT_X"].iloc[0])
            shift_y = float(grp["MAP_SHIFT_Y"].iloc[0])
        except (KeyError, ValueError, IndexError):
            skip += 1
            continue
        shot_layout = [pitch_x, pitch_y, shift_x, shift_y]

        # ── apc_hist_index_no 추출 ───────────────────────────
        if "apc_hist_index_no" not in grp.columns:
            skip += 1
            continue
        valid_apc = grp["apc_hist_index_no"].dropna().unique()
        if len(valid_apc) == 0:
            skip += 1
            continue
        apc_idx_no = valid_apc[0]

        # ── test mark 좌표 추출 ──────────────────────────────
        if "TEST" in grp.columns:
            unique_tests = sorted(grp["TEST"].dropna().unique())
            marks = []
            for t in unique_tests:
                sub = grp[grp["TEST"] == t][["coordinate_X", "coordinate_Y"]].dropna()
                if len(sub):
                    marks.append(sub.iloc[0].values)
            test_inf = np.array(marks) if marks else np.empty((0, 2))
        else:
            test_inf = (grp[["coordinate_X", "coordinate_Y"]]
                        .drop_duplicates().dropna().values)

        if len(test_inf) == 0:
            skip += 1
            continue

        # ── 전체 마크 생성 ────────────────────────────────────
        df_marks = _mark_sel_all(test_inf, shot_layout, limit_radius)
        if df_marks.empty:
            skip += 1
            continue

        # ── FCP 좌표 + 식별 정보 추가 ────────────────────────
        df_marks["fcp_x"]             = df_marks["Shot_X"] * pitch_x + shift_x
        df_marks["fcp_y"]             = df_marks["Shot_Y"] * pitch_y + shift_y
        df_marks["apc_hist_index_no"] = apc_idx_no
        df_marks["UNIQUE_ID"]         = uid
        df_marks["_mk"] = (
            df_marks["apc_hist_index_no"].astype(str) + "_" +
            df_marks["fcp_x"].round(2).astype(str) + "_" +
            df_marks["fcp_y"].round(2).astype(str)
        )

        # ── 메타데이터 추가 (UNIQUE_ID 내 대표값 = 첫 번째 행) ──
        for mc in meta_cols_avail:
            vals = grp[mc].dropna()
            df_marks[mc] = vals.iloc[0] if len(vals) > 0 else None

        # ── Fitting 적용 ─────────────────────────────────────
        fit_x = np.full(len(df_marks), np.nan)
        fit_y = np.full(len(df_marks), np.nan)

        for mk, mk_grp in df_marks.groupby("_mk"):
            if mk not in trocs_idx.index:
                continue
            row = trocs_idx.loc[mk]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            try:
                k_vals = row[k_cols].values.astype(float)
            except (KeyError, ValueError):
                continue
            if np.isnan(k_vals).all():
                continue

            k_vals = np.nan_to_num(k_vals, nan=0.0)
            Y_dx = k_vals[::2]   # k1,k3,k5,... → X방향 계수
            Y_dy = k_vals[1::2]  # k2,k4,k6,... → Y방향 계수

            rx = mk_grp["Coordinate_X"].values.astype(float)
            ry = mk_grp["Coordinate_Y"].values.astype(float)
            X_dx, X_dy = cpe_k_to_fit(rx, ry)

            fit_x[mk_grp.index] = X_dx.dot(Y_dx)
            fit_y[mk_grp.index] = X_dy.dot(Y_dy)

        df_marks[f"{result_prefix}_all_x"] = fit_x
        df_marks[f"{result_prefix}_all_y"] = fit_y
        df_marks.drop(columns=["_mk"], inplace=True)

        results.append(df_marks)
        ok += 1

    print(f"\n전체 마크 TROCS Fitting 완료")
    print(f"  총 UNIQUE_ID : {n_uid}")
    print(f"  처리 성공   : {ok}")
    print(f"  건너뜀      : {skip}")

    if not results:
        return pd.DataFrame()

    df_all = pd.concat(results, ignore_index=True)
    col_x  = f"{result_prefix}_all_x"
    print(f"  유효 마크   : {df_all[col_x].notna().sum():,} / {len(df_all):,}")
    return df_all




# lot_hist 메타데이터 + RK값 추출
trocs_meta_cols = ['event_tsdt', 'tkin_tsdt', 'apc_hist_index_no', 'lot_id', 'step_seq', 'eqp_id',
                   'sub_eqp_id', 'ppid', 'reticle_id', 'run_type',
                   'pos_x_valn', 'pos_y_valn']
rk_col_list = [f'rk{i}_valn' for i in range(1, 73)]
trocs_final_cols = trocs_meta_cols + rk_col_list

df_trocs_input = df_joined_apc[trocs_final_cols].copy()

# FCP 단위 변환: pos_x/y_valn은 mm 단위이므로, um 단위의 df_final fcp_x/y와 매칭하기 위해 *1000
df_trocs_input['pos_x_valn'] = df_trocs_input['pos_x_valn'] * 1000
df_trocs_input['pos_y_valn'] = df_trocs_input['pos_y_valn'] * 1000

print(f"[df_trocs_input] 생성 완료: {df_trocs_input.shape}")
print(f"  - 메타데이터 컬럼: {len(trocs_meta_cols)}개")
print(f"  - RK값 컬럼: {len(rk_col_list)}개")
print(f"  - pos_x/y_valn 단위 변환 완료 (mm → um, x1000)")
df_trocs_input.head()

df_trocs_input.to_csv('df_trocs_input.csv')


# df_trocs_input에 매칭 키 생성 (df_final의 match_key는 섹션 9에서 이미 생성됨)
if len(df_trocs_input) > 0:
    df_trocs_input['fcp_x_round'] = df_trocs_input['pos_x_valn'].round(2)
    df_trocs_input['fcp_y_round'] = df_trocs_input['pos_y_valn'].round(2)

    df_trocs_input['match_key'] = (
        df_trocs_input['apc_hist_index_no'].astype(str) + '_' +
        df_trocs_input['fcp_x_round'].astype(str) + '_' +
        df_trocs_input['fcp_y_round'].astype(str)
    )

    trocs_keys = set(df_trocs_input['match_key'].unique())
    final_keys = set(df_final['match_key'].unique())
    matched_keys = trocs_keys & final_keys

    print(f"df_trocs_input 고유 키: {len(trocs_keys)}")
    print(f"df_final 고유 키: {len(final_keys)}")
    print(f"매칭된 키: {len(matched_keys)}")
else:
    print("df_trocs_input이 비어있습니다.")


# TROCS Fitting 실행
if len(df_final) > 0 and len(df_trocs_input) > 0:
    print("TROCS Fitting 시작...")
    df_final = shot_fitting(df_final, df_trocs_input, k_col_prefix="rk", result_prefix="trocs_fit")
    print("TROCS Fitting 완료!")
else:
    print("데이터가 없어 TROCS Fitting을 수행할 수 없습니다.")


# ─────────────────────────────────────────────────────────────────────
# 섹션 11b-2: shot_fitting_all_marks() — 전체 마크 TROCS Fitting
# (df_final 메타데이터를 결과 DataFrame에 함께 포함)
# ─────────────────────────────────────────────────────────────────────

# df_final에서 가져올 메타데이터 컬럼 목록
_META_COLS = [
    'STEPSEQ', 'LOT_ID', 'Wafer', 'GROUP',
    'P_EQPID', 'Photo_PPID', 'P_TIME', 'M_TIME',
    'ChuckID', 'ReticleID', 'Base_EQP1', 'MMO_MRC_EQP',
    'M_STEPSEQ',
    'STEP_PITCH_X', 'STEP_PITCH_Y', 'MAP_SHIFT_X', 'MAP_SHIFT_Y',
    'photo_transn_seq', 'apc_trocs_hist_index_no',
]



# ── 실행 ─────────────────────────────────────────────────────────────
if len(df_final) > 0 and len(df_trocs_input) > 0:
    print("전체 마크 TROCS Fitting 시작...")
    df_trocs_allmarks = shot_fitting_all_marks(df_final, df_trocs_input)
else:
    print("df_final 또는 df_trocs_input이 비어 있어 건너뜁니다.")
    df_trocs_allmarks = pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────
# 섹션 11b-3: 전체 마크 Fitting 결과 저장 및 요약
# ─────────────────────────────────────────────────────────────────────
import os

if len(df_trocs_allmarks) > 0:
    os.makedirs("output", exist_ok=True)
    out_path = "output/BDQ_trocs_allmarks.csv"
    df_trocs_allmarks.to_csv(out_path, index=False, encoding="utf-8-sig")

    col_x   = "trocs_fit_all_x"
    col_y   = "trocs_fit_all_y"
    valid_n = df_trocs_allmarks[col_x].notna().sum() if col_x in df_trocs_allmarks.columns else 0

    print(f"✅ 저장 완료: {out_path}")
    print(f"   총 마크 수   : {len(df_trocs_allmarks):,}")
    print(f"   유효 Fitting : {valid_n:,}")
    print(f"\n[컬럼 목록]")
    print(df_trocs_allmarks.columns.tolist())

    show_cols = ["UNIQUE_ID", "Test_ID", "Shot_X", "Shot_Y",
                 "Coordinate_X", "Coordinate_Y",
                 "Wafer_X", "Wafer_Y", "Radius",
                 "fcp_x", "fcp_y",
                 "trocs_fit_all_x", "trocs_fit_all_y"]
    avail = [c for c in show_cols if c in df_trocs_allmarks.columns]
    print(f"\n[샘플 데이터]")
    display(df_trocs_allmarks[avail].head(10))
else:
    print("df_trocs_allmarks가 비어 있습니다 — 저장 건너뜀")
