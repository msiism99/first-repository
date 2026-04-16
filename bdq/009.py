# 9
# GROUP 생성 E1~E3
df_result_adi['GROUP'] = pd.cut(df_result_adi['TEST'], bins=[0, 80, 160, 240], labels=['E1', 'E2', 'E3'])
df_result_oco['GROUP'] = pd.cut(df_result_oco['TEST'], bins=[0, 80, 160, 240], labels=['E1', 'E2', 'E3'])

if target_mstepseq_oco[2:5] == '077':
    df_result_oco = df_result_oco[df_result_oco['GROUP'] == 'E2']
else:
    df_result_oco = df_result_oco[df_result_oco['GROUP'] == 'E1']

# 4.3 좌표계

if len(df_result_adi) > 0:
    cols = ["DieX","DieY","STEP_PITCH_X","STEP_PITCH_Y","MAP_SHIFT_X","MAP_SHIFT_Y", "coordinate_X", "coordinate_Y"]

    # 숫자형으로 강제 변환 (Categorical/문자열 포함 대응)
    for c in cols:
        df_result_adi[c] = pd.to_numeric(df_result_adi[c].astype(str).str.strip(), errors="coerce")

    # Field Center Position 계산
    df_result_adi["fcp_x"] = df_result_adi["DieX"] * df_result_adi["STEP_PITCH_X"] + df_result_adi["MAP_SHIFT_X"]
    df_result_adi["fcp_y"] = df_result_adi["DieY"] * df_result_adi["STEP_PITCH_Y"] + df_result_adi["MAP_SHIFT_Y"]
    
    # Wafer 좌표 계산
    df_result_adi['wf_x'] = df_result_adi['fcp_x'] + df_result_adi['coordinate_X']
    df_result_adi['wf_y'] = df_result_adi['fcp_y'] + df_result_adi['coordinate_Y']
    
    # Radius 계산 (웨이퍼 중심으로부터의 거리)
    df_result_adi['radius'] = np.sqrt(df_result_adi['wf_x']**2 + df_result_adi['wf_y']**2)
    
    print("✅ 좌표 계산 완료 (fcp_x/y, wf_x/y, radius)")

if len(df_result_oco) > 0:
    cols = ["DieX","DieY","STEP_PITCH_X","STEP_PITCH_Y","MAP_SHIFT_X","MAP_SHIFT_Y", "coordinate_X", "coordinate_Y"]

    # 숫자형으로 강제 변환 (Categorical/문자열 포함 대응)
    for c in cols:
        df_result_oco[c] = pd.to_numeric(df_result_oco[c].astype(str).str.strip(), errors="coerce")

    # Field Center Position 계산
    df_result_oco["fcp_x"] = df_result_oco["DieX"] * df_result_oco["STEP_PITCH_X"] + df_result_oco["MAP_SHIFT_X"]
    df_result_oco["fcp_y"] = df_result_oco["DieY"] * df_result_oco["STEP_PITCH_Y"] + df_result_oco["MAP_SHIFT_Y"]
    
    # Wafer 좌표 계산
    df_result_oco['wf_x'] = df_result_oco['fcp_x'] + df_result_oco['coordinate_X']
    df_result_oco['wf_y'] = df_result_oco['fcp_y'] + df_result_oco['coordinate_Y']
    
    # Radius 계산 (웨이퍼 중심으로부터의 거리)
    df_result_oco['radius'] = np.sqrt(df_result_oco['wf_x']**2 + df_result_oco['wf_y']**2)
    
    print("✅ 좌표 계산 완료 (fcp_x/y, wf_x/y, radius)")

    

# 4.5 UNIQUE_ID 생성
    
if len(df_result_adi) == 0:
    print("⚠️ df_result_adi가 비어있어 UNIQUE_ID를 생성하지 않습니다.")
