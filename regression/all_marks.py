#v1.4 : 1개 파일에 모든 uid 저장
#v1.3 : 주석달기
#v1.2 : radius limit을 config.py에서 불러오도록 수정
#v1.1 : 추가 정보 포함. 최종 wafer좌표계, radius 포함.


import numpy as np
import pandas as pd
import os
from config import RADIUS_THRESHOLD  # config.py에서 반경 임계값을 불러옴



# ------------------------------------------------------
# Shot의 edge 여부 판단. 해당 shot의 모서리가 반경을 넘는지 판단
# ------------------------------------------------------

def is_edge(center, pitch, limit_radius):
    output = 0
    # shot의 네 모서리 좌표 계산
    edge_position = np.array([
        [center[0] - pitch[0] / 2, center[1] - pitch[1] / 2],
        [center[0] - pitch[0] / 2, center[1] + pitch[1] / 2],
        [center[0] + pitch[0] / 2, center[1] + pitch[1] / 2],
        [center[0] + pitch[0] / 2, center[1] - pitch[1] / 2]
    ])
    # 각 모서리 좌표의 반경 계산
    edge_radius = np.sqrt(np.sum(edge_position ** 2, axis=1))
    if np.max(edge_radius) > limit_radius:
        output = 1
        if np.min(edge_radius) > limit_radius:
            output = 2  # 모든 모서리가 반경 밖일 경우
    return output

# --------------------------------------------------
# 주어진 마크(test_inf)와 shot layout 정보를 이용해
# 유효한 wafer 마크를 계산하고 정보 포함시켜 반환
# --------------------------------------------------
def mark_sel_all(test_inf, shot_layout, limit_radius):
    test_n = test_inf.shape[0]         # 마크(test) 개수
    step_n = test_inf.shape[1] // 2    # step 개수 (x,y 쌍)

    # shot 후보 영역 생성 (-10 ~ 10 범위)
    shot_array = []
    for ix in range(-10, 11):
        for iy in range(-10, 11):
            center = [ix * shot_layout[0] + shot_layout[2], iy * shot_layout[1] + shot_layout[3]]
            edge_flag = is_edge(center, shot_layout[:2], limit_radius)
            if edge_flag != 2:  # 완전히 바깥은 제외
                shot_array.append([ix, iy, edge_flag])
    shot_array = np.array(shot_array)
    shot_n = shot_array.shape[0]       # 유효한 shot 수

    # 마크 좌표 계산용 배열 초기화
    test_all = np.zeros((shot_n * test_n, 3 + step_n * 2))
    wafer_coords = np.zeros((shot_n * test_n, 2))   # wafer 절대 좌표
    step_info = np.zeros((shot_n * test_n, 4))      # step pitch 및 map shift 정보
    coord_info = np.zeros((shot_n * test_n, 2))     # 상대 마크 좌표
    temp_test = np.arange(1, test_n + 1)

    # shot 좌표 기록
    for i in range(shot_n):
        start_idx = i * test_n
        end_idx = (i + 1) * test_n
        test_all[start_idx:end_idx, 0] = temp_test        # test ID
        test_all[start_idx:end_idx, 1] = shot_array[i, 0] # shot X
        test_all[start_idx:end_idx, 2] = shot_array[i, 1] # shot Y

    # 실제 wafer 좌표 계산
    for ix in range(step_n):
        for ii in range(shot_n * test_n):
            test_id = int(test_all[ii, 0]) - 1
            rel_x = test_inf[test_id, ix * 2]
            rel_y = test_inf[test_id, ix * 2 + 1]
            shot_x = test_all[ii, 1]
            shot_y = test_all[ii, 2]
            abs_x = shot_x * shot_layout[0] + shot_layout[2] + rel_x
            abs_y = shot_y * shot_layout[1] + shot_layout[3] + rel_y
            test_all[ii, 3 + ix * 2] = abs_x
            test_all[ii, 4 + ix * 2] = abs_y

            if ix == 0:  # 첫 번째 step만 기록
                wafer_coords[ii, 0] = abs_x
                wafer_coords[ii, 1] = abs_y
                coord_info[ii, 0] = rel_x
                coord_info[ii, 1] = rel_y
                step_info[ii] = [shot_layout[0], shot_layout[1], shot_layout[2], shot_layout[3]]

    # 모든 step의 마크가 반경 내에 있는지 확인
    test_index = np.zeros((shot_n * test_n, step_n), dtype=bool)
    for ix in range(step_n):
        x = test_all[:, 3 + ix * 2]
        y = test_all[:, 4 + ix * 2]
        test_index[:, ix] = np.sqrt(x ** 2 + y ** 2) < limit_radius

    # 모든 step이 반경 안에 들어간 마크만 선택
    f_index = np.all(test_index, axis=1)

    # 결과 데이터프레임 생성
    output_data = {
        "Test ID": test_all[f_index, 0].astype(int),
        "Shot X": test_all[f_index, 1].astype(int),
        "Shot Y": test_all[f_index, 2].astype(int),
        "Step Pitch X": step_info[f_index, 0],
        "Step Pitch Y": step_info[f_index, 1],
        "Map Shift X": step_info[f_index, 2],
        "Map Shift Y": step_info[f_index, 3],
        "Coordinate X": coord_info[f_index, 0],
        "Coordinate Y": coord_info[f_index, 1],
        "Wafer X": wafer_coords[f_index, 0],
        "Wafer Y": wafer_coords[f_index, 1],
        "Radius": np.sqrt(wafer_coords[f_index, 0]**2 + wafer_coords[f_index, 1]**2)
    }

    return pd.DataFrame(output_data)

