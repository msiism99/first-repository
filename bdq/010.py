# 10

# 필터 조건 구성
mstepseq_filter = f"AND p.mstepseq = '{target_mstepseq}'" if target_mstepseq else ""

if len(df_final_adi) == 0:
    print("⚠️ df_final 데이터가 없습니다. KMRC 쿼리를 건너뜁니다.")
    df_kmrc_adi = pd.DataFrame()
else:
    # df_final에서 unique photo_transn_seq 추출
    photo_transn_seqs = df_final_adi['photo_transn_seq'].dropna().unique().tolist()
    photo_transn_seq_str = ",".join([str(x) for x in photo_transn_seqs[:1000]])
    
    sql_kmrc_adi = f"""
    SELECT
      p.photo_transn_seq,
      p.lotid,
      p.slotid,
      p.subname,
      -- W 파라미터 (wk1~wk20)
      p.wk1, p.wk2, p.wk3, p.wk4, p.wk5, p.wk6, p.wk7, p.wk8, p.wk9, p.wk10,
      p.wk11, p.wk12, p.wk13, p.wk14, p.wk15, p.wk16, p.wk17, p.wk18, p.wk19, p.wk20,
      -- R 파라미터 (rk3~rk20)
      p.rk3, p.rk4, p.rk5, p.rk6, p.rk7, p.rk8, p.rk9, p.rk10,
      p.rk11, p.rk12, p.rk13, p.rk14, p.rk15, p.rk16, p.rk17, p.rk18, p.rk19, p.rk20,
      p.impala_insert_time
    FROM ees_ds_eai.apc_nautil_paramdata p
    WHERE p.impala_insert_time >= now() - interval {days+10} days
      AND p.db_user = '{db_user}'
      AND p.photo_transn_seq IN ({photo_transn_seq_str})
      AND p.subname = 'CMP'
      {mstepseq_filter}

    LIMIT 100000
    """
    
    print("KMRC 데이터 조회 시작...")
    df_kmrc_adi = bdq.getData(sql_kmrc_adi)
    print(f"✅ KMRC rows: {len(df_kmrc_adi)}")
    
    if len(df_kmrc_adi) > 0:
        # (photo_transn_seq, lotid, slotid)별 중복 제거 (최신 1건 유지)
        df_kmrc_adi = df_kmrc_adi.sort_values('impala_insert_time', ascending=True)
        df_kmrc_adi = df_kmrc_adi.drop_duplicates(subset=['photo_transn_seq', 'lotid', 'slotid'], keep='last')
        print(f"   중복 제거 후: {len(df_kmrc_adi)} rows (unique photo_transn_seq + lotid + slotid)")
        
        # df_final과의 매칭률 확인 (LOT_ID↔lotid, Wafer↔slotid)
        df_final_keys_adi = set(
            df_final_adi[['photo_transn_seq', 'LOT_ID', 'Wafer']].dropna()
            .apply(lambda r: (r['photo_transn_seq'], r['LOT_ID'], str(r['Wafer'])), axis=1)
        )
        kmrc_keys_adi = set(
            df_kmrc_adi[['photo_transn_seq', 'lotid', 'slotid']]
            .apply(lambda r: (r['photo_transn_seq'], r['lotid'], str(r['slotid'])), axis=1)
        )
        matched = len(df_final_keys_adi & kmrc_keys_adi)
        total = len(df_final_keys_adi)
        print(f"   df_final 매칭률: {matched}/{total} 조합 ({matched/total*100:.1f}%)")
    
    print(df_kmrc_adi.head())

if len(df_final_oco) == 0:
    print("⚠️ df_final 데이터가 없습니다. KMRC 쿼리를 건너뜁니다.")
    df_kmrc_oco = pd.DataFrame()
