# OCO edge 회귀 반경 146/147mm × 배율 10~100% 비교

독립 노트북 `OCO_Edge_Radius_Sweep.ipynb`를 BASIC 폴더에 놓고 **00번에서 경로를 지정한 뒤 00→09번을 실행**합니다. 기본 `EP_BASE_DIR=Path(r"E:\PHOTO_ANALYSIS\BASIC")`입니다. 커널의 임시 작업 폴더를 기준으로 삼지 않습니다. 기존 MRC_PSM_decorrect 또는 앞선 edge 비교 notebook은 수정하지 않습니다. Notebook에 수치 함수와 입출력 코드가 모두 포함되어 별도 `.py` 파일·DB 접속은 필요 없습니다.

## 입력

제품마다 같은 실행에서 저장한 두 파일을 그대로 사용합니다. 이전 제품별 edge 비교 입력과 같습니다.

- `27_OCO_FINAL_POINTS.parquet`: 기존 `output_decorrect_notebook\stages`에 있는 전체 point 자료.
- `extension_settings.json`: 같은 실행의 `output_decorrect_notebook`에 있는 CPE 설정.

00번 `EP_SOURCES`의 folder에 두 파일을 모아 둔 폴더 또는 기존 `output_decorrect_notebook` 경로를 지정하세요. Parquet 우선, 읽기 실패 시 같은 이름의 전체 Excel을 사용합니다. `_sample` 파일은 입력으로 사용하지 않습니다. ADI 파일과 이전 sweep 결과는 불필요합니다.

기본 폴더는 `BASIC\edge_comparison_input\KGVM`, `KHVF`, `PBVC`이며 각각 두 파일을 둡니다. **KGVM·KHVF는 Y만(Y17), PBVC(VC)는 X만(X21)** 사용합니다. 실제 폴더명과 제품명은 수정 가능하며 제품마다 axis와 reference_scale도 지정합니다.

필수 point 컬럼: LOT_ID, Wafer, fcp_x/y, coordinate_X/Y, measurement_scale, 선택 방향의 raw_minus_total_fit. 배율 변경용 유효 edge point에는 원래 X_reg_original 또는 Y_reg_original이 필요합니다(100% 저장 자료도 배율을 변경하려면 원래 측정값이 필요). 반경은 radius, 결측 시 wf_x/y 또는 fcp+local에서 계산합니다. DieX/DieY와 photo 이력은 있으면 보존합니다. 비선택 방향 값은 없어도 됩니다. 한 LOT/wafer에 여러 photo 이력이 섞이면 분리하도록 중단합니다.

설정은 최신 `kmrc_definition=OCO_E1_RAW_MINUS_ADI_RAW` 방식이어야 합니다. 과거 E2 자체 regression 결과와 섞지 않습니다.

## 비교 조건

- `ER_FIT_RADII_MM=[146.,147.]`: CPE 회귀에 사용하는 **실제 측정점 반경**의 상한. 146mm 경계 포함. 144mm 안쪽은 두 조건에서 모두 유지.
- `ER_SCALES=[i/10 for i in range(1,11)]`: 144mm 초과 측정값에 적용할 10개 배율. 제품별 총 20조건.
- `reference_scale`: 앞서 관측한 제품별 최적 배율. VM .5, VF .2, VC .4. 100% 열화와 입력 지표 관계를 확인하는 고정 참고값이며 새 최적값을 강제하지 않음.
- `EP_STD_DDOF=1`: M3S = abs(mean)+3*std. 최종 통계는 nm, point 값은 µm.
- `ER_SAVE_SCENARIO_POINTS=True`: edge가 있는 shot의 point 결과를 조건별 Parquet 저장.
- `ER_SAVE_COEFFICIENTS=True`: 선택 방향의 CPE 계수와 lambda를 조건별 저장.

```text
input100 = 저장된 raw_minus_total_fit + (1 − measurement_scale) × 원래 측정값
회귀 입력 = input100 + (새 edge 배율 − 1) × 원래 측정값  [144mm 초과만 변경]
평가 residual = input100 − 새 CPE_fit
```

K-MRC를 다시 계산/적용하지 않습니다. 기적용 MRC/PSM decorrection 및 K-MRC fitting은 고정합니다. raw_minus_total_fit 자체를 배율로 곱하거나 나누지 않습니다. **146~147mm는 146mm 조건의 회귀에서만 제외하고 같은 모델로 예측하여 평가에는 남깁니다.**

