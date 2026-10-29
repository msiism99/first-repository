# %% 04. Shot별 CPE38 계산·캐시·기준 결과 재현 검사
er_native_gopt = getattr(ep_gopt_value, "_er_uncached_native", ep_gopt_value)


@lru_cache(maxsize=2048)
def er_cached_geometry_gopt(x_shape, x_bytes, eval_shape, eval_bytes, ridge_bytes, gopt_type, inner_or_partial):
    X = np.frombuffer(x_bytes, dtype=np.float64).reshape(x_shape)
    X_eval = np.frombuffer(eval_bytes, dtype=np.float64).reshape(eval_shape)
    lambdas = np.frombuffer(ridge_bytes, dtype=np.float64)
    return er_native_gopt(X, X_eval, lambdas, gopt_type=gopt_type, inner_or_partial=inner_or_partial)


def er_gopt_value(X_meas, X_eval, lambdas, gopt_type=4, inner_or_partial="partial"):
    X, V, ridge = np.ascontiguousarray(X_meas, dtype=np.float64), np.ascontiguousarray(X_eval, dtype=np.float64), np.ascontiguousarray(lambdas, dtype=np.float64)
    return er_cached_geometry_gopt(X.shape, X.tobytes(), V.shape, V.tobytes(), ridge.tobytes(), gopt_type, inner_or_partial)


er_gopt_value._er_uncached_native = er_native_gopt
ep_gopt_value = er_gopt_value  # 동일 좌표·lambda의 G-opt만 캐시. 계수·span은 측정값별 재계산


def er_prepare_product(raw, product, axis):
    points, audit = ep_prepare_points(raw, product, axes=[axis])
    original = f"{axis.upper()}_reg_original"
    needed = points._fit_valid & points.region.eq("EDGE")
    if needed.any() and (original not in points or not np.isfinite(pd.to_numeric(points.loc[needed, original], errors="coerce")).all()):
        raise ValueError(f"{product}: edge 배율 변경에 필요한 {original}이 없습니다.")
    inner = points.region.eq("INNER") & points._fit_valid
    edge = points.region.eq("EDGE") & points._fit_valid
    groups = [points[k] for k in EP_SHOT_KEYS]
    points["_mixed_shot"] = inner.groupby(groups, observed=True, dropna=False).transform("any") & edge.groupby(groups, observed=True, dropna=False).transform("any")
    return points, audit


def er_matrix_geometry(X):
    if not len(X):
        return dict(rank=0, scaled_condition=np.inf)
    norms = np.linalg.norm(X, axis=0)
    singular = np.linalg.svd(X/np.where(norms > 0, norms, 1.), compute_uv=False)
    rank = int((singular > singular[0]*ER_SVD_RCOND).sum()) if len(singular) else 0
    return dict(rank=rank, scaled_condition=float(singular[0]/singular[-1]) if rank == X.shape[1] else np.inf)


def er_build_contexts(points, axis, options):
    contexts = []
    matrix_index = 0 if axis == "x" else 1
    names = EP_CPE38_KEYS_DX if axis == "x" else EP_CPE38_KEYS_DY
    for key, shot in points.groupby(EP_SHOT_KEYS, observed=True, dropna=False):
        work = shot.loc[shot._fit_valid]
        identity = dict(zip(EP_SHOT_KEYS, key))
        identity.update({col: shot[col].iloc[0] if col in shot else np.nan for col in ["DieX", "DieY", "photo_transn_seq"]})
        context = dict(identity=identity, indices=work.index.to_numpy(), shot_indices=shot.index.to_numpy(), affected=bool(shot._has_edge_shot.any()),
                       radius=work.radius.to_numpy(float), input100=work[f"input100_{axis}"].to_numpy(float), baseline_input=work[f"raw_minus_total_fit_{axis}"].to_numpy(float),
                       X=ep_cpe_38para(work.coordinate_X, work.coordinate_Y)[matrix_index], names=names, axis=axis, options=options, cache={}, masks={})
        original = pd.Series(0., index=work.index)
        outer = work.region.eq("EDGE")
        if outer.any():
            original.loc[outer] = pd.to_numeric(work.loc[outer, f"{axis.upper()}_reg_original"], errors="coerce")
        context["edge_original"] = original.to_numpy(float)
        if len(work):
            if EP_USE_VIRTUAL_CHIP_POINTS:
                vx, vy, source, n_full, n_virtual = ep_get_virtual_points_for_group(work, work.coordinate_X, work.coordinate_Y, fcp_x=key[-2], fcp_y=key[-1], wafer_radius=EP_VIRTUAL_WAFER_RADIUS)
            else:
                vx, vy = ep_build_eval_grid_from_data(work.coordinate_X, work.coordinate_Y, grid_n=options["eval_grid_n"])
                source, n_full, n_virtual = "measured_range_grid", len(vx), len(vx)
            context.update(Xv=ep_cpe_38para(vx, vy)[matrix_index], virtual_source=source, n_virtual=n_virtual, n_virtual_full=n_full)
        for radius in ER_FIT_RADII_MM:
            mask = context["radius"] <= radius*1000
            context["masks"][radius] = (mask, er_matrix_geometry(context["X"][mask]))
        contexts.append(context)
    return contexts


