# 7
# data_kind별로 분리
if len(df_rawdata_adi) > 0:
    # RAWDATA: TEST, DieX, DieY, X_reg, Y_reg
    df_raw_rawdata_adi = df_rawdata_adi[df_rawdata_adi['data_kind'] == 'RAWDATA'].copy()
    df_raw_rawdata_adi = df_raw_rawdata_adi.rename(columns={
        'test_point_no': 'TEST',
        'coordinate_x': 'DieX',
        'coordinate_y': 'DieY',
        'value_x': 'X_reg',
        'value_y': 'Y_reg'     # Point MRC사용하는 경우에는 순수계측값이 아님.  value_y = Y_reg - MRC_RY    (즉, 순수계측값에서 Point MRC를 뺴준값이   RAWDATA에서의 Value값임.)
    })
    
    # TEST: coordinate_X, coordinate_Y, MRC_RX, MRC_RY
    df_raw_test_adi = df_rawdata_adi[df_rawdata_adi['data_kind'] == 'TESTDATA'].copy()
    df_raw_test_adi = df_raw_test_adi.rename(columns={
        'test_point_no': 'TEST',
        'value_x': 'coordinate_X',
        'value_y': 'coordinate_Y',
        'mrc_x_valn': 'MRC_RX',
        'mrc_y_valn': 'MRC_RY'
    })
    df_raw_test_adi = df_raw_test_adi[['lot_transn_seq', 'slot_id', 'TEST', 'coordinate_X', 'coordinate_Y', 'MRC_RX', 'MRC_RY']]
    
    # PERSHOTMRC: MRC_X, MRC_Y
    df_raw_pershotmrc_adi = df_rawdata_adi[df_rawdata_adi['data_kind'] == 'PERSHOT'].copy()
    df_raw_pershotmrc_adi = df_raw_pershotmrc_adi.rename(columns={
        'test_point_no': 'TEST',
        'coordinate_x': 'DieX',
        'coordinate_y': 'DieY',
        'value_x': 'PSM_X',  
        'value_y': 'PSM_Y'        # PERSHOT에서의 value값은  PSM Input임.   (MRC_Y 랑 헷갈리면 안됨. )
    })
    df_raw_pershotmrc_adi = df_raw_pershotmrc_adi[['lot_transn_seq', 'slot_id', 'TEST', 'DieX', 'DieY', 'PSM_X', 'PSM_Y']]
    
    print(f"✅ RAWDATA_ADI 분리 완료")
    print(f"  - RAWDATA_ADI: {len(df_raw_rawdata_adi)} rows")
    print(f"  - TEST_ADI: {len(df_raw_test_adi)} rows")
    print(f"  - PERSHOT_ADI: {len(df_raw_pershotmrc_adi)} rows")
else:
    print("⚠️ RAWDATA_ADI가 없습니다.")
    df_raw_rawdata_adi = pd.DataFrame()
    df_raw_test_adi = pd.DataFrame()
    df_raw_pershotmrc_adi = pd.DataFrame()


if len(df_rawdata_oco) > 0:
    # RAWDATA: TEST, DieX, DieY, X_reg, Y_reg
    df_raw_rawdata_oco = df_rawdata_oco[df_rawdata_oco['data_kind'] == 'RAWDATA'].copy()
    df_raw_rawdata_oco = df_raw_rawdata_oco.rename(columns={
        'test_point_no': 'TEST',
        'coordinate_x': 'DieX',
        'coordinate_y': 'DieY',
        'value_x': 'X_reg',
        'value_y': 'Y_reg'     # Point MRC사용하는 경우에는 순수계측값이 아님.  value_y = Y_reg - MRC_RY    (즉, 순수계측값에서 Point MRC를 뺴준값이   RAWDATA에서의 Value값임.)
    })
    
    # TEST: coordinate_X, coordinate_Y, MRC_RX, MRC_RY
    df_raw_test_oco = df_rawdata_oco[df_rawdata_oco['data_kind'] == 'TESTDATA'].copy()
    df_raw_test_oco = df_raw_test_oco.rename(columns={
        'test_point_no': 'TEST',
        'value_x': 'coordinate_X',
        'value_y': 'coordinate_Y',
        'mrc_x_valn': 'MRC_RX',
        'mrc_y_valn': 'MRC_RY'
    })
    df_raw_test_oco = df_raw_test_oco[['lot_transn_seq', 'slot_id', 'TEST', 'coordinate_X', 'coordinate_Y', 'MRC_RX', 'MRC_RY']]
    
    print(f"✅ RAWDATA_OCO 분리 완료")
    print(f"  - RAWDATA_OCO: {len(df_raw_rawdata_oco)} rows")
    print(f"  - TEST_OCO: {len(df_raw_test_oco)} rows")
