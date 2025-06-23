import pandas as pd
import numpy as np
import logging


def compute_fringe_zernike_matrix(r, theta, max_index):
    """
    ASML Fringe Zernike 다항식 기저 생성 (Z64까지)
    :param r: 방사 좌표계의 반지름 값 (0 ≤ r ≤ 1로 스케일링 필요)
    :param theta: 방사 좌표계의 각도 값 (-π ≤ θ ≤ π)
    :param max_index: 최대 인덱스 (Z1부터 Z64까지)
    :return: Zernike 기저 행렬
    """
    Z = [np.ones_like(r)]  # Z1: 상수항
    if max_index >= 2:
        Z.append(r * np.cos(theta))  # Z2
    if max_index >= 3:
        Z.append(r * np.sin(theta))  # Z3
    if max_index >= 4:
        Z.append(2 * r**2 - 1)  # Z4
    if max_index >= 5:
        Z.append(r**2 * np.cos(2 * theta))  # Z5
    if max_index >= 6:
        Z.append(r**2 * np.sin(2 * theta))  # Z6
    if max_index >= 7:
        Z.append((3 * r**3 - 2 * r) * np.cos(theta))  # Z7
    if max_index >= 8:
        Z.append((3 * r**3 - 2 * r) * np.sin(theta))  # Z8
    if max_index >= 9:
        Z.append(6 * r**4 - 6 * r**2 + 1)  # Z9
    if max_index >= 10:
        Z.append(r**3 * np.cos(3 * theta))  # Z10
    if max_index >= 11:
        Z.append(r**3 * np.sin(3 * theta))  # Z11
    if max_index >= 12:
        Z.append((4 * r**4 - 3 * r**2) * np.cos(2 * theta))  # Z12
    if max_index >= 13:
        Z.append((4 * r**4 - 3 * r**2) * np.sin(2 * theta))  # Z13
    if max_index >= 14:
        Z.append((10 * r**5 - 12 * r**3 + 3 * r) * np.cos(theta))  # Z14
    if max_index >= 15:
        Z.append((10 * r**5 - 12 * r**3 + 3 * r) * np.sin(theta))  # Z15
    if max_index >= 16:
        Z.append(20 * r**6 - 30 * r**4 + 12 * r**2 - 1)  # Z16
    if max_index >= 17:
        Z.append(r**4 * np.cos(4 * theta))  # Z17
    if max_index >= 18:
        Z.append(r**4 * np.sin(4 * theta))  # Z18
    if max_index >= 19:
        Z.append((5 * r**5 - 4 * r**3) * np.cos(3 * theta))  # Z19
    if max_index >= 20:
        Z.append((5 * r**5 - 4 * r**3) * np.sin(3 * theta))  # Z20
    if max_index >= 21:
        Z.append((15 * r**6 - 20 * r**4 + 6 * r**2) * np.cos(2 * theta))  # Z21
    if max_index >= 22:
        Z.append((15 * r**6 - 20 * r**4 + 6 * r**2) * np.sin(2 * theta))  # Z22
    if max_index >= 23:
        Z.append((35 * r**7 - 60 * r**5 + 30 * r**3 - 4 * r) * np.cos(theta))  # Z23
    if max_index >= 24:
        Z.append((35 * r**7 - 60 * r**5 + 30 * r**3 - 4 * r) * np.sin(theta))  # Z24
    if max_index >= 25:
        Z.append(70 * r**8 - 140 * r**6 + 90 * r**4 - 20 * r**2 + 1)  # Z25
    if max_index >= 26:
        Z.append(r**5 * np.cos(5 * theta))  # Z26
    if max_index >= 27:
        Z.append(r**5 * np.sin(5 * theta))  # Z27
    if max_index >= 28:
        Z.append((6 * r**6 - 5 * r**4) * np.cos(4 * theta))  # Z28
    if max_index >= 29:
        Z.append((6 * r**6 - 5 * r**4) * np.sin(4 * theta))  # Z29
    if max_index >= 30:
        Z.append((21 * r**7 - 30 * r**5 + 10 * r**3) * np.cos(3 * theta))  # Z30
    if max_index >= 31:
        Z.append((21 * r**7 - 30 * r**5 + 10 * r**3) * np.sin(3 * theta))  # Z31
    if max_index >= 32:
        Z.append((56 * r**8 - 105 * r**6 + 60 * r**4 - 10 * r**2) * np.cos(2 * theta))  # Z32
    if max_index >= 33:
        Z.append((56 * r**8 - 105 * r**6 + 60 * r**4 - 10 * r**2) * np.sin(2 * theta))  # Z33
    if max_index >= 34:
        Z.append((126 * r**9 - 280 * r**7 + 210 * r**5 - 60 * r**3 + 5 * r) * np.cos(theta))  # Z34
    if max_index >= 35:
        Z.append((126 * r**9 - 280 * r**7 + 210 * r**5 - 60 * r**3 + 5 * r) * np.sin(theta))  # Z35
    if max_index >= 36:
        Z.append(252 * r**10 - 630 * r**8 + 560 * r**6 - 210 * r**4 + 30 * r**2 - 1)  # Z36
    if max_index >= 37:
        Z.append(r**6 * np.cos(6 * theta))  # Z37
    if max_index >= 38:
        Z.append(r**6 * np.sin(6 * theta))  # Z38
    if max_index >= 39:
        Z.append((7 * r**7 - 6 * r**5) * np.cos(5 * theta))  # Z39
    if max_index >= 40:
        Z.append((7 * r**7 - 6 * r**5) * np.sin(5 * theta))  # Z40
    if max_index >= 41:
        Z.append((28 * r**8 - 42 * r**6 + 15 * r**4) * np.cos(4 * theta))  # Z41
    if max_index >= 42:
        Z.append((28 * r**8 - 42 * r**6 + 15 * r**4) * np.sin(4 * theta))  # Z42
    if max_index >= 43:
        Z.append((84 * r**9 - 168 * r**7 + 105 * r**5 - 20 * r**3) * np.cos(3 * theta))  # Z43
    if max_index >= 44:
        Z.append((84 * r**9 - 168 * r**7 + 105 * r**5 - 20 * r**3) * np.sin(3 * theta))  # Z44
    if max_index >= 45:
        Z.append((210 * r**10 - 504 * r**8 + 420 * r**6 - 140 * r**4 + 15 * r**2) * np.cos(2 * theta))  # Z45
    if max_index >= 46:
        Z.append((210 * r**10 - 504 * r**8 + 420 * r**6 - 140 * r**4 + 15 * r**2) * np.sin(2 * theta))  # Z46
    if max_index >= 47:
        Z.append((462 * r**11 - 1260 * r**9 + 1260 * r**7 - 560 * r**5 + 105 * r**3 - 6 * r) * np.cos(theta))  # Z47
    if max_index >= 48:
        Z.append((462 * r**11 - 1260 * r**9 + 1260 * r**7 - 560 * r**5 + 105 * r**3 - 6 * r) * np.sin(theta))
    if max_index >= 49:
        Z.append(924 * r**12 - 2772 * r**10 + 3150 * r**8 - 1680 * r**6 + 420 * r**4 - 42 * r**2 + 1)  # Z49
    if max_index >= 50:
        Z.append(r**7 * np.cos(7 * theta))  # Z50
    if max_index >= 51:
        Z.append(r**7 * np.sin(7 * theta))  # Z51
    if max_index >= 52:
        Z.append((8 * r**8 - 7 * r**6) * np.cos(6 * theta))  # Z52
    if max_index >= 53:
        Z.append((8 * r**8 - 7 * r**6) * np.sin(6 * theta))  # Z53
    if max_index >= 54:
        Z.append((36 * r**9 - 56 * r**7 + 21 * r**5) * np.cos(5 * theta))  # Z54
    if max_index >= 55:
        Z.append((36 * r**9 - 56 * r**7 + 21 * r**5) * np.sin(5 * theta))  # Z55
    if max_index >= 56:
        Z.append((120 * r**10 - 210 * r**8 + 105 * r**6 - 15 * r**4) * np.cos(4 * theta))  # Z56
    if max_index >= 57:
        Z.append((120 * r**10 - 210 * r**8 + 105 * r**6 - 15 * r**4) * np.sin(4 * theta))  # Z57
    if max_index >= 58:
        Z.append((330 * r**11 - 792 * r**9 + 594 * r**7 - 165 * r**5 + 15 * r**3) * np.cos(3 * theta))  # Z58
    if max_index >= 59:
        Z.append((330 * r**11 - 792 * r**9 + 594 * r**7 - 165 * r**5 + 15 * r**3) * np.sin(3 * theta))  # Z59
    if max_index >= 60:
        Z.append((792 * r**12 - 1980 * r**10 + 1650 * r**8 - 550 * r**6 + 60 * r**4 - r**2) * np.cos(2 * theta))  # Z60
    if max_index >= 61:
        Z.append((792 * r**12 - 1980 * r**10 + 1650 * r**8 - 550 * r**6 + 60 * r**4 - r**2) * np.sin(2 * theta))  # Z61
    if max_index >= 62:
        Z.append((1716 * r**13 - 4620 * r**11 + 4620 * r**9 - 1980 * r**7 + 330 * r**5 - 20 * r**3 + r) * np.cos(theta))  # Z62
    if max_index >= 63:
        Z.append((1716 * r**13 - 4620 * r**11 + 4620 * r**9 - 1980 * r**7 + 330 * r**5 - 20 * r**3 + r) * np.sin(theta))  # Z63
    if max_index >= 64:
        Z.append(3432 * r**14 - 10296 * r**12 + 12870 * r**10 - 7920 * r**8 + 2310 * r**6 - 315 * r**4 + 15 * r**2 - 1)  # Z64

    return np.array(Z).T  # 각 다항식이 열로 구성된 행렬






