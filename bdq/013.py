# 13
def cpe_k_to_fit(rx, ry):
    """
    PSM input RK값을 Fitting하기 위한 디자인 행렬.
    7차 polynomial까지 확장 (총 36개 파라미터 x 2방향)

    Parameters:
        rx, ry: 레티클 좌표 (coordinate_X, coordinate_Y)

    Returns:
        X_dx: X방향 디자인 매트릭스 (N x 36)
        X_dy: Y방향 디자인 매트릭스 (N x 36)
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
def shot_fitting(df_final, df_input, k_col_prefix, result_prefix, n_k=72):
    """
    Shot별 K값을 계측포인트에 Fitting하는 공통 함수.

    Parameters:
        df_final:       계측 데이터 (match_key 컬럼 필요)
        df_input:       K값 입력 데이터 (match_key 컬럼 필요)
        k_col_prefix:   K값 컬럼 접두사 ("mrc_k" for PSM, "rk" for TROCS)
        result_prefix:  결과 컬럼 접두사 ("psm_fit" or "trocs_fit")
        n_k:            K값 파라미터 수 (기본 72)

    Returns:
        {result_prefix}_x, {result_prefix}_y 컬럼이 추가된 DataFrame
    """
    if len(df_final) == 0 or len(df_input) == 0:
        print("데이터가 없습니다.")
        return df_final

    # K값 컬럼명 생성
    k_cols = [f"{k_col_prefix}{i}_valn" for i in range(1, n_k + 1)]

    # df_input을 match_key로 인덱싱
    input_indexed = df_input.set_index("match_key")

    # 결과 저장용
    fit_x = pd.Series(np.nan, index=df_final.index, dtype=float)
    fit_y = pd.Series(np.nan, index=df_final.index, dtype=float)

    # 매칭된 키별로 처리
    grouped = df_final.groupby("match_key")
    success_count = 0
    skip_count = 0

    for match_key, group in grouped:
        # K값 조회
        if match_key not in input_indexed.index:
            skip_count += 1
            continue

        row = input_indexed.loc[match_key]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        # K값 추출
        try:
            k_values = row[k_cols].values.astype(float)
        except (KeyError, ValueError):
            skip_count += 1
            continue

        # NaN 체크 (전부 NaN이면 건너뜀)
        if np.isnan(k_values).all():
            skip_count += 1
            continue

        # NaN을 0으로 대체
        k_values = np.nan_to_num(k_values, nan=0.0)

        # 홀수/짝수 인덱스로 X/Y 분리 (k1=X, k2=Y, ...)
        Y_dx = k_values[::2]    # k1, k3, k5, ... -> X방향
        Y_dy = k_values[1::2]   # k2, k4, k6, ... -> Y방향

        # 좌표 추출
        if "coordinate_X" not in group.columns or "coordinate_Y" not in group.columns:
            skip_count += 1
            continue

        rx = group["coordinate_X"].values.astype(float)
        ry = group["coordinate_Y"].values.astype(float)

        # NaN 체크
        if np.isnan(rx).any() or np.isnan(ry).any():
            skip_count += 1
            continue

        # 디자인 매트릭스 생성 + Fitting (행렬곱)
        X_dx, X_dy = cpe_k_to_fit(rx, ry)
        fit_x.loc[group.index] = X_dx.dot(Y_dx)
        fit_y.loc[group.index] = X_dy.dot(Y_dy)

        success_count += 1

    # 결과 컬럼 추가
    col_x = f"{result_prefix}_x"
    col_y = f"{result_prefix}_y"
    df_final = df_final.copy()
    df_final[col_x] = fit_x
    df_final[col_y] = fit_y

    print(f"{result_prefix.upper()} Fitting 완료")
    print(f"  - 처리 성공: {success_count}개 그룹")
    print(f"  - 건너뜀: {skip_count}개 그룹")
    print(f"  - 유효 행: {df_final[col_x].notna().sum()}/{len(df_final)}")

    return df_final

print("shot_fitting 공통 함수 정의 완료 (PSM/TROCS 겸용)")

# apc_hist_index_no + FCP 좌표를 매칭 키로 사용
# apc_hist_index_no: APC에서 노광 1회마다 고유하게 부여 → lot/step/rework 구분 자동 해결
# FCP 좌표: shot 위치 구분

if len(df_psm_input) > 0 and len(df_final_adi) > 0:
    # FCP 좌표 반올림 (소수점 2자리)
    df_psm_input['fcp_x_round'] = df_psm_input['pos_x_valn'].round(2)
    df_psm_input['fcp_y_round'] = df_psm_input['pos_y_valn'].round(2)

    df_final_adi['fcp_x_round'] = df_final_adi['fcp_x'].round(2)
    df_final_adi['fcp_y_round'] = df_final_adi['fcp_y'].round(2)

    # 매칭 키 생성 (apc_hist_index_no + fcp_x + fcp_y)
    df_psm_input['match_key'] = (
        df_psm_input['apc_hist_index_no'].astype(str) + '_' +
        df_psm_input['fcp_x_round'].astype(str) + '_' +
        df_psm_input['fcp_y_round'].astype(str)
    )

    df_final_adi['match_key'] = (
        df_final_adi['apc_hist_index_no'].astype(str) + '_' +
        df_final_adi['fcp_x_round'].astype(str) + '_' +
        df_final_adi['fcp_y_round'].astype(str)
    )

    # 매칭 확인
    psm_keys = set(df_psm_input['match_key'].unique())
    final_keys = set(df_final_adi['match_key'].unique())
    matched_keys = psm_keys & final_keys

    print(f"df_psm_input 고유 키: {len(psm_keys)}")
    print(f"df_final_adi 고유 키: {len(final_keys)}")
    print(f"매칭된 키: {len(matched_keys)}")
    
    # apc_hist_index_no 유효성 확인
    psm_null = df_psm_input['apc_hist_index_no'].isna().sum()
    final_null = df_final_adi['apc_hist_index_no'].isna().sum()
    if psm_null > 0 or final_null > 0:
        print(f"⚠️ apc_hist_index_no NaN: df_psm_input={psm_null}, df_final_adi={final_null}")
else:
    print("데이터가 없어 매칭 키를 생성할 수 없습니다.")


if len(df_psm_input) > 0 and len(df_final_oco) > 0:
    # FCP 좌표 반올림 (소수점 2자리)

    df_final_oco['fcp_x_round'] = df_final_oco['fcp_x'].round(2)
    df_final_oco['fcp_y_round'] = df_final_oco['fcp_y'].round(2)


    df_final_oco['match_key'] = (
        df_final_oco['apc_hist_index_no'].astype(str) + '_' +
        df_final_oco['fcp_x_round'].astype(str) + '_' +
        df_final_oco['fcp_y_round'].astype(str)
    )

    # 매칭 확인
    final_keys = set(df_final_oco['match_key'].unique())
    matched_keys = psm_keys & final_keys

    print(f"df_psm_input 고유 키: {len(psm_keys)}")
    print(f"df_final_oco 고유 키: {len(final_keys)}")
    print(f"매칭된 키: {len(matched_keys)}")
    
    # apc_hist_index_no 유효성 확인
    psm_null = df_psm_input['apc_hist_index_no'].isna().sum()
    final_null = df_final_oco['apc_hist_index_no'].isna().sum()
    if psm_null > 0 or final_null > 0:
        print(f"⚠️ apc_hist_index_no NaN: df_psm_input={psm_null}, df_final_oco={final_null}")
else:
    print("데이터가 없어 매칭 키를 생성할 수 없습니다.")

df_psm_input.to_excel('df_psm_input_13.xlsx')
df_final_adi.to_excel('df_final_adi_13.xlsx')
df_final_oco.to_excel('df_final_oco_13.xlsx')

# PSM Fitting 실행
df_final_adi = shot_fitting(df_final_adi, df_psm_input, k_col_prefix="mrc_k", result_prefix="psm_fit")
df_final_oco = shot_fitting(df_final_oco, df_psm_input, k_col_prefix="mrc_k", result_prefix="psm_fit")

df_final_adi.to_excel('df_final_adi_13_2.xlsx')
df_final_oco.to_excel('df_final_oco_13_2.xlsx')
