# OCO edge step 추가

## 처음부터 실행

`MRC_PSM_decorrect.ipynb`를 `C:\PHOTO_ANALYSIS\BASIC`에 넣습니다. 기존 개인 조회 조건을 00번에 옮긴 뒤 커널을 재시작하고 00~32번을 순서대로 실행하세요. 결과는 기존 `output_decorrect_notebook/stages`에 저장됩니다. 사내 DB 조회는 사내 환경에서 실행해야 합니다.

```python
cfg.include_oco_edge = True
cfg.target_mstepseq_oco = "VC077251"
cfg.target_mstepseq_oco_edge = "VC077252"
cfg.oco_edge_scale = 0.6
```

배율은 edge 조회 직후 `data_kind == 'RAWDATA'`인 행의 `value_x`, `value_y`에만 적용합니다. 기존 OCO, ADI, TESTDATA 좌표, PERSHOT 및 MRC 값에는 곱하지 않습니다. E1이라는 wafer edge 명칭과 GROUP의 E1은 다릅니다. 기존/edge OCO 모두 기존 E2 선택 규칙을 사용합니다.

## 기존 코드를 직접 수정

`OCO_Edge_Replacement_Cells.ipynb`에 교체할 코드 셀만 넣었습니다. 같은 내용의 `.py`도 제공합니다. 이 파일 자체는 독립 실행용이 아닙니다.

| 기존 번호 | 수정 내용 |
|---|---|
| 00 | PipelineConfig와 실행 설정에 edge 사용 여부·측정 step·배율 추가. import 셀은 그대로 유지 |
| 04 | 기존 ADI/OCO 선정은 유지하고, 동일 LOT/slot/photo의 edge LOTINFO 조회·매칭·진단 추가 |
| 05 | edge raw 조회, X/Y 배율 적용, 원래 값·출처 보존, 기존 OCO와 결합 |
| 06 | 최신 batch 대상 LOTINFO를 기존+edge로 변경. 각 lot_transn_seq별 batch 선택 유지 |
| 08 | 기존+edge LOTINFO로 각각 좌표 연결, 출처 보존, 기존 E2 필터 유지, edge 포함 현황 저장 |

위 5개 번호의 코드 셀을 **모두** 교체합니다. 00번은 class PipelineConfig로 시작하는 설정 셀만 교체하며, 개인 LOT/step/기간/출력 설정을 유지하세요. 기존 코드가 최신 shot-index 수정본보다 이전 버전이라면 전체 노트북 사용을 권장합니다. 이전 15번 이후만 재실행하면 새 edge point는 추가되지 않습니다.

09~32번의 MRC/PSM, TROCS, WK/RK, CPE 계산과 shot 정보 연결은 이번 변경에서 수정하지 않았습니다. 실제 회귀 입력에 edge point가 추가되므로 회귀 계수와 residual은 달라질 수 있습니다.

## 이력·좌표 연결 규칙

- 기존 선정 wafer를 기준으로 LOT + slot + photo_transn_seq가 같은 edge 이력만 추가합니다. 다른 LOT/wafer/노광 이력은 제외합니다. SQL에서도 photo 조건을 먼저 적용하고 같은 노광의 최신 edge LOTINFO를 선택합니다.
- 기존과 edge의 lot_transn_seq는 별도로 보존합니다. 같은 TEST 번호라도 각 step의 TESTDATA에 연결하므로 좌표가 섞이지 않습니다.
- 서로 다른 측정 step에서 같은 TEST 번호를 사용할 수 있으므로 edge의 UNIQUE_ID 계열에는 출처 suffix를 붙입니다. TROCS의 TEST 좌표 목록이 섞이지 않게 하는 조치이며 WK/RK의 LOT/wafer, CPE의 LOT/wafer/shot 회귀 그룹은 그대로입니다.
- Edge가 없는 wafer는 기존 자료로 분석합니다. 포함되지 않은 이유는 아래 진단 파일에서 확인합니다.

## 추가 출력과 확인 위치

| 파일 | 내용 |
|---|---|
| `04_LOTINFO_OCO_EDGE_QUERY` | 별도 edge LOTINFO 조회 원본 |
| `04_LOTINFO_OCO_EDGE_SELECTED` | 동일 LOT/wafer/photo에 매칭된 edge 이력 |
| `04_LOTINFO_OCO_WITH_EDGE` | 기존+edge LOTINFO |
| `04_OCO_EDGE_HISTORY_STATUS` | wafer별 기존/edge lot_transn_seq와 이력 매칭 여부 |
| `05_RAWDATA_OCO_MAIN_QUERY` | 기존 OCO, 배율 1 |
| `05_RAWDATA_OCO_EDGE_SCALED` | edge 조회 후 RAWDATA X/Y에 배율을 적용한 자료. 원래 값도 별도 컬럼에 보존 |
| `05_RAWDATA_OCO_QUERY` | 기존+배율 적용 edge를 합친 분석 입력 |
| `06_RAWDATA_OCO_LATEST` | 기존/edge 각각의 최신 batch |
| `08_OCO_EDGE_COVERAGE` | E2 선택 후 wafer별 기존/edge point 수와 포함 여부 |

Point별 결과에는 `measurement_source` (`oco_main`/`oco_edge`), `source_mstepseq`, `source_lot_transn_seq`, `measurement_scale`, `X_reg_original`, `Y_reg_original`이 이어집니다. 05/06에서는 원래 X/Y 컬럼명이 `value_x_original`, `value_y_original`입니다. 08 이후 `X_reg/Y_reg`는 배율 적용된 값입니다. `Is_Edge_Shot`은 기존 기하학적 edge 판정이며 별도 측정 출처와 같은 의미가 아닙니다.

값의 확인 예: edge 원래 X=1, Y=-2이면 0.6 적용 후 X_reg=0.6, Y_reg=-1.2입니다. 이후 MRC/PSM decorrect는 기존 보정값으로 수행합니다. 회귀 가중치를 0.6으로 주는 방식이 아닙니다.

## 검증

합성 DB 응답으로 신규 step SQL, 노광 이력 제한, 누락 edge 보존, 최신 batch 분리, TESTDATA 좌표 연결, X/Y 배율 및 재실행, E2 필터, ADI/기존 OCO 회귀 입력 불변, 뒤쪽 보정과 source 정보 전달을 검증합니다. 사내 실제 DB 자료는 직접 실행하지 않았습니다.