else:
    print("⚠️ RAWDATA_OCO가 없습니다.")
    df_raw_rawdata_oco = pd.DataFrame()
    df_raw_test_oco = pd.DataFrame()




def keep_latest_one(df, keys, time_cols, name=""):
    if df is None or len(df) == 0:
        return df
    use_cols = [c for c in time_cols if c in df.columns]
    tmp = df.copy()

    if len(use_cols) > 0:
        for c in use_cols:
            tmp[c] = pd.to_datetime(tmp[c], errors="coerce")
        tmp = tmp.sort_values(use_cols, ascending=True)
        df_u = tmp.drop_duplicates(keys, keep="last")
    else:
        df_u = tmp.drop_duplicates(keys, keep="last")

    print(f"[{name}] unique by {keys}: {len(df)} -> {len(df_u)}")
    return df_u

df_lotinfo_adi = keep_latest_one(
    df_lotinfo_adi,
    keys=['lot_transn_seq', 'slotid'],
    time_cols=['impala_insert_time','timestamp','event_tsdt'],
    name="LOTINFO"
)
df_lotinfo_oco = keep_latest_one(
    df_lotinfo_oco,
    keys=['lot_transn_seq', 'slotid'],
    time_cols=['impala_insert_time','timestamp','event_tsdt'],
    name="LOTINFO"
)

df_raw_test_adi = keep_latest_one(
    df_raw_test_adi,
    keys=['lot_transn_seq', 'slot_id', 'TEST'],
    time_cols=['impala_insert_time','timestamp','event_tsdt'],
    name="TEST"
)
df_raw_test_oco = keep_latest_one(
    df_raw_test_oco,
    keys=['lot_transn_seq', 'slot_id', 'TEST'],
    time_cols=['impala_insert_time','timestamp','event_tsdt'],
    name="TEST"
)

df_raw_pershotmrc_adi = keep_latest_one(
    df_raw_pershotmrc_adi,
    keys=['lot_transn_seq', 'slot_id', 'TEST', 'DieX', 'DieY'],
    time_cols=['impala_insert_time','timestamp','event_tsdt'],
    name="PERSHOTMRC"
)

df_expo_overlay_clean = df_expo_overlay.rename(columns={
    'lot_id': 'lotid',
    'photo_date': 'P_TIME',
})
df_expo_overlay_u = keep_latest_one(
    df_expo_overlay_clean,
    keys=['lotid', 'slot_id', 'photo_transn_seq'],
    time_cols=['impala_insert_time','P_TIME'],
    name="EXPO_OVERLAY_LOT"
)

if len(df_paramdata) > 0:
    df_paramdata['slotid'] = df_paramdata['slotid'].astype(str).str.replace('.0', '', regex=False)
df_paramdata_u = keep_latest_one(
    df_paramdata,
    keys=['photo_transn_seq', 'lotid', 'slotid'],
    time_cols=['impala_insert_time','timestamp','event_tsdt'],
    name="PARAMDATA"
)

if len(df_raw_rawdata_adi) > 0:
    df_raw_rawdata_adi['slot_id'] = df_raw_rawdata_adi['slot_id'].astype(str).str.replace('.0', '', regex=False)
if len(df_raw_rawdata_oco) > 0:
    df_raw_rawdata_oco['slot_id'] = df_raw_rawdata_oco['slot_id'].astype(str).str.replace('.0', '', regex=False)
if len(df_raw_test_adi) > 0:
    df_raw_test_adi['slot_id'] = df_raw_test_adi['slot_id'].astype(str).str.replace('.0', '', regex=False)
if len(df_raw_test_oco) > 0:
    df_raw_test_oco['slot_id'] = df_raw_test_oco['slot_id'].astype(str).str.replace('.0', '', regex=False)
if len(df_raw_pershotmrc_adi) > 0:
    df_raw_pershotmrc_adi['slot_id'] = df_raw_pershotmrc_adi['slot_id'].astype(str).str.replace('.0', '', regex=False)
