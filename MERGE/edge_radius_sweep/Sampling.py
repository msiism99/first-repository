# %% 05. 실제 point 비율·동일 mixed shot의 안쪽/edge 입력 M3S 차이
def er_shot_metadata(points):
    cols = [c for c in ["DieX", "DieY", "photo_transn_seq"] if c in points]
    return points.groupby(EP_SHOT_KEYS, observed=True, dropna=False)[cols].first().reset_index() if cols else points[EP_SHOT_KEYS].drop_duplicates()


def er_point_counts(points, keys):
    work = points[keys].copy()
    work["n_total"] = 1
    work["n_inner"] = points.radius.le(EP_INNER_RADIUS_UM).astype(int)
    work["n_edge"] = points.radius.gt(EP_INNER_RADIUS_UM).astype(int)
    work["n_edge_to_lower_radius"] = (points.radius.gt(EP_INNER_RADIUS_UM) & points.radius.le(min(ER_FIT_RADII_MM)*1000)).astype(int)
    work["n_above_lower_radius"] = points.radius.gt(min(ER_FIT_RADII_MM)*1000).astype(int)
    work["n_valid"] = points._fit_valid.astype(int)
    work["n_valid_inner"] = (points._fit_valid & points.region.eq("INNER")).astype(int)
    work["n_valid_edge"] = (points._fit_valid & points.region.eq("EDGE")).astype(int)
    work["n_inner_in_mixed_shots"] = (points._fit_valid & points.region.eq("INNER") & points._mixed_shot).astype(int)
    if "measurement_source" in points:
        work["n_edge_source_points"] = points.measurement_source.eq("oco_edge").astype(int)
    columns = [col for col in work if col not in keys]
    result = work.groupby(keys, observed=True, dropna=False)[columns].sum().reset_index()
    result["edge_point_fraction"] = result.n_edge/result.n_total.replace(0, np.nan)
    result["valid_edge_fraction"] = result.n_valid_edge/result.n_valid.replace(0, np.nan)
    result["inner_mixed_fraction"] = result.n_inner_in_mixed_shots/result.n_valid_inner.replace(0, np.nan)
    result["lower_fit_radius_mm"] = min(ER_FIT_RADII_MM)
    return result


def er_mixed_input_gap(points, keys, axis, skeleton):
    selected = points.loc[points._mixed_shot & points._fit_valid]
    tables = []
    for region in ["INNER", "EDGE"]:
        table = ep_group_stats(selected.loc[selected.region.eq(region)], keys, f"input100_{axis}", skeleton=skeleton)
        table["axis"], table["region"] = axis, region
        tables.append(table)
    result = ep_region_comparison(pd.concat(tables, ignore_index=True), keys)
    result["comparable"] = result.n_valid_inner.gt(EP_STD_DDOF) & result.n_valid_edge.gt(EP_STD_DDOF)
    return result
