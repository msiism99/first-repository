# 8
import pandas as pd

# -------------------------
# 1) 우측 테이블 "키별 최신 1건" 유틸
# -------------------------
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

# -------------------------
# 2) 우측 테이블 유니크화(A 방식)
#    - LOTINFO: slotid
#    - RAWDATA: slot_id (좌측)
#    - PARAMDATA: (photo_transn_seq, lotid, slotid)
#    - EXPO_OVERLAY: (lotid, slot_id, photo_transn_seq)
# -------------------------

# LOTINFO (lot_transn_seq + slotid)
df_lotinfo_u = keep_latest_one(
    df_lotinfo,
    keys=['lot_transn_seq', 'slotid'],
    time_cols=['impala_insert_time','timestamp','event_tsdt'],
    name="LOTINFO"
)

# TEST (lot_transn_seq + slot_id + TEST)  ※ df_raw_test가 slot_id를 가지고 있다는 전제
df_raw_test_u = keep_latest_one(
    df_raw_test,
    keys=['lot_transn_seq', 'slot_id', 'TEST'],
    time_cols=['impala_insert_time','timestamp','event_tsdt'],
    name="TEST"
)

# PERSHOTMRC (lot_transn_seq + slot_id + TEST + DieX + DieY)  ※ df_raw_pershotmrc가 slot_id를 가지고 있다는 전제
df_raw_pershotmrc_u = keep_latest_one(
    df_raw_pershotmrc,
    keys=['lot_transn_seq', 'slot_id', 'TEST', 'DieX', 'DieY'],
    time_cols=['impala_insert_time','timestamp','event_tsdt'],
    name="PERSHOTMRC"
)

# EXPO_OVERLAY_LOT: lot_id->lotid, photo_date->P_TIME, slot_id 사용
df_expo_overlay_clean = df_expo_overlay.rename(columns={
    'lot_id': 'lotid',
    'photo_date': 'P_TIME',
    
})

# ★ rework 대응: photo_transn_seq를 dedup 키에 포함하여 rework 건도 보존
df_expo_overlay_u = keep_latest_one(
    df_expo_overlay_clean,
    keys=['lotid', 'slot_id', 'photo_transn_seq'],
    time_cols=['impala_insert_time','P_TIME'],
    name="EXPO_OVERLAY_LOT"
)

# PARAMDATA: (photo_transn_seq, lotid, slotid) 기준 dedup
if len(df_paramdata) > 0:
    df_paramdata['slotid'] = df_paramdata['slotid'].astype(str).str.replace('.0', '', regex=False)
df_paramdata_u = keep_latest_one(
    df_paramdata,
    keys=['photo_transn_seq', 'lotid', 'slotid'],
    time_cols=['impala_insert_time','timestamp','event_tsdt'],
    name="PARAMDATA"
)

# -------------------------
# 2.5) slot_id / slotid 타입 통일 (str) — join 시 silent fail 방지
# -------------------------
# RAWDATA 계열: slot_id → str
if len(df_raw_rawdata) > 0:
    df_raw_rawdata['slot_id'] = df_raw_rawdata['slot_id'].astype(str).str.replace('.0', '', regex=False)
if len(df_raw_test_u) > 0:
    df_raw_test_u['slot_id'] = df_raw_test_u['slot_id'].astype(str).str.replace('.0', '', regex=False)
if len(df_raw_pershotmrc_u) > 0:
    df_raw_pershotmrc_u['slot_id'] = df_raw_pershotmrc_u['slot_id'].astype(str).str.replace('.0', '', regex=False)
# LOTINFO: slotid → str
df_lotinfo_u['slotid'] = df_lotinfo_u['slotid'].astype(str).str.replace('.0', '', regex=False)
# EXPO: slot_id → str
if len(df_expo_overlay_u) > 0:
    df_expo_overlay_u['slot_id'] = df_expo_overlay_u['slot_id'].astype(str).str.replace('.0', '', regex=False)

print("✅ slot_id/slotid 타입 통일 완료 (str)")

# -------------------------
# 3) RAWDATA 기준 조인 (행 증가 방지: validate='m:1')
# -------------------------
if len(df_raw_rawdata) == 0:
    print("⚠️ RAWDATA가 없어 조인을 진행할 수 없습니다.")
    df_result = pd.DataFrame()
