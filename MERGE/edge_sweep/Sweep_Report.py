# %% 34. Excel·Parquet 및 실행 설정 저장
es_notes = pd.DataFrame([
    ["입력", str(es_point_path)],
    ["계산", "반경 >144mm 측정점의 원래 X/Y에 50~100% 적용. 저장된 raw_minus_total_fit에 배율 차이만 더함. K-MRC 및 기존 MRC/PSM fitting은 고정."],
    ["CPE 재계산", "외곽 측정점이 포함된 shot의 전체 point만 CPE38 재회귀. 그 외 shot의 최종 결과는 저장값 재사용."],
    ["Wafer_M3S", "모든 분석 wafer. 영향 shot과 영향 없는 shot을 모두 합친 최종 residual의 통계."],
    ["Affected_shot_M3S", "144mm 바깥 측정점이 하나라도 있는 shot만 수록. 안쪽 point도 해당 shot의 새 CPE 결과 사용."],
    ["M3S", f"abs(mean(residual)) + 3*std(residual), std ddof={ES_STD_DDOF}, nm 단위. mean(abs(residual))와 다름."],
    ["영역", "R_LE_144MM: 실제 측정점 반경 <=144mm (현재 사용 메트릭). ALL_POINTS: 모든 측정점. 회귀 입력은 영역별로 자르지 않음."],
    ["유효 point", "통계는 유한한 final residual만 사용. 안쪽 point 0개 또는 표준편차 계산 불가 시 M3S는 NA이며 0으로 채우지 않음."],
    ["배율", "각 외곽 point의 measurement_scale과 X_reg_original/Y_reg_original에서 복원. raw를 단순히 배율로 나누거나 곱하지 않음."],
    ["고정 요소", "좌표·회귀 point·K-MRC·기존 MRC/PSM·CPE 모델 및 설정. 배율만 변경."],
    ["best_scale_pct", "지정한 6개 후보 중 M3S가 최소인 배율. 동률이면 낮은 배율을 표시."],
    ["현재 반경 미상 point", str(int(es_base_points.radius.isna().sum()))],
], columns=["item", "description"])
es_tables = {
    "Wafer_M3S": es_wafer_metrics, "Affected_shot_M3S": es_shot_metrics,
    "Wafer_sensitivity": es_wafer_sensitivity, "Shot_sensitivity": es_shot_sensitivity,
    "Wafer_index": es_wafer_index, "Affected_shot_index": es_shot_index,
    "Baseline_parity": es_baseline_parity, "Notes": es_notes,
}


def es_excel_safe(frame):
    out = frame.copy()
    for col in out.columns:
        if col in ["photo_transn_seq", "source_lot_transn_seq", "apc_hist_index_no", "apc_trocs_hist_index_no"]:
            out[col] = out[col].map(lambda v: str(int(v)) if pd.notna(v) else "")
    return out


es_excel_path = ES_OUTPUT_DIR / "OCO_Edge_Scale_Sweep.xlsx"
with pd.ExcelWriter(es_excel_path, engine="openpyxl") as writer:
    for name, table in es_tables.items():
        table.to_parquet(ES_OUTPUT_DIR / "tables" / f"{name}.parquet", index=False)
        export = es_excel_safe(table)
        for offset in range(0, max(1, len(export)), 1048575):
            suffix = "" if len(export) <= 1048575 else f"_{offset//1048575+1}"
            export.iloc[offset:offset+1048575].to_excel(writer, sheet_name=name[:31-len(suffix)] + suffix, index=False)
for name, table in [("Affected_CPE_Coefficients", es_cpe_coefficients), ("Affected_CPE_Diagnostics", es_cpe_diagnostics)]:
    table.to_parquet(ES_OUTPUT_DIR / "tables" / f"{name}.parquet", index=False)
es_run_settings = dict(input_points=str(es_point_path), input_settings=str(es_settings_path), scales=ES_SCALES, metric_axes=ES_METRIC_AXES, metric_radius_um=ES_RADIUS_UM,
                       std_ddof=ES_STD_DDOF, fixed_kmrc=True, recompute_only_affected_shots=True, n_input_points=len(es_base_points), n_affected_shots=len(es_shot_index), cpe_settings=es_saved_settings)
(ES_OUTPUT_DIR / "sweep_settings.json").write_text(json.dumps(es_run_settings, ensure_ascii=False, indent=2), encoding="utf-8")
display(FileLink(os.path.relpath(es_excel_path, Path.cwd()), result_html_prefix="Wafer/shot M3S Excel: "))
for path in es_plot_paths:
    if path.suffix == ".png":
        display(FileLink(os.path.relpath(path, Path.cwd()), result_html_prefix="그래프: "))
print("배율 비교 완료:", ES_OUTPUT_DIR)