else:
    # 1) index 혼합(str/int)로 인한 alignment/정렬 에러 방지
    df_result_adi = df_result_adi.reset_index(drop=True)

    def _get_series(col, default=""):
        """
        - 컬럼명이 중복이면(DataFrame으로 잡히면) 첫 번째 컬럼만 사용
        - 항상 string dtype Series로 반환
        """
        if col not in df_result_adi.columns:
            return pd.Series([default] * len(df_result_adi), index=df_result_adi.index, dtype="string")

        x = df_result_adi[col]
        # 중복 컬럼명 -> DataFrame으로 나올 수 있음
        if isinstance(x, pd.DataFrame):
            x = x.iloc[:, 0]

        return x.astype("string").fillna(default)

    def _np_str(s: pd.Series) -> np.ndarray:
        # numpy에서 안전하게 문자열 배열로
        return s.to_numpy(dtype=object).astype(str)

    def _join_np(arr_list, sep="_"):
        """
        numpy char.add로 빠르게 결합
        arr_list: 1D numpy arrays (dtype object/str)
        """
        out = arr_list[0]
        for a in arr_list[1:]:
            out = np.char.add(np.char.add(out, sep), a)
        return out

    required_cols = ['STEPSEQ', 'P_EQPID', 'Photo_PPID', 'MMO_MRC_EQP', 'P_TIME', 'M_TIME', 'LOT_ID', 'Wafer']
    missing_cols = [c for c in required_cols if c not in df_result_adi.columns]

    if missing_cols:
        print(f"⚠️ UNIQUE_ID 생성에 필요한 컬럼 누락: {missing_cols}")
        uid = _join_np([_np_str(_get_series('lot_transn_seq')), _np_str(_get_series('Wafer'))], sep="_")
        df_result_adi['UNIQUE_ID'] = uid
        print("✅ 기본 UNIQUE_ID 생성 완료")
    else:
        step   = _np_str(_get_series('STEPSEQ'))
        peqpid = _np_str(_get_series('P_EQPID'))
        ppid   = _np_str(_get_series('Photo_PPID'))
        mrc    = _np_str(_get_series('MMO_MRC_EQP'))
        ptime  = _np_str(_get_series('P_TIME'))
        mtime  = _np_str(_get_series('M_TIME'))
        lotid  = _np_str(_get_series('LOT_ID'))
        wafer  = _np_str(_get_series('Wafer'))

        group = _np_str(_get_series('GROUP'))
        test  = _np_str(_get_series('TEST'))
        diex  = _np_str(_get_series('DieX'))
        diey  = _np_str(_get_series('DieY'))

        # base = STEPSEQ_P_EQPID_Photo_PPID_MMO_MRC_EQP_P_TIME_M_TIME_LOT_ID_Wafer
        base = _join_np([step, peqpid, ppid, mrc, ptime, mtime, lotid, wafer], sep="_")

        df_result_adi['UNIQUE_ID3'] = base
        df_result_adi['UNIQUE_ID']  = _join_np([base, group], sep="_")
        df_result_adi['UNIQUE_ID2'] = _join_np([base, test, diex, diey, group], sep="_")
        df_result_adi['UNIQUE_ID4'] = _join_np([base, diex, diey, group], sep="_")

        print("✅ UNIQUE_ID 시리즈 생성 완료 (UNIQUE_ID, UNIQUE_ID2, UNIQUE_ID3, UNIQUE_ID4)")

if len(df_result_oco) == 0:
    print("⚠️ df_result_oco가 비어있어 UNIQUE_ID를 생성하지 않습니다.")
else:
    # 1) index 혼합(str/int)로 인한 alignment/정렬 에러 방지
    df_result_oco = df_result_oco.reset_index(drop=True)

    def _get_series(col, default=""):
        """
        - 컬럼명이 중복이면(DataFrame으로 잡히면) 첫 번째 컬럼만 사용
        - 항상 string dtype Series로 반환
        """
        if col not in df_result_oco.columns:
            return pd.Series([default] * len(df_result_oco), index=df_result_oco.index, dtype="string")

        x = df_result_oco[col]
        # 중복 컬럼명 -> DataFrame으로 나올 수 있음
        if isinstance(x, pd.DataFrame):
            x = x.iloc[:, 0]

        return x.astype("string").fillna(default)

    def _np_str(s: pd.Series) -> np.ndarray:
        # numpy에서 안전하게 문자열 배열로
        return s.to_numpy(dtype=object).astype(str)

    def _join_np(arr_list, sep="_"):
        """
        numpy char.add로 빠르게 결합
        arr_list: 1D numpy arrays (dtype object/str)
        """
        out = arr_list[0]
        for a in arr_list[1:]:
            out = np.char.add(np.char.add(out, sep), a)
        return out

    required_cols = ['STEPSEQ', 'P_EQPID', 'Photo_PPID', 'MMO_MRC_EQP', 'P_TIME', 'M_TIME', 'LOT_ID', 'Wafer']
    missing_cols = [c for c in required_cols if c not in df_result_oco.columns]

    if missing_cols:
        print(f"⚠️ UNIQUE_ID 생성에 필요한 컬럼 누락: {missing_cols}")
        uid = _join_np([_np_str(_get_series('lot_transn_seq')), _np_str(_get_series('Wafer'))], sep="_")
        df_result_oco['UNIQUE_ID'] = uid
        print("✅ 기본 UNIQUE_ID 생성 완료")
    else:
        step   = _np_str(_get_series('STEPSEQ'))
        peqpid = _np_str(_get_series('P_EQPID'))
        ppid   = _np_str(_get_series('Photo_PPID'))
        mrc    = _np_str(_get_series('MMO_MRC_EQP'))
        ptime  = _np_str(_get_series('P_TIME'))
        mtime  = _np_str(_get_series('M_TIME'))
        lotid  = _np_str(_get_series('LOT_ID'))
        wafer  = _np_str(_get_series('Wafer'))

        group = _np_str(_get_series('GROUP'))
        test  = _np_str(_get_series('TEST'))
        diex  = _np_str(_get_series('DieX'))
        diey  = _np_str(_get_series('DieY'))

        # base = STEPSEQ_P_EQPID_Photo_PPID_MMO_MRC_EQP_P_TIME_M_TIME_LOT_ID_Wafer
        base = _join_np([step, peqpid, ppid, mrc, ptime, mtime, lotid, wafer], sep="_")

        df_result_oco['UNIQUE_ID3'] = base
        df_result_oco['UNIQUE_ID']  = _join_np([base, group], sep="_")
        df_result_oco['UNIQUE_ID2'] = _join_np([base, test, diex, diey, group], sep="_")
        df_result_oco['UNIQUE_ID4'] = _join_np([base, diex, diey, group], sep="_")

        print("✅ UNIQUE_ID 시리즈 생성 완료 (UNIQUE_ID, UNIQUE_ID2, UNIQUE_ID3, UNIQUE_ID4)")


