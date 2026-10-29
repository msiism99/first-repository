# %% 05. 제품별 분석 실행 및 wafer·shot·제품 비교표
def ep_shot_metadata(points):
    columns = [col for col in ["DieX", "DieY", "photo_transn_seq"] if col in points]
    return points.groupby(EP_SHOT_KEYS, observed=True, dropna=False)[columns].first().reset_index() if columns else points[EP_SHOT_KEYS].drop_duplicates()


def ep_prediction_stats(points, keys, axes=None):
    axes = EP_AXES if axes is None else axes
    tables = []
    edge = points.loc[points.region.eq("EDGE")]
    for axis in axes:
        table = ep_group_stats(edge, keys, f"edge_deviation_{axis}", skeleton=points)
        candidate = edge.groupby(keys, observed=True, dropna=False).size().rename("n_edge_total").reset_index()
        table = table.merge(candidate, on=keys, how="left", validate="1:1")
        table["n_edge_total"] = table.n_edge_total.fillna(0).astype(int)
        table["coverage_fraction"] = table.n_valid / table.n_edge_total.replace(0, np.nan)
        table["axis"] = axis
        tables.append(table)
    return pd.concat(tables, ignore_index=True)


def ep_radial_profile(points, axes=None):
    axes = EP_AXES if axes is None else axes
    selected = points.loc[points._has_edge_shot].copy()
    bin_index = np.searchsorted(EP_RADIAL_BINS_MM, selected.radius.to_numpy(float)/1000, side="right") - 1
    bin_index[selected.radius.eq(EP_RADIAL_BINS_MM[-1]*1000)] = len(EP_RADIAL_BINS_MM)-2
    selected["radial_bin"] = bin_index
    selected = selected.loc[selected.radial_bin.ge(0) & selected.radial_bin.lt(len(EP_RADIAL_BINS_MM)-1)]
    tables = []
    keys = EP_WAFER_KEYS + ["radial_bin"]
    for axis in axes:
        part = selected.loc[selected[f"reference_eligible_{axis}"]]
        table = ep_group_stats(part, keys, f"reference_residual_{axis}")
        table["axis"] = axis
        if not table.empty:
            index = table.radial_bin.astype(int).to_numpy()
            table["radius_mid_mm"] = (EP_RADIAL_BINS_MM[index]+EP_RADIAL_BINS_MM[index+1])/2
        else:
            table["radius_mid_mm"] = pd.Series(dtype=float)
        tables.append(table)
    return pd.concat(tables, ignore_index=True)


ep_wafer_input, ep_shot_input, ep_wafer_prediction, ep_shot_prediction = [], [], [], []
ep_reference_diagnostics, ep_reference_coefficients, ep_profiles, ep_audits, ep_run_sources = [], [], [], [], []
for source_index, source in enumerate(EP_SOURCES):
    axes = EP_PRODUCT_AXES[str(source["product"])]
    raw, settings, point_path, settings_path = ep_read_product(source)
    options = ep_restore_settings(settings)  # 제품별 저장 설정을 매번 복원
    points, audit = ep_prepare_points(raw, source["product"], axes=axes)
    del raw
    before_wafer = ep_input_stats(points, EP_WAFER_KEYS, axes=axes)
    before_shot = ep_input_stats(points.loc[points._has_edge_shot], EP_SHOT_KEYS, axes=axes)
    result, diagnostic, coefficients = ep_fit_inner_reference(points, options, axes=axes)
    metadata = ep_shot_metadata(result)
    before_shot = before_shot.merge(metadata, on=EP_SHOT_KEYS, how="left", validate="m:1")
    wafer_prediction = ep_prediction_stats(result, EP_WAFER_KEYS, axes=axes)
    shot_prediction = ep_prediction_stats(result.loc[result._has_edge_shot], EP_SHOT_KEYS, axes=axes)
    shot_prediction = shot_prediction.merge(metadata, on=EP_SHOT_KEYS, how="left", validate="m:1")
    profile = ep_radial_profile(result, axes=axes)
    ep_wafer_input.append(before_wafer)
    ep_shot_input.append(before_shot)
    ep_wafer_prediction.append(wafer_prediction)
    ep_shot_prediction.append(shot_prediction)
    ep_reference_diagnostics.append(diagnostic)
    ep_reference_coefficients.append(coefficients)
    ep_profiles.append(profile)
    ep_audits.append(audit)
    ep_run_sources.append(dict(product=source["product"], axis=axes[0], points=str(point_path), settings=str(settings_path), original_settings=settings))
    if EP_SAVE_POINT_DATA:
        columns = EP_SHOT_KEYS + [col for col in ["DieX", "DieY", "photo_transn_seq", "TEST", "GROUP", "coordinate_X", "coordinate_Y", "radius", "region", "measurement_source", "measurement_scale", "_fit_valid"] if col in result]
        columns += [col for axis in axes for col in [f"{axis.upper()}_reg_original", f"raw_minus_total_fit_{axis}", f"input100_{axis}"] if col in result]
        columns += [f"{stem}_{axis}" for axis in axes for stem in ["inner_prediction", "reference_residual", "edge_deviation", "reference_eligible", "reference_status"]]
        result["analysis_axis"] = axes[0]
        columns += ["analysis_axis"]
        result.loc[result._has_edge_shot, columns].to_parquet(EP_OUTPUT_DIR / "points" / f"Product_{source_index+1:02d}_edge_shots.parquet", index=False)
    print(f"{source['product']} [{axes[0].upper()}]: wafer {len(points[EP_WAFER_KEYS].drop_duplicates()):,}, inner {audit['n_inner']:,} pts, edge {audit['n_edge']:,} pts, reference eligible {int(diagnostic.eligible.sum()):,}/{len(diagnostic):,} shots")
    del points, result

