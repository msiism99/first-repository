# 11
# =========================
# apc_apc_lot_hist 2회 조회 + 합성
# (기존 변수명 유지 버전)
# =========================

"""
[수정 포인트]
1) lot_id IN (...) 필터를 SQL 문법에 맞게 생성
2) head() 출력 오타 수정
3) datetime 변환 보강
4) merge_asof 전 NaT 제거
5) merge_asof 정렬 안정화
6) 결과 검증용 컬럼 추가
7) CSV 파일명은 비교용으로 변경
"""

# -------------------------
# 필터 조건 구성 (apc_lot_hist용 - 컬럼명이 다름)
# -------------------------
if target_lotid:
    lotid_str_apc = ",".join([f"'{x}'" for x in target_lotid])
    lotid_filter_apc = f"AND lot_id IN ({lotid_str_apc})"
else:
    lotid_filter_apc = ""

pstepseq_filter_apc = f"AND step_seq = '{target_pstepseq}'" if target_pstepseq else ""

print("===== apc_apc_lot_hist 2회 조회 + 합성 시작 =====")
print("lotid_filter_apc:", lotid_filter_apc)
print("pstepseq_filter_apc:", pstepseq_filter_apc)


# -------------------------
# (A) 일반 그룹 조회 (PHOTO_EEXY_GRP 제외)
# -------------------------
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
    AND event_tsdt >= now() - interval {days+2} days
    AND event_tsdt <= now() - interval {exclude_recent_days} days
    AND apc_group_name != 'PHOTO_EEXY_GRP'
    AND save_type != 'A'
    {lotid_filter_apc}
    {pstepseq_filter_apc}
"""

print("(A) apc_apc_lot_hist 일반 그룹 조회 시작...")
df_lot_hist_main = bdq.getData(sql_lot_hist_main)
print(f"  → 조회 완료: {len(df_lot_hist_main)} 건")

if len(df_lot_hist_main) > 0:
    print(f"  → apc_group_name 분포:\n{df_lot_hist_main['apc_group_name'].value_counts(dropna=False).to_string()}")
    print(df_lot_hist_main.head())
else:
    print("  → 일반 그룹 결과 없음")


# -------------------------
# (B) PHOTO_EEXY_GRP 조회
# -------------------------
sql_lot_hist_eexy = f"""
SELECT
    CAST(apc_hist_index_no AS BIGINT) AS apc_trocs_hist_index_no,
    lot_id,
    step_seq,
    eqp_id,
    sub_eqp_id,
    ppid,
    reticle_id,
    run_type,
    tkin_tsdt,
    event_tsdt AS event_tsdt_eexy
FROM ees_ds_eai.apc_apc_lot_hist
WHERE db_user = '{DB_USER_APC}'
    AND event_tsdt >= now() - interval {days+2} days
    AND event_tsdt <= now() - interval {exclude_recent_days} days
    AND apc_group_name = 'PHOTO_EEXY_GRP'
    AND save_type != 'A'
    {lotid_filter_apc}
    {pstepseq_filter_apc}
