# %% 06. 제품별 입력 통계·edge 예측 오차·예측 가능 범위 그래프
ep_products = [str(s["product"]) for s in EP_SOURCES]
ep_colors = dict(zip(ep_products, plt.get_cmap("tab10")(np.linspace(0, .9, len(ep_products)))))
ep_plot_paths = []


def ep_save_plot(fig, name):
    for extension in ["png", "pdf"]:
        path = EP_OUTPUT_DIR / "plots" / f"{name}.{extension}"
        fig.savefig(path, dpi=170, bbox_inches="tight")
        ep_plot_paths.append(path)
    display(fig)
    plt.close(fig)


def ep_boxplot(panel, data, column, title):
    rng = np.random.default_rng(20261029)
    for index, product in enumerate(ep_products):
        values = pd.to_numeric(data.loc[data["product"].eq(product), column], errors="coerce").dropna().to_numpy(float)
        if len(values):
            panel.boxplot([values], positions=[index], widths=.5, patch_artist=True, showfliers=False, boxprops=dict(facecolor=ep_colors[product], alpha=.3), medianprops=dict(color="black"))
            panel.scatter(index+rng.uniform(-.12, .12, len(values)), values, s=14, alpha=.65, color=ep_colors[product])
        else:
            panel.text(index, .5, "No eligible data", ha="center", rotation=90, transform=panel.get_xaxis_transform())
    labels = [f"{p}\nN={data.loc[data['product'].eq(p), column].notna().sum()} wafers" for p in ep_products]
    panel.set_xticks(np.arange(len(ep_products)), labels)
    panel.set_xlim(-.6, len(ep_products)-.4)
    panel.set_title(title)
    panel.set_ylabel("nm")
    panel.grid(axis="y", alpha=.25)


for axis in EP_AXES:
    base = ep_wafer_comparison.loc[ep_wafer_comparison.axis.eq(axis)]
    prediction = ep_wafer_prediction.loc[ep_wafer_prediction.axis.eq(axis)]
    fig, panels = plt.subplots(1, 2, figsize=(13, 5))
    ep_boxplot(panels[0], base, "M3S_nm_inner", "R <= 144 mm: |mean| + 3 sigma")
    ep_boxplot(panels[1], base, "M3S_nm_edge", "144 < R <= 147 mm: |mean| + 3 sigma")
    fig.suptitle(f"OCO {axis.upper()}: unscaled input after fixed K-MRC, before CPE | each dot = wafer")
    fig.tight_layout()
    ep_save_plot(fig, f"01_Input_M3S_{axis.upper()}")

    fig, panel = plt.subplots(figsize=(7, 6))
    for product in ep_products:
        part = base.loc[base["product"].eq(product)].dropna(subset=["M3S_nm_inner", "M3S_nm_edge"])
        panel.scatter(part.M3S_nm_inner, part.M3S_nm_edge, color=ep_colors[product], s=22, alpha=.7, label=f"{product} (N={len(part)})")
    limits = base[["M3S_nm_inner", "M3S_nm_edge"]].to_numpy(float)
    finite = limits[np.isfinite(limits)]
    if len(finite):
        lo, hi = float(finite.min()), float(finite.max())
        panel.plot([lo, hi], [lo, hi], ":", color="gray", label="Equal M3S")
    panel.set(xlabel="Inner input M3S [nm]", ylabel="Edge input M3S [nm]", title=f"OCO {axis.upper()}: same-wafer input comparison (before CPE)")
    panel.legend(title="Product")
    panel.grid(alpha=.25)
    fig.tight_layout()
    ep_save_plot(fig, f"02_Edge_vs_inner_input_{axis.upper()}")

    fig, panels = plt.subplots(1, 2, figsize=(13, 5))
    ep_boxplot(panels[0], prediction, "RMSE_nm", "Edge - inner-only CPE prediction: RMSE")
    ep_boxplot(panels[1], prediction, "mean_nm", "Edge - inner-only CPE prediction: signed mean")
    panels[1].axhline(0, color="gray", linewidth=.8)
    fig.suptitle(f"OCO {axis.upper()}: eligible inner references only | each dot = wafer | check coverage")
    fig.tight_layout()
    ep_save_plot(fig, f"03_Edge_prediction_error_{axis.upper()}")

    diag = ep_reference_diagnostics.loc[ep_reference_diagnostics.axis.eq(axis)]
    fig, panels = plt.subplots(1, 2, figsize=(14, 5))
    for index, product in enumerate(ep_products):
        part = diag.loc[diag["product"].eq(product)]
        panels[0].bar(index, len(part), color="lightgray")
        panels[0].bar(index, int(part.eligible.sum()), color=ep_colors[product])
        panels[0].text(index, len(part), f"{int(part.eligible.sum())}/{len(part)}", ha="center", va="bottom")
        for eligible, marker in [(True, "o"), (False, "x")]:
            selected = part.loc[part.eligible.eq(eligible)].dropna(subset=["ridge_edge_noise_gain_max", "candidate_edge_RMSE_nm"])
            panels[1].scatter(selected.ridge_edge_noise_gain_max, selected.candidate_edge_RMSE_nm, color=ep_colors[product], marker=marker, s=23, alpha=.7, label=f"{product}: {'eligible' if eligible else 'excluded'}")
    panels[0].set_xticks(np.arange(len(ep_products)), ep_products)
    panels[0].set(ylabel="Shot count", title="Eligible / all shots with edge points (gray = all)")
    panels[1].axvline(EP_MAX_EDGE_NOISE_GAIN, color="gray", linestyle=":")
    panels[1].set(xlabel="Max edge prediction noise gain (linear ridge proxy)", ylabel="Candidate edge prediction RMSE [nm]", title="Geometry / regularization diagnostic")
    panels[1].legend(fontsize=8, title="Product / reference screening")
    for panel in panels:
        panel.grid(alpha=.2)
    fig.tight_layout()
    ep_save_plot(fig, f"04_Reference_coverage_{axis.upper()}")

    fig, panel = plt.subplots(figsize=(10, 5))
    profile = ep_radial_profiles.loc[ep_radial_profiles.axis.eq(axis)]
    any_profile = False
    for product in ep_products:
        part = profile.loc[profile["product"].eq(product)]
        if part.empty:
            continue
        grouped = part.groupby("radius_mid_mm", observed=True).RMSE_nm
        median, lower, upper = grouped.median(), grouped.quantile(.25), grouped.quantile(.75)
        panel.plot(median.index, median.to_numpy(), ".-", color=ep_colors[product], label=product)
        panel.fill_between(median.index, lower.to_numpy(), upper.to_numpy(), alpha=.15, color=ep_colors[product])
        any_profile = True
    panel.axvline(EP_INNER_RADIUS_UM/1000, color="black", linestyle=":", label="144 mm boundary")
    if not any_profile:
        panel.text(.5, .5, "No eligible inner reference for radial comparison", ha="center", transform=panel.transAxes)
    panel.set(xlabel="Actual point radius [mm]", ylabel="Reference residual RMSE [nm]", title=f"OCO {axis.upper()}: wafer median / IQR | inner = fitted, edge = predicted")
    panel.legend(title="Product")
    panel.grid(alpha=.25)
    fig.tight_layout()
    ep_save_plot(fig, f"05_Radial_reference_error_{axis.upper()}")
