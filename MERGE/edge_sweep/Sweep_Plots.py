# %% 33. Wafer별·영향 shot별 M3S 그래프와 배율 민감도
from matplotlib.ticker import MaxNLocator

def es_sensitivity(metrics, keys):
    groups = keys + ["axis", "region"]
    if metrics.empty:
        return pd.DataFrame(columns=groups + ["min_M3S_nm", "max_M3S_nm", "range_M3S_nm", "best_scale_pct", "M3S_first_nm", "M3S_last_nm", "delta_last_minus_first_nm"])
    valid = metrics[metrics["M3S_nm"].notna()]
    result = metrics[groups].drop_duplicates().copy()
    if valid.empty:
        return result.assign(min_M3S_nm=np.nan, max_M3S_nm=np.nan, range_M3S_nm=np.nan, best_scale_pct=np.nan)
    stats = valid.groupby(groups, observed=True, dropna=False).agg(min_M3S_nm=("M3S_nm", "min"), max_M3S_nm=("M3S_nm", "max")).reset_index()
    best_idx = valid.groupby(groups, observed=True, dropna=False)["M3S_nm"].idxmin()
    best = valid.loc[best_idx, groups + ["scale_pct"]].rename(columns={"scale_pct": "best_scale_pct"})
    result = result.merge(stats, on=groups, how="left", validate="1:1").merge(best, on=groups, how="left", validate="1:1")
    result["range_M3S_nm"] = result["max_M3S_nm"] - result["min_M3S_nm"]
    for scale, name in [(ES_SCALES[0], "M3S_first_nm"), (ES_SCALES[-1], "M3S_last_nm")]:
        selected = metrics[metrics.scale.eq(scale)][groups + ["M3S_nm"]].rename(columns={"M3S_nm": name})
        result = result.merge(selected, on=groups, how="left", validate="1:1")
    result["delta_last_minus_first_nm"] = result["M3S_last_nm"] - result["M3S_first_nm"]
    return result


es_wafer_sensitivity = es_sensitivity(es_wafer_metrics, ES_WAFER_KEYS)
es_shot_sensitivity = es_sensitivity(es_shot_metrics, ES_SHOT_KEYS)
if not es_shot_sensitivity.empty:
    es_shot_sensitivity = es_shot_sensitivity.merge(es_shot_index, on=ES_SHOT_KEYS, how="left", validate="m:1")
es_plot_paths = []
es_colors = dict(zip(ES_SCALES, plt.get_cmap("tab10").colors))
es_region_titles = {"R_LE_144MM": "R <= 144 mm (current metric)", "ALL_POINTS": "All measured points"}


def es_save_plot(fig, stem):
    for extension in ["png", "pdf"]:
        path = ES_OUTPUT_DIR / "plots" / f"{stem}.{extension}"
        fig.savefig(path, dpi=180, bbox_inches="tight")
        es_plot_paths.append(path)
    display(fig)
    plt.close(fig)


for axis in ES_METRIC_AXES:
    fig, panels = plt.subplots(2, 1, figsize=(16, 8), sharex=True)
    for panel, region in zip(panels, es_region_titles):
        for scale in ES_SCALES:
            part = es_wafer_metrics[es_wafer_metrics.axis.eq(axis) & es_wafer_metrics.region.eq(region) & es_wafer_metrics.scale.eq(scale)].sort_values("wafer_index")
            panel.plot(part.wafer_index, part.M3S_nm, ".-", markersize=3, linewidth=1, color=es_colors[scale], label=f"{scale:.0%}")
        panel.set_title(f"OCO {axis.upper()}: wafer M3S | {es_region_titles[region]} | unscaled evaluation")
        panel.set_ylabel("|mean| + 3 sigma [nm]")
        panel.grid(alpha=.25)
        panel.legend(title="Outer-point scale for CPE fit", ncol=len(ES_SCALES))
    panels[-1].set_xlabel("Wafer index (see Wafer_index sheet)")
    panels[-1].xaxis.set_major_locator(MaxNLocator(integer=True))
    fig.tight_layout()
    es_save_plot(fig, f"01_Wafer_M3S_{axis.upper()}")

    fig, panels = plt.subplots(2, 1, figsize=(18, 8), sharex=True)
    for panel, region in zip(panels, es_region_titles):
        if es_shot_metrics.empty:
            panel.text(.5, .5, "No shots contain measured points beyond 144 mm", ha="center", transform=panel.transAxes)
        else:
            for scale in ES_SCALES:
                part = es_shot_metrics[es_shot_metrics.axis.eq(axis) & es_shot_metrics.region.eq(region) & es_shot_metrics.scale.eq(scale)].sort_values("shot_index")
                panel.plot(part.shot_index, part.M3S_nm, ".-", markersize=2, linewidth=.8, color=es_colors[scale], label=f"{scale:.0%}")
            panel.legend(title="Outer-point scale for CPE fit", ncol=len(ES_SCALES))
        panel.set_title(f"OCO {axis.upper()}: affected shots | {es_region_titles[region]} | unscaled evaluation")
        panel.set_ylabel("|mean| + 3 sigma [nm]")
        panel.grid(alpha=.25)
    panels[-1].set_xlabel("Affected shot index (see Affected_shot_index: LOT / wafer / DieX / DieY)")
    panels[-1].xaxis.set_major_locator(MaxNLocator(integer=True))
    fig.tight_layout()
    es_save_plot(fig, f"02_Affected_Shot_M3S_{axis.upper()}")

    part = es_shot_sensitivity[es_shot_sensitivity.axis.eq(axis) & es_shot_sensitivity.region.eq("R_LE_144MM")] if not es_shot_sensitivity.empty else es_shot_sensitivity
    part = part.dropna(subset=["range_M3S_nm"]).sort_values("range_M3S_nm", ascending=False).head(25)
    if not part.empty:
        labels = [f"{row.LOT_ID} / W{row.Wafer} / Die({row.DieX},{row.DieY})" for row in part.itertuples()]
        fig, panel = plt.subplots(figsize=(13, max(4, len(part)*.28)))
        panel.barh(np.arange(len(part)), part.range_M3S_nm, color="steelblue")
        panel.set_yticks(np.arange(len(part)), labels)
        panel.invert_yaxis()
        panel.set_xlabel(f"M3S max - min across {len(ES_SCALES)} scales [nm]")
        panel.set_title(f"OCO {axis.upper()}: most sensitive shots | R <= 144 mm")
        panel.grid(axis="x", alpha=.25)
        fig.tight_layout()
        es_save_plot(fig, f"03_Shot_Sensitivity_Inner_{axis.upper()}")
