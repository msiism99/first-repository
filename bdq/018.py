df_adi_cpe, coef_adi_cpe, summary_adi_cpe = run_cpe38_ridge_shotwise_after_wkrk(
    df_adi,
    label="ADI",
    wafer_cols=("LOT_ID", "Wafer"),
    shot_center_cols=("fcp_x", "fcp_y"),
    residual_cols=("raw_minus_total_fit_x", "raw_minus_total_fit_y"),
    shot_cols=("coordinate_X", "coordinate_Y"),
    span_mode=SPAN_MODE,
    min_points_guide=MIN_POINTS_GUIDE,
)

df_oco_cpe, coef_oco_cpe, summary_oco_cpe = run_cpe38_ridge_shotwise_after_wkrk(
    df_oco,
    label="OCO",
    wafer_cols=("LOT_ID", "Wafer"),
    shot_center_cols=("fcp_x", "fcp_y"),
    residual_cols=("raw_minus_total_fit_x", "raw_minus_total_fit_y"),
    shot_cols=("coordinate_X", "coordinate_Y"),
    span_mode=SPAN_MODE,
    min_points_guide=MIN_POINTS_GUIDE,
)

df_adi_cpe.to_excel("df_final_adi_after_cpe38_ridge_shotwise.xlsx", index=False)
df_oco_cpe.to_excel("df_final_oco_after_cpe38_ridge_shotwise.xlsx", index=False)

coef_adi_cpe.to_excel("coef_adi_cpe38_ridge_shotwise.xlsx", index=False)
coef_oco_cpe.to_excel("coef_oco_cpe38_ridge_shotwise.xlsx", index=False)

summary_adi_cpe.to_excel("summary_adi_cpe38_ridge_shotwise.xlsx", index=False)
summary_oco_cpe.to_excel("summary_oco_cpe38_ridge_shotwise.xlsx", index=False)
