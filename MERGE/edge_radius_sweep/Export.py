# %% 09. Excel·전체 Parquet·실행 설정 저장
er_notes = pd.DataFrame([
    ["입력", "제품별 27_OCO_FINAL_POINTS 전체 Parquet/Excel + 같은 실행의 extension_settings.json. sample 파일 미사용. DB 조회 없음."],
    ["방향", "; ".join(f"{p}: {a[0].upper()}" for p,a in EP_PRODUCT_AXES.items())],
    ["CPE", "기존 X21/Y17 및 제품별 ridge/G-opt/span/virtual 설정. K-MRC·기적용 MRC/PSM decorrection은 고정. 회귀 point만 반경으로 제한."],
    ["배율", "144mm 초과의 원래 측정 X/Y 값에 10~100% 적용. CPE 입력=복원 input100+(배율-1)*원래 측정값. raw_minus_total_fit 자체에 배율을 곱하지 않음."],
    ["평가", "metric_residual=input100-CPE_fit. 모든 배율에서 평가 입력은 동일한 원래 값. 146~147mm도 회귀에서만 제외하고 평가에는 유지."],
    ["두 평가 영역", "R_LE_144MM: 공식 사용 메트릭. ALL_R_LE_147MM: 원래 반경 147mm 이하 모든 유효 측정점. 반경 미상/147mm 초과 제외 수는 Input_audit."],
    ["두 shot 범위", "ALL_SHOTS: 전체 wafer. MIXED_SHOTS: 144mm 안쪽과 바깥쪽 유효 측정점이 함께 있는 shot만. 같은 shot 집합을 모든 조건에서 유지."],
    ["Edge shot 선정", "실제 point 반경 >144mm가 있는 shot. 077252가 144mm 밖을 측정하는 현재 구성과 같은 선정. 단계명이 달라도 반경 기준으로 동작. 실제 measurement_source 개수도 있으면 기록."],
    ["실제 point 비율", "edge_point_fraction=측정 edge point/전체 측정 point. valid_edge_fraction은 선택 방향과 좌표가 유효한 point 기준. 이전 eligible/all shot 비율과 다름."],
    ["Mixed 입력 차이", "CPE 제거 전 100% 복원 입력의 같은 shot 안쪽/edge M3S 차이. Wafer 차이는 mixed shot들의 point를 모아 다시 계산. Shot M3S의 평균이 아님."],
    ["유효 mask", "선택한 방향의 input100 및 X/Y 좌표 유효. 비선택 방향의 결측은 무시. 제품별 현재 mask로 기준 재계산이 기존 27번과 다르면 중단하여 진단 파일 저장."],
    ["기준 검증", "원래 measurement_scale 그대로 CPE를 한 번 재계산. 입력에 CPE_fit/real_residual이 있으면 일치 검사. 컬럼이 없으면 not_in_input으로 기록하며 재현 검증을 주장하지 않음."],
    ["저표본 shot", "Para 축소 없이 기존 ridge 방식을 사용하며 n_train/rank/few_points/G-opt/span 상태 기록. 안쪽 참조용 point 부족 screening으로 CPE shot을 임의 제외하지 않음."],
    ["학습점 0개", "모델 재사용 없이 예측 NA. 평가 region에 예측 누락이 있으면 그 그룹 M3S도 NA(incomplete_prediction). 예측 가능한 일부 point로 축소해 개선처럼 표시하지 않음."],
    ["제품 평균 곡선", "각 scope/평가 영역에서 모든 반경×배율 조건의 M3S가 유효한 같은 wafer 집합만 평균. n_wafers_used/total 함께 기록. Wafer별 원자료는 그대로 보존."],
    ["M3S", f"abs(mean)+3*std, ddof={EP_STD_DDOF}. 최종 residual point를 모아 계산. mean(abs)나 shot 평균의 평균이 아님. 통계/그래프 nm, point 파일 µm."],
    ["반경 차이", "Radius_delta: 작은 회귀 반경 M3S - 큰 회귀 반경 M3S, 같은 wafer·배율·평가 영역. 음수면 작은 회귀 반경이 유리."],
    ["기존 최적값", "Previous_opt_loss: 제품별 reference_scale(VM50/VF20/VC40) 고정 대비 100% 차이. Wafer_best_scale은 별도로 각 wafer의 시험 후보 중 최소값(동률은 낮은 배율)."],
    ["해석", "146mm 제한은 point 수와 최외곽 공간 영역을 함께 바꿈. 개선을 순수 point 개수 효과로 단정하지 않음."],
    ["가상 grid", "제품별 저장된 virtual grid와 wafer clip 유지. Fallback grid도 원래 전체 shot 측정 범위로 고정하여 회귀 반경과 평가 범위 혼동 방지."],
    ["최적화", "Edge 없는 shot은 기준 CPE 재사용. 두 반경의 학습점이 같은 shot은 배율별 해 재사용. 좌표/lambda 기반 G-opt만 bounded cache; y 의존 계수/span은 재계산."],
    ["Excel 용량", "Shot_M3S 전체 long table과 전체 Shot_point_counts는 tables Parquet에 저장. Excel에는 edge shot count와 shot별 inner M3S 20조건 wide table을 제공. sample로 대체하지 않음."],
    ["Point 파일", "Product_NN_baseline_all_points는 전체 wafer 기준. 반경/배율별 파일은 edge가 있는 shot만 포함. 146~147mm 평가 residual도 저장. 번호는 00번 제품 순서."],
], columns=["item","description"])
er_tables = {"Sampling_summary":er_sampling_summary,"Wafer_point_counts":er_wafer_counts,"Wafer_edge_shot_counts":er_edge_shot_counts,"Shot_point_counts":er_shot_counts,
    "Mixed_wafer_input_comparison":er_wafer_gaps,"Mixed_shot_input_comparison":er_shot_gaps,"Product_curves":er_product_curves,"Wafer_M3S":er_wafer_metrics,"Shot_M3S":er_shot_metrics,
    "Radius_delta":er_radius_delta,"Wafer_best_scale":er_best_scales,"Previous_opt_loss":er_reference_loss,"Shot_inner_M3S_wide":er_shot_inner_wide,"Diagnostic_summary":er_diagnostic_summary,
    "Baseline_parity":er_parity,"Input_audit":er_input_audit,"Input_files":pd.DataFrame(er_inventory),"Wafer_index":er_wafer_index,"Notes":er_notes}
