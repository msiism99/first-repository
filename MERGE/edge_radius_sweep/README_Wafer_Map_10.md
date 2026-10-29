# 10번 추가 코드: 제품별 측정 위치 wafer map

`OCO_Edge_Wafer_Map_10.ipynb`의 코드 셀을 기존 `OCO_Edge_Radius_Sweep.ipynb`의 09번 뒤에 복사하세요. 또는 함께 있는 `Wafer_Map_10.py` 내용을 그대로 붙여도 됩니다.

기존 **00번의 EP_SOURCES, EP_OUTPUT_DIR, 입력 함수**가 정의된 상태에서 10번을 실행하면 됩니다. 그림만 그리려면 00번→10번으로 실행할 수 있고 CPE를 다시 계산하지 않습니다. 기존 27번 전체 point 파일에서 좌표와 shot pitch를 읽습니다.

- 제품마다 측정 위치가 가장 많은 wafer를 대표로 자동 선택.
- 직접 선택: `WM_SELECT={"KGVM":("실제_LOT_ID",11)}`. 지정하지 않은 제품은 자동 선택.
- 점의 색: <=144mm 파랑 / 144~146mm 주황 / 146~147mm 빨강. 경계 144·146·147mm는 각각 안쪽 구간에 포함.
- Wafer R=150mm 검은 실선, R=144mm 검은 점선.
- 실측 shot 중심과 STEP_PITCH_X/Y로 만든 실측 shot 경계 검은 실선. Wafer 바깥으로 나가는 선은 150mm 원으로 clip.
- 같은 위치는 한 번만 표시. 147mm 초과·유효하지 않은 좌표는 지도에서 제외. Overlay 등 계측값은 표시하지 않음.
- STEP_PITCH가 없다면 `WM_PITCH_OVERRIDE_UM={"KGVM":(실제_X_pitch_um,실제_Y_pitch_um)}`에 실제 값 지정.

결과는 기존 출력 폴더의 `plots/10_Wafer_Map_Product_01/02/03.png`와 `.pdf`입니다. `10_Wafer_Map_Index.xlsx`에 선택 wafer, 구간별 점 수, shot 수와 파일명을 저장합니다. 제품 번호는 기존 00번의 EP_SOURCES 순서입니다.
