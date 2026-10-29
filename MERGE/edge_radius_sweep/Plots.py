# %% 08. 실제 point 비율 / mixed shot 차이 / 반경×배율 M3S / wafer별 결과
er_products = [str(s["product"]) for s in EP_SOURCES]
er_labels = {p:f"{p} [{EP_PRODUCT_AXES[p][0].upper()}]" for p in er_products}
er_colors = dict(zip(er_products, plt.get_cmap("tab10")(np.linspace(0, .9, len(er_products)))))
er_scale_colors = dict(zip(ER_SCALES, plt.get_cmap("tab10")(np.linspace(0, .9, len(ER_SCALES)))))
er_plot_paths = []


def er_save_plot(fig, name):
    for extension in ["png", "pdf"]:
        path = EP_OUTPUT_DIR / "plots" / f"{name}.{extension}"
        fig.savefig(path, dpi=170, bbox_inches="tight")
        er_plot_paths.append(path)
    display(fig)
    plt.close(fig)


def er_boxes(panel, data, column, title, ylabel, unit="wafers"):
    rng = np.random.default_rng(20261029)
    labels = []
    for index, product in enumerate(er_products):
        values = pd.to_numeric(data.loc[data["product"].eq(product),column],errors="coerce").dropna().to_numpy(float)
        labels.append(f"{er_labels[product]}\nN={len(values)} {unit}")
        if len(values):
            panel.boxplot([values],positions=[index],widths=.5,patch_artist=True,showfliers=False,boxprops=dict(facecolor=er_colors[product],alpha=.3),medianprops=dict(color="black"))
            panel.scatter(index+rng.uniform(-.12,.12,len(values)),values,s=10,alpha=.4,color=er_colors[product])
        else:
            panel.text(index,.5,"No comparable data",ha="center",rotation=90,transform=panel.get_xaxis_transform())
    panel.set_xticks(np.arange(len(er_products)),labels)
    panel.set_xlim(-.6,len(er_products)-.4)
    panel.set(title=title,ylabel=ylabel)
    panel.grid(axis="y",alpha=.25)


fig, panels = plt.subplots(1,2,figsize=(14,5))
er_boxes(panels[0],er_wafer_counts,"edge_point_fraction","Measured edge points / all wafer points","Point fraction")
er_boxes(panels[1],er_edge_shot_counts,"edge_point_fraction","Edge points / points in shots containing edge","Point fraction")
fig.tight_layout()
er_save_plot(fig,"01_Actual_edge_point_fraction")

fig, panels = plt.subplots(1,2,figsize=(14,5))
er_boxes(panels[0],er_wafer_gaps,"delta_M3S_edge_minus_inner_nm","Mixed shots pooled per wafer: edge M3S - inner M3S","M3S difference [nm]")
er_boxes(panels[1],er_shot_gaps,"delta_M3S_edge_minus_inner_nm","Same mixed shot: edge M3S - inner M3S","M3S difference [nm]",unit="shots")
for panel in panels:
    panel.axhline(0,color="gray",linewidth=.8)
fig.suptitle("Unscaled input after fixed K-MRC, before CPE")
fig.tight_layout()
er_save_plot(fig,"02_Mixed_shot_input_gap")

for scope,region,name in [("ALL_SHOTS","R_LE_144MM","03_Product_M3S_Inner"),("MIXED_SHOTS","R_LE_144MM","04_Product_M3S_Mixed_Inner"),("ALL_SHOTS","ALL_R_LE_147MM","05_Product_M3S_All147")]:
    fig, panels = plt.subplots(1,len(er_products),figsize=(5*len(er_products),4.5),squeeze=False,sharey=True)
    for panel,product in zip(panels[0],er_products):
        part = er_product_curves.loc[er_product_curves["product"].eq(product)&er_product_curves.scope.eq(scope)&er_product_curves.region.eq(region)]
        for radius in ER_FIT_RADII_MM:
            line = part.loc[part.fit_radius_mm.eq(radius)].sort_values("scale_pct")
            panel.plot(line.scale_pct,line.mean_M3S_nm,".-",label=f"Fit R <= {radius:g} mm; N={int(line.n_wafers_used.max()) if len(line) else 0}")
        if part.mean_M3S_nm.notna().sum()==0:
            panel.text(.5,.5,"No wafers complete across all cases",ha="center",wrap=True,transform=panel.transAxes)
        panel.set(title=er_labels[product],xlabel="Edge value scale for CPE fit [%]",ylabel="Mean wafer M3S [nm]")
        panel.grid(alpha=.25)
        panel.legend(fontsize=8)
    fig.suptitle(f"{scope} | evaluation {region} | same wafer cohort, unscaled evaluation")
    fig.tight_layout()
    er_save_plot(fig,name)

