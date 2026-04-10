# 7

# =========================================================
# 0. 공통 함수: 중복 컬럼 제거
# =========================================================
def remove_duplicated_columns(df, name="df"):
    dup_cols = df.columns[df.columns.duplicated()].tolist()
    if dup_cols:
        print(f"⚠️ {name} 중복 컬럼 제거: {dup_cols}")
        df = df.loc[:, ~df.columns.duplicated()]
    return df


# =========================================================
# 1. RAWDATA 분리
# =========================================================

if len(df_rawdata_adi) > 0:
    # RAWDATA
    df_raw_rawdata_adi = df_rawdata_adi[df_rawdata_adi['data_kind'] == 'RAWDATA'].copy()
    df_raw_rawdata_adi = df_raw_rawdata_adi.rename(columns={
        'test_point_no': 'TEST',
        'coordinate_x': 'DieX',
        'coordinate_y': 'DieY',
        'value_x': 'X_reg',
        'value_y': 'Y_reg'
    })
    df_raw_rawdata_adi = remove_duplicated_columns(df_raw_rawdata_adi, "df_raw_rawdata_adi")

    # TESTDATA
    df_raw_test_adi = df_rawdata_adi[df_rawdata_adi['data_kind'] == 'TESTDATA'].copy()
    df_raw_test_adi = df_raw_test_adi.rename(columns={
        'test_point_no': 'TEST',
        'value_x': 'coordinate_X',
        'value_y': 'coordinate_Y',
        'mrc_x_valn': 'MRC_RX',
        'mrc_y_valn': 'MRC_RY'
    })
    df_raw_test_adi = df_raw_test_adi[
        ['lot_transn_seq', 'slot_id', 'TEST', 'coordinate_X', 'coordinate_Y', 'MRC_RX', 'MRC_RY']
    ]
    df_raw_test_adi = remove_duplicated_columns(df_raw_test_adi, "df_raw_test_adi")

    # PERSHOT (ADI에서만 사용)
    df_raw_pershotmrc_adi = df_rawdata_adi[df_rawdata_adi['data_kind'] == 'PERSHOT'].copy()
    df_raw_pershotmrc_adi = df_raw_pershotmrc_adi.rename(columns={
        'test_point_no': 'TEST',
        'coordinate_x': 'DieX',
        'coordinate_y': 'DieY',
        'value_x': 'PSM_X',
        'value_y': 'PSM_Y'
    })
    df_raw_pershotmrc_adi = df_raw_pershotmrc_adi[
        ['lot_transn_seq', 'slot_id', 'TEST', 'DieX', 'DieY', 'PSM_X', 'PSM_Y']
    ]
    df_raw_pershotmrc_adi = remove_duplicated_columns(df_raw_pershotmrc_adi, "df_raw_pershotmrc_adi")

    print("✅ RAWDATA_ADI 분리 완료")
    print(f"  - RAWDATA_ADI: {len(df_raw_rawdata_adi)} rows")
    print(f"  - TEST_ADI: {len(df_raw_test_adi)} rows")
    print(f"  - PERSHOT_ADI: {len(df_raw_pershotmrc_adi)} rows")

else:
    print("⚠️ RAWDATA_ADI가 없습니다.")
    df_raw_rawdata_adi = pd.DataFrame()
    df_raw_test_adi = pd.DataFrame()
    df_raw_pershotmrc_adi = pd.DataFrame()


if len(df_rawdata_oco) > 0:
    # RAWDATA
    df_raw_rawdata_oco = df_rawdata_oco[df_rawdata_oco['data_kind'] == 'RAWDATA'].copy()
    df_raw_rawdata_oco = df_raw_rawdata_oco.rename(columns={
        'test_point_no': 'TEST',
        'coordinate_x': 'DieX',
        'coordinate_y': 'DieY',
        'value_x': 'X_reg',
        'value_y': 'Y_reg'
    })
    df_raw_rawdata_oco = remove_duplicated_columns(df_raw_rawdata_oco, "df_raw_rawdata_oco")

    # TESTDATA
    df_raw_test_oco = df_rawdata_oco[df_rawdata_oco['data_kind'] == 'TESTDATA'].copy()
    df_raw_test_oco = df_raw_test_oco.rename(columns={
        'test_point_no': 'TEST',
        'value_x': 'coordinate_X',
        'value_y': 'coordinate_Y',
        'mrc_x_valn': 'MRC_RX',
        'mrc_y_valn': 'MRC_RY'
    })
    df_raw_test_oco = df_raw_test_oco[
        ['lot_transn_seq', 'slot_id', 'TEST', 'coordinate_X', 'coordinate_Y', 'MRC_RX', 'MRC_RY']
    ]
    df_raw_test_oco = remove_duplicated_columns(df_raw_test_oco, "df_raw_test_oco")

    print("✅ RAWDATA_OCO 분리 완료")
    print(f"  - RAWDATA_OCO: {len(df_raw_rawdata_oco)} rows")
    print(f"  - TEST_OCO: {len(df_raw_test_oco)} rows")

