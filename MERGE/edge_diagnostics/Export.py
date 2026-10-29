# %% 07. Excel·전체 통계 Parquet·설정 저장
ep_notes = pd.DataFrame([
    ["입력", "제품별 27_OCO_FINAL_POINTS 전체 Parquet(또는 전체 Excel) + 같은 실행의 extension_settings.json. ADI/sweep 파일 불필요."],
    ["분석 값", "input100 = 저장된 raw_minus_total_fit + (1-measurement_scale)*원래 X/Y 측정값. 기적용 MRC/PSM decorrection 및 고정 K-MRC는 유지. 최종 residual 자체를 역배율로 나누지 않음."],
    ["영역", "실제 point 반경 <=144mm: INNER. 144mm 초과~147mm 이하: EDGE. 반경 미상/범위 밖 제외 수는 Input_audit에 기록."],
    ["입력 통계", "CPE 제거 전 input100의 mean/3sigma/M3S/RMSE. 위치·실제 변형 차이가 섞이므로 edge 측정 noise만의 크기로 해석하지 않음."],
    ["참조 모델", "같은 shot의 INNER 유효 point만 사용해 기존 CPE38(X21/Y17) 회귀. EDGE 값은 회귀 입력·ridge/span 선택에 사용하지 않음. 좌표와 shot metadata는 평가 grid에 사용."],
    ["설정", "제품별 28번 ridge/G-opt/span/virtual 설정 복원. 가상 point의 radius clip은 저장된 설정 그대로. 실제 EDGE point의 예측 noise gain은 별도 계산."],
    ["내측 최소 point", f"X 21 + {EP_MIN_EXTRA_INNER_POINTS}, Y 17 + {EP_MIN_EXTRA_INNER_POINTS}; para 수 축소 없음. 부족/미식별 shot은 예측하지 않음."],
    ["참조 screening", f"안쪽 scaled design full rank, condition <= {EP_MAX_SCALED_CONDITION:g}, edge ridge noise gain <= {EP_MAX_EDGE_NOISE_GAIN:g}, 유한 예측·G-opt·span 확인. 이 임계값은 연구용 진단 설정이며 공정 spec이 아님."],
    ["noise gain", "독립·동일 측정 noise 가정의 선형 ridge 전달 행렬 행 norm. Box 제약이 작동하면 근사값. 낮아도 모델 편향·물리적 외삽 오차가 없음을 보장하지 않음."],
    ["예측 오차", "edge_deviation = EDGE input100 - INNER-only CPE prediction. reference eligible shot만 Wafer/Shot_prediction 및 제품 요약에 포함. 부호 있는 mean은 편향, RMSE는 편향과 산포를 함께 표현."],
    ["후보 예측", "불안정하지만 full rank인 참조의 후보 값은 Shot_reference.candidate_edge_RMSE_nm와 point의 inner_prediction/reference_residual에 보존. 주요 예측 통계에서는 제외."],
    ["coverage", "각 wafer/제품에서 예측 가능한 EDGE point / 전체 EDGE point. 커버리지와 shot 종류가 다른 제품의 RMSE를 단독 순위로 해석하지 않음."],
    ["빈 결과", "안쪽만/edge만 있는 shot, 안쪽 point 부족, 미식별 또는 불안정 참조는 상태와 개수 기록. 예측 불가를 오차 0으로 대체하지 않음."],
    ["측정 noise와 구분", "예측 오차에는 실제 edge 고유 패턴, 모델 불일치, 측정 noise, 외삽 오차가 함께 포함. 반복 계측 없이 이 성분들을 분리하지 않음."],
    ["통계", f"M3S=abs(mean)+3*std, ddof={EP_STD_DDOF}. Point 수 가중 wafer 통계이며 shot 평균의 평균이 아님. Product_summary는 wafer 통계의 중앙값."],
    ["단위", "통계·그래프 nm. Point의 input100/prediction/deviation 및 기존 fitting 값은 µm. 좌표·반경 µm."],
    ["그래프", "각 점은 wafer. 제품 색은 범례/축 이름에 표시. 03은 eligible prediction만 표시. 04의 회색 막대는 전체 edge shot, 유색 막대는 eligible shot."],
    ["반경 profile", "Eligible edge shot만 포함. 안쪽 residual은 in-sample, edge는 out-of-sample이므로 양쪽 차이를 순수 noise 차이로 해석하지 않음. Band는 wafer별 값의 25~75%, 신뢰구간이 아님."],
    ["원인 판정", "이번 분석은 edge-안쪽 차이의 관측 자료를 제공하며 최적 배율이나 원인 확정을 자동 판정하지 않음."],
], columns=["item", "description"])
ep_tables = {"Product_summary": ep_product_summary, "Wafer_input_comparison": ep_wafer_comparison, "Wafer_input_stats": ep_wafer_input,
             "Mixed_shot_input_comparison": ep_shot_comparison, "Shot_input_stats": ep_shot_input, "Wafer_prediction": ep_wafer_prediction, "Shot_prediction": ep_shot_prediction,
             "Shot_reference": ep_reference_diagnostics, "Reference_coverage": ep_prediction_coverage, "Reference_coefficients": ep_reference_coefficients,
             "Radial_profile": ep_radial_profiles, "Input_audit": ep_input_audit, "Input_files": pd.DataFrame(ep_input_inventory), "Notes": ep_notes}


def ep_excel_safe(frame):
    out = frame.copy()
    for col in out:
        if col.endswith("transn_seq") or col in ["apc_hist_index_no", "apc_trocs_hist_index_no"]:
            out[col] = out[col].map(lambda value: str(int(value)) if pd.notna(value) else "")
    return out


ep_excel_path = EP_OUTPUT_DIR / "OCO_Edge_Inner_Comparison.xlsx"
with pd.ExcelWriter(ep_excel_path, engine="openpyxl") as writer:
    for name, table in ep_tables.items():
        table.to_parquet(EP_OUTPUT_DIR / "tables" / f"{name}.parquet", index=False)
        export = ep_excel_safe(table)
        for offset in range(0, max(1, len(export)), 1048575):
            suffix = "" if len(export) <= 1048575 else f"_{offset//1048575+1}"
            export.iloc[offset:offset+1048575].to_excel(writer, sheet_name=name[:31-len(suffix)]+suffix, index=False)
ep_configuration = dict(sources=ep_run_sources, axes=EP_AXES, inner_radius_um=EP_INNER_RADIUS_UM, max_radius_um=EP_MAX_RADIUS_UM, std_ddof=EP_STD_DDOF,
    minimum_extra_inner_points=EP_MIN_EXTRA_INNER_POINTS, max_scaled_condition=EP_MAX_SCALED_CONDITION, max_edge_noise_gain=EP_MAX_EDGE_NOISE_GAIN,
    svd_rcond=EP_SVD_RCOND, radial_bins_mm=EP_RADIAL_BINS_MM.tolist(), point_unit="um", statistics_unit="nm", fixed_kmrc=True, edge_values_used_for_reference_fit=False)
(EP_OUTPUT_DIR / "comparison_settings.json").write_text(json.dumps(ep_configuration, ensure_ascii=False, indent=2), encoding="utf-8")
display(FileLink(os.path.relpath(ep_excel_path, Path.cwd()), result_html_prefix="제품별 edge/inner 비교 Excel: "))
for path in ep_plot_paths:
    if path.suffix == ".png":
        display(FileLink(os.path.relpath(path, Path.cwd()), result_html_prefix="그래프: "))
print("분석 완료:", EP_OUTPUT_DIR)