fig, panels = plt.subplots(1,len(er_products),figsize=(5*len(er_products),4.5),squeeze=False,sharey=True)
complete_delta = er_radius_delta.merge(er_completeness,on=er_cohort_keys,how="left",validate="m:1")
for panel,product in zip(panels[0],er_products):
    part = complete_delta.loc[complete_delta["product"].eq(product)&complete_delta.scope.eq("ALL_SHOTS")&complete_delta.region.eq("R_LE_144MM")&complete_delta.complete_all_cases]
    grouped = part.groupby("scale_pct",observed=True).delta_M3S_nm
    mean = grouped.mean()
    panel.plot(mean.index,mean.to_numpy(),".-",color=er_colors[product])
    panel.axhline(0,color="gray",linewidth=.8)
    panel.set(title=er_labels[product],xlabel="Edge value scale [%]",ylabel="M3S: smaller fit radius - larger [nm]")
    panel.grid(alpha=.25)
fig.suptitle("Same-wafer radius difference | R <= 144 mm evaluation | negative = smaller radius better")
fig.tight_layout()
er_save_plot(fig,"06_Paired_radius_difference")

fig, panels = plt.subplots(1,2,figsize=(14,5))
relation = er_reference_loss.loc[er_reference_loss.scope.eq("ALL_SHOTS")&er_reference_loss.region.eq("R_LE_144MM")&er_reference_loss.fit_radius_mm.eq(max(ER_FIT_RADII_MM))]
for product in er_products:
    part=relation.loc[relation["product"].eq(product)]
    label=f"{er_labels[product]} (reference {er_reference_scales[product]:.0%})"
    for panel,column in zip(panels,["valid_edge_fraction","delta_M3S_edge_minus_inner_nm"]):
        paired=part.dropna(subset=[column,"loss_100_minus_reference_nm"])
        panel.scatter(paired[column],paired.loss_100_minus_reference_nm,color=er_colors[product],s=20,alpha=.6,label=label)
for panel in panels:
    panel.axhline(0,color="gray",linewidth=.8)
    panel.set_ylabel("Inner M3S: 100% - previous product reference [nm]")
    panel.grid(alpha=.25)
    panel.legend(title="Product / axis",fontsize=8)
panels[0].set_xlabel("Valid edge points / valid wafer points")
panels[1].set_xlabel("Mixed-shot pooled input M3S: edge - inner [nm]")
fig.suptitle("Same-wafer association | larger fit radius | reference scales are fixed per product")
fig.tight_layout()
er_save_plot(fig,"07_Input_gap_fraction_vs_100pct_loss")

from matplotlib.ticker import MaxNLocator
for index,product in enumerate(er_products,start=1):
    fig, panels = plt.subplots(2,2,figsize=(17,9),sharex=True,sharey="row")
    for row,region in enumerate(["R_LE_144MM","ALL_R_LE_147MM"]):
        for col,radius in enumerate(ER_FIT_RADII_MM):
            panel=panels[row,col]
            for scale in ER_SCALES:
                part=er_wafer_metrics.loc[er_wafer_metrics["product"].eq(product)&er_wafer_metrics.scope.eq("ALL_SHOTS")&er_wafer_metrics.region.eq(region)&er_wafer_metrics.fit_radius_mm.eq(radius)&er_wafer_metrics.scale.eq(scale)].sort_values("wafer_index")
                panel.plot(part.wafer_index,part.M3S_nm,".-",linewidth=.7,markersize=2,color=er_scale_colors[scale],label=f"{scale:.0%}")
            panel.set(title=f"Fit <= {radius:g} mm | evaluate {region}",ylabel="|mean| + 3 sigma [nm]")
            panel.grid(alpha=.25)
            panel.xaxis.set_major_locator(MaxNLocator(integer=True))
            if row==0:
                panel.legend(title="Edge fit scale",ncol=5,fontsize=8)
            if row==1:
                panel.set_xlabel("Wafer index (see Wafer_index sheet)")
    fig.suptitle(f"{er_labels[product]} | unscaled evaluation on original measured points")
    fig.tight_layout()
    er_save_plot(fig,f"08_Wafer_M3S_Product_{index:02d}")