else:
    print("⚠️ RAWDATA_OCO가 없습니다.")
    df_raw_rawdata_oco = pd.DataFrame()
    df_raw_test_oco = pd.DataFrame()

df_expo_overlay_u = df_expo_overlay.rename(columns={
    'lot_id': 'lotid',
    'photo_date': 'P_TIME',
})
df_expo_overlay_u = remove_duplicated_columns(df_expo_overlay_u, "df_expo_overlay_u")


# =========================================================
# 5. ADI 조인
# ADI는 PERSHOTMRC를 붙인다
# =========================================================
if len(df_raw_rawdata_adi) == 0:
    print("⚠️ RAWDATA_ADI가 없어 조인을 진행할 수 없습니다.")
    df_result_adi = pd.DataFrame()

else:
    df_result_adi = df_raw_rawdata_adi.copy()
    df_result_adi = remove_duplicated_columns(df_result_adi, "df_result_adi_init")

    # 1) LOTINFO
    df_result_adi = df_result_adi.merge(
        df_lotinfo_adi,
        left_on=['lot_transn_seq', 'slot_id'],
        right_on=['lot_transn_seq', 'slotid'],
        how='left',
        validate='m:1',
        suffixes=('', '_lotinfo')
    )
    df_result_adi = remove_duplicated_columns(df_result_adi, "df_result_adi_after_lotinfo")
    print(f"✅ LOTINFO_ADI 조인 완료: {len(df_result_adi)} rows")

    # 2) TEST
    if len(df_raw_test_adi) > 0:
        df_result_adi = df_result_adi.merge(
            df_raw_test_adi,
            on=['lot_transn_seq', 'slot_id', 'TEST'],
            how='left',
            validate='m:1',
            suffixes=('', '_test')
        )
        df_result_adi = remove_duplicated_columns(df_result_adi, "df_result_adi_after_test")
        print(f"✅ TEST_ADI 조인 완료: {len(df_result_adi)} rows")

    # 3) PERSHOT
    if len(df_raw_pershotmrc_adi) > 0:
        df_result_adi = df_result_adi.merge(
            df_raw_pershotmrc_adi,
            on=['lot_transn_seq', 'slot_id', 'TEST', 'DieX', 'DieY'],
            how='left',
            validate='m:1',
            suffixes=('', '_psm')
        )
        df_result_adi = remove_duplicated_columns(df_result_adi, "df_result_adi_after_psm")
        print(f"✅ PERSHOTMRC_ADI 조인 완료: {len(df_result_adi)} rows")

    # 4) EXPO
    df_result_adi = remove_duplicated_columns(df_result_adi, "df_result_adi_before_expo")
    if len(df_expo_overlay_u) > 0:
        if 'photo_transn_seq' in df_result_adi.columns:
            df_result_adi = df_result_adi.merge(
                df_expo_overlay_u[
                    ['lotid', 'slot_id', 'photo_transn_seq', 'P_TIME',
                     'apc_hist_index_no', 'apc_trocs_hist_index_no', 'mmo_mrc_ref_eqp_id']
                ],
                on=['lotid', 'slot_id'],
                how='left',
                validate='m:1'
            )
            df_result_adi = remove_duplicated_columns(df_result_adi, "df_result_adi_after_expo")
        else:
            df_result_adi = df_result_adi.merge(
                df_expo_overlay_u[['lotid', 'slot_id', 'P_TIME', 'apc_hist_index_no']],
                on=['lotid', 'slot_id'],
                how='left',
                validate='m:1'
            )
            df_result_adi = remove_duplicated_columns(df_result_adi, "df_result_adi_after_expo")
        print(f"✅ EXPO_OVERLAY_LOT_ADI 조인 완료: {len(df_result_adi)} rows")
        if 'apc_hist_index_no' in df_result_adi.columns:
            print(f"   apc_hist_index_no 유효: {df_result_adi['apc_hist_index_no'].notna().sum()}/{len(df_result_adi)}")

