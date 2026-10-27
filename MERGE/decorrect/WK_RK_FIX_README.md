# WK/RK wafer·shot 집계 수정

2026-10-27: 현재 번들의 본 노트북과 독립 재계산 노트북은 새 K-MRC 흐름을 사용합니다. OCO는 E1−ADI 계수 차이를 제거하며, 독립 재계산에도 `15_OCO_E1_KMRC_INPUT` 전체 자료가 추가로 필요합니다. 이전 E2-only 자료에는 이 기준 자료가 없으므로 새 본 노트북을 처음부터 실행해야 합니다. K-MRC 계산 불가 wafer는 이후 OCO 분석에서 제외합니다. 새 전체 패키지는 `MRC_PSM_KMRC_Package.zip`입니다.

`MRC_PSM_decorrect.ipynb`를 `C:\PHOTO_ANALYSIS\BASIC`의 기존 파일과 교체합니다. 00번의 개인 조회 설정은 기존 파일에서 옮기세요.

## 이미 저장된 자료로 21번 결과만 다시 만들기

동봉한 `WK_RK_20_21_Repair.ipynb`를 같은 BASIC 폴더에 놓고 위에서 아래로 실행합니다. DB 조회가 필요 없습니다.

- 입력: `output_decorrect_notebook/stages/19_ADI_TROCS_ATTACHED.parquet`, `19_OCO_TROCS_ATTACHED.parquet`.
- Parquet이 없거나 읽을 수 없으면 같은 이름의 전체 Excel을 사용합니다. `_sample_...xlsx`는 사용하지 않습니다.
- 출력: 같은 stages의 `21_*` WK/RK 결과를 재계산하여 덮어씁니다. 19번 입력과 다른 단계의 결과는 수정하지 않습니다.
- `04_LOTINFO_ADI_SELECTED`, `04_LOTINFO_OCO_SELECTED`가 있으면 실측 wafer 목록과 비교한 `21_*_WK_RK_WAFER_SCOPE`도 저장합니다. 이 표에는 선정되었지만 19번 point가 없는 wafer도 진단 목적으로 표시합니다. 실제 통계인 `WAFER_DATA`에는 실측 point가 있는 wafer만 포함합니다.

## 수정 원인과 범위

기존 pandas 범주형 groupby의 기본 `observed=False`는 실제로 없는 LOT/wafer 및 fcp_x/fcp_y 조합을 생성할 수 있습니다. A LOT에 11/12만 있고 다른 LOT에 9/10/14가 있는 합성 자료에서 A LOT에 5개 wafer가 생성되는 현상을 재현했습니다. 좌표 조합도 실측하지 않은 반경 밖 shot을 만들었습니다. 사내 실제 입력 파일은 직접 확인하지 않았습니다.

- 집계와 WK/RK·CPE 그룹 순회에 `observed=True`를 명시했습니다. 15/18/21/27/28의 관련 통계가 실제 입력 그룹만 사용합니다. 18번 TROCS ALLMARKS 자체는 기존 목적의 가상 전체 mark이며 WK/RK 실측 목록을 만들 때 사용하지 않습니다.
- `21_*_WK_RK_SHOT_DATA`에 `DieX`, `DieY`, `shot_index_status`를 추가했습니다. 원본 실측 Die index를 보존하고, 누락된 값만 `(fcp - MAP_SHIFT) / STEP_PITCH`로 복원합니다. `(0,0)`의 shot 중심은 `(MAP_SHIFT_X, MAP_SHIFT_Y)`입니다. 측정된 shot들의 평균이나 최소 좌표를 원점으로 사용하지 않습니다.
- ADI/OCO 모두 27번 CPE shot 계수·진단·통계, 28번 최종 shot 통계까지 DieX/DieY를 연결합니다. Point별 결과의 기존 index도 유지합니다. CPE를 계산할 유효 point가 없는 shot은 진단·통계에는 남고 계수표에는 생성하지 않습니다.
- 동일 shot 중심의 index 충돌은 오류로 표시합니다. index와 geometry가 모두 없으면 NA 및 `missing_geometry`를 표시합니다.
- shot 중심 반경 150 mm로 자르지 않습니다. 실측 point가 있는 edge/partial shot은 중심이 wafer 밖일 수 있습니다. **실측에 없는 조합을 만들지 않는 것**으로 문제를 수정했습니다.
- 회귀 matrix, least-squares, 최소 19개 유효 X/Y point 조건 및 raw 계산식은 유지했습니다. 실제 존재하지만 유효 point가 부족한 wafer는 통계에 남고, 기존 WAFER_DIAGNOSTICS에 `skip_too_few_points`로 기록됩니다.

## LOT별 wafer 선정 확인

02/03: LOT/slot별 최신 LOTINFO 조회 → 04: ADI 날짜 범위, ADI/OCO 공통 `(photo_transn_seq, slotid)`, 설정 slot 범위(기본 9~14) → 06: 선정된 `(lot_transn_seq, slotid)`의 RAWDATA만 유지 → 08: 실측 RAWDATA와 좌표 결합 및 OCO 그룹 선택 → 15: MMO_MRC_EQP 필터 → 19: 실측 point에 TROCS를 left join → 20: `(LOT_ID, Wafer)`별 회귀입니다. 9~14는 허용 범위이며 모든 wafer를 생성하는 명령이 아닙니다. WK/RK 집계에서 별도로 wafer를 선정하거나 채우지 않습니다.

## 기존 본 노트북에서 재실행

집계 함수는 **18번**에 있으므로 수정된 본 노트북으로 결과를 다시 만들려면 18~21번을 순서대로 실행합니다. 이후 CPE/최종 통계도 갱신하려면 22~28번까지 실행합니다. 새 커널에서는 필요한 이전 단계부터 실행하거나 위의 독립 재계산 노트북을 사용하세요.

이전에 생긴 Excel 샘플 파일은 자동 삭제하지 않습니다. 이름에 `_sample_`이 없는 새 전체 Excel 또는 새 Parquet을 확인하세요.

## 검증

`python -m unittest MERGE.decorrect.test_wk_rk_reporting MERGE.decorrect.test_storage -v`

범주형의 없는 wafer/shot 조합, nullable key, 작은/빈 입력, index 복원·충돌, LOT 교집합·RAW batch 범위, 원본 회귀 결과 동일성, 독립 노트북의 실제 Jupyter 실행과 Excel/Parquet 저장을 합성 자료로 검증합니다.