ep_wafer_input = pd.concat(ep_wafer_input, ignore_index=True)
ep_shot_input = pd.concat(ep_shot_input, ignore_index=True)
ep_wafer_prediction = pd.concat(ep_wafer_prediction, ignore_index=True)
ep_shot_prediction = pd.concat(ep_shot_prediction, ignore_index=True)
ep_reference_diagnostics = pd.concat(ep_reference_diagnostics, ignore_index=True)
ep_reference_coefficients = pd.concat(ep_reference_coefficients, ignore_index=True)
ep_radial_profiles = pd.concat(ep_profiles, ignore_index=True)
ep_input_audit = pd.DataFrame(ep_audits)
ep_wafer_comparison = ep_region_comparison(ep_wafer_input, EP_WAFER_KEYS)
ep_shot_comparison = ep_region_comparison(ep_shot_input.drop(columns=["DieX", "DieY", "photo_transn_seq"], errors="ignore"), EP_SHOT_KEYS)
ep_shot_comparison = ep_shot_comparison.loc[ep_shot_comparison.n_valid_inner.gt(0) & ep_shot_comparison.n_valid_edge.gt(0)].copy()
ep_shot_comparison = ep_shot_comparison.merge(ep_shot_input[EP_SHOT_KEYS + [col for col in ["DieX", "DieY", "photo_transn_seq"] if col in ep_shot_input]].drop_duplicates(EP_SHOT_KEYS), on=EP_SHOT_KEYS, how="left", validate="m:1")
ep_prediction_coverage = ep_reference_diagnostics.groupby(["product", "axis", "status"], observed=True, dropna=False).size().rename("n_shots").reset_index()

ep_summary_rows = []
for product in [str(s["product"]) for s in EP_SOURCES]:
    for axis in EP_PRODUCT_AXES[product]:
        base = ep_wafer_comparison.loc[ep_wafer_comparison["product"].eq(product) & ep_wafer_comparison.axis.eq(axis)]
        prediction = ep_wafer_prediction.loc[ep_wafer_prediction["product"].eq(product) & ep_wafer_prediction.axis.eq(axis)]
        diag = ep_reference_diagnostics.loc[ep_reference_diagnostics["product"].eq(product) & ep_reference_diagnostics.axis.eq(axis)]
        ep_summary_rows.append(dict(product=product, axis=axis, n_wafers=len(base), n_wafers_with_prediction=int(prediction.n_valid.gt(0).sum()), n_edge_shots=len(diag), n_eligible_shots=int(diag.eligible.sum()),
            n_edge_total=int(prediction.n_edge_total.sum()), n_edge_predicted=int(prediction.n_valid.sum()), edge_prediction_coverage=float(prediction.n_valid.sum()/prediction.n_edge_total.sum()) if prediction.n_edge_total.sum() else np.nan,
            median_wafer_inner_M3S_nm=base.M3S_nm_inner.median(), median_wafer_edge_M3S_nm=base.M3S_nm_edge.median(),
            median_wafer_edge_prediction_RMSE_nm=prediction.RMSE_nm.median(), median_wafer_edge_prediction_mean_nm=prediction.mean_nm.median()))
ep_product_summary = pd.DataFrame(ep_summary_rows)
display(ep_input_audit)
display(ep_product_summary)
display(ep_prediction_coverage)
