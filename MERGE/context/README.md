# Wafer context 통합 표

`MRC_PSM_decorrect.ipynb` 마지막의 **29~32번**을 실행합니다. 앞의 DB 조회나 보정 계산은 실행하지 않아도 됩니다. 기존 파일을 유지하려면 `Wafer_Context_29_32.ipynb`의 4개 코드 셀만 마지막에 복사하거나 이 작은 노트북을 단독 실행하세요. `.py`에는 같은 코드가 `# %%` 구간별로 들어 있습니다. 런타임에 별도 모듈을 import할 필요는 없습니다.

29번 경로:

```text
노트북 위치: C:\PHOTO_ANALYSIS\BASIC
입력: C:\PHOTO_ANALYSIS\BASIC\output_decorrect_notebook\stages
일부 QUERY 보완: C:\PHOTO_ANALYSIS\BASIC\output_decorrect_notebook\snapshots
출력: C:\PHOTO_ANALYSIS\BASIC\output_wafer_context
```

표의 한 행은 **LOT_ID + Wafer + photo_transn_seq**입니다. 같은 wafer라도 노광 이력이 다르면 별도 행을 유지합니다. ADI/OCO 대표 파일의 wafer 합집합을 사용하며 존재 여부를 `ADI_present`, `OCO_present`에 기록합니다. ADI raw / OCO Reg라는 기존 분석 기준과 보정 계산을 변경하지 않습니다.

## 결과

- **wafer_context.xlsx → Wafer_context:** 필터와 첫 3열 고정이 있는 통합 표. 장비·reticle·recipe·chuck·기준 장비·공정·시각은 ADI/OCO를 나란히 앞쪽에 배치합니다.
- **Columns:** 각 열의 원본 파일·컬럼과 집계 방식.
- **Sources:** 실제 읽은 파일, 전체 행 수, 읽은 컬럼 수, key 결측, 누락/sample/읽기 오류.
- **Joins:** 어떤 키로 연결했고 몇 wafer에 연결됐는지. 애매해서 제외한 batch 키 수도 기록.
- **Multiple_values:** 하나의 wafer에 여러 값이 있는 context 항목.
- **Context_values:** 집계 전의 고유 원값과 출처. 통합 셀 길이가 길어지는 경우도 원값은 여기에 보존.
- **Notes:** 행 기준·출처·해석 안내.
- **wafer_context.parquet / .csv:** 통합 표 전체. 이후 통계 결과에 `LOT_ID`, `Wafer`, `photo_transn_seq`로 연결해서 사용.
- **wafer_context_values.parquet / .csv:** 모든 고유 context 값과 출처.

ID는 가능한 범위에서 Parquet의 nullable integer로 보존하며 Excel의 photo_transn_seq는 문자열로 저장해 긴 번호의 정밀도 손실을 막습니다. 장비·reticle 등의 context 값은 문자열로 통일합니다. 같은 wafer에서 여러 값이 발견되면 `|`로 병기합니다. 이는 값이 여러 개라는 뜻이며 곧바로 데이터 오류라는 뜻은 아닙니다.

## 수집 범위와 연결

| 열 접두어 | 입력과 내용 |
|---|---|
| ADI__, OCO__ | 우선 15_FINAL의 장비, reticle, recipe, chuck, 계측/노광 시각, 공정, 기준 장비, geometry 설정, 처리 상태 및 실측 행·shot·TEST 수 |
| ADI_LOTINFO__, OCO_LOTINFO__ | 04_LOTINFO_SELECTED: LOTINFO의 추가 정보, 측정 이력 번호, PSM 참조 ID 등 |
| *_PAIR__ | 04_LOTINFO_PAIRED: base_eqpid, psm_update_time, OCO 이력 등 |
| *_EXPO__, *_F1__ | 07_EXPO_SELECTED 및 07_F1_QUERY. F1은 원본 흐름대로 최신 impala_insert_time을 사용 |
| *_MRC__ | 09_MRC_INPUT의 계수 이외 이력 정보 |
| *_APC__, *_APC_MAIN__, *_APC_EEXY__ | 저장된 main/EEXY 이력 ID에 해당하는 장비, recipe, reticle, run_type, 처리 시각 등 |
| *_PSM__, *_TROCS__ | 12_PSM_INPUT, 16_TROCS_INPUT_UM의 계수·좌표 이외 metadata |
| *_BATCH_RAWDATA__, *_BATCH_TESTDATA__, *_BATCH_PERSHOT__ | 06_RAWDATA_LATEST의 종류별 측정 시작/종료 시각과 원본 행 수 |

APC ID는 여러 wafer가 공유할 수 있으므로, 각 wafer에 실제 저장된 ID와 LOT로 연결합니다. **LOT만으로 최신 이력을 붙이거나 slot 홀짝으로 이력을 추정하지 않습니다.** 측정 batch의 lot_transn_seq + Wafer가 여러 노광 이력에 걸치면 임의로 배분하지 않고 해당 batch 연결을 제외합니다.

15_FINAL이 없으면 27_FINAL_POINTS, 19_TROCS_ATTACHED, 14_RAW_BEFORE_FILTER, 08_MEASURED, 04_LOTINFO_SELECTED 순으로 대표 파일을 찾습니다. 이전 단계로 fallback되면 대상 범위가 달라질 수 있으므로 Sources와 context_settings.json의 anchors를 확인하세요. 실측 파일이 없는 경우에는 point 개수를 추정하지 않습니다.

모든 선택 파일에서 측정값·point 좌표·WK/RK/CPE 계수 등을 제외한 컬럼을 수집하므로 추가 context 컬럼도 자동으로 포함됩니다. 자동 제외 컬럼도 필요하면 `CTX_EXTRA_COLUMNS`에 이름을 넣으세요. DB에만 있고 저장되지 않은 product/device 정보는 조회하거나 만들어내지 않습니다.

Parquet은 필요한 컬럼을 batch로 읽고, Excel도 행 단위로 나눠 읽습니다. 반복 metadata는 중복을 줄이되 point/shot/batch 개수는 원본 행에서 집계합니다. `_sample_...xlsx`는 일부 자료이므로 입력으로 사용하지 않습니다. 필수 대표 자료가 없으면 오류를 내고, 선택 정보의 누락은 Sources/Joins에 기록합니다.
