# 4

import pandas as pd


def filter_latest_batch_by_gap_per_kind(
    df_rawdata: pd.DataFrame,
    gap_seconds: int = 60
) -> pd.DataFrame:
    """
    같은 lot_transn_seq, slot_id, data_kind 내에서 transn_occur_date 기준으로
    시간 차이가 gap_seconds를 초과하면 새로운 batch로 간주하고,
    마지막 batch만 남긴다.

    즉 RAWDATA / TESTDATA / PERSHOT 을 각각 따로 최신 batch로 유지한다.
    """
    if df_rawdata.empty:
        return df_rawdata.copy()

    df = df_rawdata.copy()

    # datetime 변환
    df['transn_occur_date'] = pd.to_datetime(
        df['transn_occur_date'].astype(str),
        errors='coerce'
    )

    before_len = len(df)
    df = df.dropna(subset=['transn_occur_date']).copy()
    after_len = len(df)

    if before_len != after_len:
        print(f"⚠️ transn_occur_date NaT 제거: {before_len - after_len} rows")

    group_cols = ['lot_transn_seq', 'slot_id', 'data_kind']

    # 정렬
    df = df.sort_values(group_cols + ['transn_occur_date']).reset_index(drop=True)

    # 이전 시간
    df['prev_time'] = df.groupby(group_cols)['transn_occur_date'].shift(1)

    # gap
    df['gap_sec'] = (df['transn_occur_date'] - df['prev_time']).dt.total_seconds()

    # 새 batch 시작 조건
    df['new_batch'] = ((df['prev_time'].isna()) | (df['gap_sec'] > gap_seconds)).astype(int)

    # batch 번호
    df['batch_id'] = df.groupby(group_cols)['new_batch'].cumsum()

    # 각 key별 마지막 batch
    last_batch = (
        df.groupby(group_cols, dropna=False)['batch_id']
        .max()
        .reset_index()
        .rename(columns={'batch_id': 'last_batch_id'})
    )

    df = df.merge(last_batch, on=group_cols, how='inner')
    df = df[df['batch_id'] == df['last_batch_id']].copy()

    print("최신 batch 유지 후 data_kind 분포:")
    print(df['data_kind'].value_counts(dropna=False))

    # 임시 컬럼 제거
    df = df.drop(columns=['prev_time', 'gap_sec', 'new_batch', 'batch_id', 'last_batch_id'])
    df = df.reset_index(drop=True)

    return df