# LOTINFO: slotid → str
df_lotinfo_adi['slotid'] = df_lotinfo_adi['slotid'].astype(str).str.replace('.0', '', regex=False)
df_lotinfo_oco['slotid'] = df_lotinfo_oco['slotid'].astype(str).str.replace('.0', '', regex=False)
# EXPO: slot_id → str
if len(df_expo_overlay_u) > 0:
    df_expo_overlay_u['slot_id'] = df_expo_overlay_u['slot_id'].astype(str).str.replace('.0', '', regex=False)


if len(df_raw_rawdata_adi) == 0:
    print("⚠️ RAWDATA가 없어 조인을 진행할 수 없습니다.")
    df_result_adi = pd.DataFrame()
else:
    df_result_adi = df_raw_rawdata_adi.copy()

    # 1) LOTINFO 조인
    # left: slot_id, right: slotid (이름 다름)
    df_result_adi = df_result_adi.merge(
        df_lotinfo_adi,
        left_on=['lot_transn_seq', 'slot_id'],
        right_on=['lot_transn_seq', 'slotid'],
        how='left',
        validate='m:1',
        suffixes=('', '_lotinfo')
    )
    print(f"✅ LOTINFO 조인 완료: {len(df_result_adi)} rows")

    # 2) TEST 조인
    if len(df_raw_test_adi) > 0:
        df_result_adi = df_result_adi.merge(
            df_raw_test_adi,
            on=['lot_transn_seq', 'slot_id', 'TEST'],
            how='left',
            validate='m:1',
            suffixes=('', '_test')
        )
        print(f"✅ TEST 조인 완료: {len(df_result_adi)} rows")

    # 3) PERSHOTMRC 조인
    if len(df_raw_pershotmrc_adi) > 0:
        df_result_adi = df_result_adi.merge(
            df_raw_pershotmrc_adi,
            on=['lot_transn_seq', 'slot_id', 'TEST', 'DieX', 'DieY'],
            how='left',
            validate='m:1',
            suffixes=('', '_psm')
        )
        print(f"✅ PERSHOTMRC 조인 완료: {len(df_result_adi)} rows")

    # 4) EXPO_OVERLAY_LOT 조인
    #    ★ photo_transn_seq를 조인 키에 추가 (rework 시 정확 매칭)
    #    ★ apc_hist_index_no를 가져옴 (PSM 매칭 키로 사용)
    if len(df_expo_overlay_u) > 0:
        # photo_transn_seq가 df_result에 이미 존재하는지 확인 (LOTINFO에서 옴)
        if 'photo_transn_seq' in df_result_adi.columns:
            df_result_adi = df_result_adi.merge(
                df_expo_overlay_u[['lotid','slot_id','photo_transn_seq','P_TIME','apc_hist_index_no', 'apc_trocs_hist_index_no', 'mmo_mrc_ref_eqp_id']],
                on=['lotid','slot_id','photo_transn_seq'],
                how='left',
                validate='m:1'
            )
        else:
            # fallback: photo_transn_seq가 없으면 기존 방식
            df_result_adi = df_result_adi.merge(
                df_expo_overlay_u[['lotid','slot_id','P_TIME','apc_hist_index_no']],
                on=['lotid','slot_id'],
                how='left',
                validate='m:1'
            )
        print(f"✅ EXPO_OVERLAY_LOT 조인 완료: {len(df_result_adi)} rows")
        print(f"   apc_hist_index_no 유효: {df_result_adi['apc_hist_index_no'].notna().sum()}/{len(df_result_adi)}")

    # 5) PARAMDATA 조인 (Base_EQP1)
    #    ★ lotid + slotid 추가하여 wafer별 정확 매칭
    if len(df_paramdata_u) > 0 and 'photo_transn_seq' in df_result_adi.columns:
        # slotid 타입 통일 (df_result의 slotid도 str로)
        if 'slotid' in df_result_adi.columns:
            df_result_adi['slotid'] = df_result_adi['slotid'].astype(str).str.replace('.0', '', regex=False)
        df_result_adi = df_result_adi.merge(
            df_paramdata_u[['photo_transn_seq', 'lotid', 'slotid', 'base_eqp_id1']],
            on=['photo_transn_seq', 'lotid', 'slotid'],
            how='left',
            validate='m:1'
        ).rename(columns={'base_eqp_id1': 'Base_EQP1'})
        print(f"✅ PARAMDATA 조인 완료: {len(df_result_adi)} rows")

    # -------------------------
    # 4) 수치형 컬럼 일괄 변환 (Categorical/문자열 → numeric)
    #    BDQ에서 가져온 데이터가 Categorical로 들어오는 경우 대응
    # -------------------------
    numeric_cols = ['X_reg', 'Y_reg', 'PSM_X', 'PSM_Y', 'MRC_RX', 'MRC_RY']
    for col in numeric_cols:
        if col in df_result_adi.columns:
            df_result_adi[col] = pd.to_numeric(df_result_adi[col], errors='coerce')
    print("✅ 수치형 컬럼 일괄 변환 완료 (Categorical → numeric)")

    
    # (선택) LOTINFO에서 생긴 중복키 컬럼 정리: right_on으로 붙은 slotid 컬럼이 필요없으면 제거
    # df_result = df_result.drop(columns=['slotid'], errors='ignore')

    print(f"\n🎯 최종 조인 결과: {len(df_result_adi)} rows, {len(df_result_adi.columns)} cols")


