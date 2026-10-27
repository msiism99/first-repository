# %% 32. 고정 K-MRC 입력에서 영향 shot만 CPE 재계산 및 M3S 집계
def es_metric_table(frame, keys, scale):
    skeleton = frame[keys].drop_duplicates().copy()
    results = []
    for region, mask in [("R_LE_144MM", frame["radius"].le(ES_RADIUS_UM) & np.isfinite(frame["radius"])), ("ALL_POINTS", pd.Series(True, index=frame.index))]:
        part = frame.loc[mask]
        for axis in ES_METRIC_AXES:
            result = skeleton.copy()
            if not part.empty:
                work = part[keys].copy()
                values = pd.to_numeric(part[f"real_residual_{axis}"], errors="coerce") * 1000
                work["_value"] = values.where(np.isfinite(values))
                groups = work.groupby(keys, observed=True, dropna=False)
                stats = groups["_value"].agg(n_region_points="size", n_valid="count", mean_nm="mean")
                stats["sigma_nm"] = groups["_value"].std(ddof=ES_STD_DDOF)
                result = result.merge(stats.reset_index(), on=keys, how="left", validate="1:1")
            else:
                result = result.assign(n_region_points=0, n_valid=0, mean_nm=np.nan, sigma_nm=np.nan)
            result[["n_region_points", "n_valid"]] = result[["n_region_points", "n_valid"]].fillna(0).astype(int)
            result["abs_mean_nm"] = result["mean_nm"].abs()
            result["three_sigma_nm"] = 3 * result["sigma_nm"]
            result["M3S_nm"] = result["abs_mean_nm"] + result["three_sigma_nm"]
            result["metric_status"] = np.where(result.n_valid.eq(0), "no_valid_points", np.where(result.n_valid.le(ES_STD_DDOF), "too_few_points", "ok"))
            result["scale"], result["scale_pct"], result["axis"], result["region"] = scale, int(round(scale * 100)), axis, region
            results.append(result)
    return pd.concat(results, ignore_index=True)


def es_scaled_input(base, scale):
    out = base.copy()
    outer = out["_es_outer"]
    for axis in ["x", "y"]:
        original = pd.to_numeric(out[f"{axis.upper()}_reg_original"], errors="coerce")
        delta = pd.Series(0., index=out.index)
        delta.loc[outer] = (scale - out.loc[outer, "measurement_scale"]) * original.loc[outer]
        for col in [f"raw_minus_total_fit_{axis}", f"raw_{axis}", f"{axis.upper()}_reg"]:
            if col in out:
                out[col] = pd.to_numeric(out[col], errors="coerce") + delta
    out.loc[outer, "measurement_scale"] = scale
    out["edge_sweep_scale"] = scale
    return out


def es_assert_baseline(recomputed, baseline):
    rows = []
    for col in ["CPE_fit_x", "CPE_fit_y", "real_residual_x", "real_residual_y"]:
        old = pd.to_numeric(baseline[col], errors="coerce").to_numpy(float)
        new = pd.to_numeric(recomputed[col], errors="coerce").to_numpy(float)
        passed = np.allclose(old, new, rtol=1e-7, atol=ES_BASELINE_ATOL_UM, equal_nan=True)
        valid = np.isfinite(old) & np.isfinite(new)
        rows.append(dict(column=col, n_compared=int(valid.sum()), max_abs_error_nm=float(np.max(np.abs(old[valid]-new[valid]))*1000) if valid.any() else np.nan, passed=bool(passed)))
    check = pd.DataFrame(rows)
    if not check.passed.all():
        check.to_excel(ES_OUTPUT_DIR / "Baseline_Parity_Failed.xlsx", index=False)
        raise ValueError("저장된 27번 결과와 CPE 재계산이 일치하지 않습니다. 28번 설정/입력 파일이 같은 실행 자료인지 확인하세요. Baseline_Parity_Failed.xlsx 참고.")
    return check


