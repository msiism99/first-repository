# OCO 제품별 edge / 안쪽 비교

`OCO_Edge_Inner_Comparison.ipynb`를 BASIC 폴더에 놓고 00→07번을 실행합니다. **00번 `EP_BASE_DIR`를 실제 BASIC 경로로 지정하세요. 기본은 `E:\PHOTO_ANALYSIS\BASIC`이며 `Path.cwd()`를 사용하지 않습니다.** 기존 `MRC_PSM_decorrect.ipynb` 뒤에 붙일 필요가 없는 독립 노트북입니다. 기존 코드/입력 파일을 변경하지 않고 DB도 조회하지 않습니다. Notebook 내부에 기존 CPE38 수치 solver를 포함했으므로 별도 `.py` 파일은 필요 없습니다.

이번 버전은 **KGVM·KHVF = Y만(Y17), PBVC(VC) = X만(X21)** 분석합니다. 00번 `EP_SOURCES`의 `axis`가 통계·배율 복원·유효 point 판정·참조 회귀·결과 저장 전체에 적용됩니다. 그래프는 각 제품의 해당 방향을 한 그림에서 비교하고 제품 이름에 `[X]`/`[Y]`를 표시합니다. 이전 버전과 결과가 섞이지 않도록 새 출력 폴더 `output_edge_inner_comparison_critical`을 사용합니다.

## 모아둘 입력

**제품마다 같은 실행에서 나온 두 파일**을 복사합니다.

1. `output_decorrect_notebook\stages\27_OCO_FINAL_POINTS.parquet` — 전체 OCO point, 좌표와 배율·K-MRC 제거 후 입력 포함.
2. `output_decorrect_notebook\extension_settings.json` — 해당 제품/실행의 ridge·G-opt·span·virtual 설정.

예시 폴더:

```text
E:\PHOTO_ANALYSIS\BASIC\
  OCO_Edge_Inner_Comparison.ipynb
  edge_comparison_input\
    KGVM\
      27_OCO_FINAL_POINTS.parquet
      extension_settings.json
    KHVF\
      27_OCO_FINAL_POINTS.parquet
      extension_settings.json
    PBVC\
      27_OCO_FINAL_POINTS.parquet
      extension_settings.json
```

00번 `EP_SOURCES`의 제품명·방향·폴더를 실제 자료에 맞게 수정합니다. 예: `{"product": "PBVC", "axis": "x", "folder": ...}`. 파일 폴더명 자체가 `VC`이면 folder만 해당 실제 경로로 바꿔도 됩니다. 폴더는 기존 `output_decorrect_notebook` 자체를 직접 지정해도 됩니다(그때는 point 파일을 `stages` 하위에서 읽음). Parquet 우선, 읽기 실패 시 같은 이름의 **전체** `.xlsx`로 대체하며 `_sample_...xlsx`는 읽지 않습니다. ADI 자료, 29~34 배율 sweep 결과, wafer context Excel은 필요 없습니다.

필수 point 컬럼은 `LOT_ID`, `Wafer`, `fcp_x/y`, `coordinate_X/Y`, `measurement_scale` 및 **선택한 방향의** `raw_minus_total_fit_x` 또는 `raw_minus_total_fit_y`입니다. 배율이 1이 아닌 유효 point는 같은 방향의 `X_reg_original` 또는 `Y_reg_original`도 필요합니다. 분석하지 않는 방향의 값은 없어도 됩니다. 반경은 기존 `radius`, 없거나 결측이면 `wf_x/y` 또는 `fcp+local` 좌표로 계산합니다. `DieX/DieY`와 photo 이력은 있으면 그대로 결과에 연결합니다. 기존 27번 전체 Parquet에는 이 값들이 포함됩니다. 한 LOT/wafer에 여러 photo 이력이 섞이면 실행별로 분리하도록 중단합니다.

`extension_settings.json`은 `kmrc_definition=OCO_E1_RAW_MINUS_ADI_RAW`인 최신 K-MRC 방식의 자료여야 합니다. 과거 OCO E2 자체 regression 결과는 이 연구와 섞지 않습니다.

## 분석 설정