for name,table in er_tables.items():
    table.to_parquet(EP_OUTPUT_DIR/"tables"/f"{name}.parquet",index=False)
excel_tables = {name:table for name,table in er_tables.items() if name not in ["Shot_M3S","Shot_point_counts"]}
excel_tables["Edge_shot_point_counts"] = er_shot_counts.loc[er_shot_counts.n_edge.gt(0)]


def er_excel_safe(table):
    out=table.copy()
    for col in out:
        if col.endswith("transn_seq") or col in ["apc_hist_index_no","apc_trocs_hist_index_no"]:
            out[col]=out[col].map(lambda value:str(int(value)) if pd.notna(value) else "")
    return out


er_excel_path=EP_OUTPUT_DIR/"OCO_Edge_Radius_Sweep.xlsx"
with pd.ExcelWriter(er_excel_path,engine="openpyxl") as writer:
    for name,table in excel_tables.items():
        table=er_excel_safe(table)
        for offset in range(0,max(1,len(table)),1048575):
            suffix="" if len(table)<=1048575 else f"_{offset//1048575+1}"
            table.iloc[offset:offset+1048575].to_excel(writer,sheet_name=name[:31-len(suffix)]+suffix,index=False)
er_settings=dict(sources=er_sources,fit_radii_mm=ER_FIT_RADII_MM,scales=ER_SCALES,inner_radius_um=EP_INNER_RADIUS_UM,evaluation_max_radius_um=EP_MAX_RADIUS_UM,std_ddof=EP_STD_DDOF,
    fixed_kmrc=True,metric_basis="UNSCALED_INPUT_MINUS_CPE",strict_prediction_coverage=True,complete_wafer_cohort_for_curves=True,save_scenario_points=ER_SAVE_SCENARIO_POINTS)
(EP_OUTPUT_DIR/"sweep_settings.json").write_text(json.dumps(er_settings,ensure_ascii=False,indent=2),encoding="utf-8")
display(FileLink(os.path.relpath(er_excel_path,Path.cwd()),result_html_prefix="회귀 반경·edge 배율 비교 Excel: "))
for path in er_plot_paths:
    if path.suffix==".png":
        display(FileLink(os.path.relpath(path,Path.cwd()),result_html_prefix="그래프: "))
print("분석 완료:",EP_OUTPUT_DIR)