if len(df_raw_rawdata_oco) == 0:
    print("⚠️ RAWDATA가 없어 조인을 진행할 수 없습니다.")
    df_result_oco = pd.DataFrame()
else:
    df_result_oco = df_raw_rawdata_oco.copy()

    # 1) LOTINFO 조인
    # left: slot_id, right: slotid (이름 다름)
    df_result_oco = df_result_oco.merge(
        df_lotinfo_oco,
        left_on=['lot_transn_seq', 'slot_id'],
        right_on=['lot_transn_seq', 'slotid'],
        how='left',
        validate='m:1',
        suffixes=('', '_lotinfo')
    )
    print(f"✅ LOTINFO 조인 완료: {len(df_result_oco)} rows")

    # 2) TEST 조인
    if len(df_raw_test_oco) > 0:
        df_result_oco = df_result_oco.merge(
            df_raw_test_oco,
            on=['lot_transn_seq', 'slot_id', 'TEST'],
            how='left',
            validate='m:1',
            suffixes=('', '_test')
        )
        print(f"✅ TEST 조인 완료: {len(df_result_oco)} rows")

    # 3) PERSHOTMRC 조인
    if len(df_raw_pershotmrc_adi) > 0:
        df_result_oco = df_result_oco.merge(
            df_raw_pershotmrc_adi,
            on=['lot_transn_seq', 'slot_id', 'TEST', 'DieX', 'DieY'],
            how='left',
            validate='m:1',
            suffixes=('', '_psm')
        )
        print(f"✅ PERSHOTMRC 조인 완료: {len(df_result_oco)} rows")

    # 4) EXPO_OVERLAY_LOT 조인
    #    ★ photo_transn_seq를 조인 키에 추가 (rework 시 정확 매칭)
    #    ★ apc_hist_index_no를 가져옴 (PSM 매칭 키로 사용)
    if len(df_expo_overlay_u) > 0:
        # photo_transn_seq가 df_result에 이미 존재하는지 확인 (LOTINFO에서 옴)
        if 'photo_transn_seq' in df_result_oco.columns:
            df_result_oco = df_result_oco.merge(
                df_expo_overlay_u[['lotid','slot_id','photo_transn_seq','P_TIME','apc_hist_index_no', 'apc_trocs_hist_index_no', 'mmo_mrc_ref_eqp_id']],
                on=['lotid','slot_id','photo_transn_seq'],
                how='left',
                validate='m:1'
            )
        else:
            # fallback: photo_transn_seq가 없으면 기존 방식
            df_result_oco = df_result_oco.merge(
                df_expo_overlay_u[['lotid','slot_id','P_TIME','apc_hist_index_no']],
                on=['lotid','slot_id'],
                how='left',
                validate='m:1'
            )
        print(f"✅ EXPO_OVERLAY_LOT 조인 완료: {len(df_result_oco)} rows")
        print(f"   apc_hist_index_no 유효: {df_result_oco['apc_hist_index_no'].notna().sum()}/{len(df_result_oco)}")

    # 5) PARAMDATA 조인 (Base_EQP1)
    #    ★ lotid + slotid 추가하여 wafer별 정확 매칭
    if len(df_paramdata_u) > 0 and 'photo_transn_seq' in df_result_oco.columns:
        # slotid 타입 통일 (df_result의 slotid도 str로)
        if 'slotid' in df_result_oco.columns:
            df_result_oco['slotid'] = df_result_oco['slotid'].astype(str).str.replace('.0', '', regex=False)
        df_result_oco = df_result_oco.merge(
            df_paramdata_u[['photo_transn_seq', 'lotid', 'slotid', 'base_eqp_id1']],
            on=['photo_transn_seq', 'lotid', 'slotid'],
            how='left',
            validate='m:1'
        ).rename(columns={'base_eqp_id1': 'Base_EQP1'})
        print(f"✅ PARAMDATA 조인 완료: {len(df_result_oco)} rows")

    # -------------------------
    # 4) 수치형 컬럼 일괄 변환 (Categorical/문자열 → numeric)
    #    BDQ에서 가져온 데이터가 Categorical로 들어오는 경우 대응
    # -------------------------
    numeric_cols = ['X_reg', 'Y_reg', 'PSM_X', 'PSM_Y', 'MRC_RX', 'MRC_RY']
    for col in numeric_cols:
        if col in df_result_oco.columns:
            df_result_oco[col] = pd.to_numeric(df_result_oco[col], errors='coerce')
    print("✅ 수치형 컬럼 일괄 변환 완료 (Categorical → numeric)")

    
    # (선택) LOTINFO에서 생긴 중복키 컬럼 정리: right_on으로 붙은 slotid 컬럼이 필요없으면 제거
    # df_result = df_result.drop(columns=['slotid'], errors='ignore')

    print(f"\n🎯 최종 조인 결과: {len(df_result_oco)} rows, {len(df_result_oco.columns)} cols")



