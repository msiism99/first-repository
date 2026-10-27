def select_oco_model_inputs(frame, cfg):
    """Keep E1 main references separate from full-area CPE input; never restrict ADI here."""
    group = "E2" if (cfg.target_mstepseq_oco or "")[2:5] == "077" else "E1"
    source = frame["measurement_source"] if "measurement_source" in frame else pd.Series("oco_main", index=frame.index)
    reference_mask = frame["GROUP"].eq("E1") & source.eq("oco_main")
    split_steps = bool(cfg.include_oco_edge and cfg.target_mstepseq_oco_edge != cfg.target_mstepseq_oco)
    references = frame.loc[reference_mask].copy()
    if not split_steps and not references.empty:
        require_columns(references, ["radius"], "OCO E1 K-MRC 반경")
        radius = pd.to_numeric(references["radius"], errors="coerce")
        references = references[np.isfinite(radius) & radius.le(cfg.kmrc_e1_radius_um)].copy()
    analysis = frame[frame["GROUP"].eq(group) & (source.eq("oco_main") | split_steps)].copy()
    keys = ["LOT_ID", "Wafer"]
    counts = frame[keys].drop_duplicates().copy()
    for name, part in [("n_e1_main_before_radius", frame.loc[reference_mask]), ("n_e1_kmrc", references), ("n_analysis", analysis)]:
        grouped = part.groupby(keys, observed=True, dropna=False).size().rename(name).reset_index()
        counts = counts.merge(grouped, on=keys, how="left", validate="1:1")
        counts[name] = counts[name].fillna(0).astype(int)
    counts["analysis_group"], counts["split_steps"] = group, split_steps
    counts["e1_radius_limit_um"] = np.nan if split_steps else cfg.kmrc_e1_radius_um
    return analysis, references, counts


df_final_adi = df_adi_raw[df_adi_raw["MMO_MRC_EQP"].notna() & df_adi_raw["MMO_MRC_EQP"].astype(str).str.strip().ne("")].copy()
df_final_oco_all = df_oco_raw[df_oco_raw["MMO_MRC_EQP"].notna() & df_oco_raw["MMO_MRC_EQP"].astype(str).str.strip().ne("")].copy()
df_final_oco, df_oco_e1_raw, df_oco_model_input_counts = select_oco_model_inputs(df_final_oco_all, cfg)
df_wafer_summary = pd.concat([summarize(df_final_adi, "ADI"), summarize(df_final_oco, "OCO")], ignore_index=True)
save_stage("15_ADI_FINAL", df_final_adi, columns=raw_preview)
save_stage("15_OCO_FINAL", df_final_oco, columns=raw_preview)
save_stage("15_OCO_ALL_GROUPS_RAW", df_final_oco_all, columns=raw_preview)
save_stage("15_OCO_E1_KMRC_INPUT", df_oco_e1_raw, columns=raw_preview)
save_stage("15_OCO_MODEL_INPUT_COUNTS", df_oco_model_input_counts)
save_stage("15_WAFER_SUMMARY", df_wafer_summary)
print("MRC/PSM decorrect 완료: OCO 분석 입력과 E1 K-MRC 입력을 별도로 저장했습니다.")
