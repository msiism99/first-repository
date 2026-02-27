# 3
# =========================
# NAUTIL_DAT_LOTINFO 쿼리
# DB_USER: SIMAXP2
# 시점: impala_insert_time, yyyymmdd
# PHOTO 정보, pitch정보, chip 수, PSM MMO ref EQP, PSM id
# =========================

db_user = "SIMAXP2"

# 필터 조건 구성
lotid_filter = f"AND l.lotid in {target_lotid}" if target_lotid else ""
pstepseq_filter = f"AND l.pstepseq = '{target_pstepseq}'" if target_pstepseq else ""
mstepseq_filter = f"AND l.mstepseq = '{target_mstepseq}'" if target_mstepseq else ""

sql_lotinfo = f"""
WITH lotinfo_raw AS (
  SELECT *
  FROM (
    SELECT
      l.lot_transn_seq,
      l.photo_transn_seq,
      l.impala_insert_time,
      l.db_user,
      l.`timestamp`,
      l.lotid,
      l.slotid,
      l.pstepseq,
      l.mstepseq,
      l.ppid,
      l.peqpid,
      l.chuckid,
      l.reticleid,
      l.steppitch_x,
      l.steppitch_y,
      l.mapshift_x,
      l.mapshift_y,
      l.dmargin_x,
      l.dmargin_y,
      l.outlr_resdl_spec_ratio,
      l.chip_x_qty,
      l.chip_y_qty,
      l.psm_mmo_ref_eqp_id,
      l.per_shot_mrc_id,
      row_number() OVER (
        PARTITION BY l.lot_transn_seq, l.slotid
        ORDER BY l.impala_insert_time DESC
      ) AS rn
    FROM ees_ds_eai.apc_nautil_dat_lotinfo l
    WHERE l.impala_insert_time >= now() - interval {days} days
      AND l.`timestamp`      >= now() - interval {days} days
      AND l.`timestamp`      <= now() - interval {exclude_recent_days} days
      AND l.db_user = '{db_user}'
      {lotid_filter}
      {pstepseq_filter}
      {mstepseq_filter}
  ) t
  WHERE t.rn = 1
)
SELECT *
FROM lotinfo_raw
LIMIT 100000
"""

df_lotinfo = bdq.getData(sql_lotinfo)
print(f"✅ LOTINFO rows: {len(df_lotinfo)}")
print(f"Columns: {list(df_lotinfo.columns)}")
print(df_lotinfo.head())
df_lotinfo.to_csv('NAUTIL_DAT_LOTINFO.csv')
