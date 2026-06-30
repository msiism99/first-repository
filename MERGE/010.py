# 10
# PSM fitting
# - df_psm_input에는 wafer 정보 없음
# - sub_eqp_id 기준:
#     slotid / Wafer 홀수 -> EX1
#     slotid / Wafer 짝수 -> EX2
# - match_key:
#     df_psm_input : lot_id + sub_eqp_id + pos_x_valn + pos_y_valn
#     df_final     : lot    + sub_eqp_id + fcp_x      + fcp_y
# =========================================================

import numpy as np
import pandas as pd


# =========================================================
# 0) Utility functions
# =========================================================

def find_col(df, candidates):
    """
    후보 컬럼명 중 실제 df에 존재하는 컬럼명을 찾아 반환.
    대소문자 차이도 흡수.
    """
    cols = list(df.columns)
    lower_map = {c.lower(): c for c in cols}

    for cand in candidates:
        if cand in cols:
            return cand
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]

    return None


def format_coord_key(series):
    """
    좌표를 숫자로 변환 후 소수점 2자리 문자열로 통일.
    """
    s = pd.to_numeric(series, errors='coerce').round(2)
    return s.map(lambda v: f"{v:.2f}" if pd.notna(v) else "<NA>")


def build_psm_match_key(lot_series, sub_eqp_series, x_series, y_series):
    """
    PSM fitting용 match_key 생성.
    기준: lot + sub_eqp_id + x좌표 + y좌표
    """
    lot = lot_series.astype(str).str.strip()
    sub = sub_eqp_series.astype(str).str.strip()
    x = format_coord_key(x_series)
    y = format_coord_key(y_series)

    return lot + "_" + sub + "_" + x + "_" + y


# =========================================================
# 1) Design matrix
# =========================================================

def cpe_k_to_fit(rx, ry):
    """
    PSM input RK값을 fitting하기 위한 디자인 행렬.
    7차 polynomial까지 확장.
    총 36개 파라미터 x 2방향.
    """
    X_dx = np.vstack([
        np.ones(len(rx)),
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12,
        (rx ** 4) / 1e19, (rx ** 3 * ry) / 1e19, (rx ** 2 * ry ** 2) / 1e19, (rx * ry ** 3) / 1e19, (ry ** 4) / 1e19,
        (rx ** 5) / 1e23, (rx ** 4 * ry) / 1e23, (rx ** 3 * ry ** 2) / 1e23, (rx ** 2 * ry ** 3) / 1e23, (rx * ry ** 4) / 1e23, (ry ** 5) / 1e23,
        (rx ** 6) / 1e27, (rx ** 5 * ry) / 1e27, (rx ** 4 * ry ** 2) / 1e27, (rx ** 3 * ry ** 3) / 1e27, (rx ** 2 * ry ** 4) / 1e27, (rx * ry ** 5) / 1e27, (ry ** 6) / 1e27,
        (rx ** 7) / 1e31, (rx ** 6 * ry) / 1e31, (rx ** 5 * ry ** 2) / 1e31, (rx ** 4 * ry ** 3) / 1e31, (rx ** 3 * ry ** 4) / 1e31, (rx ** 2 * ry ** 5) / 1e31, (rx * ry ** 6) / 1e31, (ry ** 7) / 1e31
    ]).T

    X_dy = np.vstack([
        np.ones(len(ry)),
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12, (rx ** 3) / 1e12,
        (ry ** 4) / 1e19, (ry ** 3 * rx) / 1e19, (ry ** 2 * rx ** 2) / 1e19, (ry * rx ** 3) / 1e19, (rx ** 4) / 1e19,
        (ry ** 5) / 1e23, (ry ** 4 * rx) / 1e23, (ry ** 3 * rx ** 2) / 1e23, (ry ** 2 * rx ** 3) / 1e23, (ry * rx ** 4) / 1e23, (rx ** 5) / 1e23,
        (ry ** 6) / 1e27, (ry ** 5 * rx) / 1e27, (ry ** 4 * rx ** 2) / 1e27, (ry ** 3 * rx ** 3) / 1e27, (ry ** 2 * rx ** 4) / 1e27, (ry * rx ** 5) / 1e27, (rx ** 6) / 1e27,
        (ry ** 7) / 1e31, (ry ** 6 * rx) / 1e31, (ry ** 5 * rx ** 2) / 1e31, (ry ** 4 * rx ** 3) / 1e31, (ry ** 3 * rx ** 4) / 1e31, (ry ** 2 * rx ** 5) / 1e31, (ry * rx ** 6) / 1e31, (rx ** 7) / 1e31
    ]).T

    return X_dx, X_dy