# --------------------------------------------------
# Wrapper 함수. 외부 호출용 함수 (단일 그룹 마크 계산)
# --------------------------------------------------
def all_marks(test_inf_all, shot_layout, limit_radius):
    return mark_sel_all(test_inf_all, shot_layout, limit_radius)

# --------------------------------------------------
# CSV 파일에서 UNIQUE_ID별로 그룹을 나누고
# 각 그룹의 마크를 계산하여 CSV로 저장
# --------------------------------------------------
def extract_and_save_marks_by_unique_id(csv_path, output_path):
    limit_radius = RADIUS_THRESHOLD  # config에서 설정한 반경 임계값 사용
    df = pd.read_csv(csv_path)
    

    df_all = []  # 전체 결과를 모아둘 리스트

    for unique_id, group in df.groupby("UNIQUE_ID"):
        group = group.sort_values(by="Test No")

        # shot layout 정보 추출
        step_pitch_x = group["STEP_PITCH_X"].iloc[0]
        step_pitch_y = group["STEP_PITCH_Y"].iloc[0]
        map_shift_x = group["MAP_SHIFT_X"].iloc[0]
        map_shift_y = group["MAP_SHIFT_Y"].iloc[0]
        shot_layout = [step_pitch_x, step_pitch_y, map_shift_x, map_shift_y]

        # test 마크 정보 정리
        unique_tests = sorted(group["Test No"].unique())
        step_n = len(group[group["Test No"] == unique_tests[0]])
        test_n = len(unique_tests)

        test_inf_all = np.zeros((test_n, step_n * 2))
        for i, t in enumerate(unique_tests):
            temp = group[group["Test No"] == t]
            test_inf_all[i, 0::2] = temp["coordinate_X"].values
            test_inf_all[i, 1::2] = temp["coordinate_Y"].values

        # 마크 계산
        df_mark = all_marks(test_inf_all, shot_layout, limit_radius)
        df_mark.insert(0, "UNIQUE_ID", unique_id)  # UNIQUE_ID 컬럼 추가
        df_all.append(df_mark)

    # 전체 병합 후 한 번에 저장
    df_all_concat = pd.concat(df_all, ignore_index=True)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_all_concat.to_csv(output_path, index=False)
    print(f"✅ 전체 마크를 {output_path} 에 저장했습니다.")



# --------------------------------------------------
# 실행 예시
# --------------------------------------------------
if __name__ == "__main__":
    csv_path = "Test_Coord.csv"             # 입력 파일
    output_path = "all_marks/all_marks_total.csv"  # 1개 파일로 저장
    extract_and_save_marks_by_unique_id(csv_path, output_path)
