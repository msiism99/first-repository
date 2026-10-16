# %% 14. ADI raw WK/RK 추출 / OCO Reg에 보정량 적용
# 기존 00~13 뒤에 붙일 수 있습니다. 이전 14~19는 이 코드로 교체하세요.
OPT_AXES = list(globals().get("ANALYSIS_AXES", ["x"]))
if not OPT_AXES or len(set(OPT_AXES)) != len(OPT_AXES) or any(axis not in ["x", "y"] for axis in OPT_AXES):
    raise ValueError("ANALYSIS_AXES는 ['x'], ['y'], ['x', 'y'] 중 하나여야 합니다.")
OPT_RAW_COLS, OPT_REG_COLS = {"x": "raw_x", "y": "raw_y"}, {"x": "X_reg", "y": "Y_reg"}
OPT_SIM_COLS = {axis: f"oco_sim_{axis}_um" for axis in OPT_AXES}
OPT_DIR = BASE_DIR / "output_oco_adi_raw_optimized"
OPT_TABLE_DIR, OPT_PLOT_DIR = OPT_DIR / "tables", OPT_DIR / "plots"
OPT_TABLE_DIR.mkdir(parents=True, exist_ok=True)
OPT_PLOT_DIR.mkdir(parents=True, exist_ok=True)
opt_files = {}