else:
    # df_final에서 unique photo_transn_seq 추출
    photo_transn_seqs = df_final_oco['photo_transn_seq'].dropna().unique().tolist()
    photo_transn_seq_str = ",".join([str(x) for x in photo_transn_seqs[:1000]])
    
    sql_kmrc_oco = f"""
    SELECT
      p.photo_transn_seq,
      p.lotid,
      p.slotid,
      p.subname,
      -- W 파라미터 (wk1~wk20)
      p.wk1, p.wk2, p.wk3, p.wk4, p.wk5, p.wk6, p.wk7, p.wk8, p.wk9, p.wk10,
      p.wk11, p.wk12, p.wk13, p.wk14, p.wk15, p.wk16, p.wk17, p.wk18, p.wk19, p.wk20,
      -- R 파라미터 (rk3~rk20)
      p.rk3, p.rk4, p.rk5, p.rk6, p.rk7, p.rk8, p.rk9, p.rk10,
      p.rk11, p.rk12, p.rk13, p.rk14, p.rk15, p.rk16, p.rk17, p.rk18, p.rk19, p.rk20,
      p.impala_insert_time
    FROM ees_ds_eai.apc_nautil_paramdata p
    WHERE p.impala_insert_time >= now() - interval {days+10} days
      AND p.db_user = '{db_user}'
      AND p.photo_transn_seq IN ({photo_transn_seq_str})
      AND p.subname = 'CMP'
      {mstepseq_filter}

    LIMIT 100000
    """
    
    print("KMRC 데이터 조회 시작...")
    df_kmrc_oco = bdq.getData(sql_kmrc_oco)
    print(f"✅ KMRC rows: {len(df_kmrc_oco)}")
    
    if len(df_kmrc_oco) > 0:
        # (photo_transn_seq, lotid, slotid)별 중복 제거 (최신 1건 유지)
        df_kmrc_oco = df_kmrc_oco.sort_values('impala_insert_time', ascending=True)
        df_kmrc_oco = df_kmrc_oco.drop_duplicates(subset=['photo_transn_seq', 'lotid', 'slotid'], keep='last')
        print(f"   중복 제거 후: {len(df_kmrc_oco)} rows (unique photo_transn_seq + lotid + slotid)")
        
        # df_final과의 매칭률 확인 (LOT_ID↔lotid, Wafer↔slotid)
        df_final_keys_oco = set(
            df_final_oco[['photo_transn_seq', 'LOT_ID', 'Wafer']].dropna()
            .apply(lambda r: (r['photo_transn_seq'], r['LOT_ID'], str(r['Wafer'])), axis=1)
        )
        kmrc_keys_oco = set(
            df_kmrc_oco[['photo_transn_seq', 'lotid', 'slotid']]
            .apply(lambda r: (r['photo_transn_seq'], r['lotid'], str(r['slotid'])), axis=1)
        )
        matched = len(df_final_keys_oco & kmrc_keys_oco)
        total = len(df_final_keys_oco)
        print(f"   df_final 매칭률: {matched}/{total} 조합 ({matched/total*100:.1f}%)")
    
    print(df_kmrc_oco.head())




def osr_wk20p_rk20p(x, y, rx, ry):
    """
    WK20para, RK20para (1023_1023)
    WK, RK를 FIT하기 위한 디자인 행렬.
    
    Parameters:
        x, y: 웨이퍼 좌표 (fcp_x, fcp_y)
        rx, ry: 레티클 좌표 (coordinate_X, coordinate_Y)
    
    Returns:
        X_dx: X방향 디자인 매트릭스 (N x 19)
        X_dy: Y방향 디자인 매트릭스 (N x 19)
    """
    X_dx = np.vstack([
        np.ones(len(x)),
        x / 1e6, -y / 1e6,
        (x ** 2) / 1e12, (x * y) / 1e12, (y ** 2) / 1e12,
        (x ** 3) / 1e15, (x ** 2 * y) / 1e15, (x * y ** 2) / 1e15, (y ** 3) / 1e15,
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12
    ]).T

    X_dy = np.vstack([
        np.ones(len(y)),
        y / 1e6, x / 1e6,
        (y ** 2) / 1e12, (y * x) / 1e12, (x ** 2) / 1e12,
        (y ** 3) / 1e15, (y ** 2 * x) / 1e15, (y * x ** 2) / 1e15, (x ** 3) / 1e15,
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12, (rx ** 3) / 1e12
    ]).T

    return X_dx, X_dy


coeff_keys_dx = [
    'WK1', 'WK3', 'WK5', 'WK7', 'WK9', 'WK11', 'WK13', 'WK15', 'WK17', 'WK19',
    'RK3', 'RK5', 'RK7', 'RK9', 'RK11', 'RK13', 'RK15', 'RK17', 'RK19'
]
# X_dy 19열에 대응하는 K para 이름
coeff_keys_dy = [
    'WK2', 'WK4', 'WK6', 'WK8', 'WK10', 'WK12', 'WK14', 'WK16', 'WK18', 'WK20',
    'RK4', 'RK6', 'RK8', 'RK10', 'RK12', 'RK14', 'RK16', 'RK18', 'RK20'
]

# K para 이름 → df_kmrc 컬럼명 매핑 (대소문자 변환)
kpara_to_col = {}
for i in range(1, 21):
    kpara_to_col[f'WK{i}'] = f'wk{i}'
for i in range(3, 21):   # RK는 3부터 (rk1, rk2는 테이블에 없음)
    kpara_to_col[f'RK{i}'] = f'rk{i}'