# 좌표 변환 및 Zernike 기저 생성 함수
def prepare_zernike_coordinates(group, max_index):
    """
    Zernike 좌표 및 기저 행렬 생성
    :param group: UNIQUE_ID별 그룹 데이터
    :param max_order: 최대 차수
    :return: Zernike 기저 행렬
    """
    die_x = group['DieX']
    die_y = group['DieY']
    step_pitch_x = group['STEP_PITCH_X']
    step_pitch_y = group['STEP_PITCH_Y']
    map_shift_x = group['MAP_SHIFT_X']
    map_shift_y = group['MAP_SHIFT_Y']
    coordinate_x = group['coordinate_X']
    coordinate_y = group['coordinate_Y']

    # 방사 좌표계 변환
    wf_x = die_x * step_pitch_x + map_shift_x + coordinate_x
    wf_y = die_y * step_pitch_y + map_shift_y + coordinate_y
    r = np.sqrt(wf_x**2 + wf_y**2) / 150000  # 0~1로 스케일링
    theta = np.arctan2(wf_y, wf_x)

    # Zernike 기저 행렬 생성
    return compute_fringe_zernike_matrix(r, theta, max_index=max_index)


# Zernike 분석 함수
def zernike_analysis(df_rawdata, max_index):
    """
    Zernike 회귀분석 및 잔차 계산
    :param df_rawdata: 입력 데이터
    :param max_order: Zernike 다항식 최대 차수
    :return: (df_z_coeff, df_rawdata_with_predictions)
    """
    grouped = df_rawdata.groupby('UNIQUE_ID')
    coeff_results = []

    # 원본 데이터프레임에 예측값 및 잔차 열 추가
    df_rawdata['Z_pred_x'] = np.nan
    df_rawdata['Z_pred_y'] = np.nan
    df_rawdata['Z_residual_x'] = np.nan
    df_rawdata['Z_residual_y'] = np.nan

    for unique_id, group in grouped:
        logging.info(f"Processing UNIQUE_ID: {unique_id}")

        # Zernike 기저 생성
        Z = prepare_zernike_coordinates(group, max_index=max_index)

        # 종속변수
        Y_dx = group['raw_x']
        Y_dy = group['raw_y']

        # 회귀 계수 계산
        coeff_dx = np.linalg.lstsq(Z, Y_dx, rcond=None)[0]
        coeff_dy = np.linalg.lstsq(Z, Y_dy, rcond=None)[0]
        coeff_dx = coeff_dx * 1000
        coeff_dy = coeff_dy * 1000
        

        # 회귀 계수 저장
        coeff_result = {'UNIQUE_ID': unique_id}
        coeff_result.update({f'Z{i+1}_dx': coeff for i, coeff in enumerate(coeff_dx)})
        coeff_result.update({f'Z{i+1}_dy': coeff for i, coeff in enumerate(coeff_dy)})
        coeff_results.append(coeff_result)

        # 예측값 계산
        pred_x = (Z @ coeff_dx) / 1000
        pred_y = (Z @ coeff_dy) / 1000

        # 잔차 계산
        residual_x = Y_dx - pred_x
        residual_y = Y_dy - pred_y

        # 원본 데이터프레임에 추가
        df_rawdata.loc[group.index, 'Z_pred_x'] = pred_x
        df_rawdata.loc[group.index, 'Z_pred_y'] = pred_y
        df_rawdata.loc[group.index, 'Z_residual_x'] = residual_x
        df_rawdata.loc[group.index, 'Z_residual_y'] = residual_y

    # 회귀 계수 결과 데이터프레임 생성
    df_z_coeff = pd.DataFrame(coeff_results)
    return df_z_coeff, df_rawdata



