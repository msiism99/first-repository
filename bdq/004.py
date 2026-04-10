# 4
if len(df_lotinfo_oco) == 0:
    print("⚠️ LOTINFO 데이터가 없습니다. RAWDATA 쿼리를 건너뜁니다.")
    df_rawdata_oco = pd.DataFrame()
else:
    # lot_transn_seq 리스트 생성
    lot_transn_seqs_oco = df_lotinfo_oco['lot_transn_seq'].unique().tolist()
    lot_transn_seq_oco_str = ",".join([str(x) for x in lot_transn_seqs_oco[:1000]])  # 최대 1000개로 제한
    
    sql_rawdata_oco = f"""
    SELECT
      r.lot_transn_seq,r.slot_id,r.transn_occur_date,r.data_kind,
      r.test_point_no,r.coordinate_x,r.coordinate_y,r.value_x,r.value_y,
      r.mrc_x_valn,r.mrc_y_valn
    FROM ees_ds_eai.apc_nautil_dat_rawdata r
    WHERE r.impala_insert_time >= now() - interval {days+10} days
      AND r.db_user = '{db_user}'
      AND r.lot_transn_seq IN ({lot_transn_seq_oco_str})
      AND r.data_kind IN ('RAWDATA', 'TESTDATA', 'PERSHOT')
    LIMIT 10000000
    """
    
    print("NAUTIL_DAT_RAWDATA 데이터 조회 시작...")
    df_rawdata_oco = bdq.getData(sql_rawdata_oco)
    df_rawdata_oco['slot_id'] = df_rawdata_oco['slot_id'].astype(int)
    df_rawdata_oco = df_rawdata_oco.merge(
        df_lotinfo_oco[['lot_transn_seq', 'slotid']].drop_duplicates(),
        left_on=['lot_transn_seq', 'slot_id'],   # df_rawdata_adi 기준 컬럼
        right_on=['lot_transn_seq', 'slotid'],   # df_lotinfo_adi 기준 컬럼
        how='inner'
    ).reset_index(drop=True)

    print(f"✅ RAWDATA_OCO rows: {len(df_rawdata_oco)}")
    print(f"data_kind 분포:")
    print(df_rawdata_oco['data_kind'].value_counts())
    print(f"WF 분포:")
    print(df_rawdata_oco[['lot_transn_seq','slot_id']].value_counts())
    
    print(df_rawdata_oco.head())
df_rawdata_oco.to_excel('NAUTIL_DAT_RAWDATA_OCO.xlsx')

if len(df_lotinfo_adi) == 0:
    print("⚠️ LOTINFO 데이터가 없습니다. RAWDATA 쿼리를 건너뜁니다.")
    df_rawdata_adi = pd.DataFrame()
else:
    # lot_transn_seq 리스트 생성
    lot_transn_seqs_adi = df_lotinfo_adi['lot_transn_seq'].unique().tolist()
    lot_transn_seq_adi_str = ",".join([str(x) for x in lot_transn_seqs_adi[:1000]])  # 최대 1000개로 제한
    
    sql_rawdata_adi = f"""
    SELECT
      r.lot_transn_seq,r.slot_id,r.transn_occur_date,r.data_kind,
      r.test_point_no,r.coordinate_x,r.coordinate_y,r.value_x,r.value_y,
      r.mrc_x_valn,r.mrc_y_valn
    FROM ees_ds_eai.apc_nautil_dat_rawdata r
    WHERE r.impala_insert_time >= now() - interval {days+10} days
      AND r.db_user = '{db_user}'
      AND r.lot_transn_seq IN ({lot_transn_seq_adi_str})
      AND r.data_kind IN ('RAWDATA', 'TESTDATA', 'PERSHOT')
    LIMIT 10000000
    """
    
    print("NAUTIL_DAT_RAWDATA 데이터 조회 시작...")
    df_rawdata_adi = bdq.getData(sql_rawdata_adi)
    df_rawdata_adi['slot_id'] = df_rawdata_adi['slot_id'].astype(int)
    df_rawdata_adi = df_rawdata_adi.merge(
        df_lotinfo_adi[['lot_transn_seq', 'slotid']].drop_duplicates(),
        left_on=['lot_transn_seq', 'slot_id'],   # df_rawdata_adi 기준 컬럼
        right_on=['lot_transn_seq', 'slotid'],   # df_lotinfo_adi 기준 컬럼
        how='inner'
    ).reset_index(drop=True)

    print(f"✅ RAWDATA_OCO rows: {len(df_rawdata_adi)}")
    print(f"data_kind 분포:")
    print(df_rawdata_adi['data_kind'].value_counts())
    print(f"WF 분포:")
    print(df_rawdata_adi[['lot_transn_seq','slot_id']].value_counts())
    print(df_rawdata_adi.head())
df_rawdata_adi.to_excel('NAUTIL_DAT_RAWDATA_ADI.xlsx')