# =========================================================
# 2) match_key 생성 functions
# =========================================================

def make_psm_input_match_key(df_psm_input):
    """
    df_psm_input 쪽 match_key 생성.
    기준: lot_id + sub_eqp_id + pos_x_valn + pos_y_valn
    """
    if len(df_psm_input) == 0:
        print("⚠️ df_psm_input 데이터가 없습니다.")
        return df_psm_input

    required_cols = ['lot_id', 'sub_eqp_id', 'pos_x_valn', 'pos_y_valn']
    missing_cols = [c for c in required_cols if c not in df_psm_input.columns]

    if missing_cols:
        print("⚠️ df_psm_input 필수 컬럼 누락:", missing_cols)
        print("현재 df_psm_input 컬럼:")
        print(df_psm_input.columns.tolist())
        return df_psm_input

    df_psm_input = df_psm_input.copy()

    df_psm_input['lot_id'] = df_psm_input['lot_id'].astype(str).str.strip()
    df_psm_input['sub_eqp_id'] = df_psm_input['sub_eqp_id'].astype(str).str.strip()

    df_psm_input['fcp_x_round'] = pd.to_numeric(df_psm_input['pos_x_valn'], errors='coerce').round(2)
    df_psm_input['fcp_y_round'] = pd.to_numeric(df_psm_input['pos_y_valn'], errors='coerce').round(2)

    df_psm_input['match_key'] = build_psm_match_key(
        df_psm_input['lot_id'],
        df_psm_input['sub_eqp_id'],
        df_psm_input['fcp_x_round'],
        df_psm_input['fcp_y_round']
    )

    print("✅ df_psm_input match_key 생성 완료")
    print(f"  - rows: {len(df_psm_input)}")
    print(f"  - unique match_key: {df_psm_input['match_key'].nunique()}")
    print("  - sub_eqp_id 분포:")
    print(df_psm_input['sub_eqp_id'].value_counts(dropna=False))

    return df_psm_input


def make_final_match_key(df_final, label="ADI"):
    """
    df_final_adi / df_final_oco 쪽 match_key 생성.
    기준: lot + sub_eqp_id + fcp_x + fcp_y

    lot 컬럼 후보:
        lotid, lot_id, LOT_ID

    wafer/slot 컬럼 후보:
        slotid, slot_id, Wafer, wafer, WAFER
    """
    if len(df_final) == 0:
        print(f"⚠️ df_final_{label} 데이터가 없습니다.")
        return df_final

    lot_col = find_col(df_final, ['lotid', 'lot_id', 'LOT_ID'])
    slot_col = find_col(df_final, ['slotid', 'slot_id', 'Wafer', 'wafer', 'WAFER'])

    x_col = find_col(df_final, ['fcp_x', 'FCP_X'])
    y_col = find_col(df_final, ['fcp_y', 'FCP_Y'])

    missing = []
    if lot_col is None:
        missing.append('lot column')
    if slot_col is None:
        missing.append('slot/wafer column')
    if x_col is None:
        missing.append('fcp_x')
    if y_col is None:
        missing.append('fcp_y')

    if missing:
        print(f"⚠️ df_final_{label} 필수 컬럼 누락:", missing)
        print("현재 컬럼:")
        print(df_final.columns.tolist())
        return df_final

    df_final = df_final.copy()

    print(f"\n[{label}] match_key 생성에 사용한 컬럼")
    print("lot_col :", lot_col)
    print("slot_col:", slot_col)
    print("x_col   :", x_col)
    print("y_col   :", y_col)

    df_final['_psm_lot_key'] = df_final[lot_col].astype(str).str.strip()
    df_final['_psm_slot_key'] = pd.to_numeric(df_final[slot_col], errors='coerce').astype('Int64')

    df_final['sub_eqp_id'] = np.where(
        df_final['_psm_slot_key'] % 2 == 1,
        'EX1',
        'EX2'
    )

    df_final['fcp_x_round'] = pd.to_numeric(df_final[x_col], errors='coerce').round(2)
    df_final['fcp_y_round'] = pd.to_numeric(df_final[y_col], errors='coerce').round(2)

    df_final['match_key'] = build_psm_match_key(
        df_final['_psm_lot_key'],
        df_final['sub_eqp_id'],
        df_final['fcp_x_round'],
        df_final['fcp_y_round']
    )

    print(f"✅ df_final_{label} match_key 생성 완료")
    print(f"  - rows: {len(df_final)}")
    print(f"  - unique match_key: {df_final['match_key'].nunique()}")
    print("  - sub_eqp_id 분포:")
    print(df_final['sub_eqp_id'].value_counts(dropna=False))

    return df_final