# df_kmrc에 필요한 컬럼이 모두 있는지 사전 검증
required_dx_cols = [kpara_to_col[k] for k in coeff_keys_dx]
required_dy_cols = [kpara_to_col[k] for k in coeff_keys_dy]









if len(df_kmrc_adi) == 0 or len(df_final_adi) == 0:
    print("⚠️ KMRC 또는 df_final_adi 데이터가 없어 Decorrection을 건너뜁니다.")
else:
    # 필수 컬럼 검증
    missing_cols = [c for c in set(required_dx_cols + required_dy_cols) if c not in df_kmrc_adi.columns]
    if missing_cols:
        print(f"❌ df_kmrc_adi에 필수 컬럼 누락: {missing_cols}")
        print("   KMRC Decorrection을 중단합니다.")
    else:
        print(f"✅ K para 매핑 검증 완료")
        print(f"   X방향 (coeff_keys_dx): {coeff_keys_dx}")
        print(f"   → df_kmrc_adi 컬럼: {required_dx_cols}")
        
        # df_kmrc를 (photo_transn_seq, lotid, slotid)로 인덱싱
        df_kmrc_adi['slotid'] = df_kmrc_adi['slotid'].astype(str)
        kmrc_indexed = df_kmrc_adi.set_index(['photo_transn_seq', 'lotid', 'slotid'])
        
        # df_final의 Wafer도 문자열로 통일
        df_final_adi['_wafer_str'] = df_final_adi['Wafer'].astype(str)
        print(df_final_adi[0:5])
        # 결과 저장용 Series
        mrc_fit_x = pd.Series(np.nan, index=df_final_adi.index, dtype=float)
        mrc_fit_y = pd.Series(np.nan, index=df_final_adi.index, dtype=float)
        
        # (photo_transn_seq, LOT_ID, Wafer)별로 처리
        grouped = df_final_adi.groupby(['photo_transn_seq', 'LOT_ID', '_wafer_str'])
        success_count = 0
        skip_count = 0
        
        for (pts, lotid, wafer), group in grouped:
            # 1. KMRC K값 추출 — 이름 매핑 기반
            key = (pts, lotid, wafer)
            if key not in kmrc_indexed.index:
                skip_count += 1
                continue
            
            kmrc_row = kmrc_indexed.loc[key]
            if isinstance(kmrc_row, pd.DataFrame):
                kmrc_row = kmrc_row.iloc[0]
            
            # coeff_keys 이름으로 매핑하여 K값 추출 (순서 밀림 방지)
            try:
                mrc_k_dx = np.array([float(kmrc_row[kpara_to_col[k]]) for k in coeff_keys_dx])
                mrc_k_dy = np.array([float(kmrc_row[kpara_to_col[k]]) for k in coeff_keys_dy])
            except (KeyError, ValueError) as e:
                print(f"⚠️ ({pts}, {lotid}, {wafer}): K값 추출 실패 - {e}")
                skip_count += 1
                continue
            
            # NaN 체크
            if np.isnan(mrc_k_dx).any() or np.isnan(mrc_k_dy).any():
                print(f"⚠️ ({pts}, {lotid}, {wafer}): K값에 NaN 포함, 건너뜀")
                skip_count += 1
                continue
            
            # 2. 좌표 추출
            x = group['fcp_x'].values.astype(float)
            y = group['fcp_y'].values.astype(float)
            rx = group['coordinate_X'].values.astype(float)
            ry = group['coordinate_Y'].values.astype(float)
            
            # 3. 디자인 매트릭스 생성
            X_dx, X_dy = osr_wk20p_rk20p(x, y, rx, ry)
            
            # 4. KMRC fitting (디자인매트릭스 × K값 × -1)
            #    X_dx[i열] ↔ coeff_keys_dx[i] ↔ mrc_k_dx[i] 가 이름으로 보장됨
            fit_x = X_dx.dot(mrc_k_dx) * -1
            fit_y = X_dy.dot(mrc_k_dy) * -1
            
            # 5. 결과 저장
            mrc_fit_x.loc[group.index] = fit_x
            mrc_fit_y.loc[group.index] = fit_y
            
            success_count += 1
        
        # 6. df_final_adi에 컬럼 추가
        df_final_adi['mrc_fit_x'] = mrc_fit_x
        df_final_adi['mrc_fit_y'] = mrc_fit_y
        df_final_adi['X_reg_demrc'] = df_final_adi['X_reg'] - df_final_adi['mrc_fit_x']
        df_final_adi['Y_reg_demrc'] = df_final_adi['Y_reg'] - df_final_adi['mrc_fit_y']

        
        # raw_x/y: de-MRC'd 값 + PERSHOTMRC
        if 'PSM_X' in df_final_adi.columns and 'PSM_Y' in df_final_adi.columns:
            df_final_adi['raw_x'] = df_final_adi['X_reg_demrc'] - df_final_adi['PSM_X']
            df_final_adi['raw_y'] = df_final_adi['Y_reg_demrc'] - df_final_adi['PSM_Y']


        # 임시 컬럼 제거
        df_final_adi.drop(columns=['_wafer_str'], inplace=True)
        
        print(f"\n✅ KMRC Decorrection 완료")
        print(f"   처리 성공: {success_count}개 (photo_transn_seq, lotid, slotid) 조합")
        print(f"   건너뜀: {skip_count}개 조합 (KMRC 데이터 없음 또는 NaN)")
        print(f"   df_final_adi 유효 행: {df_final_adi['mrc_fit_x'].notna().sum()}/{len(df_final_adi)}")

