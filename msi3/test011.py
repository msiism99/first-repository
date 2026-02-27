# 11


"""
섹션 8.1 수정안: apc_lot_hist 2회 조회 + 합성
============================================

[문제]
  apc_apc_lot_hist 테이블에는 apc_trocs_hist_index_no 컬럼이 존재하지 않음.
  → CAST(apc_trocs_hist_index_no AS BIGINT) 에서 AnalysisException 발생

[원인 분석]
  apc_lot_hist는 apc_group_name별로 별도 레코드가 존재하며,
  - 일반 그룹 레코드의 apc_hist_index_no → expo_overlay_lot.apc_hist_index_no 와 매칭
  - PHOTO_EEXY_GRP 레코드의 apc_hist_index_no → shot_input_hist.apc_hist_index_no 와 매칭

  즉, 기존 v3에서 "apc_trocs_hist_index_no"라고 가정했던 값은
  실제로는 apc_group_name='PHOTO_EEXY_GRP' 레코드의 apc_hist_index_no 임.

[수정 방법]
  apc_lot_hist를 2회 조회하여 합성:
  (A) 일반 그룹: expo_overlay_lot과 연결되는 레코드 (apc_hist_index_no)
  (B) PHOTO_EEXY_GRP: shot_input_hist과 연결되는 레코드 (→ apc_trocs_hist_index_no로 rename)
  (C) 두 결과를 lot_id + step_seq + eqp_id 기준으로 merge → apc_trocs_hist_index_no 컬럼 생성
"""


# =========================
# [v3.1 수정] apc_apc_lot_hist 2회 조회 + 합성
#   - (A) 일반 그룹: expo_overlay_lot 매칭용 apc_hist_index_no
#   - (B) PHOTO_EEXY_GRP: shot_input_hist 매칭용 apc_hist_index_no → apc_trocs_hist_index_no
# =========================

# 필터 조건 구성 (apc_lot_hist용 - 컬럼명이 다름)
lotid_filter_apc = f"AND lot_id in {target_lotid}" if target_lotid else ""
pstepseq_filter_apc = f"AND step_seq = '{target_pstepseq}'" if target_pstepseq else ""


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
    AND event_tsdt >= now() - interval {days} days
    AND event_tsdt <= now() - interval {exclude_recent_days} days
    AND apc_group_name != 'PHOTO_EEXY_GRP'
    AND save_type != 'A'
    {lotid_filter_apc}
    {pstepseq_filter_apc }
"""

print("(A) apc_apc_lot_hist 일반 그룹 조회 시작...")
df_lot_hist_main = bdq.getData(sql_lot_hist_main)
print(f"  → 조회 완료: {len(df_lot_hist_main)} 건")
print(f"  → apc_group_name 분포:\n{df_lot_hist_main['apc_group_name'].value_counts().to_string()}")

print(df_lot_hist_main.head)


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
    AND event_tsdt >= now() - interval {days} days
    AND event_tsdt <= now() - interval {exclude_recent_days} days
    AND apc_group_name = 'PHOTO_EEXY_GRP'
    AND save_type != 'A'
    {lotid_filter_apc}
    {pstepseq_filter_apc}
"""

print("\n(B) apc_apc_lot_hist PHOTO_EEXY_GRP 조회 시작...")
df_lot_hist_eexy = bdq.getData(sql_lot_hist_eexy)
print(f"  → 조회 완료: {len(df_lot_hist_eexy)} 건")

print(df_lot_hist_eexy.head)

df_lot_hist_main.to_csv('df_lot_hist_main.csv')
df_lot_hist_eexy.to_csv('df_lot_hist_eexy.csv')



# --- (C) 합성: lot_id + step_seq + eqp_id 기준 merge ---
#
# ★ 조인 키 확인 필요 ★
# 현재 lot_id + step_seq + eqp_id 로 설정함.
# 만약 동일 lot/step/eqp 에서 EEXY 레코드가 여러 건이면
# sub_eqp_id, ppid, event_tsdt 등을 추가해야 할 수 있음.
#
MERGE_KEYS = ['lot_id', 'step_seq', 'eqp_id', 'sub_eqp_id']


# Categorical 타입 → string 변환 (merge_asof 호환)
for col in MERGE_KEYS:
    df_lot_hist_main[col] = df_lot_hist_main[col].astype(str)
    df_lot_hist_eexy[col] = df_lot_hist_eexy[col].astype(str)



# tkin_tsdt를 datetime으로 변환 (Categorical 해제 포함)
df_lot_hist_main['tkin_tsdt'] = pd.to_datetime(df_lot_hist_main['tkin_tsdt'].astype(str), errors='coerce')
df_lot_hist_eexy['tkin_tsdt'] = pd.to_datetime(df_lot_hist_eexy['tkin_tsdt'].astype(str), errors='coerce')



# EEXY 측 dedup (같은 키에 여러 건이 있을 경우 최신 1건만 사용)
df_lot_hist_eexy_u = (
    df_lot_hist_eexy
    .sort_values('event_tsdt_eexy', ascending=True)
    .drop_duplicates(subset=MERGE_KEYS + ['tkin_tsdt'], keep='last')
)
print(f"\n(C) EEXY dedup: {len(df_lot_hist_eexy)} → {len(df_lot_hist_eexy_u)} 건")

# merge_asof: MERGE_KEYS로 그룹화 + tkin_tsdt 근접 매칭 (tolerance 60초)
df_lot_hist_main_sorted = df_lot_hist_main.sort_values('tkin_tsdt')
df_lot_hist_eexy_sorted = df_lot_hist_eexy_u[MERGE_KEYS + ['tkin_tsdt', 'apc_trocs_hist_index_no']].sort_values('tkin_tsdt')

df_lot_hist_apc = pd.merge_asof(
    df_lot_hist_main_sorted,
    df_lot_hist_eexy_sorted,
    on='tkin_tsdt',
    by=MERGE_KEYS,
    tolerance=pd.Timedelta('60s'),
    direction='nearest'
)

# --- 결과 확인 ---
print(f"\n[LOT_HIST 합성 결과]")
print(f"  - 전체 건수: {len(df_lot_hist_apc)}")
print(f"  - lot_id 수: {df_lot_hist_apc['lot_id'].nunique()}")
print(f"  - apc_hist_index_no 수: {df_lot_hist_apc['apc_hist_index_no'].nunique()}")
print(f"  - apc_trocs_hist_index_no 수: {df_lot_hist_apc['apc_trocs_hist_index_no'].nunique()}")
eexy_match_rate = df_lot_hist_apc['apc_trocs_hist_index_no'].notna().mean() * 100
print(f"  - EEXY 매칭률: {eexy_match_rate:.1f}%")

if eexy_match_rate < 50:
    print(f"\n  ⚠️ 매칭률이 낮습니다. 조인 키({MERGE_KEYS}) 확인 필요!")
    print(f"     - Main측 키 샘플: {df_lot_hist_main[MERGE_KEYS].drop_duplicates().head(3).values.tolist()}")
    print(f"     - EEXY측 키 샘플: {df_lot_hist_eexy_u[MERGE_KEYS].drop_duplicates().head(3).values.tolist()}")

df_lot_hist_apc.head()

df_lot_hist_apc.to_csv('df_lot_hist_apc.csv')