# =========================================================
# 3) match 상태 확인
# =========================================================

def check_match_status(df_final, df_psm_input, label="ADI"):
    """
    wafer/slot별 PSM match 상태 확인.
    """
    if len(df_final) == 0 or len(df_psm_input) == 0:
        print(f"⚠️ {label} match 확인 불가: 데이터 없음")
        return

    if 'match_key' not in df_final.columns or 'match_key' not in df_psm_input.columns:
        print(f"⚠️ {label} match 확인 불가: match_key 없음")
        return

    psm_keys = set(df_psm_input['match_key'].dropna().unique())
    final_keys = set(df_final['match_key'].dropna().unique())

    df_check = df_final.copy()
    df_check['is_psm_matched'] = df_check['match_key'].isin(psm_keys)

    print(f"\n[{label}] match_key 매칭 현황")
    print(f"df_psm_input 고유 키: {len(psm_keys)}")
    print(f"df_final_{label} 고유 키: {len(final_keys)}")
    print(f"매칭된 키: {len(psm_keys & final_keys)}")

    slot_col = find_col(df_check, ['slotid', 'slot_id', 'Wafer', 'wafer', 'WAFER'])

    if slot_col is not None:
        print(f"\n[{label}] {slot_col}별 매칭 현황")
        print(
            df_check
            .groupby(slot_col)['is_psm_matched']
            .agg(['count', 'sum', 'mean'])
            .rename(columns={
                'count': 'total_rows',
                'sum': 'matched_rows',
                'mean': 'matched_ratio'
            })
        )

    if 'sub_eqp_id' in df_check.columns:
        print(f"\n[{label}] sub_eqp_id별 매칭 현황")
        print(
            df_check
            .groupby('sub_eqp_id')['is_psm_matched']
            .agg(['count', 'sum', 'mean'])
            .rename(columns={
                'count': 'total_rows',
                'sum': 'matched_rows',
                'mean': 'matched_ratio'
            })
        )

    # 매칭 안 될 때 lot 샘플 비교용
    if len(psm_keys & final_keys) == 0:
        lot_col_final = find_col(df_final, ['lotid', 'lot_id', 'LOT_ID'])

        print(f"\n⚠️ [{label}] 매칭된 key가 0개입니다. lot 샘플 확인:")
        if 'lot_id' in df_psm_input.columns:
            print("df_psm_input lot_id sample:")
            print(df_psm_input['lot_id'].dropna().astype(str).str.strip().unique()[:20])

        if lot_col_final is not None:
            print(f"df_final_{label} {lot_col_final} sample:")
            print(df_final[lot_col_final].dropna().astype(str).str.strip().unique()[:20])

        print("\nmatch_key sample 비교:")
        print("df_psm_input match_key sample:")
        print(df_psm_input['match_key'].dropna().unique()[:5])
        print(f"df_final_{label} match_key sample:")
        print(df_final['match_key'].dropna().unique()[:5])


# =========================================================
# 4) shot fitting function
# =========================================================

