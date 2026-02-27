# 5
# =========================
# EXPO_OVERLAY_LOT 쿼리
# DB_USER: SIMAXP2
# 시점: impala_insert_time, yyyymmdd
# =========================

# 필터 조건 구성
pstepseq_filter = f"AND e.photo_step_seq = '{target_pstepseq}'" if target_pstepseq else ""



if len(df_lotinfo) == 0:
    print("⚠️ LOTINFO 데이터가 없습니다. EXPO_OVERLAY_LOT 쿼리를 건너뜁니다.")
    df_expo_overlay = pd.DataFrame()
else:
    # lotid 리스트 생성
    lotids = df_lotinfo['lotid'].unique().tolist()
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
    WHERE e.impala_insert_time >= now() - interval {expo_days} days
      AND e.db_user = '{db_user}'
      AND e.lot_id IN ('{lotid_str}')
      {pstepseq_filter}
      -- AND e.metro_step_seq = 'VC077251'  # OCO는 안떠서 제외함

      
    LIMIT 100000
    """
    
    print("EXPO_OVERLAY_LOT 데이터 조회 시작...")
    df_expo_overlay = bdq.getData(sql_expo_overlay)
    print(f"✅ EXPO_OVERLAY_LOT rows: {len(df_expo_overlay)}")
    print(df_expo_overlay.head())

df_expo_overlay.to_csv('EXPO_OVERLAY_LOT.csv')
  