def er_solve_context(context, fit_radius_mm, scale=None):
    baseline = scale is None
    mask = np.ones(len(context["indices"]), dtype=bool) if baseline else context["masks"][fit_radius_mm][0]
    # 같은 shot에서 두 반경의 학습 point가 같으면 배율별 해를 재사용한다.
    cache_key = ("baseline",) if baseline else (mask.tobytes(), float(scale))
    if cache_key in context["cache"]:
        return context["cache"][cache_key]
    if not baseline and mask.all() and not np.any(context["edge_original"]):
        return context["cache"][("baseline",)]
    y = context["baseline_input"] if baseline else context["input100"] + (scale-1.)*context["edge_original"]
    prediction = np.full(len(y), np.nan)
    geometry = er_matrix_geometry(context["X"][mask]) if baseline else context["masks"][fit_radius_mm][1]
    diagnostic = dict(context["identity"], axis=context["axis"], n_eval=len(y), n_train=int(mask.sum()), n_excluded=int((~mask).sum()), n_parameters=len(context["names"]),
        rank=geometry["rank"], scaled_condition=geometry["scaled_condition"], rank_deficient=geometry["rank"] < len(context["names"]),
        few_points_flag=int(mask.sum()) < context["options"]["min_points_guide"], status="no_training_points", method=None, gopt=np.nan, lambda_max=np.nan, span_iter=0, span_violation_count=0)
    coefficient = dict(context["identity"], axis=context["axis"])
    if mask.any():
        options = context["options"]
        try:
            fit = ep_solve_vba_style_ridge_one_axis(X_fit=context["X"][mask], y=y[mask], X_eval=context["Xv"], coeff_names=context["names"], span_limits=ep_get_active_span_limits(options["span_mode"]),
                ridge_regression=options["ridge_regression"], gopt_spec=options["gopt_spec"], gopt_tolerance=options["gopt_tolerance"], minimum_ridge=EP_MINIMUM_RIDGE,
                add_ridge=EP_ADD_RIDGE, max_gopt_return=EP_MAX_GOPT_RETURN, gopt_type=options["gopt_type"], inner_or_partial=ep_determine_inner_or_partial(int(mask.sum()), context["n_virtual"]),
                use_span_box_constraint=options["use_span_box_constraint"], span_tolerance=EP_SPAN_TOLERANCE, cd_tol=EP_CD_TOL, max_span_iter=EP_MAX_SPAN_ITER,
                base_lambda_scale=ep_choose_base_lambda_scale(int(mask.sum())))
            prediction = context["X"] @ fit.beta  # 146~147mm처럼 회귀에서 제외한 point도 같은 모델로 평가
            warnings = []
            if not np.isfinite(prediction).all():
                prediction[:] = np.nan
                warnings.append("nonfinite_prediction")
            if fit.violations:
                warnings.append("span_violations")
            if options["ridge_regression"] and (not np.isfinite(fit.gopt) or fit.gopt > options["gopt_spec"]+options["gopt_tolerance"]):
                warnings.append("gopt_not_met")
            diagnostic.update(status="|".join(warnings) if warnings else "ok", method=fit.method, gopt=fit.gopt, lambda_max=float(np.max(fit.lambdas)),
                              span_iter=fit.span_iter, span_violation_count=len(fit.violations), virtual_source=context["virtual_source"], n_virtual=context["n_virtual"])
            for name, value, ridge in zip(context["names"], fit.beta, fit.lambdas):
                coefficient[name], coefficient[f"lambda_{name}"] = float(value), float(ridge)
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
            diagnostic.update(status="solver_error", error_message=str(exc))
    solution = dict(prediction=prediction, diagnostic=diagnostic, coefficient=coefficient)
    context["cache"][cache_key] = solution
    return solution