# 5) PARAMDATA
if len(df_paramdata) > 0 and 'photo_transn_seq' in df_result_adi.columns:
    if 'slotid' in df_result_adi.columns:
        df_result_adi['slotid'] = (
            df_result_adi['slotid']
            .astype(str)
            .str.replace('.0', '', regex=False)
            .str.strip()
        )

        # PARAMDATA도 동일 타입으로 맞춤
        df_param_adi = df_paramdata[['photo_transn_seq', 'lotid', 'slotid', 'base_eqp_id1']].copy()
        df_param_adi = remove_duplicated_columns(df_param_adi, "df_param_adi")

        df_param_adi['slotid'] = (
            df_param_adi['slotid']
            .astype(str)
            .str.replace('.0', '', regex=False)
            .str.strip()
        )
        df_param_adi['lotid'] = df_param_adi['lotid'].astype(str).str.strip()
        df_param_adi['photo_transn_seq'] = df_param_adi['photo_transn_seq'].astype(str).str.strip()

        if 'lotid' in df_result_adi.columns:
            df_result_adi['lotid'] = df_result_adi['lotid'].astype(str).str.strip()
        if 'photo_transn_seq' in df_result_adi.columns:
            df_result_adi['photo_transn_seq'] = df_result_adi['photo_transn_seq'].astype(str).str.strip()

        df_result_adi = remove_duplicated_columns(df_result_adi, "df_result_adi_before_param")

        df_result_adi = df_result_adi.merge(
            df_param_adi,
            on=['photo_transn_seq', 'lotid', 'slotid'],
            how='left',
            validate='m:1'
        ).rename(columns={'base_eqp_id1': 'Base_EQP1'})

        df_result_adi = remove_duplicated_columns(df_result_adi, "df_result_adi_after_param")
        print(f"✅ PARAMDATA_ADI 조인 완료: {len(df_result_adi)} rows")

    # 수치형 변환
    numeric_cols = ['X_reg', 'Y_reg', 'PSM_X', 'PSM_Y', 'MRC_RX', 'MRC_RY']
    for col in numeric_cols:
        if col in df_result_adi.columns:
            df_result_adi[col] = pd.to_numeric(df_result_adi[col], errors='coerce')

    print(f"🎯 최종 ADI 조인 결과: {len(df_result_adi)} rows, {len(df_result_adi.columns)} cols")


# =========================================================
# 6. OCO 조인
# OCO에는 PSM을 붙이지 않는다
# =========================================================
if len(df_raw_rawdata_oco) == 0:
    print("⚠️ RAWDATA_OCO가 없어 조인을 진행할 수 없습니다.")
    df_result_oco = pd.DataFrame()