if len(df_final_adi) > 0 and 'mrc_fit_x' in df_final_adi.columns:
    print("=" * 80)
    print("KMRC Decorrection 결과 확인")
    print("=" * 80)
    
    # 새로 추가된 컬럼 통계
    new_cols = ['mrc_fit_x', 'mrc_fit_y', 'X_reg_demrc', 'Y_reg_demrc']
    print("\n[추가된 컬럼 통계]")
    print(df_final_adi[new_cols].describe())
    
    # 결측치 확인
    print("\n[결측치 확인]")
    for col in new_cols:
        null_count = df_final_adi[col].isna().sum()
        print(f"  {col}: {null_count}개 NaN ({null_count/len(df_final_adi)*100:.1f}%)")
    
    # 보정 전/후 비교
    print("\n[보정 전/후 비교 (처음 5행)]")
    compare_cols = ['photo_transn_seq', 'LOT_ID', 'Wafer', 'X_reg', 'mrc_fit_x', 'X_reg_demrc', 'Y_reg', 'mrc_fit_y', 'Y_reg_demrc']
    available = [c for c in compare_cols if c in df_final_adi.columns]
    display(df_final_adi[available].head())
    
    # CSV 저장
    df_final_adi.to_excel('df_kmrc_decor_adi.xlsx')
    print(f"   {len(df_final_adi)} rows, {len(df_final_adi.columns)} columns")
else:
    print("⚠️ KMRC Decorrection 결과가 없습니다.")










if len(df_kmrc_oco) == 0 or len(df_final_oco) == 0:
    print("⚠️ KMRC 또는 df_final 데이터가 없어 Decorrection을 건너뜁니다.")