def shot_fitting(df_final, df_input, k_col_prefix, result_prefix, n_k=72):
    """
    Shot별 K값을 계측포인트에 fitting하는 공통 함수.

    Parameters:
        df_final:       계측 데이터, match_key 컬럼 필요
        df_input:       K값 입력 데이터, match_key 컬럼 필요
        k_col_prefix:   K값 컬럼 접두사, 예: "mrc_k"
        result_prefix:  결과 컬럼 접두사, 예: "psm_fit"
        n_k:            K값 파라미터 수, 기본 72

    Returns:
        {result_prefix}_x, {result_prefix}_y 컬럼이 추가된 DataFrame
    """
    if len(df_final) == 0 or len(df_input) == 0:
        print("데이터가 없습니다.")
        return df_final

    if 'match_key' not in df_final.columns or 'match_key' not in df_input.columns:
        print("⚠️ match_key 컬럼이 없어 fitting을 건너뜁니다.")
        return df_final

    k_cols = [f"{k_col_prefix}{i}_valn" for i in range(1, n_k + 1)]
    missing_k_cols = [c for c in k_cols if c not in df_input.columns]

    if missing_k_cols:
        print(f"⚠️ K 컬럼 누락. 예시: {missing_k_cols[:10]}")
        print(f"누락 개수: {len(missing_k_cols)}")
        return df_final

    df_input = df_input.copy()

    if 'event_tsdt' in df_input.columns:
        df_input['event_tsdt'] = pd.to_datetime(df_input['event_tsdt'], errors='coerce')

    if 'tkin_tsdt' in df_input.columns:
        df_input['tkin_tsdt'] = pd.to_datetime(df_input['tkin_tsdt'], errors='coerce')

    sort_cols = [c for c in ['event_tsdt', 'tkin_tsdt'] if c in df_input.columns]

    if sort_cols:
        df_input = df_input.sort_values(sort_cols, ascending=True)

    # 같은 match_key가 여러 개 있으면 가장 최근 row 사용
    before_dedup = len(df_input)
    df_input = (
        df_input
        .dropna(subset=['match_key'])
        .drop_duplicates(subset=['match_key'], keep='last')
    )
    after_dedup = len(df_input)

    print(f"\n[{result_prefix.upper()}] input dedup")
    print(f"  - before: {before_dedup}")
    print(f"  - after : {after_dedup}")

    input_indexed = df_input.set_index("match_key")

    fit_x = pd.Series(np.nan, index=df_final.index, dtype=float)
    fit_y = pd.Series(np.nan, index=df_final.index, dtype=float)

    grouped = df_final.groupby("match_key", dropna=False)

    success_count = 0
    skip_count = 0
    skip_reasons = {
        'match_key_not_found': 0,
        'k_value_error': 0,
        'all_k_nan': 0,
        'coord_missing': 0,
        'coord_nan': 0
    }

    for match_key, group in grouped:
        if pd.isna(match_key) or match_key not in input_indexed.index:
            skip_count += 1
            skip_reasons['match_key_not_found'] += 1
            continue

        row = input_indexed.loc[match_key]

        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        try:
            k_values = row[k_cols].values.astype(float)
        except Exception:
            skip_count += 1
            skip_reasons['k_value_error'] += 1
            continue

        if np.isnan(k_values).all():
            skip_count += 1
            skip_reasons['all_k_nan'] += 1
            continue

        k_values = np.nan_to_num(k_values, nan=0.0)

        # k1=X, k2=Y, k3=X, k4=Y ...
        Y_dx = k_values[::2]
        Y_dy = k_values[1::2]

        if "coordinate_X" not in group.columns or "coordinate_Y" not in group.columns:
            skip_count += 1
            skip_reasons['coord_missing'] += 1
            continue

        rx = pd.to_numeric(group["coordinate_X"], errors='coerce').values.astype(float)
        ry = pd.to_numeric(group["coordinate_Y"], errors='coerce').values.astype(float)

        if np.isnan(rx).any() or np.isnan(ry).any():
            skip_count += 1
            skip_reasons['coord_nan'] += 1
            continue

        X_dx, X_dy = cpe_k_to_fit(rx, ry)

        fit_x.loc[group.index] = X_dx.dot(Y_dx)
        fit_y.loc[group.index] = X_dy.dot(Y_dy)

        success_count += 1

    col_x = f"{result_prefix}_x"
    col_y = f"{result_prefix}_y"

    df_final = df_final.copy()
    df_final[col_x] = fit_x
    df_final[col_y] = fit_y

    print(f"\n{result_prefix.upper()} Fitting 완료")
    print(f"  - 처리 성공: {success_count}개 그룹")
    print(f"  - 건너뜀: {skip_count}개 그룹")
    print(f"  - skip reasons: {skip_reasons}")
    print(f"  - 유효 행 X: {df_final[col_x].notna().sum()}/{len(df_final)}")
    print(f"  - 유효 행 Y: {df_final[col_y].notna().sum()}/{len(df_final)}")

    return df_final


