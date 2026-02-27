# 15

# ─────────────────────────────────────────────────────────────────────
# 섹션 11c-1: [통합 완료] 메타데이터 포함 확인
# ─────────────────────────────────────────────────────────────────────
# shot_fitting_all_marks()가 df_final의 메타데이터를 df_trocs_allmarks에
# 직접 포함하여 반환하므로 별도 JOIN 단계가 필요 없습니다.

if len(df_trocs_allmarks) > 0:
    meta_check = [c for c in _META_COLS if c in df_trocs_allmarks.columns]
    missing    = [c for c in _META_COLS if c not in df_trocs_allmarks.columns]
    print(f"✅ df_trocs_allmarks에 메타데이터 포함 확인")
    print(f"   shape            : {df_trocs_allmarks.shape}")
    print(f"   포함된 메타 컬럼 : {meta_check}")
    if missing:
        print(f"   누락 컬럼       : {missing}  (df_final에 없는 컬럼)")
else:
    print("⚠️ df_trocs_allmarks가 비어 있습니다.")


# ─────────────────────────────────────────────────────────────────────
# 섹션 11c-2: UNIQUE_ID × REGION 별 |mean| + 3σ 통계 계산
# ─────────────────────────────────────────────────────────────────────

def calc_trocs_stats(df, meta_cols_in_df, region_label):
    """
    주어진 DataFrame에서 UNIQUE_ID별 |mean| + 3σ 통계를 계산합니다.

    Parameters
    ----------
    df           : 통계 대상 DataFrame (trocs_fit_all_x/y 포함)
    meta_cols_in_df : 결과에 포함할 메타데이터 컬럼 리스트
    region_label : 'ALL' / 'CENTER' / 'MIDDLE' / 'EDGE'

    Returns
    -------
    DataFrame: UNIQUE_ID + 메타데이터 + REGION + 통계값
    """
    if df.empty:
        return pd.DataFrame()

    fit_x_col = 'trocs_fit_all_x'
    fit_y_col = 'trocs_fit_all_y'

    rows = []
    for uid, grp in df.groupby('UNIQUE_ID'):
        # 유효한 Fitting 값만 사용
        x_vals = grp[fit_x_col].dropna()
        y_vals = grp[fit_y_col].dropna()

        n_total = len(grp)
        n_valid = len(x_vals)

        if n_valid == 0:
            continue

        # 통계 계산
        x_mean  = x_vals.mean()
        x_sigma = x_vals.std(ddof=1) if n_valid > 1 else 0.0
        y_mean  = y_vals.mean()
        y_sigma = y_vals.std(ddof=1) if n_valid > 1 else 0.0

        row = {'UNIQUE_ID': uid, 'REGION': region_label,
               'n_marks': n_total, 'n_valid': n_valid}

        # 메타데이터 추가
        for mc in meta_cols_in_df:
            if mc in grp.columns and mc != 'UNIQUE_ID':
                val = grp[mc].dropna()
                row[mc] = val.iloc[0] if len(val) > 0 else None

        # X 통계
        row['x_mean']        = x_mean
        row['x_sigma']       = x_sigma
        row['x_abs_mean_3s'] = abs(x_mean) + 3 * x_sigma

        # Y 통계
        row['y_mean']        = y_mean
        row['y_sigma']       = y_sigma
        row['y_abs_mean_3s'] = abs(y_mean) + 3 * y_sigma

        rows.append(row)

    return pd.DataFrame(rows)


# ── REGION 경계 정의 (단위: um) ──────────────────────────────────────
# df_trocs_allmarks의 Radius 컬럼은 _mark_sel_all()에서 um 단위로 계산됨
CENTER_MAX = 50_000    #  50 mm
MIDDLE_MAX = 100_000   # 100 mm
EDGE_MAX   = 150_000   # 150 mm

