# ADI/OCO CPE sampling 진단

`CPE_Sampling_Diagnostics.ipynb`를 `C:\PHOTO_ANALYSIS\BASIC`에 놓고 00~13을 순서대로 실행합니다. 기존 파일을 변경하거나 DB에 접속하지 않습니다. 셀 안에 모든 코드가 포함되어 있습니다.

## 입력·대표 sampling

- 각 mode의 `21_{mode}_WK_RK_REMOVED` → `27_{mode}_FINAL_POINTS` → `15_{mode}_FINAL` 순서로 좌표를 찾습니다. 전체 Parquet 우선, 같은 이름 전체 Excel 대체. sample Excel은 사용하지 않습니다.
- 필요한 Parquet 컬럼만 읽습니다. 대표 wafer 하나를 선택한 뒤 그 안의 반복 shot sampling을 구분합니다.
- 기본은 ADI/OCO의 공통 wafer 중 유효 좌표가 충분한 wafer를 선택합니다. 공통 wafer가 없으면 각각 선택합니다. 같은 wafer는 권장 사항이며 필수는 아닙니다.
- `WAFER_SELECTION={"ADI":{"LOT_ID":"LOT_A","Wafer":3},"OCO":None}`처럼 지정할 수 있습니다.
- 여러 제품이 섞였으면 `FILTERS`를 지정합니다. 필요하면 기존 `output_wafer_context/wafer_context.parquet` 또는 전체 Excel의 필터 컬럼을 전체 wafer 키로 연결합니다.
- 대표 layout은 고유 mark 수가 가장 많고 자주 반복되는 layout을 우선 선택합니다. 해당 layout 중 중심에 가까운 shot을 사용합니다. partial shot 등의 다른 layout은 별도 catalogue에 남깁니다. 이 진단의 모델 성능 수치는 대표 shot 기준입니다.
- 같은 좌표의 여러 측정 행은 삭제하지 않습니다. 반복 측정 가중치와 noise 전달에 영향을 주기 때문입니다. 좌표 반올림은 layout 이름 식별에만 사용하고 회귀는 원래 좌표로 수행합니다.
- `USE_VALID_X_MASK=True`이면 CPE 직전 X 컬럼이 있을 때 유효 측정점 조건만 맞춥니다. 합성 비교에서는 실제 오차 크기를 사용하지 않습니다. 좌표만 있는 파일도 실행됩니다.

## 무엇을 알 수 있는가

**critical X에 대한 X21 / 90° 회전 Y17의 차이**를 sampling 측면에서 분석합니다. Y 측정값은 쓰지 않습니다.

1. **항 식별성:** 독립 관측 가능한 차원(rank), 계수 nullity, 다른 항과 구분되는 각 term의 상대 성분. point 수보다 계수가 많으면 작은 학습점 residual만으로 계수나 전체 field를 확정할 수 없습니다.
2. **Alias:** basis 열의 cosine 유사도. 두 항이 측정점에서 비슷한 모양인지 보여줍니다. 여러 항을 합쳐 생기는 의존성은 rank도 함께 확인합니다.
3. **Noise 전달:** point noise가 공통 shot 영역의 예측값에 얼마나 증폭되는지 계산합니다. 표준편차 비율이 2라면 0.2 nm point noise가 그 위치의 예측에 0.4 nm 표준편차로 전달된다는 뜻입니다. 모델 누락·미관측 field의 오차까지 포함하는 지표는 아닙니다.
4. **동일 정답 replay:** 각 단항식과 혼합 field를 양쪽 sampling에서 관측한 것으로 가정하고 공통 grid의 복원 오차를 비교합니다. field는 공통 grid RMS로 정규화하므로 동일한 물리적 정답을 비교합니다.
5. **우열 역전:** 같은 정답인데도 ADI는 Y17, OCO는 X21이 유리한 합성 예시가 있는지 표시합니다. 예시 개수는 원인 확률이 아닙니다. 예시가 없다고 sampling 영향을 배제할 수도 없습니다.

좌표는 실제 공정 변형이나 계측 bias의 원인을 단독으로 식별하지 못합니다. 이 노트북은 geometry만으로 설명 가능한 부분과 실제 신호를 추가로 봐야 하는 부분을 구분하기 위한 진단입니다.

