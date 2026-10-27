def apply_kmrc_difference(analysis, adi_coeff, e1_coeff, adi_summary, e1_summary):
    """K-MRC = beta(OCO main E1 raw) - beta(ADI raw); evaluate at OCO analysis points."""
    keys = ["LOT_ID", "Wafer"]
    xcols, ycols = [f"{name}_X" for name in COEFF_KEYS_DX], [f"{name}_Y" for name in COEFF_KEYS_DY]
    values = ["wk_fit_x", "wk_fit_y", "rk_fit_x", "rk_fit_y", "total_fit_x", "total_fit_y", "raw_minus_total_fit_x", "raw_minus_total_fit_y"]
    out = analysis.copy().reset_index(drop=True)
    numeric(out, ["raw_x", "raw_y", "fcp_x", "fcp_y", "coordinate_X", "coordinate_Y"])
    for col in values:
        out[col] = np.nan
    out["global_model_source"] = "KMRC_OCO_E1_RAW_MINUS_ADI_RAW"

    def lookup(frame):
        return {tuple(row[k] for k in keys): row for row in frame.to_dict("records")}

    adi, e1, adi_info, e1_info = map(lookup, [adi_coeff, e1_coeff, adi_summary, e1_summary])
    coefficients, diagnostics, accepted, rejected = [], [], [], []
    for key, grp in out.groupby(keys, observed=True, dropna=False, sort=False):
        a, e = adi.get(key), e1.get(key)
        ai, ei = adi_info.get(key, {}), e1_info.get(key, {})
        row = dict(zip(keys, key))
        row.update(n_total=len(grp), n_adi_valid=ai.get("n_valid", 0), n_oco_e1_valid=ei.get("n_valid", 0), n_parameters_per_axis=19)
        row["adi_fit_status"], row["oco_e1_fit_status"] = ai.get("status", "missing_adi"), ei.get("status", "missing_oco_e1")
        reason = "missing_or_insufficient_adi" if a is None else "missing_or_insufficient_oco_e1" if e is None else None
        if reason:
            row.update(status="excluded", exclusion_reason=reason, n_valid=0)
            diagnostics.append(row)
            rejected.append(grp.assign(kmrc_exclusion_reason=reason))
            continue
        bx = np.array([e[col] - a[col] for col in xcols], dtype=float)
        by = np.array([e[col] - a[col] for col in ycols], dtype=float)
        if not np.isfinite(bx).all() or not np.isfinite(by).all():
            row.update(status="excluded", exclusion_reason="nonfinite_kmrc", n_valid=0)
            diagnostics.append(row)
            rejected.append(grp.assign(kmrc_exclusion_reason="nonfinite_kmrc"))
            continue
        numeric_cols = ["raw_x", "raw_y", "fcp_x", "fcp_y", "coordinate_X", "coordinate_Y"]
        valid = np.isfinite(grp[numeric_cols].to_numpy(float)).all(axis=1)
        work = grp.loc[valid]
        block = grp.copy()
        if len(work):
            mx, my = osr_wk20p_rk20p(*(work[col].to_numpy(float) for col in numeric_cols[2:]))
            for axis, matrix, beta in [("x", mx, bx), ("y", my, by)]:
                wk, rk = matrix[:, :10] @ beta[:10], matrix[:, 10:] @ beta[10:]
                block.loc[work.index, f"wk_fit_{axis}"] = wk
                block.loc[work.index, f"rk_fit_{axis}"] = rk
                block.loc[work.index, f"total_fit_{axis}"] = wk + rk
                block.loc[work.index, f"raw_minus_total_fit_{axis}"] = work[f"raw_{axis}"].to_numpy(float) - wk - rk
        row.update(status="ok", exclusion_reason="", n_valid=len(work))
        diagnostics.append(row)
        coeff_row = dict(row)
        coeff_row.update(zip(xcols, bx))
        coeff_row.update(zip(ycols, by))
        coefficients.append(coeff_row)
        accepted.append(block)
    base = keys + ["n_total", "n_valid", "n_adi_valid", "n_oco_e1_valid", "n_parameters_per_axis", "adi_fit_status", "oco_e1_fit_status", "status", "exclusion_reason"]
    result = pd.concat(accepted, ignore_index=True) if accepted else out.iloc[:0].copy()
    excluded = pd.concat(rejected, ignore_index=True) if rejected else out.iloc[:0].assign(kmrc_exclusion_reason=pd.Series(dtype="object"))
    coeff = pd.DataFrame(coefficients, columns=base + xcols + ycols)
    diag = pd.DataFrame(diagnostics, columns=base)
    return result, coeff, diag, excluded