def er_check_baseline(points, prediction, axis, product_number):
    rows = []
    for column, calculated in [(f"CPE_fit_{axis}", prediction), (f"real_residual_{axis}", points[f"raw_minus_total_fit_{axis}"]-prediction)]:
        if column not in points:
            rows.append(dict(column=column, check_status="not_in_input", passed=True, n_checked=0, max_abs_error_nm=np.nan))
            continue
        old, new = pd.to_numeric(points[column], errors="coerce").to_numpy(float), calculated.to_numpy(float)
        valid = np.isfinite(old) & np.isfinite(new)
        passed = np.allclose(old, new, rtol=1e-7, atol=ER_BASELINE_ATOL_UM, equal_nan=True)
        rows.append(dict(column=column, check_status="checked", passed=bool(passed), n_checked=int(valid.sum()), max_abs_error_nm=float(np.max(np.abs(old[valid]-new[valid]))*1000) if valid.any() else np.nan))
    table = pd.DataFrame(rows)
    if not table.passed.all():
        path = EP_OUTPUT_DIR / f"Baseline_Parity_Failed_Product_{product_number:02d}.xlsx"
        table.to_excel(path, index=False)
        raise ValueError(f"저장된 27번 CPE와 기준 재계산이 다릅니다. 같은 실행의 27번/28번 설정인지, 비선택 방향 결측 또는 147mm 밖 회귀점이 있었는지 확인하세요: {path}")
    return table


def er_metric_table(frame, keys, skeleton=None):
    expected = frame.loc[frame._fit_valid]
    result = ep_group_stats(expected, keys, "_metric_residual", skeleton=frame if skeleton is None else skeleton)
    result = result.rename(columns={"n_points": "n_expected", "n_valid": "n_predicted"})
    result["coverage_fraction"] = result.n_predicted/result.n_expected.replace(0, np.nan)
    incomplete = result.n_predicted.lt(result.n_expected)
    columns = [c for c in EP_STAT_COLUMNS if c not in ["n_points", "n_valid"]]
    result.loc[incomplete, columns] = np.nan  # 예측 누락을 제거해 통계가 좋아 보이는 것을 방지
    result["metric_status"] = np.where(result.n_expected.eq(0), "no_valid_input", np.where(incomplete, "incomplete_prediction", np.where(result.n_predicted.le(EP_STD_DDOF), "too_few_points", "ok")))
    return result


def er_scenario_metrics(frame, radius, scale):
    wafer_tables, shot_tables = [], []
    regions = {"R_LE_144MM": frame.radius.le(EP_INNER_RADIUS_UM), "ALL_R_LE_147MM": pd.Series(True, index=frame.index)}
    for scope, selected in [("ALL_SHOTS", pd.Series(True, index=frame.index)), ("MIXED_SHOTS", frame._mixed_shot)]:
        for region, mask in regions.items():
            table = er_metric_table(frame.loc[selected & mask], EP_WAFER_KEYS, skeleton=frame)
            table["scope"], table["region"] = scope, region
            wafer_tables.append(table)
    edge_shots = frame.loc[frame._has_edge_shot]
    for region, mask in [("R_LE_144MM", edge_shots.radius.le(EP_INNER_RADIUS_UM)), ("ALL_R_LE_147MM", pd.Series(True, index=edge_shots.index))]:
        table = er_metric_table(edge_shots.loc[mask], EP_SHOT_KEYS, skeleton=edge_shots)
        table["region"] = region
        shot_tables.append(table)
    wafer, shot = pd.concat(wafer_tables, ignore_index=True), pd.concat(shot_tables, ignore_index=True)
    for table in [wafer, shot]:
        table["fit_radius_mm"], table["scale"], table["scale_pct"] = radius, scale, int(round(scale*100))
    return wafer, shot
