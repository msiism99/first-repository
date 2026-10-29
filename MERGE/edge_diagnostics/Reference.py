# %% 04. 안쪽 point만으로 CPE38 추정 후 edge 위치 예측
def ep_geometry(X, X_edge):
    norms = np.linalg.norm(X, axis=0)
    safe = np.where(norms > 0, norms, 1.)
    scaled = X / safe
    singular = np.linalg.svd(scaled, compute_uv=False)
    cutoff = singular[0] * EP_SVD_RCOND if len(singular) else 0.
    rank = int((singular > cutoff).sum())
    full_rank = rank == X.shape[1]
    condition = float(singular[0] / singular[-1]) if full_rank else np.inf
    transfer = (X_edge / safe) @ np.linalg.pinv(scaled, rcond=EP_SVD_RCOND)
    gains = np.linalg.norm(transfer, axis=1)
    return dict(rank=rank, scaled_condition=condition, ols_edge_noise_gain_max=float(gains.max()), ols_edge_noise_gain_rms=float(np.sqrt(np.mean(gains**2))))


def ep_ridge_edge_gain(X, X_edge, lambdas):
    # Box 제약 활성화 전 선형 ridge의 noise gain. CD 제약이 작동하면 근사 진단값이다.
    norms = np.linalg.norm(X, axis=0)
    safe = np.where(norms > 0, norms, 1.)
    augmented = np.vstack([X / safe, np.diag(np.sqrt(np.maximum(lambdas, 0.)) / safe)])
    target = np.vstack([np.eye(len(X)), np.zeros((X.shape[1], len(X)))])
    transfer = (X_edge / safe) @ np.linalg.lstsq(augmented, target, rcond=EP_SVD_RCOND)[0]
    gains = np.linalg.norm(transfer, axis=1)
    return float(gains.max()), float(np.sqrt(np.mean(gains**2)))


