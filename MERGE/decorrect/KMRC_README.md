# ADI/OCO E1 차이 기반 K-MRC → OCO CPE38

`MRC_PSM_decorrect.ipynb`를 `C:\PHOTO_ANALYSIS\BASIC`에 놓고 개인 조회 조건을 옮긴 뒤 커널을 재시작하여 00~32를 순서대로 실행합니다. 결과는 기존 `output_decorrect_notebook/stages`에 저장합니다. 기존 데이터 파일을 자동 삭제하지 않습니다.

## 이번 계산 흐름

1. 기존 step의 OCO E1과 최종 분석 그룹을 함께 보존합니다. 분석 그룹은 step 코드의 3~5번째 자리가 077이면 E2, 그 외이면 E1입니다.
2. 기존 MRC/PSM을 각 측정 위치에서 decorrect하여 ADI/OCO raw를 만듭니다. E1에도 같은 기적용 MRC/PSM 모델을 E1 좌표에서 평가합니다.
3. ADI raw 전체를 기존 축당 19계수(WK10+RK9)로 wafer별 회귀합니다. **ADI에는 반경 제한을 적용하지 않습니다.**
4. OCO의 기존 step E1 raw만 동일 모델로 회귀합니다. 별도 edge step의 자료는 기준 회귀에 사용하지 않습니다. 두 step이 같은 단일 step 모드이면 E1 기준 자료만 실제 측정점 반경 ≤144000 µm로 제한합니다.
5. `K_MRC = K_OCO_E1 − K_ADI`를 구합니다. ADI를 OCO 위치로 upsampling하는 작업은 포함하지 않습니다.
6. 최종 분석 그룹의 측정 좌표에 K-MRC를 fitting하여 `raw_minus_total_fit = raw − K_MRC_fit`을 만듭니다. 이때 OCO 분석값을 다시 자체 WK/RK 회귀해 빼지 않습니다.
7. 이 잔차로 기존 shot별 CPE38(X21/Y17), ridge/G-opt/span 설정을 적용하고 최종 residual을 저장합니다.

ADI 자체의 WK/RK 제거와 CPE 분석은 기존대로 유지합니다. OCO에서 K-MRC를 계산할 ADI/E1 자료가 없거나 유효 point가 19개 미만이면 해당 wafer를 OCO 후속 분석에서 제외합니다. Rank 진단은 기록하며 기존 최소제곱 모델의 rank-deficient 처리 방식은 유지합니다.

## 00번 설정

```python
cfg.target_mstepseq_oco = "VC077251"
cfg.target_mstepseq_oco_edge = "VC077252"
cfg.include_oco_edge = True
cfg.oco_edge_scale = 0.5
cfg.kmrc_e1_radius_um = 144000.0
```

- 두 step이 다르면 별도 edge 이력을 조회합니다. edge RAWDATA의 X/Y에만 조회 직후 배율 0.5를 곱하며, 원래 값과 출처를 보존합니다. 077 계열의 edge step에서는 분석용 E2만 조회합니다.
- 두 step이 같으면 한 번만 조회합니다. 원래 측정값을 배율 1로 사용하고 두 번 합치지 않습니다. K-MRC용 OCO E1만 반경 제한하고 최종 PSM/CPE 입력의 147mm 측정 영역은 유지합니다.
- `include_oco_edge=False`일 때도 단일 step 방식입니다. OCO E1 기준 자료에 반경 제한을 적용합니다.
- 반경은 shot 중심이 아니라 `sqrt(wf_x**2 + wf_y**2)`인 기존 실제 측정점 `radius` 컬럼을 사용합니다. 별도 step 모드에서는 측정 영역 자체가 나뉘므로 E1에 추가 반경 필터를 걸지 않습니다.
- 조회 반환값이 Categorical이어도 X/Y를 float로 변환한 후 배율을 적용합니다. 좌표·TESTDATA·PERSHOT·보정 계수에는 배율을 적용하지 않습니다.

## 기존 파일에서 교체할 셀

`KMRC_Replacement_Cells.ipynb`는 독립 실행용이 아니라 교체할 셀 모음입니다.