else:
    df_result = df_raw_rawdata.copy()

    # 1) LOTINFO 조인
    # left: slot_id, right: slotid (이름 다름)
    df_result = df_result.merge(
        df_lotinfo_u,
        left_on=['lot_transn_seq', 'slot_id'],
        right_on=['lot_transn_seq', 'slotid'],
        how='left',
        validate='m:1',
        suffixes=('', '_lotinfo')
    )
    print(f"✅ LOTINFO 조인 완료: {len(df_result)} rows")

    # 2) TEST 조인
    if len(df_raw_test_u) > 0:
        df_result = df_result.merge(
            df_raw_test_u,
            on=['lot_transn_seq', 'slot_id', 'TEST'],
            how='left',
            validate='m:1',
            suffixes=('', '_test')
        )
        print(f"✅ TEST 조인 완료: {len(df_result)} rows")

    # 3) PERSHOTMRC 조인
    if len(df_raw_pershotmrc_u) > 0:
        df_result = df_result.merge(
            df_raw_pershotmrc_u,
            on=['lot_transn_seq', 'slot_id', 'TEST', 'DieX', 'DieY'],
            how='left',
            validate='m:1',
            suffixes=('', '_psm')
        )
        print(f"✅ PERSHOTMRC 조인 완료: {len(df_result)} rows")

    # 4) EXPO_OVERLAY_LOT 조인
    #    ★ photo_transn_seq를 조인 키에 추가 (rework 시 정확 매칭)
    #    ★ apc_hist_index_no를 가져옴 (PSM 매칭 키로 사용)
    if len(df_expo_overlay_u) > 0:
        # photo_transn_seq가 df_result에 이미 존재하는지 확인 (LOTINFO에서 옴)
        if 'photo_transn_seq' in df_result.columns:
            df_result = df_result.merge(
                df_expo_overlay_u[['lotid','slot_id','photo_transn_seq','P_TIME','apc_hist_index_no', 'apc_trocs_hist_index_no', 'mmo_mrc_ref_eqp_id']],
                on=['lotid','slot_id','photo_transn_seq'],
                how='left',
                validate='m:1'
            )
        else:
            # fallback: photo_transn_seq가 없으면 기존 방식
            df_result = df_result.merge(
                df_expo_overlay_u[['lotid','slot_id','P_TIME','apc_hist_index_no']],
                on=['lotid','slot_id'],
                how='left',
                validate='m:1'
            )
        print(f"✅ EXPO_OVERLAY_LOT 조인 완료: {len(df_result)} rows")
        print(f"   apc_hist_index_no 유효: {df_result['apc_hist_index_no'].notna().sum()}/{len(df_result)}")

    # 5) PARAMDATA 조인 (Base_EQP1)
    #    ★ lotid + slotid 추가하여 wafer별 정확 매칭
    if len(df_paramdata_u) > 0 and 'photo_transn_seq' in df_result.columns:
        # slotid 타입 통일 (df_result의 slotid도 str로)
        if 'slotid' in df_result.columns:
            df_result['slotid'] = df_result['slotid'].astype(str).str.replace('.0', '', regex=False)
        df_result = df_result.merge(
            df_paramdata_u[['photo_transn_seq', 'lotid', 'slotid', 'base_eqp_id1']],
            on=['photo_transn_seq', 'lotid', 'slotid'],
            how='left',
            validate='m:1'
        ).rename(columns={'base_eqp_id1': 'Base_EQP1'})
        print(f"✅ PARAMDATA 조인 완료: {len(df_result)} rows")

    # -------------------------
    # 4) 수치형 컬럼 일괄 변환 (Categorical/문자열 → numeric)
    #    BDQ에서 가져온 데이터가 Categorical로 들어오는 경우 대응
    # -------------------------
    numeric_cols = ['X_reg', 'Y_reg', 'PSM_X', 'PSM_Y', 'MRC_RX', 'MRC_RY']
    for col in numeric_cols:
        if col in df_result.columns:
            df_result[col] = pd.to_numeric(df_result[col], errors='coerce')
    print("✅ 수치형 컬럼 일괄 변환 완료 (Categorical → numeric)")

    
    # (선택) LOTINFO에서 생긴 중복키 컬럼 정리: right_on으로 붙은 slotid 컬럼이 필요없으면 제거
    # df_result = df_result.drop(columns=['slotid'], errors='ignore')

    print(f"\n🎯 최종 조인 결과: {len(df_result)} rows, {len(df_result.columns)} cols")


if len(df_result) > 0:
    # 컬럼명 정리
    df_result = df_result.rename(columns={
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

df_result.to_csv('df_result_rename.csv')
df_result_rename_10k = df_result.head(10_000).copy()
df_result_rename_10k.to_csv('df_result_rename_10k.csv')