def prepare_rawdata_from_lotinfo(
    df_lotinfo: pd.DataFrame,
    days: int,
    db_user: str,
    label: str,
    gap_seconds: int = 60,
    max_lot_transn_seq: int = 1000,
    limit_rows: int = 10000000
) -> pd.DataFrame:
    if len(df_lotinfo) == 0:
        print(f"⚠️ {label}: LOTINFO 데이터가 없습니다. RAWDATA 쿼리를 건너뜁니다.")
        return pd.DataFrame()

    required_cols = ['lot_transn_seq', 'slotid']
    missing_cols = [c for c in required_cols if c not in df_lotinfo.columns]
    if missing_cols:
        raise ValueError(f"{label}: df_lotinfo에 필요한 컬럼이 없습니다: {missing_cols}")

    lot_transn_seqs = (
        pd.Series(df_lotinfo['lot_transn_seq'])
        .dropna()
        .astype('int64')
        .unique()
        .tolist()
    )

    if len(lot_transn_seqs) == 0:
        print(f"⚠️ {label}: 유효한 lot_transn_seq가 없습니다.")
        return pd.DataFrame()

    lot_transn_seq_str = ",".join([str(x) for x in lot_transn_seqs[:max_lot_transn_seq]])

    sql_rawdata = f"""
    SELECT
      r.lot_transn_seq,
      r.slot_id,
      r.transn_occur_date,
      r.data_kind,
      r.test_point_no,
      r.coordinate_x,
      r.coordinate_y,
      r.value_x,
      r.value_y,
      r.mrc_x_valn,
      r.mrc_y_valn
    FROM ees_ds_eai.apc_nautil_dat_rawdata r
    WHERE r.impala_insert_time >= now() - interval {days+10} days
      AND r.db_user = '{db_user}'
      AND r.lot_transn_seq IN ({lot_transn_seq_str})
      AND r.data_kind IN ('RAWDATA', 'TESTDATA', 'PERSHOT')
    LIMIT {limit_rows}
    """

    print(f"\n[{label}] NAUTIL_DAT_RAWDATA 데이터 조회 시작...")
    df_rawdata = bdq.getData(sql_rawdata)

    if len(df_rawdata) == 0:
        print(f"⚠️ {label}: RAWDATA 조회 결과가 없습니다.")
        return df_rawdata

    print(f"[{label}] 조회 직후 rows: {len(df_rawdata)}")
    print(f"[{label}] data_kind 분포(필터 전):")
    print(df_rawdata['data_kind'].value_counts(dropna=False))

    # 타입 정리
    df_rawdata['transn_occur_date'] = pd.to_datetime(
        df_rawdata['transn_occur_date'].astype(str),
        errors='coerce'
    )
    df_rawdata['slot_id'] = pd.to_numeric(df_rawdata['slot_id'], errors='coerce')

    df_rawdata = df_rawdata.dropna(subset=['slot_id']).copy()
    df_rawdata['slot_id'] = df_rawdata['slot_id'].astype(int)

    # lotinfo key 정리
    df_lotinfo_key = df_lotinfo[['lot_transn_seq', 'slotid']].drop_duplicates().copy()
    df_lotinfo_key['lot_transn_seq'] = pd.to_numeric(df_lotinfo_key['lot_transn_seq'], errors='coerce')
    df_lotinfo_key['slotid'] = pd.to_numeric(df_lotinfo_key['slotid'], errors='coerce')
    df_lotinfo_key = df_lotinfo_key.dropna(subset=['lot_transn_seq', 'slotid']).copy()
    df_lotinfo_key['lot_transn_seq'] = df_lotinfo_key['lot_transn_seq'].astype('int64')
    df_lotinfo_key['slotid'] = df_lotinfo_key['slotid'].astype(int)

    # merge
    before_merge = len(df_rawdata)
    df_rawdata = df_rawdata.merge(
        df_lotinfo_key,
        left_on=['lot_transn_seq', 'slot_id'],
        right_on=['lot_transn_seq', 'slotid'],
        how='inner'
    ).reset_index(drop=True)

    print(f"[{label}] lotinfo merge 후 rows: {len(df_rawdata)} (drop {before_merge - len(df_rawdata)})")
    print(f"[{label}] WF 분포(상위 20개):")
    print(df_rawdata[['lot_transn_seq', 'slot_id']].value_counts().head(20))

    # data_kind별 시간 span 확인
    temp_span = df_rawdata.dropna(subset=['transn_occur_date']).copy()

    if len(temp_span) > 0:
        span_df = (
            temp_span.groupby(['lot_transn_seq', 'slot_id', 'data_kind'])['transn_occur_date']
            .agg(['min', 'max', 'count'])
            .reset_index()
        )
        span_df['span_sec'] = (span_df['max'] - span_df['min']).dt.total_seconds()

        print(f"[{label}] data_kind별 transn_occur_date span(sec) 요약:")
        print(span_df['span_sec'].describe())

    # 핵심: data_kind별 마지막 batch만 유지
    before_batch_filter = len(df_rawdata)
    df_rawdata = filter_latest_batch_by_gap_per_kind(
        df_rawdata,
        gap_seconds=gap_seconds
    )
    after_batch_filter = len(df_rawdata)

    print(f"[{label}] 최신 batch 필터 후 rows: {after_batch_filter} (drop {before_batch_filter - after_batch_filter})")
    print(f"[{label}] data_kind 분포(최신 batch 후):")
    print(df_rawdata['data_kind'].value_counts(dropna=False))
    print(f"[{label}] WF 분포(최신 batch 후 상위 20개):")
    print(df_rawdata[['lot_transn_seq', 'slot_id']].value_counts().head(20))

    print(f"[{label}] head:")
    print(df_rawdata.head())

    return df_rawdata


# =========================================================
# OCO
# =========================================================
df_rawdata_oco = prepare_rawdata_from_lotinfo(
    df_lotinfo=df_lotinfo_oco,
    days=days,
    db_user=db_user,
    label="OCO",
    gap_seconds=60,
    max_lot_transn_seq=1000,
    limit_rows=10000000
)

df_rawdata_oco.to_excel('NAUTIL_DAT_RAWDATA_OCO.xlsx', index=False)


# =========================================================
# ADI
# =========================================================
df_rawdata_adi = prepare_rawdata_from_lotinfo(
    df_lotinfo=df_lotinfo_adi,
    days=days,
    db_user=db_user,
    label="ADI",
    gap_seconds=60,
    max_lot_transn_seq=1000,
    limit_rows=10000000
)

df_rawdata_adi.to_excel('NAUTIL_DAT_RAWDATA_ADI.xlsx', index=False)