else:
    # 필수 컬럼 검증
    missing_cols = [c for c in set(required_dx_cols + required_dy_cols) if c not in df_kmrc_oco.columns]
    if missing_cols:
        print(f"❌ df_kmrc_oco에 필수 컬럼 누락: {missing_cols}")
        print("   KMRC Decorrection을 중단합니다.")
    else:
        print(f"✅ K para 매핑 검증 완료")
        print(f"   X방향 (coeff_keys_dx): {coeff_keys_dx}")
        print(f"   → df_kmrc_oco 컬럼: {required_dx_cols}")
        
        # df_kmrc를 (photo_transn_seq, lotid, slotid)로 인덱싱
        df_kmrc_oco['slotid'] = df_kmrc_oco['slotid'].astype(str)
        kmrc_indexed = df_kmrc_oco.set_index(['photo_transn_seq', 'lotid', 'slotid'])
        
        # df_final의 Wafer도 문자열로 통일
        df_final_oco['_wafer_str'] = df_final_oco['Wafer'].astype(str)
        
        # 결과 저장용 Series
        mrc_fit_x = pd.Series(np.nan, index=df_final_oco.index, dtype=float)
        mrc_fit_y = pd.Series(np.nan, index=df_final_oco.index, dtype=float)
        
        # (photo_transn_seq, LOT_ID, Wafer)별로 처리
        grouped = df_final_oco.groupby(['photo_transn_seq', 'LOT_ID', '_wafer_str'])
        success_count = 0
        skip_count = 0
        
        for (pts, lotid, wafer), group in grouped:
            # 1. KMRC K값 추출 — 이름 매핑 기반
            key = (pts, lotid, wafer)
            if key not in kmrc_indexed.index:
                skip_count += 1
                continue
            
            kmrc_row = kmrc_indexed.loc[key]
            if isinstance(kmrc_row, pd.DataFrame):
                kmrc_row = kmrc_row.iloc[0]
            
            # coeff_keys 이름으로 매핑하여 K값 추출 (순서 밀림 방지)
            try:
                mrc_k_dx = np.array([float(kmrc_row[kpara_to_col[k]]) for k in coeff_keys_dx])
                mrc_k_dy = np.array([float(kmrc_row[kpara_to_col[k]]) for k in coeff_keys_dy])
            except (KeyError, ValueError) as e:
                print(f"⚠️ ({pts}, {lotid}, {wafer}): K값 추출 실패 - {e}")
                skip_count += 1
                continue
            
            # NaN 체크
            if np.isnan(mrc_k_dx).any() or np.isnan(mrc_k_dy).any():
                print(f"⚠️ ({pts}, {lotid}, {wafer}): K값에 NaN 포함, 건너뜀")
                skip_count += 1
                continue
            
            # 2. 좌표 추출
            x = group['fcp_x'].values.astype(float)
            y = group['fcp_y'].values.astype(float)
            rx = group['coordinate_X'].values.astype(float)
            ry = group['coordinate_Y'].values.astype(float)
            
            # 3. 디자인 매트릭스 생성
            X_dx, X_dy = osr_wk20p_rk20p(x, y, rx, ry)
            
            # 4. KMRC fitting (디자인매트릭스 × K값 × -1)
            #    X_dx[i열] ↔ coeff_keys_dx[i] ↔ mrc_k_dx[i] 가 이름으로 보장됨
            fit_x = X_dx.dot(mrc_k_dx) * -1
            fit_y = X_dy.dot(mrc_k_dy) * -1
            
            # 5. 결과 저장
            mrc_fit_x.loc[group.index] = fit_x
            mrc_fit_y.loc[group.index] = fit_y
            
            success_count += 1
        
        # 6. df_final_oco에 컬럼 추가
        df_final_oco['mrc_fit_x'] = mrc_fit_x
        df_final_oco['mrc_fit_y'] = mrc_fit_y
        df_final_oco['X_reg_demrc'] = df_final_oco['X_reg'] - df_final_oco['mrc_fit_x']
        df_final_oco['Y_reg_demrc'] = df_final_oco['Y_reg'] - df_final_oco['mrc_fit_y']

        
        # raw_x/y: de-MRC'd 값 + PERSHOTMRC
        if 'PSM_X' in df_final_oco.columns and 'PSM_Y' in df_final_oco.columns:
            df_final_oco['raw_x'] = df_final_oco['X_reg_demrc'] - df_final_oco['PSM_X']
            df_final_oco['raw_y'] = df_final_oco['Y_reg_demrc'] - df_final_oco['PSM_Y']


        # 임시 컬럼 제거
        df_final_oco.drop(columns=['_wafer_str'], inplace=True)
        
        print(f"\n✅ KMRC Decorrection 완료")
        print(f"   처리 성공: {success_count}개 (photo_transn_seq, lotid, slotid) 조합")
        print(f"   건너뜀: {skip_count}개 조합 (KMRC 데이터 없음 또는 NaN)")
        print(f"   df_final_oco 유효 행: {df_final_oco['mrc_fit_x'].notna().sum()}/{len(df_final_oco)}")

if len(df_final_oco) > 0 and 'mrc_fit_x' in df_final_oco.columns:
    print("=" * 80)
    print("KMRC Decorrection 결과 확인")
    print("=" * 80)
    
    # 새로 추가된 컬럼 통계
    new_cols = ['mrc_fit_x', 'mrc_fit_y', 'X_reg_demrc', 'Y_reg_demrc']
    print("\n[추가된 컬럼 통계]")
    print(df_final_oco[new_cols].describe())
    
    # 결측치 확인
    print("\n[결측치 확인]")
    for col in new_cols:
        null_count = df_final_oco[col].isna().sum()
        print(f"  {col}: {null_count}개 NaN ({null_count/len(df_final_oco)*100:.1f}%)")
    
    # 보정 전/후 비교
    print("\n[보정 전/후 비교 (처음 5행)]")
    compare_cols = ['photo_transn_seq', 'LOT_ID', 'Wafer', 'X_reg', 'mrc_fit_x', 'X_reg_demrc', 'Y_reg', 'mrc_fit_y', 'Y_reg_demrc']
    available = [c for c in compare_cols if c in df_final_oco.columns]
    display(df_final_oco[available].head())
    
    # CSV 저장
    df_final_oco.to_excel('df_kmrc_decor_oco.xlsx')
    print(f"   {len(df_final_oco)} rows, {len(df_final_oco.columns)} columns")
else:
    print("⚠️ KMRC Decorrection 결과가 없습니다.")
