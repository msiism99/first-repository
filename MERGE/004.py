# 4

# =========================
# EXPO_OVERLAY_LOT 쿼리
# DB_USER: SIMAXP2
# 시점: impala_insert_time, yyyymmdd
# =========================

# 필터 조건 구성
pstepseq_filter = f"AND e.photo_step_seq = '{target_pstepseq}'" if target_pstepseq else ""



if len(df_lotinfo_adi) == 0:
    print("⚠️ LOTINFO 데이터가 없습니다. EXPO_OVERLAY_LOT 쿼리를 건너뜁니다.")
    df_expo_overlay = pd.DataFrame()
else:
    # lotid 리스트 생성
    lotids = df_lotinfo_adi['lotid'].unique().tolist()
    lotid_str = "','".join([str(x) for x in lotids[:1000]])
    
    sql_expo_overlay = f"""
    SELECT
      CAST(e.apc_hist_index_no AS BIGINT) AS apc_hist_index_no,
      e.apc_trocs_hist_index_no,
      e.impala_insert_time,
      e.seq_no,      
      e.lot_id,
      e.slot_id,
      e.photo_step_seq,
      e.metro_step_seq,
      e.photo_date,
      -- e.metro_date,        # OCO는 안떠서 제외함
      e.photo_transn_seq,
      e.mmo_mrc_ref_eqp_id
      -- e.metro_transn_seq   # OCO는 안떠서 제외함
      
     
    FROM ees_ds_eai.apc_expo_overlay_lot e
    WHERE e.impala_insert_time >= now() - interval {expo_days+5} days
      AND e.db_user = '{db_user}'
      AND e.lot_id IN ('{lotid_str}')
      {pstepseq_filter}
      -- AND e.metro_step_seq = 'VC077251'  # OCO는 안떠서 제외함

    LIMIT 100000
    """
    
    print("EXPO_OVERLAY_LOT 데이터 조회 시작...")
    df_expo_overlay = bdq.getData(sql_expo_overlay)
    df_expo_overlay = (
        df_expo_overlay
        .sort_values('photo_date')
        .drop_duplicates(['lot_id', 'slot_id'], keep='last')
        .reset_index(drop=True)
    )
    df_expo_overlay['slot_id'] = df_expo_overlay['slot_id'].astype(int)
    df_lotinfo_adi['slotid'] = df_lotinfo_adi['slotid'].astype(int)
    df_expo_overlay = df_expo_overlay.merge(
        df_lotinfo_adi[['lotid', 'slotid']].drop_duplicates(),
        left_on=['lot_id', 'slot_id'],   # df_rawdata_adi 기준 컬럼
        right_on=['lotid', 'slotid'],   # df_lotinfo_adi 기준 컬럼
        how='inner'
    ).reset_index(drop=True)

    print(f"✅ EXPO_OVERLAY_LOT rows: {len(df_expo_overlay)}")
    print(df_expo_overlay.head())

df_expo_overlay = df_expo_overlay.sort_values(by=['photo_transn_seq', 'slotid'], ascending=[True, True]).reset_index(drop=True)

df_expo_overlay.to_excel('EXPO_OVERLAY_LOT.xlsx')








# =========================
# NAUTIL_PARAMDATA 쿼리
# DB_USER: SIMAXP2
# 시점: impala_insert_time
# 주의: lot_transn_seq가 없음! photo_transn_seq 사용
# subname='F1' 필터: base_eqp_id1 추출 용도
# =========================

mstepseq_filter = f"AND p.mstepseq = '{target_mstepseq}'" if target_mstepseq else ""

if len(df_lotinfo_adi) == 0:
    print("⚠️ LOTINFO 데이터가 없습니다. NAUTIL_PARAMDATA 쿼리를 건너뜁니다.")
    df_paramdata = pd.DataFrame()

else:
    photo_transn_seqs = (
        df_lotinfo_adi['photo_transn_seq']
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if len(photo_transn_seqs) == 0:
        print("⚠️ photo_transn_seq가 없어 NAUTIL_PARAMDATA 쿼리를 건너뜁니다.")
        df_paramdata = pd.DataFrame()

    else:
        # 숫자형이면 따옴표 없이, 문자형이면 따옴표 포함이 필요할 수 있는데
        # 기존 흐름상 숫자형으로 보이므로 그대로 유지
        photo_transn_seq_str = ",".join(photo_transn_seqs[:1000])

        sql_paramdata = f"""
        SELECT
          p.photo_transn_seq,
          p.lotid,
          p.slotid,
          p.base_eqp_id1,
          p.impala_insert_time
        FROM ees_ds_eai.apc_nautil_paramdata p
        WHERE p.impala_insert_time >= now() - interval {days+5} days
          AND p.db_user = '{db_user}'
          AND p.photo_transn_seq IN ({photo_transn_seq_str})
          AND p.subname = 'F1'
          {mstepseq_filter}
        LIMIT 1000000
        """

        print("NAUTIL_PARAMDATA 데이터 조회 시작... (subname=F1)")
        df_paramdata = bdq.getData(sql_paramdata)

        if len(df_paramdata) > 0:
            if 'slotid' in df_paramdata.columns:
                df_paramdata['slotid'] = (
                    df_paramdata['slotid']
                    .astype(str)
                    .str.strip()
                    .str.replace('.0', '', regex=False)
                )

        print(f"✅ PARAMDATA rows: {len(df_paramdata)}")
        print(df_paramdata.head(20))
df_paramdata['slotid'] = df_paramdata['slotid'].astype(int)
df_paramdata = df_paramdata.merge(
    df_lotinfo_adi[['photo_transn_seq', 'slotid']].drop_duplicates(),
    left_on=['photo_transn_seq', 'slotid'],   # df_rawdata_adi 기준 컬럼
    right_on=['photo_transn_seq', 'slotid'],   # df_lotinfo_adi 기준 컬럼
    how='inner'
).reset_index(drop=True)
df_paramdata = df_paramdata.sort_values(by=['photo_transn_seq', 'slotid'], ascending=[True, True]).reset_index(drop=True)
df_paramdata.to_excel('NAUTIL_PARAMDATA.xlsx', index=False)