# 4.6 Edge Shot 판정

if len(df_result_adi) > 0:
    wafer_radius = 147000  # um (150mm)

    # 필요한 컬럼만 numpy로
    x  = df_result_adi['fcp_x'].to_numpy(dtype=float)
    y  = df_result_adi['fcp_y'].to_numpy(dtype=float)
    sx = df_result_adi['STEP_PITCH_X'].to_numpy(dtype=float) / 2.0
    sy = df_result_adi['STEP_PITCH_Y'].to_numpy(dtype=float) / 2.0

    # 4코너 좌표 (벡터)
    x1, y1 = x - sx, y - sy
    x2, y2 = x + sx, y - sy
    x3, y3 = x - sx, y + sy
    x4, y4 = x + sx, y + sy

    # 각 코너의 거리^2 계산 후 최대값
    d1 = x1*x1 + y1*y1
    d2 = x2*x2 + y2*y2
    d3 = x3*x3 + y3*y3
    d4 = x4*x4 + y4*y4

    max_d2 = np.maximum.reduce([d1, d2, d3, d4])  # 거리^2의 최대
    max_d  = np.sqrt(max_d2)

    df_result_adi['Max_Corner_Distance'] = max_d
    df_result_adi['Is_Edge_Shot'] = max_d > wafer_radius

    print("✅ Edge Shot 판정 완료(벡터화)")
    print(f"Edge Shot 비율: {df_result_adi['Is_Edge_Shot'].mean() * 100:.2f}%")
else:
    print("⚠️ df_result_adi가 비어있어 Edge Shot 판정을 생략합니다.")



if len(df_result_oco) > 0:
    wafer_radius = 147000  # um (150mm)

    # 필요한 컬럼만 numpy로
    x  = df_result_oco['fcp_x'].to_numpy(dtype=float)
    y  = df_result_oco['fcp_y'].to_numpy(dtype=float)
    sx = df_result_oco['STEP_PITCH_X'].to_numpy(dtype=float) / 2.0
    sy = df_result_oco['STEP_PITCH_Y'].to_numpy(dtype=float) / 2.0

    # 4코너 좌표 (벡터)
    x1, y1 = x - sx, y - sy
    x2, y2 = x + sx, y - sy
    x3, y3 = x - sx, y + sy
    x4, y4 = x + sx, y + sy

    # 각 코너의 거리^2 계산 후 최대값
    d1 = x1*x1 + y1*y1
    d2 = x2*x2 + y2*y2
    d3 = x3*x3 + y3*y3
    d4 = x4*x4 + y4*y4

    max_d2 = np.maximum.reduce([d1, d2, d3, d4])  # 거리^2의 최대
    max_d  = np.sqrt(max_d2)

    df_result_oco['Max_Corner_Distance'] = max_d
    df_result_oco['Is_Edge_Shot'] = max_d > wafer_radius

    print("✅ Edge Shot 판정 완료(벡터화)")
    print(f"Edge Shot 비율: {df_result_oco['Is_Edge_Shot'].mean() * 100:.2f}%")
else:
    print("⚠️ df_result_oco가 비어있어 Edge Shot 판정을 생략합니다.")



# 5.1 컬럼순서 정리