if len(df_trocs_allmarks) > 0:
    # 결과에 포함할 메타 컬럼 (UNIQUE_ID·통계 컬럼 제외)
    stat_meta_cols = [c for c in df_trocs_allmarks.columns
                      if c not in ('UNIQUE_ID', 'trocs_fit_all_x', 'trocs_fit_all_y',
                                   'Test_ID', 'Shot_X', 'Shot_Y',
                                   'Coordinate_X', 'Coordinate_Y',
                                   'Wafer_X', 'Wafer_Y', 'Radius',
                                   'fcp_x', 'fcp_y')]

    # ── ALL: 반경 무관 전체 마크 ──
    df_stat_all    = calc_trocs_stats(df_trocs_allmarks, stat_meta_cols, 'ALL')

    # ── CENTER: Radius < 50,000 um ──
    df_center = df_trocs_allmarks[df_trocs_allmarks['Radius'] < CENTER_MAX]
    df_stat_center = calc_trocs_stats(df_center, stat_meta_cols, 'CENTER')

    # ── MIDDLE: 50,000 ≤ Radius < 100,000 um ──
    df_middle = df_trocs_allmarks[
        (df_trocs_allmarks['Radius'] >= CENTER_MAX) &
        (df_trocs_allmarks['Radius'] <  MIDDLE_MAX)
    ]
    df_stat_middle = calc_trocs_stats(df_middle, stat_meta_cols, 'MIDDLE')

    # ── EDGE: 100,000 ≤ Radius ≤ 150,000 um ──
    df_edge = df_trocs_allmarks[df_trocs_allmarks['Radius'] >= MIDDLE_MAX]
    df_stat_edge   = calc_trocs_stats(df_edge, stat_meta_cols, 'EDGE')

    # ── 전체 병합 ──
    df_trocs_stat = pd.concat(
        [df_stat_all, df_stat_center, df_stat_middle, df_stat_edge],
        ignore_index=True
    )

    # REGION 순서 정렬
    region_order = {'ALL': 0, 'CENTER': 1, 'MIDDLE': 2, 'EDGE': 3}
    df_trocs_stat['_region_order'] = df_trocs_stat['REGION'].map(region_order)
    df_trocs_stat = (df_trocs_stat
                     .sort_values(['UNIQUE_ID', '_region_order'])
                     .drop(columns=['_region_order'])
                     .reset_index(drop=True))

    print(f"✅ 통계 계산 완료")
    print(f"   총 행 수          : {len(df_trocs_stat)}")
    print(f"   UNIQUE_ID 수      : {df_trocs_stat['UNIQUE_ID'].nunique()}")
    print(f"   REGION별 행 수    : {df_trocs_stat['REGION'].value_counts().to_dict()}")
    print()
    print("[통계 결과 샘플]")
    show_cols = ['UNIQUE_ID', 'REGION', 'n_marks', 'n_valid',
                 'x_mean', 'x_sigma', 'x_abs_mean_3s',
                 'y_mean', 'y_sigma', 'y_abs_mean_3s']
    avail = [c for c in show_cols if c in df_trocs_stat.columns]
    display(df_trocs_stat[avail].head(8))

else:
    df_trocs_stat = pd.DataFrame()
    print("⚠️ df_trocs_allmarks가 비어 있어 통계 계산을 건너뜁니다.")


# ─────────────────────────────────────────────────────────────────────
# 섹션 11c-3: 통계 결과 저장
# ─────────────────────────────────────────────────────────────────────
import os

if len(df_trocs_stat) > 0:
    os.makedirs("output", exist_ok=True)

    # ── 통계 결과 저장 ──
    stat_path = "output/BDQ_trocs_allmarks_stat.csv"
    df_trocs_stat.to_csv(stat_path, index=False, encoding="utf-8-sig")
    print(f"✅ 저장 완료: {stat_path}")
    print(f"   행 수    : {len(df_trocs_stat):,}")
    print(f"   컬럼 수  : {len(df_trocs_stat.columns)}")

    # ── 컬럼 목록 출력 ──
    print(f"\n[df_trocs_stat 컬럼]")
    print(df_trocs_stat.columns.tolist())

    # ── REGION별 요약 ──
    print(f"\n[REGION별 |mean|+3σ 평균값]")
    summary_cols = ['REGION', 'x_abs_mean_3s', 'y_abs_mean_3s']
    avail = [c for c in summary_cols if c in df_trocs_stat.columns]
    display(df_trocs_stat.groupby('REGION')[avail[1:]].mean().round(4))
else:
    print("⚠️ df_trocs_stat가 비어 있습니다 — 저장 건너뜀")


# ─────────────────────────────────────────────────────────────────────
# 섹션 11d-1: TROCS All Marks 통계 Scatter Plot 시각화
#
# Layout : 2행 × 4열
#   행 0  : X방향 |mean|+3σ  (x_abs_mean_3s)
#   행 1  : Y방향 |mean|+3σ  (y_abs_mean_3s)
#   열    : ALL / CENTER / MIDDLE / EDGE
#
# X축    : P_TIME (노광 시각)
# Y축    : |mean|+3σ 값 (um)
# 색상   : P_EQPID (장비 ID)
# ─────────────────────────────────────────────────────────────────────
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import os

# ── 사전 검증 ─────────────────────────────────────────────────────────
_required = ['REGION', 'P_TIME', 'P_EQPID', 'x_abs_mean_3s', 'y_abs_mean_3s']
if len(df_trocs_stat) == 0:
    print("⚠️ df_trocs_stat가 비어 있습니다 — 시각화를 건너뜁니다.")