"""

print("\n(B) apc_apc_lot_hist PHOTO_EEXY_GRP 조회 시작...")
df_lot_hist_eexy = bdq.getData(sql_lot_hist_eexy)
print(f"  → 조회 완료: {len(df_lot_hist_eexy)} 건")

if len(df_lot_hist_eexy) > 0:
    print(df_lot_hist_eexy.head())
else:
    print("  → EEXY 그룹 결과 없음")


# -------------------------
# 원본 비교용 CSV 저장
# -------------------------
df_lot_hist_main.to_csv('df_lot_hist_main_compare_new.csv', index=False)
df_lot_hist_eexy.to_csv('df_lot_hist_eexy_compare_new.csv', index=False)


# -------------------------
# (C) 합성: lot_id + step_seq + eqp_id + sub_eqp_id + tkin_tsdt 근접 매칭
# -------------------------
MERGE_KEYS = ['lot_id', 'step_seq', 'eqp_id', 'sub_eqp_id']


# 1) merge key string 정리
for col in MERGE_KEYS:
    if col in df_lot_hist_main.columns:
        df_lot_hist_main[col] = df_lot_hist_main[col].astype(str).str.strip()
    if col in df_lot_hist_eexy.columns:
        df_lot_hist_eexy[col] = df_lot_hist_eexy[col].astype(str).str.strip()


# 2) datetime 변환
if len(df_lot_hist_main) > 0:
    df_lot_hist_main['tkin_tsdt'] = pd.to_datetime(df_lot_hist_main['tkin_tsdt'].astype(str), errors='coerce')
    df_lot_hist_main['event_tsdt'] = pd.to_datetime(df_lot_hist_main['event_tsdt'].astype(str), errors='coerce')

if len(df_lot_hist_eexy) > 0:
    df_lot_hist_eexy['tkin_tsdt'] = pd.to_datetime(df_lot_hist_eexy['tkin_tsdt'].astype(str), errors='coerce')
    df_lot_hist_eexy['event_tsdt_eexy'] = pd.to_datetime(df_lot_hist_eexy['event_tsdt_eexy'].astype(str), errors='coerce')


# 3) EEXY dedup
if len(df_lot_hist_eexy) > 0:
    df_lot_hist_eexy_u = (
        df_lot_hist_eexy
        .sort_values('event_tsdt_eexy', ascending=True)
        .drop_duplicates(subset=MERGE_KEYS + ['tkin_tsdt'], keep='last')
        .copy()
    )
else:
    df_lot_hist_eexy_u = pd.DataFrame(columns=df_lot_hist_eexy.columns)

print(f"\n(C) EEXY dedup: {len(df_lot_hist_eexy)} → {len(df_lot_hist_eexy_u)} 건")


# 4) merge_asof용 NaT 제거
if len(df_lot_hist_main) > 0:
    df_lot_hist_main = df_lot_hist_main[df_lot_hist_main['tkin_tsdt'].notna()].copy()

if len(df_lot_hist_eexy_u) > 0:
    df_lot_hist_eexy_u = df_lot_hist_eexy_u[df_lot_hist_eexy_u['tkin_tsdt'].notna()].copy()


# 5) merge_asof
if len(df_lot_hist_main) == 0:
    print("⚠️ main 데이터가 없어 합성을 건너뜁니다.")
    df_lot_hist_apc = pd.DataFrame()

elif len(df_lot_hist_eexy_u) == 0:
    print("⚠️ eexy 데이터가 없어 apc_trocs_hist_index_no 없이 main만 유지합니다.")
    df_lot_hist_apc = df_lot_hist_main.copy()
    df_lot_hist_apc['apc_trocs_hist_index_no'] = np.nan
    df_lot_hist_apc['tkin_tsdt_eexy'] = pd.NaT
    df_lot_hist_apc['eexy_tdiff_sec'] = np.nan

else:
    df_lot_hist_main_sorted = (
        df_lot_hist_main
        .sort_values('tkin_tsdt')
        .reset_index(drop=True)
        .copy()
    )

    df_lot_hist_eexy_sorted = (
        df_lot_hist_eexy_u[MERGE_KEYS + ['tkin_tsdt', 'apc_trocs_hist_index_no']]
        .rename(columns={'tkin_tsdt': 'tkin_tsdt_eexy'})
        .sort_values('tkin_tsdt_eexy')
        .reset_index(drop=True)
        .copy()
    )

    print("left tkin_tsdt sorted:", df_lot_hist_main_sorted['tkin_tsdt'].is_monotonic_increasing)
    print("right tkin_tsdt_eexy sorted:", df_lot_hist_eexy_sorted['tkin_tsdt_eexy'].is_monotonic_increasing)

    df_lot_hist_apc = pd.merge_asof(
        df_lot_hist_main_sorted,
        df_lot_hist_eexy_sorted,
        left_on='tkin_tsdt',
        right_on='tkin_tsdt_eexy',
        by=MERGE_KEYS,
        tolerance=pd.Timedelta('60s'),
        direction='nearest'
    )

    # 시간차 검증용 컬럼
    df_lot_hist_apc['eexy_tdiff_sec'] = (
        df_lot_hist_apc['tkin_tsdt'] - df_lot_hist_apc['tkin_tsdt_eexy']
    ).dt.total_seconds().abs()


# -------------------------
# 결과 확인
# -------------------------
print(f"\n[LOT_HIST 합성 결과]")
print(f"  - 전체 건수: {len(df_lot_hist_apc)}")

if len(df_lot_hist_apc) > 0:
    print(f"  - lot_id 수: {df_lot_hist_apc['lot_id'].nunique()}")
    print(f"  - apc_hist_index_no 수: {df_lot_hist_apc['apc_hist_index_no'].nunique()}")
    print(f"  - apc_trocs_hist_index_no 수: {df_lot_hist_apc['apc_trocs_hist_index_no'].nunique(dropna=True)}")

    eexy_match_rate = df_lot_hist_apc['apc_trocs_hist_index_no'].notna().mean() * 100
    print(f"  - EEXY 매칭률: {eexy_match_rate:.1f}%")

    if 'eexy_tdiff_sec' in df_lot_hist_apc.columns:
        print("  - EEXY 시간차(sec) 요약:")
        print(df_lot_hist_apc['eexy_tdiff_sec'].describe())

    if eexy_match_rate < 50:
        print(f"\n  ⚠️ 매칭률이 낮습니다. 조인 키({MERGE_KEYS}) 확인 필요!")
        if len(df_lot_hist_main) > 0:
            print(f"     - Main측 키 샘플: {df_lot_hist_main[MERGE_KEYS].drop_duplicates().head(3).values.tolist()}")
        if len(df_lot_hist_eexy_u) > 0:
            print(f"     - EEXY측 키 샘플: {df_lot_hist_eexy_u[MERGE_KEYS].drop_duplicates().head(3).values.tolist()}")

    print("\n[합성 결과 샘플]")
    cols_show = [
        'lot_id', 'step_seq', 'eqp_id', 'sub_eqp_id',
        'apc_hist_index_no', 'apc_trocs_hist_index_no',
        'tkin_tsdt', 'tkin_tsdt_eexy', 'eexy_tdiff_sec'
    ]
    cols_show = [c for c in cols_show if c in df_lot_hist_apc.columns]
    print(df_lot_hist_apc[cols_show].head())

    print("\n[미매칭 샘플]")
    unmatched = df_lot_hist_apc[df_lot_hist_apc['apc_trocs_hist_index_no'].isna()]
    if len(unmatched) > 0:
        cols_unmatched = [c for c in MERGE_KEYS + ['tkin_tsdt'] if c in unmatched.columns]
        print(unmatched[cols_unmatched].head())
    else:
        print("  미매칭 없음")


df_lot_hist_apc.head()


# -------------------------
# 비교용 CSV 저장
# -------------------------
df_lot_hist_apc.to_csv('df_lot_hist_apc_compare_new.csv', index=False)

if len(df_lot_hist_apc) > 0 and 'apc_trocs_hist_index_no' in df_lot_hist_apc.columns:
    df_lot_hist_apc[df_lot_hist_apc['apc_trocs_hist_index_no'].notna()] \
        .to_csv('df_lot_hist_apc_matched_only_compare_new.csv', index=False)

    df_lot_hist_apc[df_lot_hist_apc['apc_trocs_hist_index_no'].isna()] \
        .to_csv('df_lot_hist_apc_unmatched_only_compare_new.csv', index=False)

print("\n✅ 비교용 CSV 저장 완료")
print("  - df_lot_hist_main_compare_new.csv")
print("  - df_lot_hist_eexy_compare_new.csv")
print("  - df_lot_hist_apc_compare_new.csv")
print("  - df_lot_hist_apc_matched_only_compare_new.csv")
print("  - df_lot_hist_apc_unmatched_only_compare_new.csv")