전체 평가 영역은 항상 원래 <=147mm point 집합이며, 공식 메트릭은 그중 <=144mm입니다. >147mm 및 반경 미상 제외 수는 Input_audit에 기록합니다. 회귀 반경별로 평가 point를 함께 줄이지 않습니다.

기존 CPE38 X21/Y17·제품별 ridge/G-opt/span/virtual grid 설정을 복원합니다. 146mm 제한으로 point가 줄어도 para 수를 줄이지 않습니다. n_train, rank, few_points, G-opt, lambda, span 상태를 진단에 남깁니다. 안쪽 참조 모델의 screening 기준으로 실제 CPE 회귀 shot을 임의로 버리지 않습니다.

학습 point가 0개이면 새 모델은 예측 NA입니다. **해당 평가 그룹에 원래 유효 입력 point의 예측 누락이 하나라도 있으면 M3S도 NA**로 표시합니다. 예를 들어 146mm 밖에만 측정점이 있는 shot은 146mm 회귀에서 예측할 수 없으므로 전체 <=147mm M3S가 NA일 수 있습니다. 그 shot에 <=144mm point가 없다면 공식 안쪽 메트릭에는 영향이 없습니다. 예측 가능한 일부 point로 줄여 M3S가 좋아 보이게 하지 않습니다.

## 동일 mixed shot 차이와 실제 sampling 비율

**Edge point가 있는 shot**은 실제 반경 >144mm 측정점이 있는 shot입니다. 현재 077252 영역과 같은 선정이며, 별도 edge step이 없는 제품에도 적용됩니다. measurement_source가 있으면 oco_edge source point 수도 별도 기록합니다.

- Wafer/shot point 수: 전체, <=144, >144, >144~146, >146~147, 유효 point 수.
- `edge_point_fraction`: 실제 edge 측정 point / 전체 측정 point.
- `valid_edge_fraction`: 선택 방향 및 좌표가 유효한 edge point / 전체 유효 point.
- `inner_mixed_fraction`: 안쪽 유효 point 중 mixed shot에 속한 비율.
- `Wafer_edge_shot_counts`: edge가 있는 shot만 모았을 때의 point 비율.

**Mixed shot**은 같은 shot 안쪽과 edge에 유효 측정점이 함께 있는 shot입니다. 배율 적용 전 100% 복원 입력으로 각각 M3S를 계산합니다. `delta_M3S_edge_minus_inner_nm`은 edge−inner입니다. 양쪽 std를 계산할 point가 부족하면 comparable=False이며 차이는 NA입니다. Wafer 차이는 해당 mixed shot들의 point를 모아 다시 계산하며, shot M3S의 평균이 아닙니다. Pure edge shot은 이 입력 차이 비교에서는 제외하지만 실제 CPE 시뮬레이션에는 포함합니다.

## 기준 재현과 계산 최적화

먼저 원래 measurement_scale 그대로 CPE를 재계산합니다. 입력에 CPE_fit/real_residual이 있으면 선택 방향의 재현 여부를 검사합니다. 없으면 not_in_input으로 기록합니다. 불일치하면 Baseline_Parity_Failed 파일과 함께 중단합니다. 같은 실행의 설정인지, 비선택 방향 결측 때문에 기존 공동 mask와 현재 mask가 달라졌는지, 기존 회귀에 147mm 밖 point가 포함되었는지 확인하세요. 기준 검증에서는 배율 적용된 기존 real_residual을 사용하고, 새로운 M3S는 배율 복원 후 평가 residual을 사용합니다.

Edge 없는 shot은 기준 CPE를 재사용합니다. 두 회귀 반경에서 학습 point가 같으면 배율별 해를 재사용합니다. 좌표/lambda로만 결정되는 G-opt 계산을 제한된 메모리 캐시에 저장하며, 측정값에 의존하는 계수·span 계산은 원래 solver 그대로 수행합니다. 가상 grid/wafer clip은 저장 설정을 유지하고, fallback grid도 원래 전체 shot 측정 범위로 유지하여 회귀 반경에 따라 평가 grid가 축소되지 않게 합니다.

## 결과를 볼 순서

출력: `BASIC\output_edge_radius_sweep\OCO_Edge_Radius_Sweep.xlsx`.