| 번호 | 변경 |
|---|---|
| 00 | 동일 step 허용, edge 기본 배율 0.5, E1 기준 반경 설정 |
| 04 | 동일 step 중복 조회 방지, 별도 edge 이력 매칭 |
| 05 | 기존 E1/E2 유지, edge 분석 그룹만 추가, 배율 적용 |
| 06 | OCO는 기존/edge 이력·data_kind·TEST 그룹별 최신 batch 선택. 늦게 측정한 E2 때문에 E1이 사라지지 않게 처리 |
| 08 | OCO E1을 버리지 않고 기준·분석 역할을 표시하며 좌표 연결 |
| 15 | decorrect raw에서 OCO 분석 입력과 E1 K-MRC 입력 분리 |
| 20 | 기존 19계수 모델 유지, 두 계수 차이의 fitting 함수 추가 |
| 21 | ADI/E1 회귀 → K-MRC 차이 → 분석 raw에 적용, 부적격 wafer 제외 |
| 28 | K-MRC 정의, step·배율·반경 설정을 extension_settings에 기록 |

00번은 import 셀을 유지하고 설정 셀만 교체합니다. 위 셀을 교체한 뒤 커널 재시작 → 00번부터 다시 실행합니다. 기존 15번/19번 저장 자료에는 E1이 없을 수 있으므로 이전 파일만으로 새 K-MRC를 복원할 수는 없습니다.

## 주요 확인 파일

| 파일 | 내용 |
|---|---|
| `08_OCO_EDGE_COVERAGE` | 최종 분석 그룹의 main/edge point 수 |
| `15_OCO_ALL_GROUPS_RAW` | MRC/PSM decorrect 및 MMO_MRC_EQP 필터 후 보존한 모든 OCO 그룹 |
| `15_OCO_FINAL` | 최종 PSM/CPE 분석 대상 raw(E2 또는 E1), K-MRC 적용 전 |
| `15_OCO_E1_KMRC_INPUT` | 실제 K-MRC 기준 회귀에 넣는 main E1 raw |
| `15_OCO_MODEL_INPUT_COUNTS` | wafer별 반경 적용 전후 E1 수 및 분석 point 수 |
| `21_ADI_WK_WAFER_COEFFICIENTS`, `21_ADI_RK_WAFER_COEFFICIENTS` | 기존 ADI raw 회귀 계수 |
| `21_OCO_E1_WAFER_COEFFICIENTS` | OCO main E1 raw 회귀 계수 |
| `21_KMRC_WAFER_COEFFICIENTS` | OCO E1 − ADI의 19계수/축, source별 유효 point 수 |
| `21_OCO_WK_RK_REMOVED` | 분석 raw에서 K-MRC fitting을 제거한 point별 결과 |
| `21_OCO_WK_RK_WAFER_DIAGNOSTICS` | 적용/제외 상태와 ADI/E1의 rank 진단 |
| `21_KMRC_EXCLUDED_OCO_POINTS` | 제외 wafer의 분석 point와 제외 이유 |
| `27_OCO_FINAL_POINTS`, `28_OCO_FINAL_SHOT_DATA` | K-MRC 제거 후 CPE38을 적용한 최종 결과 |

호환성을 위해 OCO의 기존 `wk_fit/rk_fit/total_fit` 컬럼명을 유지하지만 값은 **K-MRC의 WK/RK fitting**입니다. `21_OCO_WK/RK_WAFER_COEFFICIENTS`도 K-MRC 계수입니다. E1 자체 회귀 계수는 별도 `21_OCO_E1_WAFER_COEFFICIENTS`를 확인하세요. DieX/DieY는 21번부터 27/28번 shot 통계·CPE 계수·진단으로 이어집니다.

최종 분해식은 `raw = KMRC_WK_fit + KMRC_RK_fit + CPE_fit + real_residual`입니다. K-MRC 단계에서 제외된 wafer는 이 분해/CPE 결과에 포함되지 않습니다.

## 검증

합성 데이터로 알려진 계수 차이·부호·다른 측정 좌표에서의 fitting, ADI 반경 무제한, 단일 step E1 반경, edge 제외, 누락 기준 wafer 제외, 동일 step 단일 조회, X/Y 배율과 Categorical 입력, 077 및 비077의 전체 노트북 흐름을 검증합니다. 사내 DB는 직접 실행하지 않습니다.
