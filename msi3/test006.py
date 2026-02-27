# 6
# =========================
# NAUTIL_PARAMDATA 쿼리
# DB_USER: SIMAXP2
# 시점: impala_insert_time, yyyymmdd
# 주의: lot_transn_seq가 없음! photo_transn_seq 사용
# subname='F1' 필터: base_eqp_id1 추출 용도
# =========================


# 필터 조건 구성
mstepseq_filter = f"AND p.mstepseq = '{target_mstepseq}'" if target_mstepseq else ""



if len(df_lotinfo) == 0:
    print("⚠️ LOTINFO 데이터가 없습니다. NAUTIL_PARAMDATA 쿼리를 건너뜁니다.")
    df_paramdata = pd.DataFrame()
else:
    # LOTINFO에서 photo_transn_seq 리스트 생성
    photo_transn_seqs = df_lotinfo['photo_transn_seq'].unique().tolist()
    photo_transn_seq_str = ",".join([str(x) for x in photo_transn_seqs[:1000]])  # 최대 1000개로 제한
    
    sql_paramdata = f"""
    SELECT
      p.photo_transn_seq,
      p.lotid,
      p.slotid,
      p.base_eqp_id1
    FROM ees_ds_eai.apc_nautil_paramdata p
    WHERE p.impala_insert_time >= now() - interval {days} days
      AND p.db_user = '{db_user}'
      AND p.photo_transn_seq IN ({photo_transn_seq_str})
      AND p.subname = 'F1'
      {mstepseq_filter}


    LIMIT 1000000
    """
    
    print("NAUTIL_PARAMDATA 데이터 조회 시작... (subname=F1)")
    df_paramdata = bdq.getData(sql_paramdata)
    print(f"✅ PARAMDATA rows: {len(df_paramdata)}")
    print(df_paramdata.head(20))
    
df_paramdata.to_csv('NAUTIL_PARAMDATA.csv')
