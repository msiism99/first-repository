lotid_filter_apc = f"AND lot_id in {target_lotid}" if target_lotid else ""
pstepseq_filter_apc = f"AND step_seq = '{target_pstepseq}'" if target_pstepseq else ""
   
# lotid_str은 #5에 있음
# --- (A) 일반 그룹 조회 (PHOTO_EEXY_GRP 제외) ---
sql_lot_hist_main = f"""
SELECT
    CAST(apc_hist_index_no AS BIGINT) AS apc_hist_index_no,
    apc_group_name,
    lot_id,
    step_seq,
    eqp_id,
    sub_eqp_id,
    ppid,
    reticle_id,
    run_type,
    event_tsdt,
    tkin_tsdt
FROM ees_ds_eai.apc_apc_lot_hist
WHERE db_user = '{DB_USER_APC}'
    AND event_tsdt >= now() - interval {days+5} days
    AND event_tsdt <= now() - interval {exclude_recent_days} days
    AND apc_group_name != 'PHOTO_EEXY_GRP'
    AND save_type != 'A'
    AND lot_id IN ('{lotid_str}')
    {lotid_filter_apc}
    {pstepseq_filter_apc}
"""

print("(A) apc_apc_lot_hist 일반 그룹 조회 시작...")
df_lot_hist_main = bdq.getData(sql_lot_hist_main)
print(f"  → 조회 완료: {len(df_lot_hist_main)} 건")

if len(df_lot_hist_main) > 0:
    if 'apc_group_name' in df_lot_hist_main.columns:
        print(f"  → apc_group_name 분포:\n{df_lot_hist_main['apc_group_name'].value_counts(dropna=False).to_string()}")
    print(df_lot_hist_main.head())
else:
    print("  → df_lot_hist_main 비어있음")


# --- (B) PHOTO_EEXY_GRP 조회 ---
sql_lot_hist_eexy = f"""
SELECT
    CAST(apc_hist_index_no AS BIGINT) AS apc_trocs_hist_index_no,
    lot_id,
    step_seq,
    eqp_id,
    sub_eqp_id,
    tkin_tsdt,
    event_tsdt AS event_tsdt_eexy
FROM ees_ds_eai.apc_apc_lot_hist
WHERE db_user = '{DB_USER_APC}'
    AND event_tsdt >= now() - interval {days+5} days
    AND event_tsdt <= now() - interval {exclude_recent_days} days
    AND apc_group_name = 'PHOTO_EEXY_GRP'
    AND save_type != 'A'
    AND lot_id IN ('{lotid_str}')
    {lotid_filter_apc}
    {pstepseq_filter_apc}
"""

print("\n(B) apc_apc_lot_hist PHOTO_EEXY_GRP 조회 시작...")
df_lot_hist_eexy = bdq.getData(sql_lot_hist_eexy)
print(f"  → 조회 완료: {len(df_lot_hist_eexy)} 건")

if len(df_lot_hist_eexy) > 0:
    print(df_lot_hist_eexy.head())
else:
    print("  → df_lot_hist_eexy 비어있음")


# CSV 저장
df_lot_hist_main.to_csv("df_lot_hist_main.csv", index=False)
df_lot_hist_eexy.to_csv("df_lot_hist_eexy.csv", index=False)


# --- (C) 합성: lot_id + step_seq + eqp_id + sub_eqp_id + tkin_tsdt 근접 매칭 ---
MERGE_KEYS = ['lot_id', 'step_seq', 'eqp_id', 'sub_eqp_id']

if len(df_lot_hist_main) == 0:
    print("⚠️ df_lot_hist_main이 비어있어 합성을 건너뜁니다.")
    df_lot_hist_apc = pd.DataFrame()

elif len(df_lot_hist_eexy) == 0:
    print("⚠️ df_lot_hist_eexy가 비어있습니다. apc_trocs_hist_index_no 없이 main만 사용합니다.")
    df_lot_hist_apc = df_lot_hist_main.copy()
    df_lot_hist_apc['apc_trocs_hist_index_no'] = pd.NA