- 제품마다 `EP_SOURCES`의 `axis`를 `"x"` 또는 `"y"`로 지정합니다. **X21 / Y17 CPE38을 그대로 사용**하며 para 축소·좌표 회전은 하지 않습니다. `EP_AXES`는 내부에서 자동 생성되므로 직접 수정하지 않습니다.
- 실제 측정점 반경 `<=144mm`는 INNER, `144mm 초과~147mm 이하`는 EDGE입니다. `EP_MAX_RADIUS_UM`으로 끝 반경을 바꿀 수 있습니다. 범위 밖·반경 미상 point 수는 `Input_audit`에 남깁니다.
- **선택한 방향 값과 X/Y 좌표**가 유효한 point를 참조 회귀에 사용합니다. 분석하지 않는 방향의 결측은 point를 제외하지 않습니다. 단순 입력 통계도 선택 방향의 유효값을 사용합니다.
- 안쪽 참조 최소 point는 X `21+2`, Y `17+2`; 기본 추가 point `EP_MIN_EXTRA_INNER_POINTS=2`입니다. 부족한 shot의 예측을 억지로 계산하지 않습니다.
- Full rank, scaled condition `<=1e6`, 실제 edge 예측 ridge noise gain `<=5`, 유한 예측, 저장된 G-opt 및 span 조건을 확인합니다. `EP_MAX_SCALED_CONDITION`과 `EP_MAX_EDGE_NOISE_GAIN`은 **연구용 진단 임계값이며 공정 spec이 아닙니다.**
- Full rank라도 진단 기준을 넘으면 후보 예측을 보존하되 주요 예측 통계에서는 제외합니다. ridge가 미식별 문제를 가려버리지 않도록 rank 부족은 예측하지 않습니다.

## 계산

```text
input100 = 저장된 raw_minus_total_fit + (1 − measurement_scale) × 원래 X/Y 측정값
```

측정값의 배율만 복원합니다. 기적용 MRC/PSM decorrection과 고정 K-MRC는 유지합니다. `raw_minus_total_fit` 자체를 역배율로 나누지 않습니다.

첫 번째 비교는 각 wafer의 INNER/EDGE `input100`의 mean, 3σ, M3S, RMSE입니다. **CPE 제거 전 값**이므로 기존 최종 residual M3S와 다릅니다. 서로 다른 위치의 실제 변형 패턴이 포함되므로 edge 측정 noise만의 크기로 해석할 수 없습니다. 같은 shot 안에서 안쪽과 edge가 함께 있는 자료의 통계도 별도 저장합니다.

두 번째 비교는 **같은 shot의 INNER 유효 point만**으로 기존 CPE38을 회귀하고 실제 EDGE 좌표에 예측합니다.

```text
edge_deviation = EDGE input100 − INNER-only CPE38 prediction at EDGE coordinates
```

부호 있는 mean은 편향, 3σ는 산포, RMSE는 편향과 산포를 함께 표현합니다. EDGE 측정값은 이 참조 회귀와 ridge/span 선택에 사용하지 않습니다. 가상 grid는 원래 shot metadata(또는 전체 유효 측정 좌표 범위)를 사용하고 wafer clip도 저장된 설정대로 유지합니다. 이에 더해 **실제 EDGE 좌표의 noise gain을 별도 진단**합니다. Clip된 grid에서 G-opt가 좋아도 EDGE 외삽이 안정적이라는 뜻은 아닙니다.

Noise gain은 독립·동일 측정 noise에 대한 선형 ridge 예측 전달 행렬의 행 norm입니다. Box 제약이 작동하면 근사값이고, 작아도 모델 편향이나 물리적 외삽 오차를 보장하지 않습니다. 예측 오차에는 실제 edge 고유 패턴, 측정 noise, CPE 모델 불일치, 외삽 오차가 함께 들어갑니다. 이 결과만으로 원인을 확정하거나 최적 배율을 자동 판정하지 않습니다.

## 결과를 볼 순서

`output_edge_inner_comparison_critical\OCO_Edge_Inner_Comparison.xlsx`:

| 시트 | 확인할 내용 |
|---|---|
| `Product_summary` | 제품별 wafer 수, 안쪽·edge 입력 M3S 중앙값, edge 예측 오차 RMSE 중앙값, 예측 coverage |
| `Wafer_input_comparison` | 같은 wafer의 안쪽·edge 입력 mean/3σ/M3S 비교 |
| `Mixed_shot_input_comparison` | 같은 shot에 안쪽·edge가 함께 있을 때의 입력 통계 비교, DieX/DieY 포함 |
| `Wafer_prediction` | 안정적인 참조를 확보한 edge point의 wafer별 예측 오차 mean/3σ/RMSE, point 수·coverage |
| `Shot_prediction` | 위 예측 오차를 shot별로 정리, DieX/DieY 포함 |
| `Shot_reference` | 각 edge shot의 안쪽 point 수, rank/condition, G-opt/λ/span, 예측 제외 이유, 후보 RMSE |
| `Reference_coverage` | 제품별 참조 가능/제외 사유별 shot 수 |
| `Radial_profile` | wafer별 반경 구간의 참조 residual 통계 |
| `Input_audit` | 읽은 point 수, 반경 제외 수, 배율 복원 대상 수 |

안쪽 point가 부족하거나 없는 edge shot은 coverage에서 제외되고 예측 오차는 NA입니다. 0으로 대체하지 않습니다. **Coverage가 낮거나 제품마다 포함 shot이 다르면 예측 RMSE만으로 순위를 매기지 마세요.** 입력 통계는 참조 예측이 불가능해도 계산합니다. 입력 통계는 전체 wafer를 대상으로 하고, 참조 예측은 edge가 있는 shot만 대상으로 합니다.

`plots`의 PNG/PDF:

1. `01_Input_M3S_CRITICAL`: 제품별 안쪽·edge 입력 M3S 분포, 한 점=wafer. KGVM[Y], KHVF[Y], PBVC[X].
2. `02_Edge_vs_inner_input_CRITICAL`: 같은 wafer의 안쪽 M3S 대 edge M3S, 제품·방향별 색·범례.
3. `03_Edge_prediction_error_CRITICAL`: 제품별 edge 예측 RMSE와 해당 방향의 signed mean. 안정적인 참조만 표시.
4. `04_Reference_coverage_CRITICAL`: 참조 가능한 shot 비율과 noise gain 대비 후보 예측 오차.
5. `05_Radial_reference_error_CRITICAL`: 반경별 참조 residual RMSE. 선은 wafer 중앙값, band는 25~75% 범위. 안쪽은 회귀에 사용한 값, edge는 예측값이므로 차이를 순수 noise 차이로 해석하지 않습니다.

`tables`에는 전체 통계 Parquet, `points`에는 edge가 포함된 shot의 point별 복원 입력·예측·오차·참조 상태를 제품별로 저장합니다. 파일 `Product_01/02/03_edge_shots.parquet`의 번호는 00번 `EP_SOURCES` 순서입니다. 제품명은 `product`, 분석 방향은 `analysis_axis`에 기록하고 해당 방향의 값만 저장합니다. Excel 통계표에는 실제 방향을 `axis` 컬럼에 유지합니다. `input100`, `inner_prediction`, `reference_residual`, `edge_deviation`은 **µm**, 통계표·그래프만 **nm**입니다.

`reference_residual`은 full-rank 후보 참조의 오차(불안정 후보 포함), `edge_deviation`은 주요 통계에 사용한 eligible EDGE point의 오차입니다. 제품별 원래 설정과 분석 임계값은 `comparison_settings.json`에 기록합니다.

기본 표준편차는 ddof=1, `M3S=abs(mean)+3*std`입니다. Product_summary는 wafer별 값의 중앙값이며 모든 point를 한꺼번에 합친 통계가 아닙니다. 개별 wafer 통계는 해당 wafer의 point를 합쳐 계산합니다. 최소 point 때문에 계산할 수 없는 통계는 NA입니다.

## 검증

합성 자료 기반 9개 테스트: 배율 복원과 반경 경계, 알려진 edge-only 오차 복원, edge 값이 참조 추정에 들어가지 않음, rank/noise screening과 NA 처리, 제품별 설정 독립 복원, 전체 Excel 대체와 sample 제외, 기존 solver와 실제 ridge/span 제약 작동 결과 일치, 제품별 Y/Y/X 방향 및 17/17/21 para 적용, 비선택 방향이 아예 없는 입력, 임시 커널 폴더와 다른 명시적 기준 경로, 3제품 및 edge 없는 경우의 실제 Jupyter 실행·Excel/Parquet/통합 그래프 저장을 확인했습니다. 실제 사내 자료나 DB는 사용하지 않았습니다.
