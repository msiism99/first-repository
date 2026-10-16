# %% 12. Sampling 지도 / alias / noise 증폭 / 항별 복원 오차 그림
plot_paths = []
def finish_figure(fig,name):
    fig.tight_layout()
    path = PLOT_DIR / f"{name}.png"
    fig.savefig(path,dpi=160,bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"),bbox_inches="tight")
    plot_paths.append(str(path))
    if SHOW_PLOTS:
        display(fig)
    plt.close(fig)

fig, axes = plt.subplots(2,2,figsize=(12,10))
wafer_extent = 1.06*max(VIRTUAL_WAFER_RADIUS/1000,float(shot_layouts[["fcp_x","fcp_y"]].abs().max().max())/1000)
for column, mode in enumerate(MODES):
    shots = shot_layouts.loc[shot_layouts["mode"].eq(mode)]
    ax = axes[0,column]
    ax.scatter(shots.fcp_x/1000,shots.fcp_y/1000,s=16,color="tab:blue",label="Shot centers")
    work = primary_frames[mode]
    ax.scatter(work.fcp_x.iloc[0]/1000,work.fcp_y.iloc[0]/1000,s=130,marker="*",color="tab:orange",label="Representative shot")
    ax.add_patch(plt.Circle((0,0),VIRTUAL_WAFER_RADIUS/1000,fill=False,color="gray",linestyle=":",lw=.8,label="Virtual-point radius"))
    ax.set(xlabel="Wafer X [mm]",ylabel="Wafer Y [mm]",title=f"{mode}: selected wafer",xlim=(-wafer_extent,wafer_extent),ylim=(-wafer_extent,wafer_extent))
    ax.set_aspect("equal",adjustable="box")
    ax.legend(fontsize=8)
    ax = axes[1,column]
    counts = work.groupby(COORDS).size().reset_index(name="count")
    ax.scatter(counts[COORDS[0]]/1000,counts[COORDS[1]]/1000,s=20+counts["count"]*10,color="tab:blue",label="Measured coordinates")
    ax.set(xlim=(-half_x/1000,half_x/1000),ylim=(-half_y/1000,half_y/1000),xlabel="Local X [mm]",ylabel="Local Y [mm]",title=f"{mode}: {len(work)} rows / {len(counts)} unique points")
    ax.set_aspect("equal",adjustable="box")
    ax.legend(fontsize=8)
for ax in axes.ravel():
    ax.grid(alpha=.2)
finish_figure(fig,"01_sampling_layout")

fig, axes = plt.subplots(2,2,figsize=(13,11))
for row,mode in enumerate(MODES):
    for column,case in enumerate(NATIVE_CASES):
        spec,ax = model_cases[(mode,case)],axes[row,column]
        im = ax.imshow(np.abs(spec["cosine"]),vmin=0,vmax=1,cmap="viridis")
        ax.set_xticks(range(len(spec["names"])),spec["names"],rotation=90,fontsize=7)
        ax.set_yticks(range(len(spec["names"])),spec["names"],fontsize=7)
        ax.set_title(f"{mode} / {case}: rank {spec['rank']}/{len(spec['names'])}")
        fig.colorbar(im,ax=ax,label="Absolute column cosine")
finish_figure(fig,"02_term_alias")

fig, axes = plt.subplots(2,2,figsize=(12,10))
vmax = max(float(spec["noise_gains"]["GOPT_RIDGE"].max()) for spec in model_cases.values())
for row,mode in enumerate(MODES):
    for column,case in enumerate(NATIVE_CASES):
        spec,ax = model_cases[(mode,case)],axes[row,column]
        im = ax.imshow(spec["noise_gains"]["GOPT_RIDGE"].reshape(xx.shape),origin="lower",extent=(-half_x/1000,half_x/1000,-half_y/1000,half_y/1000),vmin=0,vmax=max(vmax,1e-12),cmap="magma",aspect="equal")
        work = primary_frames[mode]
        ax.scatter(work[COORDS[0]]/1000,work[COORDS[1]]/1000,s=9,facecolors="none",edgecolors="cyan",label="Sampling")
        ax.set(xlabel="Local X [mm]",ylabel="Local Y [mm]",title=f"{mode} / {case}\nG-opt ridge before span/box")
        ax.legend(fontsize=8)
        fig.colorbar(im,ax=ax,label="Prediction noise / point noise")
finish_figure(fig,"03_noise_amplification")

single_patterns = pattern_catalogue.loc[~pattern_catalogue.group.eq("MIXED"),"pattern"].tolist()
fig, axes = plt.subplots(1,2,figsize=(13,12))
for ax,method in zip(axes,["OLS_SVD","GOPT_RIDGE"]):
    table = pattern_response.loc[pattern_response.method.eq(method)].pivot(index="pattern",columns=["mode","case"],values="expected_grid_rmse_nm")
    columns = [(mode,case) for mode in MODES for case in NATIVE_CASES]
    matrix = table.loc[single_patterns,columns].to_numpy(float)
    im = ax.imshow(matrix,aspect="auto",cmap="magma")
    ax.set_yticks(range(len(single_patterns)),single_patterns,fontsize=8)
    ax.set_xticks(range(4),[f"{mode}\n{case}" for mode,case in columns],fontsize=8)
    ax.set_title(f"{method}: sqrt(E[grid MSE]), signal {SYNTHETIC_SIGNAL_RMS_NM:g} nm RMS")
    fig.colorbar(im,ax=ax,label=f"nm (assumed point noise {ASSUMED_POINT_NOISE_NM:g} nm)")
finish_figure(fig,"04_pattern_reconstruction")

colors = {"SHARED":"tab:gray","X21_ONLY":"tab:blue","ROT_Y17_ONLY":"tab:orange","NEITHER":"tab:purple","MIXED":"tab:green"}
for metric,label,filename in [("train_3sigma_nm","sample residual 3sigma","05_sample_residual_interaction"),("grid_rmse_nm","common-grid RMSE","06_grid_reconstruction_interaction")]:
    fig, axes = plt.subplots(1,3,figsize=(16,5))
    fig.suptitle("Identical noiseless truth field at both samplings")
    x_col,y_col = [f"{mode}_delta_{metric}_ROT_minus_X21" for mode in MODES]
    for ax,method in zip(axes,["OLS_SVD","GOPT_RIDGE","NATIVE_SPAN"]):
        table = sampling_interaction.loc[sampling_interaction.method.eq(method)]
        for group,color in colors.items():
            points = table.loc[table.group.eq(group)]
            ax.scatter(points[x_col],points[y_col],label=group,color=color,s=23,alpha=.75)
        examples = table.loc[table[x_col].lt(-1e-6) & table[y_col].gt(1e-6)].copy()
        examples["strength"] = examples[x_col].abs()+examples[y_col].abs()
        for row in examples.nlargest(3,"strength").to_dict("records"):
            ax.annotate(row["pattern"],(row[x_col],row[y_col]),xytext=(4,4),textcoords="offset points",fontsize=7)
        ax.axhline(0,color="gray",lw=.7)
        ax.axvline(0,color="gray",lw=.7)
        ax.set(xlabel=f"ADI: rotated Y17 - X21 {label} [nm]",ylabel=f"OCO: rotated Y17 - X21 {label} [nm]",title=f"{method}\nUpper-left: ADI Y17 / OCO X21 preferred")
        ax.grid(alpha=.15)
        ax.legend(fontsize=6)
    finish_figure(fig,filename)

# %% 13. 진단 Excel / 재현 설정 / 입력·출력 목록 저장
notes = pd.DataFrame([
    ("scope","같은 critical X의 X21 / 회전 Y17을 비교. Y 실측값은 사용하지 않음. 각 mode 대표 wafer/대표 shot 하나의 좌표 진단."),
    ("selection","가능하면 같은 wafer 선택. 가장 많은 고유 mark를 갖는 반복 layout에서 wafer 중심에 가까운 shot 선택. 전체 layout 목록 별도 저장."),
    ("geometry_only","좌표는 관측 가능성과 노이즈 전달을 결정하지만 실제 오차 패턴의 원인을 단독으로 확정하지 못함."),
    ("same_truth","같은 정답 field를 두 sampling에서 평가하고 공통 grid에서 복원 오차 비교. ADI/OCO 간 point 1:1 매칭을 하지 않음."),
    ("synthetic_units","합성 정답과 오차는 nm. 각 정답 field는 공통 grid RMS로 정규화. 좌표 µm. native span 계산 시 nm를 µm로 변환."),
    ("grid","공통 영역은 두 sampling의 pitch/좌표 범위를 포함하는 직사각형. hull 밖은 외삽 진단. shared_hull_rmse는 두 sampling hull 교집합만 평가."),
    ("OLS_SVD","열 정규화 SVD 최소노름 회귀. rank 부족이면 측정점 residual이 작아도 전체 field를 유일하게 복원할 수 없음."),
    ("GOPT_RIDGE","원본 G-opt로 정한 lambda의 선형 ridge. span/box 이전 단계. 원본 normal equation 계산 방식 사용."),
    ("NATIVE_SPAN","동일 lambda에서 원본 span 검사와 box CD를 적용. 좌표로 정해지는 lambda를 재사용하며 원본 한 방향 solver와 동일한 순서."),
    ("noise","독립·동일 분산 point noise 가정. 실제 noise 추정값 아님. Noise gain은 선형 OLS/ridge에 대한 값. rank 부족의 미관측 field 불확실성은 포함하지 않음."),
    ("expected_grid_rmse","sqrt(무noise grid MSE + sigma_noise^2 * mean(sum(H_grid^2))). sqrt(E[MSE])이며 box 이후에는 계산하지 않음."),
    ("expected_train_3sigma","3*sqrt(E[sample residual variance]). 같은 측정점에서의 signal 잔차 분산 + 가정한 noise 잔차 분산. grid 복원 오차와 구분. box 이후에는 계산하지 않음."),
    ("independent_fraction","한 basis 열을 다른 모든 열로 회귀한 후 남는 상대 norm. 0에 가까우면 해당 계수의 개별 식별이 어려움. alias는 두 열 cosine이므로 다중 항 의존성은 rank도 확인."),
    ("matches_observed","같은 가상 field의 ADI Y17 우세/OCO X21 우세 여부. training_3sigma는 기존 그림과 같은 측정점 잔차 지표, noiseless/with_assumed_noise는 공통 grid RMSE 기준. 예시 개수는 원인 확률이 아님."),
    ("observed_check","입력에 CPE 직전 실측 X가 있을 때 대표 shot에서만 재회귀. 전체 wafer 결과를 대체하지 않음. 실측 Y 불필요."),
    ("observed_gain","공통 12항 OLS 대비 각 모델 전용 항의 추가 측정점 설명력. rank 증가가 0이면 추가 항이 관측 공간을 늘리지 못할 수 있음. noise도 포함할 수 있음."),
    ("missing_shot_geometry","pitch/chip metadata가 없으면 원본과 같이 측정 범위 virtual grid 사용. sampling별 평가영역 차이는 sampling_summary에 표시."),
],columns=["item","description"])
report_path = OUTPUT_DIR / "CPE_Sampling_Diagnostics.xlsx"
report_tables = {
    "Sampling_summary":sampling_summary,"Selected_wafers":selection,"Layout_catalogue":layout_catalogue,"Term_identifiability":term_identifiability,"Alias_pairs":alias_pairs,
    "Pattern_response":pattern_response,"Sampling_interaction":sampling_interaction,"Observed_check":observed_check,"Observed_group_gain":observed_group_gain,
    "Model_terms":term_mapping,"Pattern_catalogue":pattern_catalogue,"Pitch_and_extent":pitch_table,"Notes":notes,
}
with pd.ExcelWriter(report_path,engine="openpyxl") as writer:
    for sheet,table in report_tables.items():
        excel_safe(table).to_excel(writer,sheet_name=sheet,index=False)
        ws = writer.book[sheet]
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions
        for column in ws.columns:
            ws.column_dimensions[column[0].column_letter].width = min(45,max(16,len(str(column[0].value))+2))
settings = dict(
    rotation_deg=ROTATION_DEG,wafer_selection=WAFER_SELECTION,filters=FILTERS,svd_rcond=SVD_RCOND,common_grid_n=COMMON_GRID_N,common_shot_size_um=[2*half_x,2*half_y],
    signal_rms_nm=SYNTHETIC_SIGNAL_RMS_NM,assumed_point_noise_nm=ASSUMED_POINT_NOISE_NM,random_seed=RANDOM_SEED,random_mixtures=RANDOM_MIXTURES,
    solver_overrides=SOLVER_OVERRIDES,solver={name:globals()[name] for name in sorted(set(SETTINGS_MAP.values()))},active_span_limits=NATIVE_SPAN_LIMITS,plots=plot_paths,
)
(OUTPUT_DIR / "sampling_settings.json").write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding="utf-8")
pd.DataFrame(input_manifest).to_csv(OUTPUT_DIR / "input_manifest.csv",index=False,encoding="utf-8-sig")
pd.DataFrame(output_manifest.values()).to_csv(OUTPUT_DIR / "saved_files.csv",index=False,encoding="utf-8-sig")
display(FileLink(os.path.relpath(report_path,Path.cwd())))
print("sampling 진단 완료:",report_path)
