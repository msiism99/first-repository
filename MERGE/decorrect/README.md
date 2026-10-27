# MRC_PSM_decorrect 저장 코드 정리

2026-10-27 최신 계산: OCO K-MRC는 raw 기준 `회귀(OCO main E1) − 회귀(ADI)`로 계산합니다. 동일 step이면 단일 조회 및 OCO E1 기준 회귀에만 144mm 반경 제한, ADI는 무제한입니다. 별도 edge step 배율 기본값은 0.5입니다. 전체 흐름과 교체 셀은 `MRC_PSM_KMRC_Package.zip` 및 `KMRC_README.md`를 확인하세요. 아래 저장 정리·edge 설명은 이전 작업의 변경 기록입니다.

압축의 `MRC_PSM_decorrect.ipynb`를 `C:\PHOTO_ANALYSIS\BASIC`에 넣고 기존과 같이 위에서 아래로 실행합니다. 00~32의 단계와 보정 계산을 유지합니다.

2026-10-23: wafer/shot 통계가 범주형의 미측정 조합을 생성하지 않도록 `observed=True`를 적용했고, 21번 shot 통계에 중앙 기준 DieX/DieY를 추가했습니다. 집계 함수가 18번에 있으므로 기존 변수로 이어 실행할 때는 18~21번을 다시 실행하세요. 저장된 19번 자료만으로 재계산하려면 별도 `MRC_PSM_WK_RK_Fix_Package.zip`의 `WK_RK_20_21_Repair.ipynb`를 사용합니다.

ADI/OCO 모두 27번 CPE shot 계수·진단·통계와 28번 최종 shot 통계까지 DieX/DieY가 이어집니다. 처음부터 실행할 때는 본 노트북만 사용하면 됩니다.

OCO edge 추가본: 00번의 `cfg.include_oco_edge = True`, `cfg.target_mstepseq_oco_edge = "VC077252"`, `cfg.oco_edge_scale = 0.6`으로 별도 edge 측정을 포함합니다. 수정 범위와 교체 셀은 `MRC_PSM_OCO_Edge_Package.zip`에 있습니다. Edge RAWDATA의 X/Y에만 조회 직후 배율을 적용하며 기존 E2 필터를 유지합니다.

이번 정리에서는 조회 결과의 별도 복사본과 SQL/manifest를 저장하던 기능, 그 파일을 읽는 replay 설정, `saved_files.csv` 생성 및 목록 표시를 제거했습니다. 조회는 사내 `bigdataquery`를 사용합니다. 동일 SQL의 메모리 cache는 유지하며 필요하면 `source.release_cache()`로 비울 수 있습니다.

## 유지되는 출력

- `output_decorrect_notebook/stages`: 조회 원본, MRC/PSM decorrect, TROCS, WK/RK, CPE 및 최종 결과의 전체 Parquet과 Excel 미리보기.
- 원본 조회도 `02_LOTINFO_OCO_QUERY`, `03_LOTINFO_ADI_QUERY`, `05_RAWDATA_*_QUERY`, `07_F1_QUERY`, `11_APC_*_QUERY`, `12_PSM_SHOT_QUERY` 등 기존 단계 이름으로 **stages에 직접 저장**합니다.
- 큰 Excel은 기존처럼 `_sample_행수.xlsx`입니다. 전체 자료는 Parquet을 사용합니다. 파일 링크는 각 셀에 표시합니다.
- `extension_settings.json`: 후속 회전·sampling 분석이 읽는 CPE 설정을 계속 저장합니다.
- 29~32의 wafer context Excel/Parquet/CSV. context 입력도 stages만 사용합니다.

기존 저장 자료를 이어 쓸 때, F1/APC 원본 조회 파일이 stages에 없다면 해당 조회 셀을 다시 실행해 저장하세요. 기존에 만들어진 파일을 자동 삭제하지는 않습니다.

ADI 실제 오차는 raw, 후속 상관 분석의 OCO 기준은 Reg라는 정의를 유지합니다. MRC/PSM 부호, TROCS 연결, WK/RK 및 CPE의 계산식을 변경하지 않았습니다.

## 검증

`python -m unittest MERGE.decorrect.test_storage MERGE.context.test_context -v`

동일 SQL 재사용·반환값 보호, 전체 Parquet/Excel 미리보기 저장, 제거된 출력 미생성, 15/28 단계 실행과 context의 stages 연결을 합성 데이터 및 실제 Jupyter 커널에서 확인합니다. 사내 DB에는 접속하지 않습니다.