elif any(c not in df_trocs_stat.columns for c in _required):
    _missing = [c for c in _required if c not in df_trocs_stat.columns]
    print(f"⚠️ 필요 컬럼 누락: {_missing} — 시각화를 건너뜁니다.")
else:
    # ── P_TIME 변환 ────────────────────────────────────────────────────
    df_plot = df_trocs_stat.copy()
    df_plot['P_TIME'] = pd.to_datetime(df_plot['P_TIME'], errors='coerce')
    df_plot = df_plot.dropna(subset=['P_TIME', 'P_EQPID'])

    # ── P_EQPID 색상 매핑 ─────────────────────────────────────────────
    eqpids   = sorted(df_plot['P_EQPID'].dropna().unique())
    cmap     = plt.cm.get_cmap('tab10', max(len(eqpids), 1))
    color_map = {e: cmap(i) for i, e in enumerate(eqpids)}

    # ── 플롯 설정 ──────────────────────────────────────────────────────
    REGIONS    = ['ALL', 'CENTER', 'MIDDLE', 'EDGE']
    DIRECTIONS = [
        ('x_abs_mean_3s', 'X direction  |mean|+3\u03c3 (um)'),
        ('y_abs_mean_3s', 'Y direction  |mean|+3\u03c3 (um)'),
    ]

    fig, axes = plt.subplots(
        nrows=2, ncols=4,
        figsize=(22, 9),
        sharey='row',        # 같은 행(방향)끼리 Y축 공유
        constrained_layout=True
    )

    for row_i, (col_name, y_label) in enumerate(DIRECTIONS):
        for col_i, region in enumerate(REGIONS):
            ax = axes[row_i, col_i]

            df_r = df_plot[df_plot['REGION'] == region]

            for eqp, grp in df_r.groupby('P_EQPID'):
                x_vals = grp['P_TIME']
                y_vals = grp[col_name]
                ax.scatter(
                    x_vals, y_vals,
                    color=color_map.get(eqp, 'gray'),
                    s=35, alpha=0.8, linewidths=0.4,
                    edgecolors='white', zorder=3
                )

            # X축 날짜 포맷
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
            plt.setp(ax.get_xticklabels(), rotation=35, ha='right', fontsize=8)

            ax.set_title(region, fontsize=11, fontweight='bold', pad=4)
            ax.set_xlabel('P_TIME', fontsize=8)
            ax.grid(True, linestyle='--', alpha=0.4, zorder=0)
            ax.set_axisbelow(True)

            if col_i == 0:
                ax.set_ylabel(y_label, fontsize=9)

    # ── 범례 (P_EQPID) ────────────────────────────────────────────────
    legend_handles = [
        mpatches.Patch(color=color_map[e], label=str(e))
        for e in eqpids
    ]
    fig.legend(
        handles=legend_handles,
        title='P_EQPID',
        title_fontsize=9,
        fontsize=8,
        loc='lower center',
        ncol=min(len(eqpids), 10),
        bbox_to_anchor=(0.5, -0.04),
        framealpha=0.9
    )

    fig.suptitle(
        'TROCS All Marks  |mean|+3\u03c3  by P_TIME  (color = P_EQPID)',
        fontsize=13, fontweight='bold', y=1.01
    )

    # ── 저장 ───────────────────────────────────────────────────────────
    os.makedirs("output", exist_ok=True)
    out_png = "output/TROCS_allmarks_stat_scatter.png"
    fig.savefig(out_png, dpi=150, bbox_inches='tight')
    print(f"✅ 저장 완료: {out_png}")
    plt.show()
    print(f"   UNIQUE_ID 수  : {df_plot['UNIQUE_ID'].nunique()}")
    print(f"   P_EQPID 목록  : {eqpids}")


import os
os.makedirs("output", exist_ok=True)

# df_psm_input 저장
df_psm_input.to_csv("output/BDQ_psm_input.csv", index=False)
print("저장 완료: output/BDQ_psm_input.csv")

# df_trocs_input 저장
df_trocs_input.to_csv("output/BDQ_trocs_input.csv", index=False)
print("저장 완료: output/BDQ_trocs_input.csv")

# df_final 저장 (KMRC Decorrection + PSM Fitting + TROCS Fitting 결과 포함)
df_final.to_csv("output/BDQ_RawData_with_PSM_Fit.csv", index=False, encoding='utf-8-sig')
print("저장 완료: output/BDQ_RawData_with_PSM_Fit.csv")
