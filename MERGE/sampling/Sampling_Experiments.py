# %% 10. 동일한 정답 패턴을 ADI/OCO 좌표에 넣어 복원 성능 비교
def raw_pattern(x, y, components):
    result = np.zeros(len(x), dtype=float)
    for px, py, weight in components:
        result += weight * (np.asarray(x)/half_x)**px * (np.asarray(y)/half_y)**py
    return result

def error_metrics(truth, prediction, prefix):
    error = np.asarray(truth)-np.asarray(prediction)
    return {f"{prefix}_rmse_nm": float(np.sqrt(np.mean(error**2))), f"{prefix}_mean_nm": float(np.mean(error)), f"{prefix}_3sigma_nm": float(3*np.std(error,ddof=1)) if len(error)>1 else np.nan}

x_power_set = set(X_POWERS)
rotated_y_power_set = {(b,a) for a,b in Y_POWERS}
all_powers = [(px,degree-px) for degree in range(8) for px in range(degree,-1,-1)]
patterns = []
for px,py in all_powers:
    member_x, member_y = (px,py) in x_power_set, (px,py) in rotated_y_power_set
    group = "SHARED" if member_x and member_y else "X21_ONLY" if member_x else "ROT_Y17_ONLY" if member_y else "NEITHER"
    patterns.append(dict(pattern=f"x{px}_y{py}", group=group, components=[(px,py,1.)]))
for weight in np.linspace(0,1,11):
    patterns.append(dict(pattern=f"MIX_y3_x4_{weight:.1f}", group="MIXED", components=[(0,3,float(weight)), (4,0,float(1-weight))]))
rng = np.random.default_rng(RANDOM_SEED)
union_powers = sorted(x_power_set | rotated_y_power_set)
for index in range(RANDOM_MIXTURES):
    components = [(px,py,float(rng.normal()/(1+px+py))) for px,py in union_powers]
    patterns.append(dict(pattern=f"RANDOM_MIX_{index:02d}", group="MIXED", components=components))
pattern_rows, response_rows = [], []
for pattern_index, pattern in enumerate(patterns):
    components = pattern["components"]
    raw_grid = raw_pattern(grid_coordinates[:,0],grid_coordinates[:,1],components)
    norm = float(np.sqrt(np.mean(raw_grid**2)))
    if norm <= 0:
        raise ValueError(f"0 패턴: {pattern['pattern']}")
    scale = SYNTHETIC_SIGNAL_RMS_NM/norm
    truth_grid = raw_grid*scale
    pattern_rows.append(dict(pattern=pattern["pattern"], group=pattern["group"], components=json.dumps(components), signal_rms_nm=SYNTHETIC_SIGNAL_RMS_NM))
    for (mode,case), spec in model_cases.items():
        work = primary_frames[mode]
        truth_measured = raw_pattern(work[COORDS[0]].to_numpy(float),work[COORDS[1]].to_numpy(float),components)*scale
        for method in ["OLS_SVD", "GOPT_RIDGE", "NATIVE_SPAN"]:
            if method == "NATIVE_SPAN":
                beta, violations, iterations = native_fixed_lambda(spec["matrix"],truth_measured,spec["evaluation"],spec["names"],spec["lambdas"])
                noise_rms, train_noise_3sigma = np.nan, np.nan
            else:
                beta = spec["operators"][method] @ truth_measured
                violations, iterations = np.nan, 0
                noise_rms = ASSUMED_POINT_NOISE_NM * float(np.sqrt(np.mean(spec["noise_gains"][method]**2)))
                train_noise_3sigma = 3 * ASSUMED_POINT_NOISE_NM * spec["train_noise_gains"][method]
            predicted_measured, predicted_grid = spec["matrix"] @ beta, spec["common_eval"] @ beta
            row = dict(pattern=pattern["pattern"], group=pattern["group"], mode=mode, case=case, method=method, n_points=len(work), rank=spec["rank"], n_parameters=len(spec["names"]), span_violations_after=violations, span_iterations=iterations)
            row.update(error_metrics(truth_measured,predicted_measured,"train"))
            row.update(error_metrics(truth_grid,predicted_grid,"grid"))
            row["shared_hull_rmse_nm"] = float(np.sqrt(np.mean((truth_grid[shared_hull_mask]-predicted_grid[shared_hull_mask])**2))) if shared_hull_mask.any() else np.nan
            row["noise_prediction_rms_nm"] = noise_rms
            row["expected_grid_rmse_nm"] = float(np.sqrt(row["grid_rmse_nm"]**2+noise_rms**2)) if np.isfinite(noise_rms) else np.nan
            row["train_noise_3sigma_nm"] = train_noise_3sigma
            row["expected_train_3sigma_nm"] = float(np.sqrt(row["train_3sigma_nm"]**2+train_noise_3sigma**2)) if np.isfinite(train_noise_3sigma) else np.nan
            response_rows.append(row)
    if (pattern_index+1) % 20 == 0:
        print(f"동일 패턴 재현: {pattern_index+1}/{len(patterns)}")
pattern_catalogue, pattern_response = pd.DataFrame(pattern_rows), pd.DataFrame(response_rows)
save_table("10_PATTERN_CATALOGUE", pattern_catalogue)
save_table("10_PATTERN_RESPONSE", pattern_response)

