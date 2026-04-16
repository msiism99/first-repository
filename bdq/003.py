# 3
if target_lotid:
    lotid_str = ",".join([f"'{x}'" for x in target_lotid])
    lotid_filter = f"AND l.lotid IN ({lotid_str})"
else:
    lotid_filter = ""

pstepseq_filter = f"AND l.pstepseq = '{target_pstepseq}'" if target_pstepseq else ""
mstepseq_filter = f"AND l.mstepseq = '{target_mstepseq}'" if target_mstepseq else ""
mstepseq_filter_oco = f"AND l.mstepseq = '{target_mstepseq_oco}'" if target_mstepseq_oco else ""

sql_lotinfo_oco = f"""
WITH lotinfo_raw AS (
  SELECT *
  FROM (
    SELECT
      l.lot_transn_seq,l.photo_transn_seq,l.impala_insert_time,
      l.db_user,l.`timestamp`,l.lotid,l.slotid,
      l.pstepseq,l.mstepseq,l.ppid,l.peqpid,l.chuckid,l.reticleid,
      l.steppitch_x,l.steppitch_y,l.mapshift_x,l.mapshift_y,
      l.dmargin_x,l.dmargin_y,l.outlr_resdl_spec_ratio,l.chip_x_qty,l.chip_y_qty,
      l.psm_mmo_ref_eqp_id,l.per_shot_mrc_id,
      row_number() OVER (
        PARTITION BY l.lot_transn_seq, l.slotid
        ORDER BY l.impala_insert_time DESC
      ) AS rn
    FROM ees_ds_eai.apc_nautil_dat_lotinfo l
    WHERE l.impala_insert_time >= now() - interval {days} days
      AND l.`timestamp` >= now() - interval {days} days
      AND l.`timestamp` <= now() - interval {exclude_recent_days} days
      AND l.db_user = '{db_user}'
      {lotid_filter}
      {pstepseq_filter}
      {mstepseq_filter_oco}
  ) t
  WHERE t.rn = 1
)
SELECT *
FROM lotinfo_raw
LIMIT 1000
"""

df_lotinfo_oco = bdq.getData(sql_lotinfo_oco)
photo_transn_seqs = df_lotinfo_oco['photo_transn_seq'].unique().tolist()
photo_transn_seq_str = ",".join([str(int(x)) for x in photo_transn_seqs[:1000] if pd.notna(x)])

sql_lotinfo_adi = f"""
WITH lotinfo_raw AS (
  SELECT *
  FROM (
    SELECT
      l.lot_transn_seq,l.photo_transn_seq,l.impala_insert_time,
      l.db_user,l.`timestamp`,l.lotid,l.slotid,
      l.pstepseq,l.mstepseq,l.ppid,l.peqpid,l.chuckid,l.reticleid,
      l.steppitch_x,l.steppitch_y,l.mapshift_x,l.mapshift_y,
      l.dmargin_x,l.dmargin_y,l.outlr_resdl_spec_ratio,l.chip_x_qty,l.chip_y_qty,
      l.psm_mmo_ref_eqp_id,l.per_shot_mrc_id,
      row_number() OVER (
        PARTITION BY l.lot_transn_seq, l.slotid
        ORDER BY l.impala_insert_time DESC
      ) AS rn
    FROM ees_ds_eai.apc_nautil_dat_lotinfo l
    WHERE l.impala_insert_time >= now() - interval {days+10} days
      AND l.`timestamp` >= now() - interval {days+10} days
      AND l.`timestamp` <= now() - interval {exclude_recent_days} days
      AND l.db_user = '{db_user}'
      AND l.photo_transn_seq IN ({photo_transn_seq_str})
      {pstepseq_filter}
      {mstepseq_filter}
  ) t
  WHERE t.rn = 1
)
SELECT *
FROM lotinfo_raw
LIMIT 100000
"""
print(photo_transn_seq_str)
df_lotinfo_adi = bdq.getData(sql_lotinfo_adi)

oco_keys = (df_lotinfo_oco[['photo_transn_seq', 'slotid']].dropna().drop_duplicates().copy())
adi_keys = (df_lotinfo_adi[['photo_transn_seq', 'slotid']].dropna().drop_duplicates().copy())

# 공통 key만 추출
common_keys = oco_keys.merge(adi_keys, on=['photo_transn_seq', 'slotid'], how='inner')
df_lotinfo_oco = df_lotinfo_oco.merge(common_keys, on=['photo_transn_seq', 'slotid'], how='inner')
df_lotinfo_adi = df_lotinfo_adi.merge(common_keys, on=['photo_transn_seq', 'slotid'], how='inner')

df_lotinfo_oco = df_lotinfo_oco.sort_values(by=['photo_transn_seq', 'slotid'], ascending=[True, True]).reset_index(drop=True)
df_lotinfo_adi = df_lotinfo_adi.sort_values(by=['photo_transn_seq', 'slotid'], ascending=[True, True]).reset_index(drop=True)

df_lotinfo_oco['slotid'] = df_lotinfo_oco['slotid'].astype(int)
df_lotinfo_adi['slotid'] = df_lotinfo_adi['slotid'].astype(int)

print(f"✅ ADI LOTINFO rows: {len(df_lotinfo_adi)}")
print(f"Columns: {list(df_lotinfo_adi.columns)}")
df_lotinfo_adi.to_excel('NAUTIL_DAT_LOTINFO_ADI.xlsx', index=False)

print(f"✅ OCO LOTINFO rows: {len(df_lotinfo_oco)}")
print(f"Columns: {list(df_lotinfo_oco.columns)}")
df_lotinfo_oco.to_excel('NAUTIL_DAT_LOTINFO_OCO.xlsx', index=False)
