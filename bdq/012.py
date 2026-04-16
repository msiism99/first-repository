# 12

# [v4 수정]
# - apc_trocs_hist_index_no empty 방지
# - join key 타입 통일
# - lot_hist subset을 apc_trocs_hist_index_no 기준으로 dedup
# - join 결과 디버그 강화

apc_trocs_index_list = (
    pd.to_numeric(df_lot_hist_apc['apc_trocs_hist_index_no'], errors='coerce')
    .dropna()
    .astype('Int64')
    .unique()
    .tolist()
)

print(f"조회할 apc_trocs_hist_index_no 수: {len(apc_trocs_index_list)}")

# MRC K값 + RK값 컬럼 생성
mrc_cols_sql = ", ".join([f"mrc_k{i}_valn" for i in range(1, 73)])
rk_cols_sql = ", ".join([f"rk{i}_valn" for i in range(1, 73)])

if len(apc_trocs_index_list) == 0:
    print("⚠️ apc_trocs_hist_index_no가 없어 shot_input_hist 조회를 건너뜁니다.")
    df_shot_input_apc = pd.DataFrame()
else:
    index_str = ", ".join([str(int(idx)) for idx in apc_trocs_index_list])

    sql_shot_input_apc = f"""
    SELECT
        CAST(apc_hist_index_no AS BIGINT) AS apc_hist_index_no,
        pos_x_valn,
        pos_y_valn,
        {mrc_cols_sql},
        {rk_cols_sql}
    FROM ees_ds_eai.apc_apc_photo_shot_input_hist
    WHERE db_user = '{DB_USER_APC}'
        AND impala_insert_time >= now() - interval {days+10} days
        AND CAST(apc_hist_index_no AS BIGINT) IN ({index_str})
    """

    print("apc_apc_photo_shot_input_hist 조회 시작...")
    print("  (lot_hist.apc_trocs_hist_index_no 기준으로 필터링)")
    df_shot_input_apc = bdq.getData(sql_shot_input_apc)
    print(f"[SHOT_INPUT_HIST] 조회 완료: {len(df_shot_input_apc)} 건")
    print(f"  - MRC K 컬럼: mrc_k1_valn ~ mrc_k72_valn (72개)")
    print(f"  - RK 컬럼: rk1_valn ~ rk72_valn (72개)")

    if len(df_shot_input_apc) > 0:
        print(df_shot_input_apc.head())

df_shot_input_apc.to_excel('df_shot_input_apc.xlsx', index=False)


# === 숫자형 변환 ===
if len(df_shot_input_apc) > 0:
    numeric_cols = (
        ['pos_x_valn', 'pos_y_valn'] +
        [f'mrc_k{i}_valn' for i in range(1, 73)] +
        [f'rk{i}_valn' for i in range(1, 73)]
    )

    for col in numeric_cols:
        if col in df_shot_input_apc.columns:
            df_shot_input_apc[col] = pd.to_numeric(df_shot_input_apc[col], errors='coerce')

    df_shot_input_apc['apc_hist_index_no'] = pd.to_numeric(
        df_shot_input_apc['apc_hist_index_no'], errors='coerce'
    ).astype('Int64')

df_lot_hist_apc['apc_hist_index_no'] = pd.to_numeric(
    df_lot_hist_apc['apc_hist_index_no'], errors='coerce'
).astype('Int64')

df_lot_hist_apc['apc_trocs_hist_index_no'] = pd.to_numeric(
    df_lot_hist_apc['apc_trocs_hist_index_no'], errors='coerce'
).astype('Int64')

print("타입 변환 완료")
if len(df_shot_input_apc) > 0:
    print(f"  pos_x_valn dtype = {df_shot_input_apc['pos_x_valn'].dtype}")
    print(f"  shot apc_hist_index_no dtype = {df_shot_input_apc['apc_hist_index_no'].dtype}")
print(f"  lot apc_hist_index_no dtype = {df_lot_hist_apc['apc_hist_index_no'].dtype}")
print(f"  lot apc_trocs_hist_index_no dtype = {df_lot_hist_apc['apc_trocs_hist_index_no'].dtype}")


# --- lot_hist에서 필요한 컬럼만 선택 ---
lot_cols_apc = [
    'apc_hist_index_no', 'apc_trocs_hist_index_no', 'lot_id', 'step_seq', 'eqp_id',
    'sub_eqp_id', 'ppid', 'reticle_id', 'run_type', 'event_tsdt', 'tkin_tsdt'
]