# %% 11. 우열 역전 패턴 / 대표 shot 실측 확인 / 전용 항의 추가 설명력
interaction_rows, observed_rows, group_gain_rows = [], [], []
for (pattern,method), group in pattern_response.groupby(["pattern","method"], sort=False):
    row = dict(pattern=pattern, group=group["group"].iloc[0], method=method)
    indexed = group.set_index(["mode","case"])
    for mode in MODES:
        for metric in ["grid_rmse_nm","expected_grid_rmse_nm","shared_hull_rmse_nm","train_3sigma_nm","expected_train_3sigma_nm"]:
            row[f"{mode}_delta_{metric}_ROT_minus_X21"] = float(indexed.loc[(mode,NATIVE_CASES[1]),metric]-indexed.loc[(mode,NATIVE_CASES[0]),metric])
    row["matches_observed_noiseless"] = row["ADI_delta_grid_rmse_nm_ROT_minus_X21"] < -1e-6 and row["OCO_delta_grid_rmse_nm_ROT_minus_X21"] > 1e-6
    row["matches_observed_training_3sigma"] = row["ADI_delta_train_3sigma_nm_ROT_minus_X21"] < -1e-6 and row["OCO_delta_train_3sigma_nm_ROT_minus_X21"] > 1e-6
    row["matches_observed_expected_training_3sigma"] = row["ADI_delta_expected_train_3sigma_nm_ROT_minus_X21"] < -1e-6 and row["OCO_delta_expected_train_3sigma_nm_ROT_minus_X21"] > 1e-6
    noisy_values = [row[f"{mode}_delta_expected_grid_rmse_nm_ROT_minus_X21"] for mode in MODES]
    row["noise_metric_available"] = bool(np.isfinite(noisy_values).all())
    row["matches_observed_with_assumed_noise"] = noisy_values[0] < -1e-6 and noisy_values[1] > 1e-6 if row["noise_metric_available"] else False
    interaction_rows.append(row)
sampling_interaction = pd.DataFrame(interaction_rows)
if RUN_OBSERVED_CHECK:
    for mode, work in primary_frames.items():
        if TARGET not in work or not np.isfinite(work[TARGET]).all():
            print(mode, ": CPE 직전 실측 X가 없어 좌표 진단만 수행합니다.")
            continue
        observed = work[TARGET].to_numpy(float)*UM_TO_NM
        common_mask = term_mapping.loc[term_mapping["case"].eq(NATIVE_CASES[0]),"shared_monomial"].to_numpy(bool)
        common_matrix = model_cases[(mode,NATIVE_CASES[0])]["matrix"][:,common_mask]
        common_operator, _, _, common_rank = scaled_ols_operator(common_matrix)
        common_residual = observed-common_matrix @ common_operator @ observed
        for case in NATIVE_CASES:
            spec = model_cases[(mode,case)]
            ols_residual = observed-spec["matrix"] @ spec["operators"]["OLS_SVD"] @ observed
            group_gain_rows.append(dict(mode=mode, case=case, n_points=len(work), common_rank=common_rank, full_rank=spec["rank"], added_fit_dof=spec["rank"]-common_rank, common_sse_nm2=float(common_residual @ common_residual), full_sse_nm2=float(ols_residual @ ols_residual), incremental_sse_reduction_nm2=float(common_residual @ common_residual-ols_residual @ ols_residual)))
            for method in ["OLS_SVD", "GOPT_RIDGE", "NATIVE_SPAN"]:
                if method == "NATIVE_SPAN":
                    beta, violations, iterations = native_fixed_lambda(spec["matrix"],observed,spec["evaluation"],spec["names"],spec["lambdas"])
                else:
                    beta = spec["operators"][method] @ observed
                    violations, iterations = np.nan, 0
                row = dict(mode=mode, case=case, method=method, n_points=len(work), span_violations_after=violations, span_iterations=iterations)
                row.update(error_metrics(observed,spec["matrix"] @ beta,"residual"))
                observed_rows.append(row)
observed_check = pd.DataFrame(observed_rows, columns=["mode","case","method","n_points","span_violations_after","span_iterations","residual_rmse_nm","residual_mean_nm","residual_3sigma_nm"])
observed_group_gain = pd.DataFrame(group_gain_rows, columns=["mode","case","n_points","common_rank","full_rank","added_fit_dof","common_sse_nm2","full_sse_nm2","incremental_sse_reduction_nm2"])
for name, table in [("11_SAMPLING_INTERACTION",sampling_interaction),("11_OBSERVED_CHECK",observed_check),("11_OBSERVED_GROUP_GAIN",observed_group_gain)]:
    save_table(name,table)
matching_examples = sampling_interaction.loc[sampling_interaction.matches_observed_noiseless | sampling_interaction.matches_observed_with_assumed_noise | sampling_interaction.matches_observed_training_3sigma | sampling_interaction.matches_observed_expected_training_3sigma]
display(matching_examples.head(PREVIEW_ROWS))
print("같은 정답 패턴으로 ADI는 Y17 / OCO는 X21 우열을 재현한 예시:", len(matching_examples), "행")
print("예시 개수는 원인 확률이 아닙니다. 실측 원인은 좌표·회귀 조건과 실제 오차 패턴을 함께 확인해야 합니다.")
