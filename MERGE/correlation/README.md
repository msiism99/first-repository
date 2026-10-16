# ADI/OCO wafer별 상관 분석

`ADI_OCO_Correlation.ipynb` 하나로 실행합니다. `build_notebook.py`와 테스트 코드는 다운로드 후 실행할 때 필요하지 않습니다.

## 실행 위치와 저장 폴더

- 노트북: `C:\PHOTO_ANALYSIS\BASIC\ADI_OCO_Correlation.ipynb`
- 입력: `C:\PHOTO_ANALYSIS\BASIC\output_decorrect_notebook\stages`
- 출력: `C:\PHOTO_ANALYSIS\BASIC\output_adi_oco_correlation`
- 표: 출력 폴더의 `tables`, 그래프: `plots`

노트북 00부터 13까지 순서대로 실행합니다. 각 단계에 결과 DataFrame과 저장 파일을 남깁니다. 원본 `MRC_PSM_decorrect.ipynb`를 실행 중인 커널과 별개로 실행할 수 있습니다. pandas, numpy, scipy, matplotlib, pyarrow, openpyxl, IPython이 필요합니다.

입력은 같은 stem의 Parquet을 먼저 선택하고 없으면 전체 Excel을 읽습니다. `_sample_행수.xlsx`는 전체 입력으로 사용하지 않습니다. 출력 표는 전체 Parquet/CSV와 Excel로 저장합니다. 10,000행을 넘는 Excel은 `_sample_10000`으로 표시하며 00에서 이 제한을 변경할 수 있습니다. PNG/PDF 그래프와 전체 설정·파일 목록도 저장합니다.

## 필요한 입력

파일명은 확장자를 제외하고 00의 `INPUT_STEMS`에서 변경할 수 있습니다.

| 입력 stem | 역할 |
|---|---|
| `15_ADI_FINAL` | ADI Reg·좌표·raw·실제 PERSHOT |
| `15_OCO_FINAL` | OCO Reg·좌표 |
| `27_OCO_FINAL_POINTS` | OCO `real_residual_x/y` |
| `09_MRC_ADI_INPUT` | 기적용 CMP MRC K |
| `12_PSM_INPUT` | 기적용 PSM K·LOT/chuck/shot 위치 |
| `21_ADI_WK_WAFER_COEFFICIENTS` | ADI raw에서 추정한 wafer WK beta |
| `21_ADI_RK_WAFER_COEFFICIENTS` | ADI raw에서 추정한 wafer RK beta |
| `27_ADI_CPE_SHOT_COEFFICIENTS` | ADI raw WK/RK 잔차에서 추정한 shot CPE38 beta |
| `27_ADI_FINAL_POINTS` | 선택 입력: 기존 ADI residual과 simulation의 차이 점검 |

기본 wafer 연결 키는 `LOT_ID + Wafer + photo_transn_seq`입니다. 저장된 전체 ADI(E1)/OCO(E2) 측정점을 사용합니다. GROUP/공통 shot/공통 point 필터를 추가하지 않습니다. 기존 계수 파일의 키가 LOT/wafer뿐인데 같은 LOT/wafer에 여러 노광 이력이 있다면 해당 계수의 이력을 추정하지 않고 오류를 냅니다.

## 비교 1: Reg 통계

`X_reg/Y_reg`에서 X/Y mean 및 `3 × std(ddof=1)`를 wafer별로 계산합니다. 원단위는 사용자가 확인한 µm이며 통계는 ×1000하여 nm로 저장합니다. 각 방향의 유효점 수를 기록합니다.

`04_REG_WAFER_STATISTICS`, `04_REG_CORRELATIONS` 및 `04_REG_vs_REG.png/pdf`를 확인하세요.

## 비교 2: ΔK에 따른 ADI ideal 보정 simulation

ideal 추정에는 저장된 **raw WK/RK와 shot CPE38 회귀 계수**를 사용합니다. 기존 ridge/G-opt/span 제약으로 계산된 결과를 재사용하므로 이 노트북에서 CPE 회귀를 다시 실행하지 않습니다. 계수 파일을 만든 원래 데이터와 설정을 갱신하면 이 분석도 다시 실행하세요.

기존 코드의 부호:

- 기적용 MRC 적용값: `-B_MRC @ K_MRC`
- 기적용 PSM 적용값: `+B_CPE @ K_PSM`
- ideal MRC 적용 K: `raw WK/RK beta`
- ideal PSM 적용 K: `-raw residual CPE38 beta`

사용자 정의에 따라 `delta_K = K_applied - K_ideal`로 계산합니다.

```text
delta_MRC(point) = -B_MRC(point) @ delta_K_MRC
delta_PSM(point) = +B_CPE38(point) @ delta_K_PSM
simulated_Reg(point) = original_Reg(point) - delta_MRC(point) - delta_PSM(point)
```