else:
    # 타입 정리
    for col in MERGE_KEYS:
        df_lot_hist_main[col] = df_lot_hist_main[col].astype(str).str.strip()
        df_lot_hist_eexy[col] = df_lot_hist_eexy[col].astype(str).str.strip()

    # datetime 정리
    df_lot_hist_main['tkin_tsdt'] = pd.to_datetime(df_lot_hist_main['tkin_tsdt'].astype(str), errors='coerce')
    df_lot_hist_main['event_tsdt'] = pd.to_datetime(df_lot_hist_main['event_tsdt'].astype(str), errors='coerce')

    df_lot_hist_eexy['tkin_tsdt'] = pd.to_datetime(df_lot_hist_eexy['tkin_tsdt'].astype(str), errors='coerce')
    df_lot_hist_eexy['event_tsdt_eexy'] = pd.to_datetime(df_lot_hist_eexy['event_tsdt_eexy'].astype(str), errors='coerce')

    # APC index 정리
    df_lot_hist_main['apc_hist_index_no'] = pd.to_numeric(
        df_lot_hist_main['apc_hist_index_no'], errors='coerce'
    ).astype('Int64')

    df_lot_hist_eexy['apc_trocs_hist_index_no'] = pd.to_numeric(
        df_lot_hist_eexy['apc_trocs_hist_index_no'], errors='coerce'
    ).astype('Int64')

    # merge_asof용 유효행만 사용
    df_lot_hist_main_valid = df_lot_hist_main.dropna(subset=['tkin_tsdt']).copy()
    df_lot_hist_eexy_valid = df_lot_hist_eexy.dropna(subset=['tkin_tsdt']).copy()

    # EEXY dedup: 같은 key + tkin_tsdt에 대해 최신 event_tsdt_eexy 유지
    df_lot_hist_eexy_u = (
        df_lot_hist_eexy_valid
        .sort_values(['event_tsdt_eexy'])
        .drop_duplicates(subset=MERGE_KEYS + ['tkin_tsdt'], keep='last')
    )

    print(f"\n(C) EEXY dedup: {len(df_lot_hist_eexy_valid)} → {len(df_lot_hist_eexy_u)} 건")

    # merge_asof
    df_lot_hist_main_sorted = df_lot_hist_main_valid.sort_values('tkin_tsdt').copy()
    df_lot_hist_eexy_sorted = (
        df_lot_hist_eexy_u[MERGE_KEYS + ['tkin_tsdt', 'apc_trocs_hist_index_no']]
        .sort_values('tkin_tsdt')
        .copy()
    )

    df_lot_hist_apc = pd.merge_asof(
        df_lot_hist_main_sorted,
        df_lot_hist_eexy_sorted,
        on='tkin_tsdt',
        by=MERGE_KEYS,
        tolerance=pd.Timedelta('60s'),
        direction='nearest'
    )

    # 혹시 main에서 tkin_tsdt NaT였던 행은 뒤에 다시 붙임
    df_lot_hist_main_invalid = df_lot_hist_main[df_lot_hist_main['tkin_tsdt'].isna()].copy()
    if len(df_lot_hist_main_invalid) > 0:
        df_lot_hist_main_invalid['apc_trocs_hist_index_no'] = pd.NA
        df_lot_hist_apc = pd.concat([df_lot_hist_apc, df_lot_hist_main_invalid], ignore_index=True)

    # index 정리
    df_lot_hist_apc['apc_hist_index_no'] = pd.to_numeric(
        df_lot_hist_apc['apc_hist_index_no'], errors='coerce'
    ).astype('Int64')

    df_lot_hist_apc['apc_trocs_hist_index_no'] = pd.to_numeric(
        df_lot_hist_apc['apc_trocs_hist_index_no'], errors='coerce'
    ).astype('Int64')

# --- 결과 확인 ---
print(f"\n[LOT_HIST 합성 결과]")
print(f"  - 전체 건수: {len(df_lot_hist_apc)}")

if len(df_lot_hist_apc) > 0:
    print(f"  - lot_id 수: {df_lot_hist_apc['lot_id'].nunique(dropna=True)}")
    print(f"  - apc_hist_index_no 수: {df_lot_hist_apc['apc_hist_index_no'].nunique(dropna=True)}")
    print(f"  - apc_trocs_hist_index_no 수: {df_lot_hist_apc['apc_trocs_hist_index_no'].nunique(dropna=True)}")

    eexy_match_rate = df_lot_hist_apc['apc_trocs_hist_index_no'].notna().mean() * 100
    print(f"  - EEXY 매칭률: {eexy_match_rate:.1f}%")

    if eexy_match_rate < 50 and len(df_lot_hist_eexy) > 0:
        print(f"\n  ⚠️ 매칭률이 낮습니다. 조인 키({MERGE_KEYS}) 확인 필요!")
        print(f"     - Main측 키 샘플: {df_lot_hist_main[MERGE_KEYS].drop_duplicates().head(3).values.tolist()}")
        print(f"     - EEXY측 키 샘플: {df_lot_hist_eexy[MERGE_KEYS].drop_duplicates().head(3).values.tolist()}")

    print(df_lot_hist_apc.head())
else:
    print("  - df_lot_hist_apc 비어있음")

df_lot_hist_apc['event_tsdt'] = pd.to_datetime(df_lot_hist_apc['event_tsdt'], errors='coerce')

df_lot_hist_apc = (
    df_lot_hist_apc
    .sort_values('event_tsdt')  # 오래된 → 최신
    .drop_duplicates(subset=['lot_id', 'sub_eqp_id'], keep='last')
    .reset_index(drop=True)
)

df_lot_hist_apc.to_csv("df_lot_hist_apc.csv", index=False)