# =========================================================
# 5) fitting 이후 유효 행 확인
# =========================================================

def check_fit_valid_by_slot(df_final, label="ADI", result_prefix="psm_fit"):
    """
    fitting 이후 slot/wafer별 유효 행 확인.
    """
    col_x = f"{result_prefix}_x"
    col_y = f"{result_prefix}_y"

    if col_x not in df_final.columns or col_y not in df_final.columns:
        print(f"⚠️ [{label}] {col_x}, {col_y} 컬럼이 없습니다.")
        return

    slot_col = find_col(df_final, ['slotid', 'slot_id', 'Wafer', 'wafer', 'WAFER'])

    print(f"\n[{label}] wafer/slot별 {result_prefix} 유효 행")

    if slot_col is not None:
        print(
            df_final
            .assign(psm_valid=df_final[col_x].notna() & df_final[col_y].notna())
            .groupby(slot_col)['psm_valid']
            .agg(['count', 'sum', 'mean'])
            .rename(columns={
                'count': 'total_rows',
                'sum': 'valid_rows',
                'mean': 'valid_ratio'
            })
        )
    else:
        print("slot/wafer 컬럼을 찾지 못했습니다.")
        print("전체 유효 행:")
        print((df_final[col_x].notna() & df_final[col_y].notna()).sum(), "/", len(df_final))


print("shot_fitting 공통 함수 정의 완료")


# =========================================================
# 6) 실행부
# =========================================================

# 6-1) df_psm_input match_key 생성
df_psm_input = make_psm_input_match_key(df_psm_input)


# 6-2) df_final_adi / df_final_oco match_key 생성
df_final_adi = make_final_match_key(df_final_adi, label="ADI")
df_final_oco = make_final_match_key(df_final_oco, label="OCO")


# 6-3) match 상태 확인
check_match_status(df_final_adi, df_psm_input, label="ADI")
check_match_status(df_final_oco, df_psm_input, label="OCO")


# 6-4) PSM fitting 실행
df_final_adi = shot_fitting(
    df_final_adi,
    df_psm_input,
    k_col_prefix="mrc_k",
    result_prefix="psm_fit",
    n_k=72
)

df_final_oco = shot_fitting(
    df_final_oco,
    df_psm_input,
    k_col_prefix="mrc_k",
    result_prefix="psm_fit",
    n_k=72
)


# 6-5) fitting 이후 wafer별 유효 행 확인
check_fit_valid_by_slot(df_final_adi, label="ADI", result_prefix="psm_fit")
check_fit_valid_by_slot(df_final_oco, label="OCO", result_prefix="psm_fit")

df_final_adi = df_final_adi[
    df_final_adi['MMO_MRC_EQP'].notna() &
    (df_final_adi['MMO_MRC_EQP'].astype(str).str.strip() != '')
].copy()

df_final_oco = df_final_oco[
    df_final_oco['MMO_MRC_EQP'].notna() &
    (df_final_oco['MMO_MRC_EQP'].astype(str).str.strip() != '')
].copy()


# 6-6) 저장
# df_final_adi.to_excel('df_final_adi_13_2.xlsx', index=False)
# df_final_oco.to_excel('df_final_oco_13_2.xlsx', index=False)