if len(df_result_adi) > 0:
    # 컬럼명 정리
    df_result_adi = df_result_adi.rename(columns={
        'pstepseq': 'STEPSEQ',
        'lotid': 'LOT_ID',
        'slotid': 'Wafer',
        'peqpid': 'P_EQPID',
        'ppid': 'Photo_PPID',
        'chuckid': 'ChuckID',
        'reticleid': 'ReticleID',
        'steppitch_x': 'STEP_PITCH_X',
        'steppitch_y': 'STEP_PITCH_Y',
        'mapshift_x': 'MAP_SHIFT_X',
        'mapshift_y': 'MAP_SHIFT_Y',
        'dmargin_x': 'Dmargin_X',
        'dmargin_y': 'Dmargin_Y',
        'outlr_resdl_spec_ratio': 'Outlier_Spec_Ratio',
        'chip_x_qty': 'CHIP_X_NUM',
        'chip_y_qty': 'CHIP_Y_NUM',
        'mmo_mrc_ref_eqp_id': 'MMO_MRC_EQP',
        'mstepseq': 'M_STEPSEQ',
        'timestamp' : 'M_TIME'
    })
    
    print("✅ 컬럼명 정리 완료")
else:
    print("⚠️ 결과 데이터가 없습니다.")

if len(df_result_oco) > 0:
    # 컬럼명 정리
    df_result_oco = df_result_oco.rename(columns={
        'pstepseq': 'STEPSEQ',
        'lotid': 'LOT_ID',
        'slotid': 'Wafer',
        'peqpid': 'P_EQPID',
        'ppid': 'Photo_PPID',
        'chuckid': 'ChuckID',
        'reticleid': 'ReticleID',
        'steppitch_x': 'STEP_PITCH_X',
        'steppitch_y': 'STEP_PITCH_Y',
        'mapshift_x': 'MAP_SHIFT_X',
        'mapshift_y': 'MAP_SHIFT_Y',
        'dmargin_x': 'Dmargin_X',
        'dmargin_y': 'Dmargin_Y',
        'outlr_resdl_spec_ratio': 'Outlier_Spec_Ratio',
        'chip_x_qty': 'CHIP_X_NUM',
        'chip_y_qty': 'CHIP_Y_NUM',
        'mmo_mrc_ref_eqp_id': 'MMO_MRC_EQP',
        'mstepseq': 'M_STEPSEQ',
        'timestamp' : 'M_TIME'
    })
    
    print("✅ 컬럼명 정리 완료")
else:
    print("⚠️ 결과 데이터가 없습니다.")

df_result_adi[0:10000].to_excel('df_result_adi_10000.xlsx')
df_result_oco[0:10000].to_excel('df_result_oco_10000.xlsx')



df_raw_rawdata_adi.to_excel('point_ADI_RAW.xlsx')
df_raw_test_adi.to_excel('point_ADI_test.xlsx')
df_raw_pershotmrc_adi.to_excel('point_ADI_PSM_input.xlsx')
df_raw_rawdata_oco.to_excel('point_OCO_RAW.xlsx')
df_raw_test_oco.to_excel('point_OCO_test.xlsx')
