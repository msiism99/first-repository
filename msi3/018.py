def run_cpe38_ridge_shotwise_after_wkrk(
    df,
    label="ADI",
    wafer_cols=("LOT_ID", "Wafer"),
    shot_center_cols=("fcp_x", "fcp_y"),
    residual_cols=("residual_x", "residual_y"),
    shot_cols=("coordinate_X", "coordinate_Y"),
    span_mode="OVO3_38P_F2F",
    min_points_guide=10,
):
    """
    shot별 CPE38 ridge fitting.
    point가 적어도 skip하지 않고,
    base lambda를 키워서라도 결과를 산출한다.
    """
    df = df.copy()

    required = list(wafer_cols) + list(shot_center_cols) + list(residual_cols) + list(shot_cols)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"[{label}] 필수 컬럼 누락: {missing}")

    _to_numeric(df, list(shot_center_cols) + list(residual_cols) + list(shot_cols))

    for c in [
        "CPE_fit_x", "CPE_fit_y",
        "real_residual_x", "real_residual_y",
        "CPE_gopt_x", "CPE_gopt_y",
    ]:
        df[c] = np.nan

    span_limits = get_active_span_limits(span_mode)

    coef_rows = []
    summary_rows = []

    group_keys = list(wafer_cols) + list(shot_center_cols)

    for gkey, grp in df.groupby(group_keys, dropna=False):
        valid_mask = (
            grp[residual_cols[0]].notna() &
            grp[residual_cols[1]].notna() &
            grp[shot_cols[0]].notna() &
            grp[shot_cols[1]].notna()
        )
        work = grp.loc[valid_mask].copy()

        n_valid = len(work)
        if n_valid == 0:
            summary_rows.append({
                "LOT_ID": gkey[0],
                "Wafer": gkey[1],
                "fcp_x": gkey[2],
                "fcp_y": gkey[3],
                "n_total": len(grp),
                "n_valid": 0,
                "few_points_flag": True,
                "status": "no_valid_points",
            })
            continue

        rx = work[shot_cols[0]].to_numpy(dtype=float)
        ry = work[shot_cols[1]].to_numpy(dtype=float)

        residual_x = work[residual_cols[0]].to_numpy(dtype=float)
        residual_y = work[residual_cols[1]].to_numpy(dtype=float)

        X_dx, X_dy = cpe_38para(rx, ry)

        grid_rx, grid_ry = build_eval_grid_from_data(rx, ry, grid_n=CPE_EVAL_GRID_N)
        X_eval_dx, X_eval_dy = cpe_38para(grid_rx, grid_ry)

        few_points_flag = n_valid < min_points_guide
        base_lambda_scale = choose_base_lambda_scale(n_valid)

        fit_x = solve_ridge_with_gopt_and_span(
            X_fit=X_dx,
            y=residual_x,
            X_eval=X_eval_dx,
            coeff_names=CPE38_KEYS_DX,
            span_limits=span_limits,
            base_lambda_scale=base_lambda_scale,
            gopt_spec=RIDGE_G_OPT_SPEC,
            gopt_tol=RIDGE_G_OPT_TOLERANCE,
            gopt_max_iter=RIDGE_G_OPT_MAX_ITER,
            span_max_iter=RIDGE_SPAN_MAX_ITER,
            min_lambda=RIDGE_MIN_LAMBDA,
            max_lambda=RIDGE_MAX_LAMBDA,
            lambda_increment=RIDGE_LAMBDA_INCREMENT,
            span_tolerance=RIDGE_SPAN_TOLERANCE,
            enable_span_control=ENABLE_RIDGE_SPAN_CONTROL,
            debug=False,
            debug_label=f"{label}|{gkey[0]}|W{gkey[1]}|({gkey[2]:.0f},{gkey[3]:.0f})|X",
        )
        fit_y = solve_ridge_with_gopt_and_span(
            X_fit=X_dy,
            y=residual_y,
            X_eval=X_eval_dy,
            coeff_names=CPE38_KEYS_DY,
            span_limits=span_limits,
            base_lambda_scale=base_lambda_scale,
            gopt_spec=RIDGE_G_OPT_SPEC,
            gopt_tol=RIDGE_G_OPT_TOLERANCE,
            gopt_max_iter=RIDGE_G_OPT_MAX_ITER,
            span_max_iter=RIDGE_SPAN_MAX_ITER,
            min_lambda=RIDGE_MIN_LAMBDA,
            max_lambda=RIDGE_MAX_LAMBDA,
            lambda_increment=RIDGE_LAMBDA_INCREMENT,
            span_tolerance=RIDGE_SPAN_TOLERANCE,
            enable_span_control=ENABLE_RIDGE_SPAN_CONTROL,
            debug=False,
            debug_label=f"{label}|{gkey[0]}|W{gkey[1]}|({gkey[2]:.0f},{gkey[3]:.0f})|Y",
        )

        beta_x = fit_x["beta"]
        beta_y = fit_y["beta"]

        cpe_fit_x = fit_x["pred"]
        cpe_fit_y = fit_y["pred"]

        real_residual_x = residual_x - cpe_fit_x
        real_residual_y = residual_y - cpe_fit_y

        valid_idx = work.index

        df.loc[valid_idx, "CPE_fit_x"] = cpe_fit_x
        df.loc[valid_idx, "CPE_fit_y"] = cpe_fit_y
        df.loc[valid_idx, "real_residual_x"] = real_residual_x
        df.loc[valid_idx, "real_residual_y"] = real_residual_y
        df.loc[valid_idx, "CPE_gopt_x"] = fit_x["gopt"]
        df.loc[valid_idx, "CPE_gopt_y"] = fit_y["gopt"]

        coef_row = {
            "LOT_ID": gkey[0],
            "Wafer": gkey[1],
            "fcp_x": gkey[2],
            "fcp_y": gkey[3],
            "n_total": len(grp),
            "n_valid": n_valid,
            "few_points_flag": few_points_flag,
            "base_lambda_scale": base_lambda_scale,
            "gopt_x": fit_x["gopt"],
            "gopt_y": fit_y["gopt"],
        }
        for name, val in zip(CPE38_KEYS_DX, beta_x):
            coef_row[f"{name}_X"] = val
        for name, val in zip(CPE38_KEYS_DY, beta_y):
            coef_row[f"{name}_Y"] = val
        coef_rows.append(coef_row)

        summary_rows.append({
            "LOT_ID": gkey[0],
            "Wafer": gkey[1],
            "fcp_x": gkey[2],
            "fcp_y": gkey[3],
            "n_total": len(grp),
            "n_valid": n_valid,
            "few_points_flag": few_points_flag,
            "base_lambda_scale": base_lambda_scale,
            "gopt_x": fit_x["gopt"],
            "gopt_y": fit_y["gopt"],
            "rms_before_x": float(np.sqrt(np.nanmean(residual_x ** 2))),
            "rms_before_y": float(np.sqrt(np.nanmean(residual_y ** 2))),
            "rms_after_x": float(np.sqrt(np.nanmean(real_residual_x ** 2))),
            "rms_after_y": float(np.sqrt(np.nanmean(real_residual_y ** 2))),
            "status": "ok",
        })

    coef_df = pd.DataFrame(coef_rows)
    summary_df = pd.DataFrame(summary_rows)

    print(f"[{label}] shot별 CPE38 ridge 완료")
    print(f"  shot groups: {len(summary_df)}")
    print(f"  coef rows: {len(coef_df)}")
    if "few_points_flag" in summary_df.columns:
        print(f"  few points shots: {summary_df['few_points_flag'].sum()}")

    return df, coef_df, summary_df


