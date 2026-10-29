# %% 01. 통계·제품별 CPE 설정 복원 함수
EP_STAT_COLUMNS = ["n_points", "n_valid", "mean_nm", "abs_mean_nm", "sigma_nm", "three_sigma_nm", "M3S_nm", "RMSE_nm", "p95_abs_nm"]


def ep_group_stats(frame, keys, value_col, skeleton=None):
    result = frame[keys].drop_duplicates().copy() if skeleton is None else skeleton[keys].drop_duplicates().copy()
    if frame.empty:
        for col in EP_STAT_COLUMNS:
            result[col] = 0 if col in ["n_points", "n_valid"] else np.nan
        return result
    work = frame[keys].copy()
    values = pd.to_numeric(frame[value_col], errors="coerce") * 1000
    work["_v"] = values.where(np.isfinite(values))
    work["_v2"], work["_abs"] = work._v ** 2, work._v.abs()
    groups = work.groupby(keys, observed=True, dropna=False)
    stats = groups._v.agg(n_points="size", n_valid="count", mean_nm="mean")
    stats["sigma_nm"] = groups._v.std(ddof=EP_STD_DDOF)
    stats["RMSE_nm"] = np.sqrt(groups._v2.mean())
    stats["p95_abs_nm"] = groups._abs.quantile(.95)
    result = result.merge(stats.reset_index(), on=keys, how="left", validate="1:1")
    result[["n_points", "n_valid"]] = result[["n_points", "n_valid"]].fillna(0).astype(int)
    result["abs_mean_nm"] = result.mean_nm.abs()
    result["three_sigma_nm"] = 3 * result.sigma_nm
    result["M3S_nm"] = result.abs_mean_nm + result.three_sigma_nm
    return result


def ep_input_stats(points, keys, axes=None):
    axes = EP_AXES if axes is None else axes
    tables = []
    for axis in axes:
        for region in ["INNER", "EDGE"]:
            table = ep_group_stats(points.loc[points.region.eq(region)], keys, f"input100_{axis}", skeleton=points)
            table["axis"], table["region"] = axis, region
            tables.append(table)
    return pd.concat(tables, ignore_index=True)


def ep_region_comparison(stats, keys):
    columns = keys + ["axis"]
    inner = stats.loc[stats.region.eq("INNER")].drop(columns="region")
    edge = stats.loc[stats.region.eq("EDGE")].drop(columns="region")
    result = inner.merge(edge, on=columns, suffixes=("_inner", "_edge"), validate="1:1")
    result["delta_M3S_edge_minus_inner_nm"] = result.M3S_nm_edge - result.M3S_nm_inner
    result["ratio_3sigma_edge_to_inner"] = result.three_sigma_nm_edge / result.three_sigma_nm_inner.replace(0, np.nan)
    return result


def ep_restore_settings(settings):
    required = ["cpe_options", "use_virtual_chip_points", "virtual_wafer_radius_um", "span_tolerance", "minimum_ridge", "add_ridge", "max_gopt_return", "max_span_iter", "cd_tol", "ridge_valves", "active_span_limits"]
    missing = [key for key in required if key not in settings]
    if missing:
        raise ValueError(f"28번 실행 설정에 필수 항목이 없습니다: {missing}")
    if settings.get("kmrc_definition") != "OCO_E1_RAW_MINUS_ADI_RAW":
        raise ValueError("현재 K-MRC(E1 raw−ADI raw) 방식의 27·28번 저장 자료가 필요합니다. 이전 E2 자체 regression 자료와 섞을 수 없습니다.")
    options = copy.deepcopy(settings["cpe_options"])
    globals_map = {"use_virtual_chip_points": "EP_USE_VIRTUAL_CHIP_POINTS", "virtual_wafer_radius_um": "EP_VIRTUAL_WAFER_RADIUS", "span_tolerance": "EP_SPAN_TOLERANCE",
                   "minimum_ridge": "EP_MINIMUM_RIDGE", "add_ridge": "EP_ADD_RIDGE", "max_gopt_return": "EP_MAX_GOPT_RETURN", "max_span_iter": "EP_MAX_SPAN_ITER", "cd_tol": "EP_CD_TOL"}
    for key, variable in globals_map.items():
        globals()[variable] = settings[key]
    globals()["EP_RIDGE_VALVE_HYPER"] = copy.deepcopy(settings["ridge_valves"])
    span_variables = {"OVO3_38P_HARDLIMIT": "EP_RK_SPAN_LIMITS_OVO3_38P_HARDLIMIT", "OVO3_38P_F2F": "EP_RK_SPAN_LIMITS_OVO3_38P_F2F"}
    if options["span_mode"] not in span_variables:
        raise ValueError(f"지원하지 않는 span_mode: {options['span_mode']}")
    globals()[span_variables[options["span_mode"]]] = copy.deepcopy(settings["active_span_limits"])
    return options