else:
    df_result_oco = df_raw_rawdata_oco.copy()
    df_result_oco = remove_duplicated_columns(df_result_oco, "df_result_oco_init")

    # 1) LOTINFO
    df_result_oco = df_result_oco.merge(
        df_lotinfo_oco,
        left_on=['lot_transn_seq', 'slot_id'],
        right_on=['lot_transn_seq', 'slotid'],
        how='left',
        validate='m:1',
        suffixes=('', '_lotinfo')
    )
    df_result_oco = remove_duplicated_columns(df_result_oco, "df_result_oco_after_lotinfo")
    print(f"✅ LOTINFO_OCO 조인 완료: {len(df_result_oco)} rows")

    # 2) TEST
    if len(df_raw_test_oco) > 0:
        df_result_oco = df_result_oco.merge(
            df_raw_test_oco,
            on=['lot_transn_seq', 'slot_id', 'TEST'],
            how='left',
            validate='m:1',
            suffixes=('', '_test')
        )
        df_result_oco = remove_duplicated_columns(df_result_oco, "df_result_oco_after_test")
        print(f"✅ TEST_OCO 조인 완료: {len(df_result_oco)} rows")

    # 3) EXPO
    df_result_oco = remove_duplicated_columns(df_result_oco, "df_result_oco_before_expo")
    if len(df_expo_overlay_u) > 0:
        if 'photo_transn_seq' in df_result_oco.columns:
            df_result_oco = df_result_oco.merge(
                df_expo_overlay_u[
                    ['lotid', 'slot_id', 'photo_transn_seq', 'P_TIME',
                     'apc_hist_index_no', 'apc_trocs_hist_index_no', 'mmo_mrc_ref_eqp_id']
                ],
                on=['lotid', 'slot_id'],
                how='left',
                validate='m:1'
            )
            df_result_oco = remove_duplicated_columns(df_result_oco, "df_result_oco_after_expo")
        else:
            df_result_oco = df_result_oco.merge(
                df_expo_overlay_u[['lotid', 'slot_id', 'P_TIME', 'apc_hist_index_no']],
                on=['lotid', 'slot_id'],
                how='left',
                validate='m:1'
            )
            df_result_oco = remove_duplicated_columns(df_result_oco, "df_result_oco_after_expo")
        print(f"✅ EXPO_OVERLAY_LOT_OCO 조인 완료: {len(df_result_oco)} rows")
        if 'apc_hist_index_no' in df_result_oco.columns:
            print(f"   apc_hist_index_no 유효: {df_result_oco['apc_hist_index_no'].notna().sum()}/{len(df_result_oco)}")

    # 4) PARAMDATA
    if len(df_paramdata) > 0 and 'photo_transn_seq' in df_result_oco.columns:
        if 'slotid' in df_result_oco.columns:
            df_result_oco['slotid'] = (
                df_result_oco['slotid']
                .astype(str)
                .str.replace('.0', '', regex=False)
                .str.strip()
            )

        # PARAMDATA도 동일 타입으로 맞춤
        df_param_oco = df_paramdata[['photo_transn_seq', 'lotid', 'slotid', 'base_eqp_id1']].copy()
        df_param_oco = remove_duplicated_columns(df_param_oco, "df_param_oco")

        df_param_oco['slotid'] = (
            df_param_oco['slotid']
            .astype(str)
            .str.replace('.0', '', regex=False)
            .str.strip()
        )
        df_param_oco['lotid'] = df_param_oco['lotid'].astype(str).str.strip()
        df_param_oco['photo_transn_seq'] = df_param_oco['photo_transn_seq'].astype(str).str.strip()

        if 'lotid' in df_result_oco.columns:
            df_result_oco['lotid'] = df_result_oco['lotid'].astype(str).str.strip()
        if 'photo_transn_seq' in df_result_oco.columns:
            df_result_oco['photo_transn_seq'] = df_result_oco['photo_transn_seq'].astype(str).str.strip()

        df_result_oco = remove_duplicated_columns(df_result_oco, "df_result_oco_before_param")

        df_result_oco = df_result_oco.merge(
            df_param_oco,
            on=['photo_transn_seq', 'lotid', 'slotid'],
            how='left',
            validate='m:1'
        ).rename(columns={'base_eqp_id1': 'Base_EQP1'})

        df_result_oco = remove_duplicated_columns(df_result_oco, "df_result_oco_after_param")
        print(f"✅ PARAMDATA_OCO 조인 완료: {len(df_result_oco)} rows")
    # 수치형 변환
    numeric_cols = ['X_reg', 'Y_reg', 'MRC_RX', 'MRC_RY']
    for col in numeric_cols:
        if col in df_result_oco.columns:
            df_result_oco[col] = pd.to_numeric(df_result_oco[col], errors='coerce')

    print(f"🎯 최종 OCO 조인 결과: {len(df_result_oco)} rows, {len(df_result_oco.columns)} cols")


# =========================================================
# 7. 컬럼명 정리
# =========================================================
if len(df_result_adi) > 0:
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
        'timestamp': 'M_TIME'
    })
    df_result_adi = remove_duplicated_columns(df_result_adi, "df_result_adi_after_rename")
    print("✅ ADI 컬럼명 정리 완료")
else:
    print("⚠️ ADI 결과 데이터가 없습니다.")

if len(df_result_oco) > 0:
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
        'timestamp': 'M_TIME'
    })
    df_result_oco = remove_duplicated_columns(df_result_oco, "df_result_oco_after_rename")
    print("✅ OCO 컬럼명 정리 완료")
else:
    print("⚠️ OCO 결과 데이터가 없습니다.")

df_result_adi = df_result_adi.drop('psm_mmo_ref_eqp_id', axis=1)
df_result_oco = df_result_oco.drop('psm_mmo_ref_eqp_id', axis=1)
df_result_adi = df_result_adi.rename(columns={'photo_transn_seq_x': 'photo_transn_seq'})
df_result_adi = df_result_adi.drop(columns=['photo_transn_seq_y'])
df_result_oco = df_result_oco.rename(columns={'photo_transn_seq_x': 'photo_transn_seq'})
df_result_oco = df_result_oco.drop(columns=['photo_transn_seq_y'])
# =========================================================
# 8. 저장
# =========================================================
df_result_adi.to_excel('df_result_adi.xlsx')
df_result_oco.to_excel('df_result_oco.xlsx')

#df_raw_rawdata_adi.to_excel('point_ADI_RAW.xlsx')
#df_raw_test_adi.to_excel('point_ADI_test.xlsx')
#df_raw_pershotmrc_adi.to_excel('point_ADI_PSM_input.xlsx')
#df_raw_rawdata_oco.to_excel('point_OCO_RAW.xlsx')
#df_raw_test_oco.to_excel('point_OCO_test.xlsx')