if len(df_lot_hist_apc) > 0:
    df_lot_subset_apc = df_lot_hist_apc[lot_cols_apc].copy()

    if 'event_tsdt' in df_lot_subset_apc.columns:
        df_lot_subset_apc['event_tsdt'] = pd.to_datetime(df_lot_subset_apc['event_tsdt'], errors='coerce')
    if 'tkin_tsdt' in df_lot_subset_apc.columns:
        df_lot_subset_apc['tkin_tsdt'] = pd.to_datetime(df_lot_subset_apc['tkin_tsdt'], errors='coerce')

    # 조인 키 기준 dedup
    df_lot_subset_apc = df_lot_subset_apc.dropna(subset=['apc_trocs_hist_index_no']).copy()
    df_lot_subset_apc = df_lot_subset_apc.sort_values(['event_tsdt', 'tkin_tsdt'], ascending=True)
    df_lot_subset_apc = df_lot_subset_apc.drop_duplicates(subset=['apc_trocs_hist_index_no'], keep='last')
else:
    df_lot_subset_apc = pd.DataFrame(columns=lot_cols_apc)

print(f"lot_subset rows: {len(df_lot_subset_apc)}")
if len(df_lot_subset_apc) > 0:
    print(f"lot_subset unique apc_trocs_hist_index_no: {df_lot_subset_apc['apc_trocs_hist_index_no'].nunique(dropna=True)}")


# --- 조인 수행 ---
if len(df_shot_input_apc) == 0 or len(df_lot_subset_apc) == 0:
    print("⚠️ shot_input 또는 lot_subset이 비어 있어 조인을 건너뜁니다.")
    df_joined_apc = df_shot_input_apc.copy()
else:
    df_joined_apc = pd.merge(
        df_shot_input_apc,
        df_lot_subset_apc,
        left_on='apc_hist_index_no',
        right_on='apc_trocs_hist_index_no',
        how='left',
        suffixes=('_shot', '_lot'),
        validate='many_to_one'
    )

    print(f"shot_input rows: {len(df_shot_input_apc)}")
    print(f"joined rows: {len(df_joined_apc)}")
    print(f"joined matched rows (lot_id notna): {df_joined_apc['lot_id'].notna().sum()}")

# --- 조인 후 컬럼 정리 ---
# shot 쪽 apc_hist_index_no = apc_trocs_hist_index_no
# lot 쪽 apc_hist_index_no = expo_overlay_lot / df_final과 연결되는 본체 key

if len(df_joined_apc) > 0:
    df_joined_apc = df_joined_apc.rename(columns={
        'apc_hist_index_no_lot': 'apc_hist_index_no'
    })

    df_joined_apc = df_joined_apc.drop(
        columns=['apc_hist_index_no_shot', 'apc_trocs_hist_index_no'],
        errors='ignore'
    )

    df_joined_apc['apc_hist_index_no'] = pd.to_numeric(
        df_joined_apc['apc_hist_index_no'], errors='coerce'
    ).astype('Int64')


# --- 컬럼 순서 재정렬 ---
psm_meta_cols = [
    'event_tsdt', 'tkin_tsdt', 'apc_hist_index_no', 'lot_id', 'step_seq', 'eqp_id',
    'sub_eqp_id', 'ppid', 'reticle_id', 'run_type', 'pos_x_valn', 'pos_y_valn'
]

mrc_col_list = [f'mrc_k{i}_valn' for i in range(1, 73)]
rk_col_list = [f'rk{i}_valn' for i in range(1, 73)]
psm_final_cols = psm_meta_cols + mrc_col_list + rk_col_list

available_cols = [c for c in psm_final_cols if c in df_joined_apc.columns]
df_psm_input = df_joined_apc[available_cols].copy()

# FCP 단위 변환: pos_x/y_valn mm -> um
if len(df_psm_input) > 0:
    df_psm_input['pos_x_valn'] = pd.to_numeric(df_psm_input['pos_x_valn'], errors='coerce') * 1000
    df_psm_input['pos_y_valn'] = pd.to_numeric(df_psm_input['pos_y_valn'], errors='coerce') * 1000
    df_psm_input['apc_hist_index_no'] = pd.to_numeric(
        df_psm_input['apc_hist_index_no'], errors='coerce'
    ).astype('Int64')

print(f"[df_psm_input] 생성 완료: {df_psm_input.shape}")
if len(df_psm_input) > 0:
    print(f"  - 메타데이터 컬럼: {len([c for c in psm_meta_cols if c in df_psm_input.columns])}개")
    print(f"  - MRC K값 컬럼: {len([c for c in mrc_col_list if c in df_psm_input.columns])}개")
    print(f"  - RK값 컬럼: {len([c for c in rk_col_list if c in df_psm_input.columns])}개")
    print(f"  - pos_x/y_valn 단위 변환 완료 (mm → um, ×1000)")
    print(f"  - apc_hist_index_no unique: {df_psm_input['apc_hist_index_no'].nunique(dropna=True)}")
    print(df_psm_input.head())
else:
    print("  - df_psm_input 비어있음")

df_psm_input.to_excel('df_psm_input.xlsx', index=False)