if len(df_result_adi) > 0:
    # 원하는 컬럼 순서 (RawData-1.csv와 동일하게)
    desired_columns = [
        # 고유 식별자
        'UNIQUE_ID', 'UNIQUE_ID2', 'UNIQUE_ID3', 'UNIQUE_ID4',
        # 기본 정보
        'STEPSEQ', 'LOT_ID', 'Wafer',
        # 장비/공정 정보
        'P_EQPID', 'Photo_PPID', 'P_TIME', 'M_TIME', 'ChuckID', 'ReticleID', 'Base_EQP1', 'MMO_MRC_EQP',
        # 측정 정보
        'GROUP', 'TEST', 'DieX', 'DieY',
        # 스텝/좌표 정보
        'STEP_PITCH_X', 'STEP_PITCH_Y', 'MAP_SHIFT_X', 'MAP_SHIFT_Y', 'coordinate_X', 'coordinate_Y',
        # 계산된 좌표
        'fcp_x', 'fcp_y', 'wf_x', 'wf_y', 'radius', 'CHIP_X_NUM', 'CHIP_Y_NUM',
        # 컨텍스트 정보
        'Outlier_Spec_Ratio', 'Dmargin_X', 'Dmargin_Y',
        # 측정값
        'X_reg', 'Y_reg', 'MRC_RX', 'MRC_RY', 'PSM_X', 'PSM_Y',       # 'MRC_X', 'MRC_Y' -> 삭제함.
        # Edge Shot
        'Is_Edge_Shot', 'Max_Corner_Distance',
        # 추가 정보
        'M_STEPSEQ',
        # KMRC/PSM 조인 키
        'photo_transn_seq',
        'apc_hist_index_no',
        'apc_trocs_hist_index_no'
    ]
    
    # 존재하는 컬럼만 선택
    available_columns = [col for col in desired_columns if col in df_result_adi.columns]
    df_final_adi = df_result_adi[available_columns].copy()
    
    print(f"✅ 최종 데이터 정리 완료")
    print(f"Shape: {df_final_adi.shape}")
    print(f"Columns: {list(df_final_adi.columns)}")
else:
    df_final_adi = pd.DataFrame()
    print("⚠️ 최종 데이터가 없습니다.")


if len(df_result_oco) > 0:
    # 원하는 컬럼 순서 (RawData-1.csv와 동일하게)
    desired_columns = [
        # 고유 식별자
        'UNIQUE_ID', 'UNIQUE_ID2', 'UNIQUE_ID3', 'UNIQUE_ID4',
        # 기본 정보
        'STEPSEQ', 'LOT_ID', 'Wafer',
        # 장비/공정 정보
        'P_EQPID', 'Photo_PPID', 'P_TIME', 'M_TIME', 'ChuckID', 'ReticleID', 'Base_EQP1', 'MMO_MRC_EQP',
        # 측정 정보
        'GROUP', 'TEST', 'DieX', 'DieY',
        # 스텝/좌표 정보
        'STEP_PITCH_X', 'STEP_PITCH_Y', 'MAP_SHIFT_X', 'MAP_SHIFT_Y', 'coordinate_X', 'coordinate_Y',
        # 계산된 좌표
        'fcp_x', 'fcp_y', 'wf_x', 'wf_y', 'radius', 'CHIP_X_NUM', 'CHIP_Y_NUM',
        # 컨텍스트 정보
        'Outlier_Spec_Ratio', 'Dmargin_X', 'Dmargin_Y',
        # 측정값
        'X_reg', 'Y_reg', 'MRC_RX', 'MRC_RY', 'PSM_X', 'PSM_Y',       # 'MRC_X', 'MRC_Y' -> 삭제함.
        # Edge Shot
        'Is_Edge_Shot', 'Max_Corner_Distance',
        # 추가 정보
        'M_STEPSEQ',
        # KMRC/PSM 조인 키
        'photo_transn_seq',
        'apc_hist_index_no',
        'apc_trocs_hist_index_no'
    ]
    
    # 존재하는 컬럼만 선택
    available_columns = [col for col in desired_columns if col in df_result_oco.columns]
    df_final_oco = df_result_oco[available_columns].copy()
    
    print(f"✅ 최종 데이터 정리 완료")
    print(f"Shape: {df_final_oco.shape}")
    print(f"Columns: {list(df_final_oco.columns)}")
else:
    df_final_oco = pd.DataFrame()
    print("⚠️ 최종 데이터가 없습니다.")

# 5.3 CSV 파일로 저장

df_final_adi.to_excel('df_final_adi.xlsx')
print(f"   - 총 {len(df_final_adi)} rows, {len(df_final_adi.columns)} columns")
df_final_oco.to_excel('df_final_oco.xlsx')
print(f"   - 총 {len(df_final_oco)} rows, {len(df_final_oco.columns)} columns")