def opt_save_table(name, frame):
    frame.to_parquet(OPT_TABLE_DIR / f"{name}.parquet", index=False)
    frame.to_csv(OPT_TABLE_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")
    if SAVE_EXCEL:
        suffix = f"_sample_{EXCEL_MAX_ROWS}" if len(frame) > EXCEL_MAX_ROWS else ""
        frame.head(EXCEL_MAX_ROWS).to_excel(OPT_TABLE_DIR / f"{name}{suffix}.xlsx", index=False)
    opt_files[name] = dict(table=name, rows=len(frame), columns=len(frame.columns), parquet=str(OPT_TABLE_DIR / f"{name}.parquet"))
    pd.DataFrame(opt_files.values()).to_csv(OPT_DIR / "saved_files.csv", index=False, encoding="utf-8-sig")
    print(f"[{name}] {len(frame):,} rows × {len(frame.columns)} columns")
    display(frame.head(PREVIEW_ROWS))

def opt_save_figure(fig, name):
    fig.tight_layout()
    fig.savefig(OPT_PLOT_DIR / f"{name}.png", dpi=PLOT_DPI, bbox_inches="tight")
    fig.savefig(OPT_PLOT_DIR / f"{name}.pdf", bbox_inches="tight")
    if SHOW_PLOTS:
        display(NotebookImage(filename=str(OPT_PLOT_DIR / f"{name}.png")))
    plt.close(fig)

def fit_selected_terms(frame, mode, value_cols):
    require(frame, PAIR_KEYS + COORD_COLS + list(value_cols.values()), mode)
    points, coefficients, diagnostics = frame.copy().reset_index(drop=True), [], []
    for axis in value_cols:
        for name in ["wk_fit", "rk_fit", "total_fit", "fit_residual"]:
            points[f"selected_{name}_{axis}_um"] = np.nan
    for key, group in points.groupby(PAIR_KEYS, sort=False, dropna=False):
        for axis, column in value_cols.items():
            numeric = group[COORD_COLS + [column]].apply(pd.to_numeric, errors="coerce")
            work = numeric.loc[np.isfinite(numeric.to_numpy(float)).all(axis=1)]
            diag = dict(zip(PAIR_KEYS, key), mode=mode, axis=axis, input_column=column, n_total=len(group), n_valid=len(work), rank=0, status="skip_too_few_points")
            if len(work) >= WK_RK_MIN_POINTS:
                matrix = osr_wk20p_rk20p(*(work[col].to_numpy(float) for col in COORD_COLS))[0 if axis == "x" else 1]
                beta, _, rank, singular = np.linalg.lstsq(matrix, work[column].to_numpy(float), rcond=None)
                condition = float(singular[0] / singular[-1]) if singular[-1] > 0 else np.inf
                wk, rk = matrix[:, :10] @ beta[:10], matrix[:, 10:] @ beta[10:]
                for name, value in [("wk_fit", wk), ("rk_fit", rk), ("total_fit", wk+rk), ("fit_residual", work[column].to_numpy(float)-wk-rk)]:
                    points.loc[work.index, f"selected_{name}_{axis}_um"] = value
                for term, value in zip(GLOBAL_NAMES[axis], beta):
                    coefficients.append(dict(zip(PAIR_KEYS, key), mode=mode, axis=axis, term=term, family=term[:2], input_column=column, k_reg=float(value), n_valid=len(work), rank=int(rank), condition_number=condition, fit_valid=bool(rank == 19)))
                diag.update(rank=int(rank), condition_number=condition, status="ok" if rank == 19 else "rank_deficient")
            diagnostics.append(diag)
    columns = PAIR_KEYS + ["mode", "axis", "term", "family", "input_column", "k_reg", "n_valid", "rank", "condition_number", "fit_valid"]
    return points, pd.DataFrame(coefficients, columns=columns), pd.DataFrame(diagnostics)

def simulate_oco_from_adi_raw(oco, adi_coeff):
    require(oco, PAIR_KEYS + COORD_COLS + [OPT_REG_COLS[axis] for axis in OPT_AXES], "OCO Reg")
    require(adi_coeff, PAIR_KEYS + ["axis", "term", "k_reg", "fit_valid", "input_column"], "ADI raw K")
    if adi_coeff.duplicated(PAIR_KEYS + ["axis", "term"]).any():
        raise ValueError("ADI raw K에 wafer/axis/term 중복이 있습니다.")
    for axis in OPT_AXES:
        if not adi_coeff.loc[adi_coeff["axis"].eq(axis), "input_column"].eq(OPT_RAW_COLS[axis]).all():
            raise ValueError("ADI 보정의 계수 출처는 raw_x/raw_y여야 합니다. Reg 계수는 사용할 수 없습니다.")
    lookup = {key: group.set_index("term") for key, group in adi_coeff.groupby(PAIR_KEYS + ["axis"], dropna=False, sort=False)}
    result, audit = oco.copy().reset_index(drop=True), []
    for axis in OPT_AXES:
        for name in ["adi_wk_on_oco", "adi_rk_on_oco", "adi_total_on_oco", "input_change", "oco_sim"]:
            result[f"{name}_{axis}_um"] = np.nan
        result[f"simulation_status_{axis}"] = "invalid_oco_point"
    for key, group in result.groupby(PAIR_KEYS, dropna=False, sort=False):
        for axis in OPT_AXES:
            source = lookup.get(key + (axis,))
            selected = source.reindex(GLOBAL_NAMES[axis]) if source is not None else None
            beta = pd.to_numeric(selected["k_reg"], errors="coerce").to_numpy(float) if selected is not None else np.full(19, np.nan)
            status = "missing_or_nonfinite_adi_raw_k" if not np.isfinite(beta).all() else "ok"
            if status == "ok" and not selected["fit_valid"].eq(True).all():
                status = "rank_deficient_adi_raw_k"
            numeric = group[COORD_COLS + [OPT_REG_COLS[axis]]].apply(pd.to_numeric, errors="coerce")
            work = numeric.loc[np.isfinite(numeric.to_numpy(float)).all(axis=1)]
            if status == "ok" and len(work):
                matrix = osr_wk20p_rk20p(*(work[col].to_numpy(float) for col in COORD_COLS))[0 if axis == "x" else 1]
                wk, rk = matrix[:, :10] @ beta[:10], matrix[:, 10:] @ beta[10:]
                for name, value in [("adi_wk_on_oco", wk), ("adi_rk_on_oco", rk), ("adi_total_on_oco", wk+rk), ("input_change", -wk-rk), ("oco_sim", work[OPT_REG_COLS[axis]].to_numpy(float)-wk-rk)]:
                    result.loc[work.index, f"{name}_{axis}_um"] = value
                result.loc[work.index, f"simulation_status_{axis}"] = "ok"
            elif status != "ok":
                result.loc[group.index, f"simulation_status_{axis}"] = status
            audit.append(dict(zip(PAIR_KEYS, key), axis=axis, n_total=len(group), n_valid_oco_points=len(work), n_simulated=len(work) if status == "ok" else 0, adi_k_status=status))
    for axis in OPT_AXES:
        result[f"simulation_valid_{axis}"] = result[f"simulation_status_{axis}"].eq("ok")
        result[f"oco_sim_{axis}_nm"] = result[f"oco_sim_{axis}_um"] * UM_TO_NM
    result["simulation_valid"] = result[[f"simulation_valid_{axis}" for axis in OPT_AXES]].all(axis=1)
    return result, pd.DataFrame(audit)

df_adi_raw_fitted, raw_k_adi, raw_diag_adi = fit_selected_terms(df_adi, "ADI_RAW", {axis: OPT_RAW_COLS[axis] for axis in OPT_AXES})
df_oco_reg_selected, opt_k_reg, opt_reg_diag = fit_selected_terms(df_oco, "OCO", {axis: OPT_REG_COLS[axis] for axis in OPT_AXES})
df_oco_adi_opt, opt_audit = simulate_oco_from_adi_raw(df_oco, raw_k_adi)
opt_save_table("14_ADI_RAW_WK_RK_COEFFICIENTS", raw_k_adi)
opt_save_table("14_ADI_RAW_WK_RK_POINTS", df_adi_raw_fitted)
opt_save_table("14_OCO_REG_WK_RK_COEFFICIENTS", opt_k_reg)
opt_save_table("14_REGRESSION_DIAGNOSTICS", pd.concat([raw_diag_adi, opt_reg_diag], ignore_index=True))
opt_save_table("14_OCO_SIMULATED_POINTS", df_oco_adi_opt)
opt_save_table("14_OCO_SIMULATION_AUDIT", opt_audit)
print("기준: ADI raw → OCO Reg | 분석 방향:", OPT_AXES, "| 출력:", OPT_DIR)

# %% 15. OCO_sim의 WK/RK 추출 / K_sim = K_OCO_Reg - K_ADI_raw 검증
opt_fit_points, opt_k_sim, opt_fit_diag = fit_selected_terms(df_oco_adi_opt, "OCO_SIM", OPT_SIM_COLS)
opt_join_keys = PAIR_KEYS + ["axis", "term", "family"]
opt_k_check = opt_k_reg.merge(opt_k_sim, on=opt_join_keys, how="outer", suffixes=("_reg", "_sim"), validate="1:1")
opt_adi_k = raw_k_adi[opt_join_keys + ["k_reg", "fit_valid"]].rename(columns={"k_reg": "k_adi_raw", "fit_valid": "adi_raw_fit_valid"})
opt_k_check = opt_k_check.merge(opt_adi_k, on=opt_join_keys, how="left", validate="1:1")
opt_k_check["k_sim_expected"] = opt_k_check["k_reg_reg"] - opt_k_check["k_adi_raw"]
opt_k_check["k_identity_error"] = opt_k_check["k_reg_sim"] - opt_k_check["k_sim_expected"]
opt_k_check["identity_check_valid"] = opt_k_check["fit_valid_reg"].eq(True) & opt_k_check["fit_valid_sim"].eq(True) & opt_k_check["adi_raw_fit_valid"].eq(True)
opt_save_table("15_OCO_SIM_WK_RK_COEFFICIENTS", opt_k_sim)
opt_save_table("15_OCO_SIM_WK_RK_POINTS", opt_fit_points)
opt_save_table("15_OCO_SIM_REGRESSION_DIAGNOSTICS", opt_fit_diag)
opt_save_table("15_K_REG_MINUS_ADI_RAW_CHECK", opt_k_check)
print("유효 회귀의 K identity 최대 오차[원본 계수 스케일]:", opt_k_check.loc[opt_k_check["identity_check_valid"], "k_identity_error"].abs().max())

# %% 16. ADI raw / OCO Reg / OCO_sim K의 공통 좌표 nm 환산
opt_reference = df_adi if K_REFERENCE == "ADI" else df_oco
opt_k_nm = convert_reg_k_nm(pd.concat([raw_k_adi, opt_k_reg], ignore_index=True), opt_k_sim, opt_reference)

def pair_opt_k(left, right):
    lhs = opt_k_nm.loc[opt_k_nm["mode"].eq(left)].drop(columns="mode")
    rhs = opt_k_nm.loc[opt_k_nm["mode"].eq(right)].drop(columns="mode")
    paired = lhs.merge(rhs, on=opt_join_keys, how="outer", suffixes=("_left", "_right"), validate="1:1")
    paired["both_fits_valid"] = paired["fit_valid_left"].eq(True) & paired["fit_valid_right"].eq(True)
    paired["change_nm"] = paired[K_PLOT_VALUE + "_right"] - paired[K_PLOT_VALUE + "_left"]
    paired["abs_change_nm"] = paired[K_PLOT_VALUE + "_right"].abs() - paired[K_PLOT_VALUE + "_left"].abs()
    return paired

def select_opt_k(paired, axis, term):
    selected = paired.loc[paired["axis"].eq(axis) & paired["term"].eq(term)].copy()
    return selected.loc[selected["both_fits_valid"]] if EXCLUDE_RANK_DEFICIENT_K else selected

def summarize_opt_k(paired, left, right):
    rows = []
    for axis in OPT_AXES:
        for term in GLOBAL_NAMES[axis]:
            selected = select_opt_k(paired, axis, term)
            x_col, y_col = K_PLOT_VALUE + "_left", K_PLOT_VALUE + "_right"
            values = selected[[x_col, y_col]].apply(pd.to_numeric, errors="coerce")
            values = values.loc[np.isfinite(values.to_numpy(float)).all(axis=1)]
            row = dict(axis=axis, term=term, family=term[:2], left_source=left, right_source=right, nm_definition=K_PLOT_VALUE, reference_mode=K_REFERENCE)
            row.update(correlation_result(selected, x_col, y_col))
            row.update(n_excluded=len(common_wafers)-row["n_wafer"], left_mean_abs_nm=values[x_col].abs().mean(), right_mean_abs_nm=values[y_col].abs().mean())
            row["mean_abs_change_nm"] = row["right_mean_abs_nm"] - row["left_mean_abs_nm"]
            rows.append(row)
    return pd.DataFrame(rows)

opt_raw_k_pairs, opt_k_pairs = pair_opt_k("ADI_RAW", "OCO"), pair_opt_k("OCO", "OCO_SIM")
opt_raw_k_summary = summarize_opt_k(opt_raw_k_pairs, "ADI_RAW", "OCO_REG")
opt_k_summary = summarize_opt_k(opt_k_pairs, "OCO_REG", "OCO_SIM")
for name, table in [("16_K_NM_LONG", opt_k_nm), ("16_ADI_RAW_VS_OCO_REG_K_NM", opt_raw_k_pairs), ("16_ADI_RAW_VS_OCO_REG_K_SUMMARY", opt_raw_k_summary), ("16_OCO_REG_VS_SIM_K_NM", opt_k_pairs), ("16_OCO_REG_VS_SIM_K_SUMMARY", opt_k_summary)]:
    opt_save_table(name, table)

# %% 17. ADI raw ↔ OCO Reg / 동일 OCO 측정점의 Reg ↔ simulation 통계
def selected_statistics(frame, value_cols, prefix):
    result = frame[PAIR_KEYS].drop_duplicates()
    for axis, column in value_cols.items():
        values = pd.to_numeric(frame[column], errors="coerce")
        work = frame[PAIR_KEYS].assign(value=values.where(np.isfinite(values)))
        stats = work.groupby(PAIR_KEYS, dropna=False).agg(n_valid=("value", "count"), mean_nm=("value", "mean"), std_nm=("value", lambda values: values.std(ddof=STD_DDOF))).reset_index()
        stats[["mean_nm", "std_nm"]] *= UM_TO_NM
        stats["3sigma_nm"] = 3 * stats["std_nm"]
        stats["mean_plus_3sigma_nm"] = stats["mean_nm"] + stats["3sigma_nm"]
        stats = stats.rename(columns={col: f"{prefix}_{axis}_{col}" for col in stats if col not in PAIR_KEYS})
        result = result.merge(stats, on=PAIR_KEYS, how="left", validate="1:1")
    return result

opt_raw_stats = selected_statistics(df_adi, {axis: OPT_RAW_COLS[axis] for axis in OPT_AXES}, "adi_raw")
opt_oco_stats = selected_statistics(df_oco, {axis: OPT_REG_COLS[axis] for axis in OPT_AXES}, "oco_reg")
opt_raw_comparison = opt_raw_stats.merge(opt_oco_stats, on=PAIR_KEYS, how="inner", validate="1:1")
opt_stats = df_oco_adi_opt[PAIR_KEYS].drop_duplicates()
for axis in OPT_AXES:
    shared = df_oco_adi_opt.loc[df_oco_adi_opt[f"simulation_valid_{axis}"]]
    for prefix, column in [("oco_reg", OPT_REG_COLS[axis]), ("oco_sim", OPT_SIM_COLS[axis])]:
        stats = selected_statistics(shared, {axis: column}, prefix)
        opt_stats = opt_stats.merge(stats, on=PAIR_KEYS, how="left", validate="1:1")
        opt_stats[f"{prefix}_{axis}_n_valid"] = opt_stats[f"{prefix}_{axis}_n_valid"].fillna(0).astype(int)
    for metric in ["mean", "3sigma", "mean_plus_3sigma"]:
        opt_stats[f"{axis}_{metric}_change_nm"] = opt_stats[f"oco_sim_{axis}_{metric}_nm"] - opt_stats[f"oco_reg_{axis}_{metric}_nm"]
opt_stat_corr = []
for table, left, right in [(opt_raw_comparison, "adi_raw", "oco_reg"), (opt_stats, "oco_reg", "oco_sim")]:
    for axis in OPT_AXES:
        for metric in ["mean", "3sigma", "mean_plus_3sigma"]:
            row = dict(left_source=left, right_source=right, axis=axis, metric=metric)
            row.update(correlation_result(table, f"{left}_{axis}_{metric}_nm", f"{right}_{axis}_{metric}_nm"))
            opt_stat_corr.append(row)
opt_save_table("17_ADI_RAW_VS_OCO_REG_WAFER_STATISTICS", opt_raw_comparison)
opt_save_table("17_OCO_REG_VS_SIM_WAFER_STATISTICS", opt_stats)
opt_save_table("17_STATISTICS_CORRELATIONS", pd.DataFrame(opt_stat_corr))
print(f"mean+3sigma = signed mean + 3×std(ddof={STD_DDOF}). OCO 전후 통계는 방향별 동일 측정점을 사용합니다.")

# %% 18. 통계 및 K term 그래프 / 실행 설정 저장
for table, left, right, name in [(opt_raw_comparison, "adi_raw", "oco_reg", "ADI_RAW_VS_OCO_REG"), (opt_stats, "oco_reg", "oco_sim", "OCO_REG_VS_SIM")]:
    fig, axes = plt.subplots(len(OPT_AXES), 3, figsize=(18, 5*len(OPT_AXES)), squeeze=False)
    for row_index, axis in enumerate(OPT_AXES):
        for col_index, metric in enumerate(["mean", "3sigma", "mean_plus_3sigma"]):
            ax = axes[row_index, col_index]
            scatter_panel(ax, table, f"{left}_{axis}_{metric}_nm", f"{right}_{axis}_{metric}_nm", f"{name}: {axis.upper()} {metric}")
    opt_save_figure(fig, f"18_{name}_STATISTICS")
for paired, left, right, name in [(opt_raw_k_pairs, "ADI raw", "OCO Reg", "ADI_RAW_VS_OCO_REG"), (opt_k_pairs, "OCO Reg", "OCO simulation", "OCO_REG_VS_SIM")]:
    for family in ["WK", "RK"]:
        terms = sorted([(axis, term) for axis in OPT_AXES for term in GLOBAL_NAMES[axis] if term.startswith(family)], key=lambda item: int(item[1][2:]))
        for start in range(0, len(terms), 12):
            fig, axes = plt.subplots(4, 3, figsize=(16, 18))
            page = terms[start:start+12]
            for ax, (axis, term) in zip(axes.ravel(), page):
                scatter_panel(ax, select_opt_k(paired, axis, term), K_PLOT_VALUE+"_left", K_PLOT_VALUE+"_right", f"{name}: {term}_{axis.upper()}")
                ax.set(xlabel=f"{left} K [nm]", ylabel=f"{right} K [nm]")
            for ax in axes.ravel()[len(page):]:
                ax.set_visible(False)
            opt_save_figure(fig, f"18_{name}_{family}_{start//12+1:02d}")
fig, axes = plt.subplots(2, 1, figsize=(15, 9))
for ax, family in zip(axes, ["WK", "RK"]):
    selected = opt_k_summary.loc[opt_k_summary["family"].eq(family)].copy()
    selected["order"] = selected["term"].str[2:].astype(int)
    selected = selected.sort_values("order")
    positions = np.arange(len(selected))
    ax.bar(positions-.18, selected["left_mean_abs_nm"], width=.36, label="OCO Reg")
    ax.bar(positions+.18, selected["right_mean_abs_nm"], width=.36, label="OCO simulation")
    ax.set_xticks(positions, selected["term"]+"_"+selected["axis"].str.upper(), rotation=45, ha="right")
    ax.set(ylabel="Mean absolute term contribution [nm]", title=f"{family}: {K_PLOT_VALUE}, common {K_REFERENCE} reference")
    ax.grid(axis="y", alpha=.2)
    ax.legend()
opt_save_figure(fig, "18_OCO_REG_VS_SIM_K_MAGNITUDE")
opt_settings = dict(formula="OCO_sim = OCO_Reg - B_OCO @ K_ADI_raw", adi_basis="raw_x/raw_y", oco_basis="X_reg/Y_reg", axes=OPT_AXES, transfer_gain=1., pair_keys=PAIR_KEYS, unit_input="um", unit_output="nm", um_to_nm=UM_TO_NM, std_ddof=STD_DDOF, k_reference=K_REFERENCE, k_plot_value=K_PLOT_VALUE, skip_rank_deficient_adi=True, exclude_rank_deficient_k=EXCLUDE_RANK_DEFICIENT_K, input_files=input_manifest)
(OPT_DIR / "run_settings.json").write_text(json.dumps(opt_settings, ensure_ascii=False, indent=2), encoding="utf-8")
print("완료:", OPT_DIR)

# %% 19. 산포 증가 진단: 현재 보정 / 반대 부호 / WK·RK 분리
diag_rows = []
for key, group in df_oco_adi_opt.groupby(PAIR_KEYS, dropna=False, sort=False):
    for axis in OPT_AXES:
        cols = [OPT_REG_COLS[axis], f"adi_total_on_oco_{axis}_um", f"adi_wk_on_oco_{axis}_um", f"adi_rk_on_oco_{axis}_um", f"oco_sim_{axis}_um"]
        values = group[cols].apply(pd.to_numeric, errors="coerce").to_numpy(float) * UM_TO_NM
        values = values[np.isfinite(values).all(axis=1)]
        row = dict(zip(PAIR_KEYS, key), axis=axis, n_points=len(values), status="too_few_points")
        if len(values) > max(1, STD_DDOF):
            reg, correction, wk, rk, saved_sim = values.T
            reg_var, correction_var = np.var(reg, ddof=STD_DDOF), np.var(correction, ddof=STD_DDOF)
            covariance = np.cov(reg, correction, ddof=STD_DDOF)[0, 1]
            row.update(status="ok", reg_3sigma_nm=3*np.std(reg, ddof=STD_DDOF), correction_3sigma_nm=3*np.std(correction, ddof=STD_DDOF))
            row.update(minus_3sigma_nm=3*np.std(reg-correction, ddof=STD_DDOF), plus_3sigma_nm=3*np.std(reg+correction, ddof=STD_DDOF))
            row.update(wk_only_3sigma_nm=3*np.std(reg-wk, ddof=STD_DDOF), rk_only_3sigma_nm=3*np.std(reg-rk, ddof=STD_DDOF))
            has_range = np.ptp(reg) > CORR_MIN_RANGE_NM and np.ptp(correction) > CORR_MIN_RANGE_NM
            row["corr_reg_correction"] = covariance / np.sqrt(reg_var*correction_var) if has_range and reg_var > 0 and correction_var > 0 else np.nan
            row["corr_needed_for_reduction"] = np.sqrt(correction_var/reg_var)/2 if reg_var > 0 else np.nan
            row["saved_sim_identity_error_nm"] = float(np.max(np.abs(saved_sim-(reg-correction))))
        diag_rows.append(row)
oco_sim_diagnostic = pd.DataFrame(diag_rows)
opt_save_table("19_OCO_SIM_SPREAD_DIAGNOSTIC", oco_sim_diagnostic)
diag_ok = oco_sim_diagnostic.loc[oco_sim_diagnostic["status"].eq("ok")]
if not diag_ok.empty:
    print("wafer별 진단값의 중앙값:")
    display(diag_ok.groupby("axis")[["reg_3sigma_nm", "correction_3sigma_nm", "minus_3sigma_nm", "plus_3sigma_nm", "wk_only_3sigma_nm", "rk_only_3sigma_nm", "corr_reg_correction", "corr_needed_for_reduction"]].median())
