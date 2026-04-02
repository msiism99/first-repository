# 12

# [v3 변경] apc_hist_index_no → apc_trocs_hist_index_no 기준으로 변경
# (shot_input_hist의 apc_hist_index_no에 대응하는 값)
# [v2 기존] apc_hist_index_list = df_lot_hist_apc['apc_hist_index_no'].unique()
apc_trocs_index_list = df_lot_hist_apc['apc_trocs_hist_index_no'].dropna().unique().tolist()
index_str = ", ".join([str(int(idx)) for idx in apc_trocs_index_list])

print(f"조회할 apc_trocs_hist_index_no 수: {len(apc_trocs_index_list)}")



# MRC K값 + RK값 컬럼 생성
mrc_cols_sql = ", ".join([f"mrc_k{i}_valn" for i in range(1, 73)])
rk_cols_sql = ", ".join([f"rk{i}_valn" for i in range(1, 73)])

# [v3 변경] index_str이 apc_trocs_hist_index_no 값으로 구성됨
# shot_input_hist.apc_hist_index_no = lot_hist.apc_trocs_hist_index_no
# [v2 기존] index_str이 lot_hist.apc_hist_index_no 값이었음 → 매칭 안 됨
sql_shot_input_apc = f"""
SELECT
    CAST(apc_hist_index_no AS BIGINT) AS apc_hist_index_no,
    pos_x_valn,
    pos_y_valn,
    {mrc_cols_sql},
    {rk_cols_sql}
FROM ees_ds_eai.apc_apc_photo_shot_input_hist
WHERE db_user = '{DB_USER_APC}'
    AND impala_insert_time >= now() - interval {days} days
    AND CAST(apc_hist_index_no AS BIGINT) IN ({index_str})
"""

print("apc_apc_photo_shot_input_hist 조회 시작...")
print(f"  (lot_hist.apc_trocs_hist_index_no 기준으로 필터링)")
df_shot_input_apc = bdq.getData(sql_shot_input_apc)
print(f"[SHOT_INPUT_HIST] 조회 완료: {len(df_shot_input_apc)} 건")
print(f"  - MRC K 컬럼: mrc_k1_valn ~ mrc_k72_valn (72개)")
print(f"  - RK 컬럼: rk1_valn ~ rk72_valn (72개)")
df_shot_input_apc.head()

df_shot_input_apc.to_excel('df_shot_input_apc.xlsx')





# === 8.3 수정 코드 ===

# shot_input_apc의 숫자 컬럼들을 numeric으로 변환
numeric_cols = ['pos_x_valn', 'pos_y_valn'] + \
               [f'mrc_k{i}_valn' for i in range(1, 73)] + \
               [f'rk{i}_valn' for i in range(1, 73)]

for col in numeric_cols:
    if col in df_shot_input_apc.columns:
        df_shot_input_apc[col] = pd.to_numeric(df_shot_input_apc[col], errors='coerce')

# apc_hist_index_no도 통일 (양쪽 다 int로)
df_shot_input_apc['apc_hist_index_no'] = pd.to_numeric(df_shot_input_apc['apc_hist_index_no'], errors='coerce').astype('Int64')
df_lot_hist_apc['apc_hist_index_no'] = pd.to_numeric(df_lot_hist_apc['apc_hist_index_no'], errors='coerce').astype('Int64')

print(f"타입 변환 완료: pos_x_valn={df_shot_input_apc['pos_x_valn'].dtype}, "
      f"apc_hist_index_no={df_shot_input_apc['apc_hist_index_no'].dtype}")

# --- 이하 기존 8.3 코드 그대로 ---


# lot_hist에서 필요한 컬럼만 선택
lot_cols_apc = ['apc_hist_index_no', 'apc_trocs_hist_index_no', 'lot_id', 'step_seq', 'eqp_id',
                'sub_eqp_id', 'ppid', 'reticle_id', 'run_type', 'event_tsdt', 'tkin_tsdt']
df_lot_subset_apc = df_lot_hist_apc[lot_cols_apc].drop_duplicates()

# 조인 수행
# [v3 변경] 조인 키 수정
# [v2 기존] on='apc_hist_index_no' → 매칭 안 됨
# [v3 수정] left_on=shot의 apc_hist_index_no, right_on=lot의 apc_trocs_hist_index_no
df_joined_apc = pd.merge(
    df_shot_input_apc,
    df_lot_subset_apc,
    left_on='apc_hist_index_no',          # shot_input_hist의 apc_hist_index_no
    right_on='apc_trocs_hist_index_no',   # lot_hist의 apc_trocs_hist_index_no
    how='left',
    suffixes=('_shot', '_lot')
)



# [v3 변경] 조인 후 컬럼 정리:
# - apc_hist_index_no_shot: shot_input_hist 원본값 (= lot_hist.apc_trocs_hist_index_no)
# - apc_hist_index_no_lot: lot_hist 원본값 (= expo_overlay_lot, df_final과 매칭되는 값)
# → apc_hist_index_no_lot을 apc_hist_index_no로 rename하여 이후 매칭에 사용
df_joined_apc = df_joined_apc.rename(columns={
    'apc_hist_index_no_lot': 'apc_hist_index_no'
})
df_joined_apc = df_joined_apc.drop(columns=['apc_hist_index_no_shot', 'apc_trocs_hist_index_no'], errors='ignore')


# 컬럼 순서 재정렬: 메타데이터 + pos + mrc
psm_meta_cols = ['event_tsdt', 'tkin_tsdt', 'apc_hist_index_no', 'lot_id', 'step_seq', 'eqp_id',
                 'sub_eqp_id', 'ppid', 'reticle_id', 'run_type',
                 'pos_x_valn', 'pos_y_valn']
mrc_col_list = [f'mrc_k{i}_valn' for i in range(1, 73)]
psm_final_cols = psm_meta_cols + mrc_col_list

df_psm_input = df_joined_apc[psm_final_cols].copy()

# FCP 단위 변환: pos_x/y_valn은 mm 단위이므로, um 단위인 df_final의 fcp_x/y와 매칭하기 위해 *1000
df_psm_input['pos_x_valn'] = df_psm_input['pos_x_valn'] * 1000
df_psm_input['pos_y_valn'] = df_psm_input['pos_y_valn'] * 1000

print(f"[df_psm_input] 생성 완료: {df_psm_input.shape}")
print(f"  - 메타데이터 컬럼: {len(psm_meta_cols)}개")
print(f"  - MRC K값 컬럼: {len(mrc_col_list)}개")
print(f"  - pos_x/y_valn 단위 변환 완료 (mm → um, ×1000)")
df_psm_input.head()

df_psm_input.to_excel('df_psm_input.xlsx')
