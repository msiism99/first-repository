# OCO 외곽 배율 10~100% 비교 — PSM 추정과 M3S 평가 분리

이번 작업은 **기존 28번까지 완료, 29번 context 미실행** 상태를 기준으로 합니다. 원본 `MRC_PSM_decorrect.ipynb`는 수정하지 않습니다.

이번 수정에서는 **외곽 배율은 PSM(CPE38) 추정에만 사용**합니다. M3S는 **배율 적용 전 측정값에서 고정 K-MRC와 새 PSM fitting을 뺀 값**으로 계산합니다. 이전 버전은 배율이 적용된 회귀 residual을 M3S에도 사용했습니다. 기존 00~28번 저장 자료로 새 29~34번만 실행하면 됩니다.

직접 기존 셀을 수정한다면 **29번**의 `ES_SCALES`, **32번**의 평가 residual 생성 및 집계 대상, **33번**의 그래프 표기, **34번**의 결과 설명·실행 설정이 변경되었습니다. **30·31번 CPE solver는 동일**합니다.

- **추천:** `OCO_Edge_Sweep_29_34.ipynb`를 `C:\PHOTO_ANALYSIS\BASIC`에 놓고 29~34번을 순서대로 실행합니다. 새 커널에서도 실행할 수 있습니다. DB 조회 없이 기존 저장 자료만 읽습니다.
- 기존 노트북에 붙이려면 기존 29번 이후 context 셀을 빼고, 이 파일의 29~34번을 복사합니다.
- `MRC_PSM_decorrect_Edge_Sweep.ipynb`는 기존 00~28번을 그대로 두고 29~34번을 붙인 전체 파일입니다. 처음부터 실행할 때만 사용하고 개인 조회 조건은 옮기세요. 이 파일에는 기존 29~32 context 코드가 없습니다.

## 입력과 출력

입력은 `output_decorrect_notebook/stages/27_OCO_FINAL_POINTS.parquet`와 `output_decorrect_notebook/extension_settings.json`입니다. Parquet이 없거나 읽을 수 없으면 같은 이름의 전체 Excel을 사용합니다. `_sample_...xlsx`는 사용하지 않습니다.

출력은 BASIC 아래의 새 폴더 `output_oco_edge_scale_sweep`입니다. 기존 stages는 덮어쓰지 않습니다.

## 계산

반경은 실제 측정점의 wafer 좌표 기준이며, 기존 `radius` 컬럼을 사용합니다. 144mm **초과** point만 배율 변경 대상입니다. 144mm 경계는 안쪽 메트릭에 포함합니다.

```text
새 CPE 입력 = 저장된 raw_minus_total_fit + (새 배율 − 해당 point의 기존 배율) × 원래 X/Y 측정값
```

K-MRC 계수·fitting과 기적용 MRC/PSM fitting은 고정합니다. raw에 단순히 0.6/0.5를 곱하지 않습니다. 기본 배율은 10·20·30·40·50·60·70·80·90·100%입니다. 29번 `ES_SCALES`에서 변경합니다.

- 바깥 point가 있는 shot은 **안쪽 point까지 포함한 그 shot 전체**로 기존 CPE38을 다시 회귀합니다.
- 바깥 point가 없는 shot은 저장된 최종 residual을 그대로 재사용합니다.
- 각 배율의 전체 wafer 평가 residual은 재계산 shot의 **배율 적용 전 평가값**과 기존 shot의 결과를 합친 값입니다.
- 별도 edge step의 측정 영역이 바깥으로 정의되어 있다면 기존 edge 배율 비교와 같습니다. 단일 step 자료에서도 실제 반경으로 바깥 point를 골라 비교할 수 있습니다. 기존 배율이 100%이면 100% 결과를 기준 재현 확인에 사용합니다.
- 28번에 저장한 ridge/G-opt/span/virtual-grid 설정을 복원합니다. solver에는 별도 es_/ES_ 이름을 사용하여 기존 00~28의 함수·설정·결과 변수를 보존합니다.
- 저장된 결과와 같은 배율의 재계산 결과를 먼저 검증합니다. 기존 배율이 point별로 섞여 있으면 원래 배율 그대로 한 번 재계산해 검증합니다. 불일치하면 `Baseline_Parity_Failed.xlsx`를 저장하고 중단합니다.

## 메트릭

```text
metric_input = 새 CPE 입력 + (1 − 새 배율) × 원래 X/Y 측정값  [144mm 초과 point만 복원]
metric_residual = metric_input − 새 CPE_fit
M3S = abs(mean(metric_residual)) + 3 × std(metric_residual)
```

