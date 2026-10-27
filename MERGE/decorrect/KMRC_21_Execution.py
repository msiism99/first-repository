df_adi_reg, coef_adi, summary_adi = run_company_joint_regression(df_adi_trocs, label="ADI", min_points=WK_RK_MIN_POINTS)
df_oco_e1_reg, coef_oco_e1, summary_oco_e1 = run_company_joint_regression(df_oco_e1_raw, label="OCO_E1_KMRC_REFERENCE", min_points=WK_RK_MIN_POINTS)
df_oco_reg, coef_oco, summary_oco, df_oco_kmrc_excluded = apply_kmrc_difference(df_oco_trocs, coef_adi, coef_oco_e1, summary_adi, summary_oco_e1)
df_wk_coeff_adi, df_rk_coeff_adi = split_wk_rk_coefficients(coef_adi)
df_wk_coeff_oco, df_rk_coeff_oco = split_wk_rk_coefficients(coef_oco)
df_wk_rk_diag_adi = wk_rk_rank_diagnostics(df_adi_reg, summary_adi)
df_oco_e1_diag = wk_rk_rank_diagnostics(df_oco_e1_reg, summary_oco_e1)
df_wk_rk_diag_oco = summary_oco.copy()
for prefix, rank_source in [("adi", df_wk_rk_diag_adi), ("oco_e1", df_oco_e1_diag)]:
    cols = WAFER_KEYS + ["rank_x", "rank_y", "rank_deficient"]
    rank_source = rank_source.reindex(columns=cols).rename(columns={col: f"{prefix}_{col}" for col in cols if col not in WAFER_KEYS})
    df_wk_rk_diag_oco = df_wk_rk_diag_oco.merge(rank_source, on=WAFER_KEYS, how="left", validate="1:1")
wk_rk_values = ["raw_x", "raw_y", "wk_fit_x", "wk_fit_y", "rk_fit_x", "rk_fit_y", "raw_minus_total_fit_x", "raw_minus_total_fit_y"]
df_wk_rk_wafer_adi, df_wk_rk_wafer_oco = summarize_values(df_adi_reg, WAFER_KEYS, wk_rk_values), summarize_values(df_oco_reg, WAFER_KEYS, wk_rk_values)
df_wk_rk_shot_adi = attach_measured_shot_indices(summarize_values(df_adi_reg, SHOT_KEYS, wk_rk_values), df_adi_reg)
df_wk_rk_shot_oco = attach_measured_shot_indices(summarize_values(df_oco_reg, SHOT_KEYS, wk_rk_values), df_oco_reg)
df_wk_removed_adi = df_adi_reg[[col for col in POINT_KEYS + ["wk_fit_x", "wk_fit_y"] if col in df_adi_reg]].copy()
df_wk_removed_oco = df_oco_reg[[col for col in POINT_KEYS + ["wk_fit_x", "wk_fit_y"] if col in df_oco_reg]].copy()
df_rk_removed_adi = df_adi_reg[[col for col in POINT_KEYS + ["rk_fit_x", "rk_fit_y"] if col in df_adi_reg]].copy()
df_rk_removed_oco = df_oco_reg[[col for col in POINT_KEYS + ["rk_fit_x", "rk_fit_y"] if col in df_oco_reg]].copy()
wk_rk_results = [
    ("ADI", df_adi_reg, df_wk_coeff_adi, df_rk_coeff_adi, df_wk_removed_adi, df_rk_removed_adi, df_wk_rk_diag_adi, df_wk_rk_wafer_adi, df_wk_rk_shot_adi),
    ("OCO", df_oco_reg, df_wk_coeff_oco, df_rk_coeff_oco, df_wk_removed_oco, df_rk_removed_oco, df_wk_rk_diag_oco, df_wk_rk_wafer_oco, df_wk_rk_shot_oco),
]
for mode, reg, wk, rk, wk_points, rk_points, diag, wafer, shot in wk_rk_results:
    save_stage(f"21_{mode}_WK_RK_REMOVED", reg, columns=POINT_KEYS + wk_rk_values)
    save_stage(f"21_{mode}_WK_WAFER_COEFFICIENTS", wk)
    save_stage(f"21_{mode}_RK_WAFER_COEFFICIENTS", rk)
    save_stage(f"21_{mode}_WK_REMOVED_POINTS", wk_points)
    save_stage(f"21_{mode}_RK_REMOVED_POINTS", rk_points)
    save_stage(f"21_{mode}_WK_RK_WAFER_DIAGNOSTICS", diag)
    save_stage(f"21_{mode}_WK_RK_WAFER_DATA", wafer)
    save_stage(f"21_{mode}_WK_RK_SHOT_DATA", shot)
save_stage("21_OCO_E1_WAFER_COEFFICIENTS", coef_oco_e1)
save_stage("21_OCO_E1_WAFER_DIAGNOSTICS", df_oco_e1_diag)
save_stage("21_KMRC_WAFER_COEFFICIENTS", coef_oco)
save_stage("21_KMRC_EXCLUDED_OCO_POINTS", df_oco_kmrc_excluded)
print(f"K-MRC 적용: OCO {len(df_oco_reg):,} points, 제외 {len(df_oco_kmrc_excluded):,} points")