def ep_fit_inner_reference(points, options, axes=None):
    axes = EP_AXES if axes is None else axes
    out = points.copy()
    for axis in axes:
        out[f"inner_prediction_{axis}"], out[f"reference_residual_{axis}"], out[f"edge_deviation_{axis}"] = np.nan, np.nan, np.nan
        out[f"reference_eligible_{axis}"] = False
        out[f"reference_status_{axis}"] = "no_edge"
    rows, coefficients = [], []
    spans = ep_get_active_span_limits(options["span_mode"])
    for key, shot in out.loc[out._has_edge_shot].groupby(EP_SHOT_KEYS, observed=True, dropna=False):
        valid = shot.loc[shot._fit_valid]
        inner, edge = valid.loc[valid.region.eq("INNER")], valid.loc[valid.region.eq("EDGE")]
        identity = dict(zip(EP_SHOT_KEYS, key))
        identity.update({col: shot[col].iloc[0] if col in shot else np.nan for col in ["DieX", "DieY", "photo_transn_seq"]})
        for axis_index, axis in enumerate(["x", "y"]):
            if axis not in axes:
                continue
            names = EP_CPE38_KEYS_DX if axis == "x" else EP_CPE38_KEYS_DY
            row = dict(identity, axis=axis, n_inner=len(inner), n_edge=len(edge), n_parameters=len(names), eligible=False, status="not_evaluated",
                       rank=np.nan, scaled_condition=np.nan, ols_edge_noise_gain_max=np.nan, ridge_edge_noise_gain_max=np.nan, ridge_edge_noise_gain_rms=np.nan,
                       method=None, gopt=np.nan, lambda_max=np.nan, span_violation_count=np.nan, span_iter=np.nan, inner_RMSE_nm=np.nan, candidate_edge_RMSE_nm=np.nan)
            reasons = []
            if not len(edge):
                reasons.append("no_valid_edge_points")
            if len(inner) < len(names) + EP_MIN_EXTRA_INNER_POINTS:
                reasons.append("too_few_inner_points")
            if reasons:
                row["status"] = "|".join(reasons)
                out.loc[shot.index, f"reference_status_{axis}"] = row["status"]
                rows.append(row)
                continue
            X = ep_cpe_38para(inner.coordinate_X, inner.coordinate_Y)[axis_index]
            Xe = ep_cpe_38para(edge.coordinate_X, edge.coordinate_Y)[axis_index]
            geometry = ep_geometry(X, Xe)
            row.update(geometry)
            if geometry["rank"] < len(names):
                row["status"] = "inner_rank_deficient"
                out.loc[shot.index, f"reference_status_{axis}"] = row["status"]
                rows.append(row)
                continue
            if geometry["scaled_condition"] > EP_MAX_SCALED_CONDITION:
                reasons.append("inner_condition_high")
            if EP_USE_VIRTUAL_CHIP_POINTS:
                vx, vy, virtual_source, n_full, n_virtual = ep_get_virtual_points_for_group(valid, valid.coordinate_X, valid.coordinate_Y, fcp_x=key[-2], fcp_y=key[-1], wafer_radius=EP_VIRTUAL_WAFER_RADIUS)
            else:
                vx, vy = ep_build_eval_grid_from_data(valid.coordinate_X, valid.coordinate_Y, grid_n=options["eval_grid_n"])
                virtual_source, n_full, n_virtual = "measured_range_grid", len(vx), len(vx)
            Xv = ep_cpe_38para(vx, vy)[axis_index]
            try:
                fit = ep_solve_vba_style_ridge_one_axis(X_fit=X, y=inner[f"input100_{axis}"].to_numpy(float), X_eval=Xv, coeff_names=names, span_limits=spans,
                    ridge_regression=options["ridge_regression"], gopt_spec=options["gopt_spec"], gopt_tolerance=options["gopt_tolerance"], minimum_ridge=EP_MINIMUM_RIDGE,
                    add_ridge=EP_ADD_RIDGE, max_gopt_return=EP_MAX_GOPT_RETURN, gopt_type=options["gopt_type"], inner_or_partial=ep_determine_inner_or_partial(len(inner), n_virtual),
                    use_span_box_constraint=options["use_span_box_constraint"], span_tolerance=EP_SPAN_TOLERANCE, cd_tol=EP_CD_TOL, max_span_iter=EP_MAX_SPAN_ITER,
                    base_lambda_scale=ep_choose_base_lambda_scale(len(inner)))
                gain_max, gain_rms = ep_ridge_edge_gain(X, Xe, fit.lambdas)
                Xall = ep_cpe_38para(valid.coordinate_X, valid.coordinate_Y)[axis_index]
                prediction = Xall @ fit.beta
                errors = valid[f"input100_{axis}"].to_numpy(float) - prediction
                edge_error = errors[valid.region.eq("EDGE").to_numpy()]
                if not np.isfinite(prediction).all() or not np.isfinite(gain_max):
                    reasons.append("nonfinite_prediction")
                if gain_max > EP_MAX_EDGE_NOISE_GAIN:
                    reasons.append("edge_prediction_noise_high")
                if fit.violations:
                    reasons.append("remaining_span_violations")
                if options["ridge_regression"] and (not np.isfinite(fit.gopt) or fit.gopt > options["gopt_spec"] + options["gopt_tolerance"]):
                    reasons.append("gopt_not_met")
                row.update(ridge_edge_noise_gain_max=gain_max, ridge_edge_noise_gain_rms=gain_rms, method=fit.method, gopt=fit.gopt, lambda_max=float(np.max(fit.lambdas)),
                           span_violation_count=len(fit.violations), span_iter=fit.span_iter, virtual_source=virtual_source, n_virtual=n_virtual, n_virtual_full=n_full,
                           inner_RMSE_nm=float(np.sqrt(np.mean((inner[f"input100_{axis}"].to_numpy(float)-fit.pred)**2))*1000), candidate_edge_RMSE_nm=float(np.sqrt(np.mean(edge_error**2))*1000))
                row["eligible"], row["status"] = not reasons, "|".join(reasons) if reasons else "ok"
                out.loc[valid.index, f"inner_prediction_{axis}"] = prediction
                out.loc[valid.index, f"reference_residual_{axis}"] = errors
                out.loc[shot.index, f"reference_eligible_{axis}"] = row["eligible"]
                if row["eligible"]:
                    out.loc[edge.index, f"edge_deviation_{axis}"] = edge_error
                coefficient = dict(identity, axis=axis)
                for name, beta, ridge in zip(names, fit.beta, fit.lambdas):
                    coefficient[name], coefficient[f"lambda_{name}"] = float(beta), float(ridge)
                coefficients.append(coefficient)
            except (np.linalg.LinAlgError, ValueError, FloatingPointError) as exc:
                row["status"], row["error_message"] = "solver_error", str(exc)
            out.loc[shot.index, f"reference_status_{axis}"] = row["status"]
            rows.append(row)
    columns = EP_SHOT_KEYS + ["axis", "n_inner", "n_edge", "n_parameters", "eligible", "status", "rank", "scaled_condition", "ridge_edge_noise_gain_max", "candidate_edge_RMSE_nm"]
    diagnostics = pd.DataFrame(rows) if rows else pd.DataFrame(columns=columns)
    coeff = pd.DataFrame(coefficients) if coefficients else pd.DataFrame(columns=EP_SHOT_KEYS + ["axis"])
    return out, diagnostics, coeff
