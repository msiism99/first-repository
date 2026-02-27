# 4
# =========================
# NAUTIL_DAT_RAWDATA 쿼리
# DB_USER: SIMAXP2
# 시점: impala_insert_time, yyyymmdd
# =========================


# LOTINFO에서 추출한 키 목록으로 RAWDATA 필터링
if len(df_lotinfo) == 0:
    print("⚠️ LOTINFO 데이터가 없습니다. RAWDATA 쿼리를 건너뜁니다.")
    df_rawdata = pd.DataFrame()
else:
    # lot_transn_seq 리스트 생성
    lot_transn_seqs = df_lotinfo['lot_transn_seq'].unique().tolist()
    lot_transn_seq_str = ",".join([str(x) for x in lot_transn_seqs[:1000]])  # 최대 1000개로 제한
    
    sql_rawdata = f"""
    SELECT
      r.lot_transn_seq,
      r.slot_id,
      r.transn_occur_date,
      r.data_kind,
      r.test_point_no,
      r.coordinate_x,
      r.coordinate_y,
      r.value_x,
      r.value_y,
      r.mrc_x_valn,
      r.mrc_y_valn
    FROM ees_ds_eai.apc_nautil_dat_rawdata r
    WHERE r.impala_insert_time >= now() - interval {days} days
      AND r.db_user = '{db_user}'
      AND r.lot_transn_seq IN ({lot_transn_seq_str})
      AND r.data_kind IN ('RAWDATA', 'TESTDATA', 'PERSHOT')
    LIMIT 10000000
    """
    
    print("NAUTIL_DAT_RAWDATA 데이터 조회 시작...")
    df_rawdata = bdq.getData(sql_rawdata)
    print(f"✅ RAWDATA rows: {len(df_rawdata)}")
    print(f"data_kind 분포:")
    print(df_rawdata['data_kind'].value_counts())
    print(df_rawdata.head())
df_rawdata.to_csv('NAUTIL_DAT_RAWDATA.csv')