`metric_input`은 각 배율에서 동일한 배율 적용 전 입력으로 복원됩니다. 기적용 MRC/PSM decorrection과 K-MRC 제거는 유지하며, 새 CPE fitting 자체는 배율로 나누거나 다시 곱하지 않습니다. 기존 `real_residual`은 회귀 입력 기준 진단값으로 보존하지만 M3S에는 사용하지 않습니다. 100%에서는 `real_residual`과 `metric_residual`이 같습니다.

따라서 **144mm 이하 메트릭은 이전 계산과 같고, 전체 point 메트릭은 100%를 제외하고 달라질 수 있습니다.** 안쪽 point에도 외곽 배율에 따른 PSM 추정 변화는 전달됩니다.

기본은 표본 표준편차(ddof=1), 출력 단위는 nm입니다. `mean(abs(metric_residual))`가 아닙니다. X/Y를 따로 계산하며 29번 `ES_METRIC_AXES`를 `["x"]`로 바꾸면 X만 보고할 수 있습니다. CPE solver는 기존처럼 X/Y를 함께 처리합니다.

Wafer와 영향 shot 모두 두 영역의 통계를 제공합니다.

- `R_LE_144MM`: 실제 반경 ≤144mm인 point만 통계에 포함. 현재 사용 중인 메트릭.
- `ALL_POINTS`: 모든 point를 통계에 포함.

이 영역 제한은 **통계 계산에만** 적용합니다. 영역별로 회귀를 따로 하지 않습니다. 안쪽 point가 없는 shot은 안쪽 M3S가 NA이며 0으로 채우지 않습니다. 유효 residual이 1개뿐이면 ddof=1의 3σ 및 M3S도 NA입니다.

## 결과

`OCO_Edge_Scale_Sweep.xlsx`의 주요 시트:

| 시트 | 내용 |
|---|---|
| `Wafer_M3S` | 모든 wafer의 배율·X/Y·영역별 mean, sigma, 3sigma, M3S, point 수 |
| `Affected_shot_M3S` | 바깥 point가 있는 shot만 같은 메트릭. LOT/wafer/DieX/DieY/shot 중심 포함 |
| `Affected_shot_index` | 해당 shot 목록, 바깥 point 수, 실제 회귀에 유효한 바깥 point 수 |
| `Wafer_sensitivity` | 배율에 따른 wafer M3S 범위와 지정한 후보 중 최소 배율 |
| `Shot_sensitivity` | 영향 shot별 같은 비교 |
| `Baseline_parity` | 저장 결과와 현재 재계산 결과의 일치 확인 |
| `Wafer_index` | 그래프 wafer index와 실제 LOT/wafer 대응 |

`plots`에는 PNG/PDF 그래프를 저장합니다. Wafer별 M3S와 영향 shot별 M3S는 두 영역을 각각 패널로 표시하며 색·범례는 **PSM 회귀에 사용한 외곽 배율**입니다. 제목의 `unscaled evaluation`은 배율 적용 전 측정값으로 평가함을 뜻합니다. 안쪽 메트릭이 가장 민감한 shot 상위 25개 그래프도 제공합니다.

`tables`에는 전체 통계와 영향 shot의 배율별 CPE 계수·진단을 Parquet으로 저장합니다. 기본 `ES_SAVE_AFFECTED_POINTS=True`이면 `points`에 영향 shot의 point별 결과를 배율마다 저장합니다. 이 파일은 전체 wafer point 파일이 아니며, 영향 없는 shot은 기존 27번 결과를 사용합니다.

Point 파일의 `raw_minus_total_fit_x/y`와 `real_residual_x/y`는 배율이 적용된 회귀 기준 값입니다. **M3S를 검산하려면 `metric_residual_x/y`를 사용**하세요. `metric_input_x/y`에는 배율을 복원한 CPE 제거 전 입력을 저장합니다. 이 point별 수치의 단위는 기존과 같은 µm이고, 통계표에서만 nm로 환산합니다. 통계표의 `metric_basis=UNSCALED_MEASUREMENT`와 `sweep_settings.json`에도 평가 기준을 기록합니다.

## 검증

고정 K-MRC의 입력 갱신식, 원래 측정값 기반 평가 residual, 100%에서 회귀·평가 residual 일치, 안쪽 메트릭 불변, 측정점 반경 경계, 같은 shot 안쪽 point에 전달되는 CPE 변화, 영향 없는 shot 재사용, abs(mean) 및 표본 표준편차, 안쪽 point 0개, 기준 배율 재현, 저장 설정 복원, 10개 배율의 Excel/Parquet·그래프를 합성 자료와 실제 Jupyter 커널로 검증합니다. 생산 DB는 조회하지 않습니다.
