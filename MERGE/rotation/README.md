# Critical X: 기존 X21 / 회전 Y17 비교

`CPE_Critical_Rotation.ipynb`를 `C:\PHOTO_ANALYSIS\BASIC`에 놓고 00~11을 순서대로 실행합니다. 각 셀은 직접 수정할 수 있고 외부 Python 파일을 import하지 않습니다. 기존 노트북·stage는 변경하지 않습니다.

## 입력과 설정

- `output_decorrect_notebook/stages/21_ADI_WK_RK_REMOVED.parquet`
- `output_decorrect_notebook/stages/21_OCO_WK_RK_REMOVED.parquet`
- 전체 Parquet 우선, 같은 이름의 전체 Excel 대체. sample Excel은 제외합니다.
- 21 파일이 없으면 `27_{mode}_FINAL_POINTS`의 동일한 CPE 직전 컬럼을 읽습니다.
- 실제 입력은 **raw에서 wafer WK/RK를 제거한 `raw_minus_total_fit_x`**입니다. Y 오차는 사용하지 않습니다.
- `MODES`는 기본 ADI/OCO 모두입니다. 하나만 원하면 00에서 수정합니다.
- **문제 제품만 선택하도록 `FILTERS` / `FILTERS_BY_MODE`를 지정하세요.** 예: `FILTERS={"LOT_ID":["LOT_A"]}`. 필터가 비어 있으면 전체를 critical X 제품으로 처리합니다.
- 기존 `output_wafer_context/wafer_context.parquet` 또는 전체 Excel이 있으면 전체 wafer 키로 연결합니다. 컬럼명은 `tables/02_input_columns.csv`에서 확인합니다.
- `output_decorrect_notebook/extension_settings.json`이 있으면 원본의 ridge/G-opt/span 설정을 복원합니다. 없으면 원본 노트북의 기본값을 사용합니다. `SOLVER_OVERRIDES`로 변경할 수 있습니다.

## 비교 방식

1. 원래 좌표의 X21 모델로 같은 X point를 재회귀합니다.
2. `u=-s*y, v=s*x`, `error_v=s*error_x`로 변환합니다. `s=+1`은 +90°, `s=-1`은 -90°입니다.
3. 회전 좌표에서 Y17 모델과 Y측 ridge/span 설정으로 회귀합니다.
4. `fit_x=s*fit_v`로 원래 장비 X에 복원하고 `residual_x=input_x-fit_x`를 계산합니다.
5. 두 결과의 제거 CPE / 최종 residual을 wafer·shot별로 비교합니다.

이 과정은 이미 제거한 WK/RK를 재계산하거나 wafer 전체를 재회전하는 과정이 아닙니다. **CPE 항 구성의 방향을 바꾸는 비교**입니다. wafer 경계에서 먼저 잘라낸 원래 virtual point를 그대로 회전하여 G-opt와 span을 평가하므로 edge shot에서도 동일한 물리 위치를 사용합니다.

두 모델은 같은 유효 X point를 사용합니다. Y 결측 때문에 X point를 제외하지 않습니다. 원래 회귀가 X/Y 공통 유효 조건을 썼고 Y에 결측이 있었다면, 이 노트북의 X21 재회귀와 과거 저장 CPE 값은 달라질 수 있습니다.

X21과 회전 Y17은 포함관계가 아닙니다. 공통 단항식 12개, X21 전용 9개, 회전 Y17 전용 5개입니다. `07_TERM_MAPPING`에 원래 장비 좌표에서의 차수·부호·스케일·제약을 저장합니다. 예를 들어 원래 `x^4`는 X21에 없고 회전 Y17에 있습니다.

기본 native 비교에는 **항 구성과 X/Y별 제약 설정 차이가 모두 포함**됩니다. 별도 `OLS_DIAGNOSTIC`은 ridge/span 없이 설명력 차이를 봅니다. 동일한 학습 point의 결과이며, point가 부족하거나 rank가 낮은 shot의 외삽 능력을 보장하지 않습니다. rank/condition/G-opt/span 위반을 함께 저장합니다.

## 결과

`C:\PHOTO_ANALYSIS\BASIC\output_cpe_critical_rotation`

- **`CPE_Critical_Rotation_Comparison.xlsx`**: wafer/shot 비교, 통계, term별 shot 산포, 진단, 항 대응표.
- `tables/08_{mode}_ROTATION_POINTS.parquet`: 입력·두 모델의 제거 CPE와 최종 residual. CSV도 전체 저장합니다.
- `tables/08_{mode}_SHOT_COEFFICIENTS.parquet`: shot별 native 계수, 원래 X 단항식 부호 기준 nm 기여량, virtual point span, lambda. nm 환산에는 **같은 wafer의 전체 유효 측정 좌표**를 모든 shot의 공통 기준으로 사용하며 해당 basis 최대값도 저장합니다.
- `tables/09_WAFER_COMPARISON`: 동일 wafer의 X21/회전Y17 비교. `delta_ROT_minus_X21`은 회전−기존이며 residual 3σ에서 음수이면 감소입니다.
- `tables/09_TERM_WAFER_STATISTICS`: 각 모델의 각 term nm 기여량이 wafer 내 shot들 사이에서 갖는 산포. 같은 RK 번호를 두 모델 사이에서 직접 비교하지 말고 항 대응표를 참고하세요.
- `plots`: wafer별 대응 그래프. 산점도는 한 점이 한 wafer이고 단일 색입니다. 선 그래프는 범례로 두 모델을 구분합니다.
- `rotation_settings.json`, 입력/출력 manifest.

측정값·좌표는 µm, 출력 통계는 nm, 표준편차는 ddof=1입니다. wafer 통계는 전체 유효 point에서 계산하며 shot 통계의 평균이 아닙니다. 제거 성분의 3σ가 작다는 이유만으로 개선으로 판단하지 말고 최종 residual을 확인하세요. 성분 간 covariance 때문에 variance budget도 단순 가산되지 않습니다.

큰 표의 Excel은 `_sample_10000.xlsx` 미리보기이며 전체 자료는 Parquet/CSV입니다. 비교 report Excel은 전체 표를 저장합니다.

## 개발 검증

`python -m unittest MERGE.rotation.test_rotation -v`

회전/역변환 부호, 항 대응, 원본 X21 회귀 일치, Y 없이 실행, 서로 다른 설명력의 합성 패턴, virtual edge clipping, 파일 대체/필터/Excel, 실제 Jupyter 커널을 검증합니다. 사내 실제 데이터는 포함하지 않습니다.