| 시트 | 내용 |
|---|---|
| `Sampling_summary` | 실제 wafer별 edge point 비율 요약 |
| `Wafer_point_counts` | 전체 wafer의 실제 point 수·edge 비율 |
| `Wafer_edge_shot_counts` | Edge가 있는 shot만 모은 point 비율 |
| `Mixed_shot_input_comparison` | 같은 mixed shot의 안쪽/edge 입력 통계 차이, DieX/Y |
| `Mixed_wafer_input_comparison` | Mixed shot들만 모은 wafer별 입력 차이 |
| `Product_curves` | 반경×배율별 제품 평균 M3S와 사용 wafer 수 |
| `Wafer_M3S` | Wafer별 20조건 mean/3sigma/M3S 및 coverage |
| `Radius_delta` | 같은 wafer·배율의 작은 반경−큰 반경 M3S 차이. 음수면 작은 반경 유리 |
| `Previous_opt_loss` | 100%−제품별 기존 고정 최적 배율의 M3S 차이, mean·3sigma 변화, 입력 차이·point 비율 연결 |
| `Wafer_best_scale` | 각 wafer의 시험 후보 중 최소 배율. 10개가 모두 유효할 때만 판정하며 동률은 낮은 배율 |
| `Shot_inner_M3S_wide` | Edge shot별 안쪽 M3S를 20조건 열로 비교 |
| `Diagnostic_summary` | CPE 상태·rank 부족·few point 여부별 shot 수 |
| `Baseline_parity`, `Input_audit` | 기존 결과 재현 및 입력 point 제외 내역 |

평가 scope: ALL_SHOTS는 전체 wafer, MIXED_SHOTS는 안쪽·edge가 함께 있는 고정 shot 집합. 평가 region: R_LE_144MM 및 ALL_R_LE_147MM. 제품 평균 곡선은 **각 scope/region에서 모든 20조건이 유효한 동일 wafer 집합**만 사용합니다. N_used/N_total을 같이 확인하세요. 개별 wafer 통계는 삭제하지 않습니다.

`plots`의 PNG/PDF:

1. `01_Actual_edge_point_fraction`: wafer 전체 및 edge shot 내 실제 edge point 비율.
2. `02_Mixed_shot_input_gap`: 같은 mixed shot 및 mixed shot을 모은 wafer의 edge−inner 입력 M3S.
3. `03_Product_M3S_Inner`: 공식 <=144mm 메트릭의 제품별 배율 곡선, 146/147mm 비교.
4. `04_Product_M3S_Mixed_Inner`: mixed shot 안쪽 point만 같은 비교.
5. `05_Product_M3S_All147`: 동일 전체 <=147mm 평가점에서 비교.
6. `06_Paired_radius_difference`: 동일 wafer의 작은 회귀 반경−큰 회귀 반경 안쪽 M3S 변화.
7. `07_Input_gap_fraction_vs_100pct_loss`: 실제 edge 비율/동일 mixed shot 차이와 100% 열화의 관계.
8. `08_Wafer_M3S_Product_01/02/03`: wafer별 20조건 M3S, index는 Wafer_index 시트.

`tables`에는 모든 통계의 전체 Parquet을 저장합니다. **Shot_M3S long table은 Parquet에만 저장**하고 Excel에는 shot별 안쪽 M3S 20조건을 wide 형태로 제공합니다. 전체 Shot_point_counts도 Parquet에 저장하며 Excel은 edge shot만 포함합니다. Sample로 대체하지 않습니다. 행이 Excel 한도를 넘으면 시트를 나눕니다.

`points`에는 전체 wafer 기준 point 파일 한 개와, edge shot만 포함한 반경/배율별 point 파일을 제품별로 저장합니다. `used_for_fit=False`인 146~147mm point도 예측 및 metric_residual을 확인할 수 있습니다. Point 단위는 µm입니다. `cases`에는 조건별 wafer/shot 통계, `coefficients`에는 CPE 계수/lambda, `diagnostics`에는 shot별 실제 회귀 상태를 저장합니다. 제품 번호는 00번 입력 순서이며 파일 내부 product/analysis_axis로 확인합니다.

이번 실험은 최외곽 공간 영역과 point 개수를 함께 바꾸므로 순수 point 수 효과로 해석하지 않습니다. 최적 배율은 시험 후보 중 결과이며 rework 판정 기준을 자동 결정하지 않습니다.

## 검증

합성 자료 기반 7개 테스트로 기존 native 전체 회귀와 영향 shot만 재계산한 결과의 일치, 기존 CPE 기준 재현, 배율 복원·고정 보정 유지, 144/146/147mm 경계, 같은 shot의 입력 차이와 실제 point 비율, 146~147mm 제외 point 예측, 학습점 0개 및 엄격한 평가 coverage, G-opt 캐시 재실행, 3제품 20조건과 edge 없는 경우의 실제 Jupyter 실행·Excel/Parquet/그래프 저장을 확인했습니다. 실제 사내 데이터나 DB를 사용하지 않았습니다.