## Solver와 공통 grid

- 원본 notebook의 CPE38/virtual point/G-opt/span 코드를 그대로 포함하고, `extension_settings.json`이 있으면 설정을 복원합니다.
- **OLS_SVD:** 열 정규화 SVD 최소노름 회귀. `SVD_RCOND`로 rank 기준을 명시합니다.
- **GOPT_RIDGE:** 원본 G-opt가 sampling과 virtual grid로 정한 lambda를 재사용한 span 이전 선형 회귀. 원본 normal equation 방식입니다.
- **NATIVE_SPAN:** 같은 lambda에서 원본 span 검사 및 box CD를 수행합니다. 가상 정답 단위 nm를 원본 span 단위 µm로 변환합니다.
- 공통 grid는 기본적으로 두 sampling의 shot pitch·측정 범위를 포함합니다. 동일 제품인지 `Pitch_and_extent`를 확인하세요. `COMMON_SHOT_SIZE_UM`으로 영역을 고정할 수 있습니다.
- 전체 공통 영역의 `grid_rmse_nm`와 두 sampling convex hull의 교집합 `shared_hull_rmse_nm`를 함께 저장하여 외삽 영향도 볼 수 있습니다.
- `expected_grid_rmse_nm`는 독립·동일 분산 noise 가정에서 **sqrt(E[grid MSE])**입니다. 실제 noise 추정치나 실측 성능이 아닙니다. nonlinear span/box 결과에는 이 식을 적용하지 않습니다.
- `train_3sigma_nm`는 기존 wafer 비교 그림과 같은 **측정점 residual 3σ**입니다. `expected_train_3sigma_nm`는 가정한 noise까지 더한 `3*sqrt(E[표본분산])`입니다. 공통 grid에서의 복원 오차와 구분해 저장합니다.
- rank 부족에서 최소노름 해의 noise gain이 작더라도, 관측되지 않은 field까지 정확하다는 뜻은 아닙니다. rank와 replay의 공통 grid 오차를 같이 보세요.

## 주요 결과

`C:\PHOTO_ANALYSIS\BASIC\output_cpe_sampling_diagnostics`

**`CPE_Sampling_Diagnostics.xlsx`**

| Sheet | 확인 내용 |
|---|---|
| Sampling_summary | 좌표 수, 축별 위치 수, rank/nullity, lambda, noise gain |
| Selected_wafers / Layout_catalogue | 선택한 wafer와 대표 sampling, 다른 shot layout |
| Term_identifiability / Alias_pairs | 구분하기 어려운 항 및 유사한 항 조합 |
| Pattern_response | 같은 정답 패턴의 측정점·공통 grid 복원 오차 |
| Sampling_interaction | 측정점 residual 3σ / 공통 grid RMSE 각각의 ADI Y17·OCO X21 우열 역전 여부 |
| Observed_check | 입력에 실측 X가 있을 때 대표 shot의 참고용 재회귀 결과 |
| Observed_group_gain | 공통 12항에 모델 전용 항을 더했을 때의 실측점 설명력 증가 |
| Model_terms / Pattern_catalogue | 물리적 X 기준 항 대응 및 합성 정답 정의 |
| Notes | 단위·가정·해석 방법 |

`plots`에는 sampling 지도, alias heatmap, noise 증폭 지도, 단항식 복원 오차, 측정점 residual 3σ와 공통 grid RMSE 각각의 우열 역전 그래프 6개가 저장됩니다. 모든 그림은 PNG/PDF입니다. `tables`에는 중간 표와 공통 grid를 전체 Parquet/CSV로 저장합니다. 큰 표의 Excel은 명시한 sample입니다.

실제 결과를 보기 전에 `Sampling_summary` → `Pattern_response` → `Sampling_interaction` 순서로 확인하면 됩니다. 공통 grid 오차가 크면서 학습점 오차가 작은 경우를 특히 확인하세요.

## 개발 검증

`python -m unittest MERGE.sampling.test_sampling -v`

동일 sampling의 재현성, 서로 다른 sampling의 alias·rank·noise 전달, 알려진 정답 복원, 원본 native solver와의 일치, 좌표 전용 입력, 대표 wafer/shot 선택, 실제 Jupyter 실행과 Excel을 합성 데이터로 검증합니다.
