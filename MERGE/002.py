# 2

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
        PARTITION BY l.lotid, l.slotid
        ORDER BY l.impala_insert_time DESC
      ) AS rn
    FROM ees_ds_eai.apc_nautil_dat_lotinfo l
    WHERE l.impala_insert_time >= now() - interval {days+5} days
      AND l.`timestamp` >= now() - interval {days+5} days
      AND l.`timestamp` <= now() - interval {max(0, exclude_recent_days - 3)} days
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
        PARTITION BY l.lotid, l.slotid
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

df_lotinfo_adi = bdq.getData(sql_lotinfo_adi)

df_lotinfo_adi['timestamp'] = pd.to_datetime(df_lotinfo_adi['timestamp'])

today = pd.Timestamp.today().normalize()

start_date = today - pd.Timedelta(days=days)
end_date_exclusive = today - pd.Timedelta(days=exclude_recent_days)

df_lotinfo_adi = df_lotinfo_adi[
    (df_lotinfo_adi['timestamp'] >= start_date) &
    (df_lotinfo_adi['timestamp'] < end_date_exclusive)
].copy()

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

df_lotinfo_oco = df_lotinfo_oco[df_lotinfo_oco['slotid'].between(9, 14)].copy()
df_lotinfo_adi = df_lotinfo_adi[df_lotinfo_adi['slotid'].between(9, 14)].copy()

print(f"✅ ADI LOTINFO rows: {len(df_lotinfo_adi)}")
print(f"✅ OCO LOTINFO rows: {len(df_lotinfo_oco)}")

df_lotinfo_save = df_lotinfo_adi.copy()

oco_add_cols = (
    df_lotinfo_oco[
        ['photo_transn_seq', 'slotid', 'lot_transn_seq', 'timestamp', 'mstepseq']
    ]
    .drop_duplicates(subset=['photo_transn_seq', 'slotid'])
    .rename(columns={
        'lot_transn_seq': 'lot_transn_seq_oco',
        'timestamp': 'timestamp_oco',
        'mstepseq': 'mstepseq_oco'
    })
    .copy()
)

df_lotinfo_save = df_lotinfo_save.merge(
    oco_add_cols,
    on=['photo_transn_seq', 'slotid'],
    how='left'
)

df_lotinfo_save['base_eqpid'] = (
    df_lotinfo_save['per_shot_mrc_id']
    .astype(str)
    .str.split('/')
    .str[-1]
    .str.split('_')
    .str[0]
)

df_lotinfo_save['psm_update_time'] = (
    df_lotinfo_save['per_shot_mrc_id']
    .astype(str)
    .str.split('/')
    .str[-1]
    .str.split('_')
    .str[1]
)

df_lotinfo_save['psm_update_time'] = (
    df_lotinfo_save['psm_update_time']
    .where(df_lotinfo_save['psm_update_time'].notna())
    .astype("string")
    .str.replace(r'^20', '', regex=True)   # 맨 앞이 20이면 제거
    .str[:10]                              # 10자리 초과면 앞 10자리만 사용
)

df_lotinfo_save.to_excel('NAUTIL_DAT_LOTINFO.xlsx', index=False)