df_adi_cpe, coef_adi_cpe, summary_adi_cpe = run_cpe38_ridge_shotwise_after_wkrk(
    df_adi,
    label="ADI",
    wafer_cols=("LOT_ID", "Wafer"),
    shot_center_cols=("fcp_x", "fcp_y"),
    residual_cols=("raw_minus_total_fit_x", "raw_minus_total_fit_y"),
    shot_cols=("coordinate_X", "coordinate_Y"),
    span_mode=SPAN_MODE,
    min_points_guide=MIN_POINTS_GUIDE,
)

df_oco_cpe, coef_oco_cpe, summary_oco_cpe = run_cpe38_ridge_shotwise_after_wkrk(
    df_oco,
    label="OCO",
    wafer_cols=("LOT_ID", "Wafer"),
    shot_center_cols=("fcp_x", "fcp_y"),
    residual_cols=("raw_minus_total_fit_x", "raw_minus_total_fit_y"),
    shot_cols=("coordinate_X", "coordinate_Y"),
    span_mode=SPAN_MODE,
    min_points_guide=MIN_POINTS_GUIDE,
)

df_adi_cpe.to_excel("df_final_adi_after_cpe38_ridge_shotwise.xlsx", index=False)
df_oco_cpe.to_excel("df_final_oco_after_cpe38_ridge_shotwise.xlsx", index=False)

coef_adi_cpe.to_excel("coef_adi_cpe38_ridge_shotwise.xlsx", index=False)
coef_oco_cpe.to_excel("coef_oco_cpe38_ridge_shotwise.xlsx", index=False)

summary_adi_cpe.to_excel("summary_adi_cpe38_ridge_shotwise.xlsx", index=False)
summary_oco_cpe.to_excel("summary_oco_cpe38_ridge_shotwise.xlsx", index=False)
