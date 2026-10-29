# %% 07. 같은 wafer 집합의 제품 곡선 / 반경 차이 / 최적 배율 / 기존 최적값 대비 열화
er_cohort_keys = EP_WAFER_KEYS + ["axis", "scope", "region"]
er_case_count = len(ER_FIT_RADII_MM)*len(ER_SCALES)
er_completeness = er_wafer_metrics.groupby(er_cohort_keys, observed=True, dropna=False).M3S_nm.count().rename("n_finite_cases").reset_index()
er_completeness["complete_all_cases"] = er_completeness.n_finite_cases.eq(er_case_count)
er_wafer_metrics = er_wafer_metrics.merge(er_completeness, on=er_cohort_keys, how="left", validate="m:1")
curve_keys = ["product", "axis", "scope", "region", "fit_radius_mm", "scale", "scale_pct"]
er_product_curves = er_wafer_metrics[curve_keys].drop_duplicates()
er_curve_population = er_wafer_metrics.groupby(curve_keys, observed=True, dropna=False).size().rename("n_wafers_total").reset_index()
complete = er_wafer_metrics.loc[er_wafer_metrics.complete_all_cases]
if not complete.empty:
    grouped = complete.groupby(curve_keys, observed=True, dropna=False).M3S_nm
    summary = grouped.agg(n_wafers_used="count", mean_M3S_nm="mean", median_M3S_nm="median", min_M3S_nm="min", max_M3S_nm="max").reset_index()
    er_product_curves = er_product_curves.merge(summary, on=curve_keys, how="left", validate="1:1")
else:
    er_product_curves = er_product_curves.assign(n_wafers_used=0, mean_M3S_nm=np.nan, median_M3S_nm=np.nan, min_M3S_nm=np.nan, max_M3S_nm=np.nan)
er_product_curves = er_product_curves.merge(er_curve_population, on=curve_keys, how="left", validate="1:1")
er_product_curves["n_wafers_used"] = er_product_curves.n_wafers_used.fillna(0).astype(int)

delta_keys = er_cohort_keys + ["scale", "scale_pct"]
columns = delta_keys + ["M3S_nm", "abs_mean_nm", "three_sigma_nm", "n_expected", "n_predicted", "metric_status"]
small = er_wafer_metrics.loc[er_wafer_metrics.fit_radius_mm.eq(min(ER_FIT_RADII_MM)), columns]
large = er_wafer_metrics.loc[er_wafer_metrics.fit_radius_mm.eq(max(ER_FIT_RADII_MM)), columns]
er_radius_delta = small.merge(large, on=delta_keys, suffixes=("_smaller_radius", "_larger_radius"), validate="1:1")
for col in ["M3S_nm", "abs_mean_nm", "three_sigma_nm"]:
    er_radius_delta[f"delta_{col}"] = er_radius_delta[f"{col}_smaller_radius"]-er_radius_delta[f"{col}_larger_radius"]
er_radius_delta["smaller_fit_radius_mm"], er_radius_delta["larger_fit_radius_mm"] = min(ER_FIT_RADII_MM), max(ER_FIT_RADII_MM)

best_keys = er_cohort_keys + ["fit_radius_mm"]
er_best_scales = er_wafer_metrics[best_keys].drop_duplicates()
counts = er_wafer_metrics.groupby(best_keys, observed=True, dropna=False).M3S_nm.count().rename("n_finite_scales").reset_index()
er_best_scales = er_best_scales.merge(counts, on=best_keys, validate="1:1")
valid = er_wafer_metrics.merge(counts, on=best_keys, validate="m:1")
valid = valid.loc[valid.n_finite_scales.eq(len(ER_SCALES))]
if not valid.empty:
    indices = valid.groupby(best_keys, observed=True, dropna=False).M3S_nm.idxmin()
    best = valid.loc[indices, best_keys+["scale_pct", "M3S_nm"]].rename(columns={"scale_pct":"best_scale_pct", "M3S_nm":"best_M3S_nm"})
    er_best_scales = er_best_scales.merge(best, on=best_keys, how="left", validate="1:1")
else:
    er_best_scales = er_best_scales.assign(best_scale_pct=np.nan, best_M3S_nm=np.nan)
