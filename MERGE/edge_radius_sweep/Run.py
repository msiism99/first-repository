# %% 06. 제품별 20조건 실행 / 기존 입력·기준 결과 검증 / 중간 파일 저장
er_wafer_metrics, er_shot_metrics, er_wafer_counts, er_edge_shot_counts, er_shot_counts = [], [], [], [], []
er_wafer_gaps, er_shot_gaps, er_parity, er_audits, er_diagnostic_summaries, er_sources = [], [], [], [], [], []
for product_number, source in enumerate(EP_SOURCES, start=1):
    product, axis = str(source["product"]), str(source["axis"]).lower()
    raw, saved_settings, point_path, settings_path = ep_read_product(source)
    options = ep_restore_settings(saved_settings)
    er_cached_geometry_gopt.cache_clear()
    points, audit = er_prepare_product(raw, product, axis)
    del raw
    metadata = er_shot_metadata(points)
    counts = er_point_counts(points, EP_WAFER_KEYS)
    edge_counts = er_point_counts(points.loc[points._has_edge_shot], EP_WAFER_KEYS)
    shot_counts = er_point_counts(points, EP_SHOT_KEYS).merge(metadata, on=EP_SHOT_KEYS, how="left", validate="1:1")
    wafer_gap = er_mixed_input_gap(points, EP_WAFER_KEYS, axis, skeleton=points)
    shot_gap = er_mixed_input_gap(points, EP_SHOT_KEYS, axis, skeleton=points.loc[points._mixed_shot]).merge(metadata, on=EP_SHOT_KEYS, how="left", validate="1:1")
    for table in [counts, edge_counts, shot_counts]:
        table["axis"] = axis
    er_wafer_counts.append(counts)
    er_edge_shot_counts.append(edge_counts)
    er_shot_counts.append(shot_counts)
    er_wafer_gaps.append(wafer_gap)
    er_shot_gaps.append(shot_gap)
    er_audits.append(audit)
    er_sources.append(dict(product=product, axis=axis, reference_scale=source["reference_scale"], points=str(point_path), settings=str(settings_path), original_settings=saved_settings))
    contexts = er_build_contexts(points, axis, options)
    baseline_prediction = pd.Series(np.nan, index=points.index, dtype=float)
    baseline_diagnostics, baseline_coefficients = [], []
    for context in contexts:
        solution = er_solve_context(context, max(ER_FIT_RADII_MM), scale=None)
        baseline_prediction.loc[context["indices"]] = solution["prediction"]
        baseline_diagnostics.append(solution["diagnostic"])
        baseline_coefficients.append(solution["coefficient"])
    parity = er_check_baseline(points, baseline_prediction, axis, product_number)
    parity["product"], parity["axis"] = product, axis
    er_parity.append(parity)
    pd.DataFrame(baseline_diagnostics).to_parquet(EP_OUTPUT_DIR / "diagnostics" / f"Product_{product_number:02d}_baseline.parquet", index=False)
    if ER_SAVE_COEFFICIENTS:
        pd.DataFrame(baseline_coefficients).to_parquet(EP_OUTPUT_DIR / "coefficients" / f"Product_{product_number:02d}_baseline.parquet", index=False)
    point_cols = EP_SHOT_KEYS + [c for c in ["DieX", "DieY", "photo_transn_seq", "TEST", "GROUP", "coordinate_X", "coordinate_Y", "radius", "measurement_source", "source_mstepseq", "measurement_scale", f"{axis.upper()}_reg_original", f"raw_minus_total_fit_{axis}", f"input100_{axis}"] if c in points]
    baseline_points = points[point_cols].copy()
    baseline_points["analysis_axis"] = axis
    baseline_points[f"CPE_fit_{axis}"] = baseline_prediction
    baseline_points[f"metric_residual_{axis}"] = points[f"input100_{axis}"]-baseline_prediction
    baseline_points.to_parquet(EP_OUTPUT_DIR / "points" / f"Product_{product_number:02d}_baseline_all_points.parquet", index=False)
    frame = points[EP_SHOT_KEYS + ["radius", "_fit_valid", "_mixed_shot", "_has_edge_shot"]].copy()
    affected = [context for context in contexts if context["affected"]]
    print(f"{product} [{axis.upper()}]: wafer {len(counts):,}, 전체 shot {len(contexts):,}, 영향 shot {len(affected):,}; 기준 CPE 검증 완료")
    for radius in ER_FIT_RADII_MM:
        for scale in ER_SCALES:
            prediction = baseline_prediction.copy()
            diagnostics, coefficients = [], []
            for context in affected:
                solution = er_solve_context(context, radius, scale=scale)
                prediction.loc[context["indices"]] = solution["prediction"]
                case = dict(fit_radius_mm=radius, scale=scale, scale_pct=int(round(scale*100)))
                diagnostics.append(dict(solution["diagnostic"], **case))
                coefficients.append(dict(solution["coefficient"], **case))
            frame["_metric_residual"] = points[f"input100_{axis}"]-prediction  # 평가는 항상 배율 적용 전 값
            wafer, shot = er_scenario_metrics(frame, radius, scale)
            wafer["axis"], shot["axis"] = axis, axis
            shot = shot.merge(metadata, on=EP_SHOT_KEYS, how="left", validate="m:1")
            er_wafer_metrics.append(wafer)
            er_shot_metrics.append(shot)
            stem = f"Product_{product_number:02d}_R{radius:g}_S{int(round(scale*100)):03d}"
            wafer.to_parquet(EP_OUTPUT_DIR / "cases" / f"{stem}_Wafer_M3S.parquet", index=False)
            shot.to_parquet(EP_OUTPUT_DIR / "cases" / f"{stem}_Shot_M3S.parquet", index=False)
            diag = pd.DataFrame(diagnostics) if diagnostics else pd.DataFrame(columns=EP_SHOT_KEYS+["axis", "status", "rank_deficient", "few_points_flag", "fit_radius_mm", "scale", "scale_pct"])
            diag.to_parquet(EP_OUTPUT_DIR / "diagnostics" / f"{stem}.parquet", index=False)
            if not diag.empty:
                summary = diag.groupby(["product", "axis", "status", "rank_deficient", "few_points_flag"], observed=True, dropna=False).size().rename("n_shots").reset_index()
                summary["fit_radius_mm"], summary["scale_pct"] = radius, int(round(scale*100))
                er_diagnostic_summaries.append(summary)
            if ER_SAVE_COEFFICIENTS:
                pd.DataFrame(coefficients).to_parquet(EP_OUTPUT_DIR / "coefficients" / f"{stem}.parquet", index=False)
            if ER_SAVE_SCENARIO_POINTS:
                selected = points._has_edge_shot
                trace = points.loc[selected, point_cols].copy()
                trace["analysis_axis"], trace["fit_radius_mm"], trace["edge_scale"] = axis, radius, scale
                trace["used_for_fit"] = points.loc[selected, "_fit_valid"] & points.loc[selected, "radius"].le(radius*1000)
                trace[f"CPE_fit_{axis}"] = prediction.loc[selected]
                trace[f"metric_residual_{axis}"] = frame.loc[selected, "_metric_residual"]
                original = pd.Series(0., index=trace.index)
                outer = trace.radius.gt(EP_INNER_RADIUS_UM) & points.loc[selected, "_fit_valid"]
                if outer.any():
                    original.loc[outer] = trace.loc[outer, f"{axis.upper()}_reg_original"]
                trace[f"training_input_{axis}"] = trace[f"input100_{axis}"] + (scale-1.)*original
                trace[f"training_residual_{axis}"] = (trace[f"training_input_{axis}"]-trace[f"CPE_fit_{axis}"]).where(trace.used_for_fit)
                trace.to_parquet(EP_OUTPUT_DIR / "points" / f"{stem}.parquet", index=False)
            print(f"  fit R<={radius:g}mm / edge {scale:.0%}: inner M3S 계산, CPE 진단 {len(diag):,} shots")
    del points, contexts, frame, baseline_points

er_wafer_metrics = pd.concat(er_wafer_metrics, ignore_index=True)
er_shot_metrics = pd.concat(er_shot_metrics, ignore_index=True)
er_wafer_counts = pd.concat(er_wafer_counts, ignore_index=True)
er_edge_shot_counts = pd.concat(er_edge_shot_counts, ignore_index=True)
er_shot_counts = pd.concat(er_shot_counts, ignore_index=True)
er_wafer_gaps = pd.concat(er_wafer_gaps, ignore_index=True)
er_shot_gaps = pd.concat(er_shot_gaps, ignore_index=True)
er_parity = pd.concat(er_parity, ignore_index=True)
er_input_audit = pd.DataFrame(er_audits)
er_diagnostic_summary = pd.concat(er_diagnostic_summaries, ignore_index=True) if er_diagnostic_summaries else pd.DataFrame(columns=["product", "axis", "status", "rank_deficient", "few_points_flag", "n_shots", "fit_radius_mm", "scale_pct"])
display(er_parity)
display(er_input_audit)