PSM 적용 가능 항은 X21/Y17의 38항입니다. 기존 DB 쿼리가 읽는 72개 컬럼은 7차까지 전체 다항식(X36/Y36)이며, CPE38은 그중 선택된 항입니다. 선택되지 않은 항이 모두 7차인 것은 아닙니다. 이번 simulation은 지원하는 38항만 바꾸고 나머지의 ΔK는 0으로 둡니다. `nonzero_outside_cpe38`에 DB의 지원 외 비영 계수를 기록합니다.

기적용 PSM 일부 NaN은 기존 규칙처럼 0으로 평가하고 원래 NaN 여부를 보관합니다. 전체 NaN/키 누락/ideal 계수 누락은 NaN과 상태로 남깁니다. 기존 Reg와 실제 PERSHOT 값을 계수로 재구성한 값으로 덮어쓰지 않습니다. 따라서 PERSHOT과 K 평가값이 다르면 simulation과 저장된 ADI `real_residual`도 달라집니다.

주요 결과:

- `08_ADI_SIMULATED_POINTS`: 기존 Reg, 기적용·ideal 적용값, Δ보정값, simulated Reg
- `08_MRC_APPLIED_IDEAL_DELTA_K`: wafer별 MRC 기적용/ideal/ΔK
- `08_PSM38_APPLIED_IDEAL_DELTA_K`: shot별 PSM38 기적용/ideal/ΔK
- `08_SIMULATION_WAFER_AUDIT`: 보정 교체 항등식, MRC 재현 오차, 실제 PERSHOT과 K 평가값 차이
- `09_SIMULATION_WAFER_STATISTICS`, `09_SIMULATION_CORRELATIONS`: simulated ADI ↔ OCO `real_residual`의 mean·3σ

동일 데이터에서 추정한 보정의 simulation입니다. 독립 측정점에 대한 예측 검증이나 rework 판정을 수행하는 분석은 아닙니다.

## 비교 3: Reg에서 추출한 WK/RK

ADI/OCO 각각 **Reg에서** WK10+RK9를 X/Y별로 동시에 최소제곱 회귀합니다. 기존 raw 계수 파일을 재사용하지 않습니다. 19점 미만이면 생략하고, matrix rank가 19보다 작으면 계수의 비유일 가능성을 진단에 표시합니다. 기본값에서는 rank 부족 계수를 K 상관·산점도에서 제외하며 원계수·진단에는 보존합니다.

nm 환산은 두 계수 모두 같은 wafer의 ADI 측정 좌표를 reference로 사용합니다. OCO 측정점을 기준으로 사용하려면 `K_REFERENCE="OCO"`로 변경합니다.

| 저장값 | 계산 |
|---|---|
| `signed_peak_nm` | `K × max(abs(reference basis)) × 1000` — 기본 그래프, K 부호 유지 |
| `max_nm` | `max(reference basis × K) × 1000` — 실제 signed 최대값 |
| `min_nm` | `min(reference basis × K) × 1000` |
| `peak_abs_nm` | `max(abs(reference basis × K)) × 1000` |
| `peak_value_nm` | 최대 절대 기여점에서의 실제 signed 기여값 |

`K_PLOT_VALUE="max_nm"`로 바꾸면 실제 signed 최대값으로 상관·그래프를 계산할 수 있습니다. WK는 fcp, RK는 shot-local 좌표의 basis를 사용합니다. 공통 reference로 ADI/OCO의 환산 길이를 맞추며 원래 측정점의 1:1 대응을 요구하지 않습니다.

`10_*_REG_WK_RK_COEFFICIENTS`, `11_REG_K_NM_LONG`, `11_REG_K_NM_PAIRED`, `12_REG_K_CORRELATIONS`와 WK/RK 산점도 및 상관계수 overview 그래프를 확인하세요.

## 상관계수와 검증

Pearson/Spearman은 유효 wafer 3개 이상에서 계산합니다. 값 범위가 `CORR_MIN_RANGE_NM` 이하이면 `constant_or_nearly_constant`로 표시합니다. CPE 후 residual mean이 거의 0일 때 수치 오차만으로 상관을 해석하지 않도록 하기 위한 설정입니다. 상관계수·유효 wafer 수를 함께 저장합니다.

실제 Jupyter 커널에서 합성 stages를 읽어 전체 노트북을 검증합니다. 합성 검증은 기존 matrix와의 일치, MRC/PSM 부호, PERSHOT 불일치 보존, CPE38 외 항 제외, Reg 계수 회복, 공통 좌표 nm 환산, 누락 계수, rank 부족 및 Excel sample 배제를 포함합니다. 사내 생산 데이터는 이 환경에서 읽지 않았습니다.

저장소에서 개발용 검증:

```bash
python -m unittest MERGE.correlation.test_analysis -v
```

사용자 실행에는 위 테스트나 builder가 필요하지 않습니다. 노트북만 BASIC 폴더에 두면 됩니다.
