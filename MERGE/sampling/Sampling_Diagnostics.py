# %% 08. 공통 평가 영역 / 물리적 X 기준 행렬 / SVD helper
def physical_design(x, y, case):
    if case == NATIVE_CASES[0]:
        return cpe_38para(x,y)[0]
    u, v = rotate_local(x,y)
    return ROTATION_SIGN * cpe_38para(u,v)[1]

def scaled_ols_operator(matrix):
    norms = np.linalg.norm(matrix, axis=0)
    norms = np.where(norms > 0, norms, 1.)
    scaled = matrix / norms
    u, singular, vt = np.linalg.svd(scaled, full_matrices=False)
    keep = singular > (singular[0] * SVD_RCOND if len(singular) else 0)
    inverse = np.zeros_like(singular)
    inverse[keep] = 1/singular[keep]
    operator = ((vt.T * inverse) @ u.T) / norms[:,None]
    rank = int(keep.sum())
    return operator, scaled, singular, rank

def hull_metrics(coordinates, grid):
    unique = np.unique(coordinates, axis=0)
    try:
        hull = ConvexHull(unique)
        inside = Delaunay(unique).find_simplex(grid) >= 0
        area = float(hull.volume)
    except (QhullError, ValueError):
        area, inside = 0., np.zeros(len(grid), dtype=bool)
    return area, inside

def native_fixed_lambda(matrix, values_nm, evaluation, names, lambdas):
    beta, _ = ridge_predict(matrix, values_nm/UM_TO_NM, lambdas)
    spans = calc_contribution_spans(evaluation, beta, names)
    violations = find_span_violations(spans, NATIVE_SPAN_LIMITS, tolerance=SPAN_TOLERANCE)
    iterations = 0
    if RIDGE_REGRESSION and USE_SPAN_BOX_CONSTRAINT and violations:
        lower, upper = build_beta_bounds_from_span(evaluation, names, NATIVE_SPAN_LIMITS)
        beta, _, iterations, _ = projected_coordinate_descent_ridge(matrix, values_nm/UM_TO_NM, lambdas, beta_init=beta, lower=lower, upper=upper, tol=CD_TOL, max_iter=MAX_SPAN_ITER)
        spans = calc_contribution_spans(evaluation, beta, names)
        violations = find_span_violations(spans, NATIVE_SPAN_LIMITS, tolerance=SPAN_TOLERANCE)
    return beta*UM_TO_NM, len(violations), iterations

pitch_rows = []
for mode, work in primary_frames.items():
    for axis, coordinate in [("X", "coordinate_X"), ("Y", "coordinate_Y")]:
        col = f"STEP_PITCH_{axis}"
        values = work[col].dropna().unique() if col in work else np.array([])
        values = values[np.isfinite(values) & (values > 0)]
        if len(values) > 1 and not np.allclose(values, values[0]):
            raise ValueError(f"{mode}: 대표 shot의 {col} 값이 일관되지 않습니다.")
        pitch_rows.append(dict(mode=mode, axis=axis, pitch_um=float(values[0]) if len(values) else np.nan, observed_half_extent_um=float(work[coordinate].abs().max())))
pitch_table = pd.DataFrame(pitch_rows)
if COMMON_SHOT_SIZE_UM is not None:
    half_x, half_y = np.asarray(COMMON_SHOT_SIZE_UM, dtype=float)/2
else:
    half_x, half_y = [max(float(pitch_table.loc[pitch_table.axis.eq(axis),"observed_half_extent_um"].max()), float(pitch_table.loc[pitch_table.axis.eq(axis),"pitch_um"].fillna(0).max())/2) for axis in ["X", "Y"]]
if not np.isfinite([half_x,half_y]).all() or min(half_x,half_y) <= 0:
    raise ValueError("공통 평가 영역을 만들 수 없습니다. COMMON_SHOT_SIZE_UM을 지정하세요.")
xx, yy = np.meshgrid(np.linspace(-half_x,half_x,COMMON_GRID_N), np.linspace(-half_y,half_y,COMMON_GRID_N))
grid_coordinates = np.column_stack([xx.ravel(), yy.ravel()])
grid_table = pd.DataFrame(grid_coordinates, columns=COORDS)
inside_hulls = {}
for mode, work in primary_frames.items():
    _, inside_hulls[mode] = hull_metrics(work[COORDS].to_numpy(float), grid_coordinates)
    grid_table[f"inside_{mode}_hull"] = inside_hulls[mode]
shared_hull_mask = inside_hulls["ADI"] & inside_hulls["OCO"]
grid_table["inside_shared_hull"] = shared_hull_mask
save_table("08_COMMON_GRID", grid_table)
save_table("08_PITCH_AND_EXTENT", pitch_table)
print("공통 평가 크기 [um]:", (2*half_x,2*half_y), "; 공통 convex hull 내부 grid:", int(shared_hull_mask.sum()), "/", len(grid_table))