hundred = er_wafer_metrics.loc[er_wafer_metrics.scale.eq(1.), best_keys+["M3S_nm"]].rename(columns={"M3S_nm":"M3S_100pct_nm"})
er_best_scales = er_best_scales.merge(hundred, on=best_keys, how="left", validate="1:1")
er_best_scales["loss_100_minus_wafer_best_nm"] = er_best_scales.M3S_100pct_nm-er_best_scales.best_M3S_nm

er_reference_scales = {str(s["product"]):float(s["reference_scale"]) for s in EP_SOURCES}
reference_rows = er_wafer_metrics.loc[np.isclose(er_wafer_metrics.scale, er_wafer_metrics["product"].map(er_reference_scales))]
reference = reference_rows[best_keys+["M3S_nm", "abs_mean_nm", "three_sigma_nm"]].rename(columns={"M3S_nm":"M3S_reference_nm", "abs_mean_nm":"abs_mean_reference_nm", "three_sigma_nm":"three_sigma_reference_nm"})
hundred = er_wafer_metrics.loc[er_wafer_metrics.scale.eq(1.), best_keys+["M3S_nm", "abs_mean_nm", "three_sigma_nm"]].rename(columns={"M3S_nm":"M3S_100pct_nm", "abs_mean_nm":"abs_mean_100pct_nm", "three_sigma_nm":"three_sigma_100pct_nm"})
er_reference_loss = reference.merge(hundred, on=best_keys, validate="1:1")
er_reference_loss["reference_scale_pct"] = er_reference_loss["product"].map(er_reference_scales)*100
er_reference_loss["loss_100_minus_reference_nm"] = er_reference_loss.M3S_100pct_nm-er_reference_loss.M3S_reference_nm
er_reference_loss["delta_abs_mean_nm"] = er_reference_loss.abs_mean_100pct_nm-er_reference_loss.abs_mean_reference_nm
er_reference_loss["delta_three_sigma_nm"] = er_reference_loss.three_sigma_100pct_nm-er_reference_loss.three_sigma_reference_nm
er_reference_loss = er_reference_loss.merge(er_wafer_counts, on=EP_WAFER_KEYS+["axis"], how="left", validate="m:1")
er_reference_loss = er_reference_loss.merge(er_wafer_gaps[EP_WAFER_KEYS+["axis", "delta_M3S_edge_minus_inner_nm"]], on=EP_WAFER_KEYS+["axis"], how="left", validate="m:1")

er_wafer_index = er_wafer_counts[EP_WAFER_KEYS+["axis"]].drop_duplicates().sort_values(EP_WAFER_KEYS).reset_index(drop=True)
er_wafer_index["wafer_index"] = er_wafer_index.groupby("product", observed=True).cumcount()
er_wafer_metrics = er_wafer_metrics.merge(er_wafer_index, on=EP_WAFER_KEYS+["axis"], how="left", validate="m:1")
inner_shot = er_shot_metrics.loc[er_shot_metrics.region.eq("R_LE_144MM")].copy()
inner_shot["case"] = [f"R{r:g}_S{int(s):03d}" for r,s in zip(inner_shot.fit_radius_mm,inner_shot.scale_pct)]
er_shot_inner_wide = inner_shot.pivot(index=EP_SHOT_KEYS+["axis"], columns="case", values="M3S_nm").reset_index()
er_shot_inner_wide.columns.name = None
er_shot_inner_wide = er_shot_inner_wide.merge(er_shot_counts[EP_SHOT_KEYS+["axis"]+[c for c in ["DieX", "DieY", "photo_transn_seq"] if c in er_shot_counts]], on=EP_SHOT_KEYS+["axis"], how="left", validate="1:1")
er_sampling_summary = er_wafer_counts.groupby(["product", "axis"], observed=True).agg(n_wafers=("Wafer","size"), median_edge_point_fraction=("edge_point_fraction","median"), median_inner_mixed_fraction=("inner_mixed_fraction","median"), total_measured_points=("n_total","sum"), total_edge_points=("n_edge","sum")).reset_index()
display(er_sampling_summary)
display(er_product_curves.loc[er_product_curves.scope.eq("ALL_SHOTS") & er_product_curves.region.eq("R_LE_144MM")])