es_wafer_results, es_shot_results, es_coefficients, es_diagnostics, es_parity_rows = [], [], [], [], []
es_outer_scales = es_affected_base.loc[es_affected_base["_es_outer"], "measurement_scale"].dropna().unique()
es_matched_scale = float(es_outer_scales[0]) if len(es_outer_scales) == 1 and any(np.isclose(es_outer_scales[0], s, rtol=0, atol=1e-12) for s in ES_SCALES) else None
if not es_affected_base.empty and es_matched_scale is None:
    baseline_fit, _, _ = es_run_cpe38_vba_style_shotwise(es_affected_base, label="OCO_SAVED_BASELINE", **ES_CPE_OPTIONS)
    es_parity_rows.append(es_assert_baseline(baseline_fit, es_affected_base))
for scale in ES_SCALES:
    full = es_base_points[ES_SHOT_KEYS + ["radius", "_es_affected", "real_residual_x", "real_residual_y"]].copy()
    if not es_affected_base.empty:
        changed = es_scaled_input(es_affected_base, scale)
        fitted, coeff, diagnostic = es_run_cpe38_vba_style_shotwise(changed, label=f"OCO_EDGE_{scale:.0%}", **ES_CPE_OPTIONS)
        if es_matched_scale is not None and np.isclose(scale, es_matched_scale, rtol=0, atol=1e-12):
            es_parity_rows.append(es_assert_baseline(fitted, es_affected_base))
        # Replace complete affected shots, including their inner points; unchanged shots reuse 27's results.
        for col in ["real_residual_x", "real_residual_y"]:
            full.loc[fitted.index, col] = fitted[col].to_numpy()
        for table, store in [(coeff, es_coefficients), (diagnostic, es_diagnostics)]:
            table = table.reindex(columns=list(dict.fromkeys(ES_SHOT_KEYS + list(table.columns))))
            table["scale"], table["scale_pct"] = scale, int(round(scale*100))
            store.append(table)
        if ES_SAVE_AFFECTED_POINTS:
            selected = ES_SHOT_KEYS + [col for col in ["photo_transn_seq", "DieX", "DieY", "TEST", "GROUP", "coordinate_X", "coordinate_Y", "radius", "measurement_source", "measurement_scale", "X_reg_original", "Y_reg_original", "raw_x", "raw_y", "wk_fit_x", "wk_fit_y", "rk_fit_x", "rk_fit_y", "total_fit_x", "total_fit_y", "raw_minus_total_fit_x", "raw_minus_total_fit_y", "CPE_fit_x", "CPE_fit_y", "real_residual_x", "real_residual_y"] if col in fitted]
            fitted[selected].to_parquet(ES_OUTPUT_DIR / "points" / f"Affected_points_scale_{int(round(scale*100)):03d}.parquet", index=False)
    wafer = es_metric_table(full, ES_WAFER_KEYS, scale)
    wafer = wafer.merge(es_wafer_index, on=ES_WAFER_KEYS, how="left", validate="m:1")
    shot = es_metric_table(full.loc[full["_es_affected"]], ES_SHOT_KEYS, scale)
    if not shot.empty:
        shot = shot.merge(es_shot_index, on=ES_SHOT_KEYS, how="left", validate="m:1")
    es_wafer_results.append(wafer)
    es_shot_results.append(shot)
    print(f"{scale:.0%}: wafer metric {len(wafer):,} rows, 영향 shot metric {len(shot):,} rows")
es_wafer_metrics = pd.concat(es_wafer_results, ignore_index=True)
es_shot_metrics = pd.concat(es_shot_results, ignore_index=True)
es_baseline_parity = pd.concat(es_parity_rows, ignore_index=True) if es_parity_rows else pd.DataFrame([dict(column="no_affected_shots", n_compared=0, max_abs_error_nm=0., passed=True)])
es_cpe_coefficients = pd.concat(es_coefficients, ignore_index=True) if es_coefficients else pd.DataFrame(columns=ES_SHOT_KEYS + ["scale", "scale_pct"])
es_cpe_diagnostics = pd.concat(es_diagnostics, ignore_index=True) if es_diagnostics else pd.DataFrame(columns=ES_SHOT_KEYS + ["scale", "scale_pct"])
display(es_baseline_parity)
display(es_wafer_metrics.head(12))