# %% 09. Sampling별 항 식별성 / alias / noise 전달 계산
geometry_rows, term_rows, alias_rows, model_cases = [], [], [], {}
for mode, work in primary_frames.items():
    coordinates = work[COORDS].to_numpy(float)
    rx, ry = coordinates.T
    fcp_x, fcp_y = (float(work[col].iloc[0]) for col in ["fcp_x", "fcp_y"])
    if USE_VIRTUAL_CHIP_POINTS:
        gx, gy, virtual_source, n_virtual_full, n_virtual = get_virtual_points_for_group(work, rx, ry, fcp_x, fcp_y, wafer_radius=VIRTUAL_WAFER_RADIUS)
    else:
        gx, gy = build_eval_grid_from_data(rx, ry, grid_n=CPE_EVAL_GRID_N)
        virtual_source, n_virtual_full, n_virtual = "measured_range_grid", len(gx), len(gx)
    area, _ = hull_metrics(coordinates, grid_coordinates)
    for case in NATIVE_CASES:
        names = CPE38_KEYS_DX if case == NATIVE_CASES[0] else CPE38_KEYS_DY
        matrix = physical_design(rx, ry, case)
        evaluation = physical_design(gx, gy, case)
        common_eval = physical_design(grid_coordinates[:,0], grid_coordinates[:,1], case)
        ols, scaled, singular, rank = scaled_ols_operator(matrix)
        tuned = solve_case(matrix, np.zeros(len(matrix)), evaluation, names, n_virtual)
        normal = matrix.T @ matrix + np.diag(tuned.lambdas)
        try:
            ridge = np.linalg.solve(normal, matrix.T)
        except np.linalg.LinAlgError:
            ridge = np.linalg.pinv(normal) @ matrix.T
        operators = {"OLS_SVD": ols, "GOPT_RIDGE": ridge}
        noise_gains, train_noise_gains = {}, {}
        for method, operator in operators.items():
            hat_grid = common_eval @ operator
            noise_gains[method] = np.sqrt(np.sum(hat_grid**2, axis=1))
            residual_operator = np.eye(len(matrix)) - matrix @ operator
            centered_trace = float(np.sum(residual_operator**2) - np.sum(residual_operator.sum(axis=0)**2)/len(matrix))
            train_noise_gains[method] = np.sqrt(max(centered_trace,0.)/(len(matrix)-1)) if len(matrix)>1 else np.nan
        cosine = scaled.T @ scaled
        metadata = term_mapping.loc[term_mapping["case"].eq(case)].reset_index(drop=True)
        for j, name in enumerate(names):
            other = np.delete(scaled, j, axis=1)
            other_operator = scaled_ols_operator(other)[0]
            residual = scaled[:,j] - other @ other_operator @ scaled[:,j]
            denominator = np.linalg.norm(scaled[:,j])
            fraction = float(np.linalg.norm(residual)/denominator) if denominator > 0 else 0.
            row = metadata.iloc[j]
            term_rows.append(dict(mode=mode, case=case, term=name, power_x=int(row.power_x), power_y=int(row.power_y), monomial=f"x^{int(row.power_x)} y^{int(row.power_y)}", independent_fraction=min(fraction,1.), separable_from_other_terms=fraction > 1e-6, observed_column_norm=float(np.linalg.norm(matrix[:,j]))))
            for k in range(j+1,len(names)):
                if abs(cosine[j,k]) >= ALIAS_COSINE_THRESHOLD:
                    alias_rows.append(dict(mode=mode, case=case, term_a=name, term_b=names[k], cosine=float(cosine[j,k]), abs_cosine=float(abs(cosine[j,k]))))
        geometry_rows.append(dict(
            mode=mode, case=case, n_points=len(work), n_unique_points=len(np.unique(coordinates,axis=0)), n_unique_x=work[COORDS[0]].nunique(), n_unique_y=work[COORDS[1]].nunique(),
            span_x_um=float(np.ptp(rx)), span_y_um=float(np.ptp(ry)), convex_hull_area_um2=area, hull_area_fraction=area/(4*half_x*half_y),
            n_parameters=len(names), rank=rank, coefficient_nullity=len(names)-rank, full_column_rank=rank == len(names),
            scaled_condition=float(singular[0]/singular[-1]) if rank == len(names) else np.inf,
            identifiable_subspace_condition=float(singular[0]/singular[rank-1]) if rank else np.inf, normal_equation_condition=float(np.linalg.cond(normal)),
            n_virtual=n_virtual, n_virtual_full=n_virtual_full, virtual_source=virtual_source, gopt=float(tuned.gopt), lambda_max=float(np.max(tuned.lambdas)),
            OLS_noise_gain_rms=float(np.sqrt(np.mean(noise_gains["OLS_SVD"]**2))), ridge_noise_gain_rms=float(np.sqrt(np.mean(noise_gains["GOPT_RIDGE"]**2))),
            ridge_noise_gain_max=float(np.max(noise_gains["GOPT_RIDGE"])), ridge_train_noise_std_gain=float(train_noise_gains["GOPT_RIDGE"]), source_x_values_available=TARGET in work,
        ))
        model_cases[(mode,case)] = dict(matrix=matrix, evaluation=evaluation, common_eval=common_eval, names=names, operators=operators, lambdas=tuned.lambdas, noise_gains=noise_gains, train_noise_gains=train_noise_gains, cosine=cosine, rank=rank, gopt=tuned.gopt)
sampling_summary, term_identifiability = pd.DataFrame(geometry_rows), pd.DataFrame(term_rows)
alias_pairs = pd.DataFrame(alias_rows, columns=["mode", "case", "term_a", "term_b", "cosine", "abs_cosine"])
for name, table in [("09_SAMPLING_SUMMARY", sampling_summary), ("09_TERM_IDENTIFIABILITY", term_identifiability), ("09_ALIAS_PAIRS", alias_pairs)]:
    save_table(name, table)
display(sampling_summary[["mode","case","n_points","rank","n_parameters","coefficient_nullity","lambda_max","ridge_noise_gain_rms"]])
