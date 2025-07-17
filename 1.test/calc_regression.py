# 250321 design_matrix.py에서 design_matrix를 가져오도록 수정
# 250321 outlier detection에서 dmargin_x, dmargin_y, outlier_spec_ratio 를 config에서 가져오도록 수정
# 250118 adi용으로 wk,rk regression할때,  X_reg, Y_reg가 아닌 raw_x, raw_y를 사용하도록 수정

from config import PROCESS_MODE
from process_mode import PROCESS_MODE_FUNCTIONS

from config import DEFAULT_OSR_OPTION, DEFAULT_CPE_OPTION, DEFAULT_CPE_FIT_OPTION
from config import OUTLIER_THRESHOLD, DMARGIN_X, DMARGIN_Y, OUTLIER_SPEC_RATIO


from design_matrix import osr_wk6p_rk6p, osr_wk20p_rk15p, osr_wk20p_rk18p, osr_wk20p_rk19p, osr_wk20p_rk20p
from design_matrix import cpe_15para, cpe_18para, cpe_6para, cpe_20para, cpe_38para, cpe_k_to_fit

from design_matrix import DESIGN_MATRIX_FUNCTIONS


import pandas as pd
import numpy as np
from datetime import datetime
import time
import os


# Function to extract coordinates
def get_coordinates(group):
    die_x = group['DieX'].values
    die_y = group['DieY'].values
    step_pitch_x = group['STEP_PITCH_X'].values
    step_pitch_y = group['STEP_PITCH_Y'].values
    map_shift_x = group['MAP_SHIFT_X'].values
    map_shift_y = group['MAP_SHIFT_Y'].values
    coordinate_x = group['coordinate_X'].values
    coordinate_y = group['coordinate_Y'].values

    x = die_x * step_pitch_x + map_shift_x
    y = die_y * step_pitch_y + map_shift_y
    rx = coordinate_x
    ry = coordinate_y

    return x, y, rx, ry

# Function to get MRC k-values
def get_mrc_k_values(df_mrc_input, unique_id):
    mrc_k_odd = df_mrc_input[
        (df_mrc_input['UNIQUE_ID'] == unique_id) & 
        (df_mrc_input['K PARA'].isin([
            'W1', 'W3', 'W5', 'W7', 'W9', 'W11', 'W13', 'W15', 'W17', 'W19',
            'R3', 'R5', 'R7', 'R9', 'R11', 'R13', 'R15', 'R17', 'R19'
        ]))
    ]['GPM'].values.astype(float)
    mrc_k_even = df_mrc_input[
        (df_mrc_input['UNIQUE_ID'] == unique_id) & 
        (df_mrc_input['K PARA'].isin([
            'W2', 'W4', 'W6', 'W8', 'W10', 'W12', 'W14', 'W16', 'W18', 'W20',
            'R4', 'R6', 'R8', 'R10', 'R12', 'R14', 'R16', 'R18', 'R20'
        ]))
    ]['GPM'].values.astype(float)

    
    if len(mrc_k_odd) != 19 or len(mrc_k_even) != 19:
        return None, None
    

    return mrc_k_odd, mrc_k_even

# Function to perform MRC decorrection
def kmrc_decorrect(df_rawdata, df_mrc_input):
    grouped = df_rawdata.groupby('UNIQUE_ID3')
    mrc_list = []

    for unique_id, group in grouped:
        x, y, rx, ry = get_coordinates(group)
        X_dx, X_dy = osr_wk20p_rk20p(x, y, rx, ry)

        mrc_k_odd, mrc_k_even = get_mrc_k_values(df_mrc_input, unique_id)

        if mrc_k_odd is None or mrc_k_even is None:
            print(f"UNIQUE_ID {unique_id}의 MRC 데이터가 부족합니다.")
            continue

        mrc_fit_x = X_dx.dot(mrc_k_odd) * -1
        mrc_fit_y = X_dy.dot(mrc_k_even) * -1

        X_reg_demrc = group['X_reg'].values - mrc_fit_x
        Y_reg_demrc = group['Y_reg'].values - mrc_fit_y

        mrc_list.append(pd.DataFrame({
            'mrc_fit_x': mrc_fit_x,
            'mrc_fit_y': mrc_fit_y,
            'X_reg_demrc': X_reg_demrc,
            'Y_reg_demrc': Y_reg_demrc,
        }))

    df_mrc_de = pd.concat(mrc_list, ignore_index=True)
    return df_mrc_de

# Function to perform WK,RK Input decorrection
def wk_rk_input_decorrect(df_rawdata, df_wk_rk_input):
    grouped = df_rawdata.groupby('UNIQUE_ID3')
    wk_rk_input_list = []

    for unique_id, group in grouped:
        x, y, rx, ry = get_coordinates(group)
        X_dx, X_dy = osr_wk20p_rk20p(x, y, rx, ry)

        mrc_k_odd, mrc_k_even = get_mrc_k_values(df_wk_rk_input, unique_id)

        if mrc_k_odd is None or mrc_k_even is None:
            print(f"UNIQUE_ID {unique_id}의 MRC 데이터가 부족합니다.")
            continue

        wk_rk_input_fit_x = X_dx.dot(mrc_k_odd) * -1
        wk_rk_input_fit_y = X_dy.dot(mrc_k_even) * -1

        X_reg_demrc_dewkrk = group['X_reg_demrc'].values - wk_rk_input_fit_x
        Y_reg_demrc_dewkrk = group['Y_reg_demrc'].values - wk_rk_input_fit_y

        wk_rk_input_list.append(pd.DataFrame({
            'wk_rk_input_fit_x': wk_rk_input_fit_x,
            'wk_rk_input_fit_y': wk_rk_input_fit_y,
            'X_reg_demrc_dewkrk': X_reg_demrc_dewkrk,
            'Y_reg_demrc_dewkrk': Y_reg_demrc_dewkrk,
        }))

    df_mrcwkrk_de = pd.concat(wk_rk_input_list, ignore_index=True)
    return df_mrcwkrk_de



# Function to remove PSM input and add point MRC
def remove_psm_add_pointmrc(df_rawdata):
    df_rawdata['raw_x'] = df_rawdata['X_reg_demrc'] + df_rawdata['MRC_X'] 
    df_rawdata['raw_y'] = df_rawdata['Y_reg_demrc'] + df_rawdata['MRC_Y'] 
    return df_rawdata


# Function to perform multi-lot regression & fit & residual 

def multi_lot_regression_and_fitting(df_rawdata, osr_option=DEFAULT_OSR_OPTION, process_mode='ADI'):
    """
    여러 로트의 데이터를 그룹별로 회귀분석하고 예측 및 잔차를 계산하는 함수.
    osr_option에 따른 디자인 행렬과 회귀 계수 키를 매핑 테이블로 관리하여,
    조건 분기 코드를 단순화했습니다.
    """
    # osr_option에 따른 회귀 계수 키 목록 매핑 테이블
    coeff_keys_mapping = {
        '18para': {
            'dx': ['WK1', 'WK3', 'WK5', 'WK7', 'WK9', 'WK11', 'WK13', 'WK15', 'WK17', 'WK19',
                   'RK3', 'RK5', 'RK7', 'RK9', 'RK11', 'RK15', 'RK17', 'RK19'],
            'dy': ['WK2', 'WK4', 'WK6', 'WK8', 'WK10', 'WK12', 'WK14', 'WK16', 'WK18', 'WK20',
                   'RK4', 'RK6', 'RK8', 'RK10', 'RK12', 'RK14', 'RK16', 'RK18']
        },
        '15para': {
            'dx': ['WK1', 'WK3', 'WK5', 'WK7', 'WK9', 'WK11', 'WK13', 'WK15', 'WK17', 'WK19',
                   'RK3', 'RK5', 'RK7', 'RK11', 'RK19'],
            'dy': ['WK2', 'WK4', 'WK6', 'WK8', 'WK10', 'WK12', 'WK14', 'WK16', 'WK18', 'WK20',
                   'RK4', 'RK6', 'RK8', 'RK10', 'RK12', 'RK14', 'RK16']
        },
        '6para': {
            'dx': ['WK1', 'WK3', 'WK5', 'RK3', 'RK5'],
            'dy': ['WK2', 'WK4', 'WK6', 'RK4', 'RK6']
        },
        '19para': {
            'dx': ['WK1', 'WK3', 'WK5', 'WK7', 'WK9', 'WK11', 'WK13', 'WK15', 'WK17', 'WK19',
                   'RK3', 'RK5', 'RK7', 'RK9', 'RK11', 'RK13', 'RK15', 'RK17', 'RK19'],
            'dy': ['WK2', 'WK4', 'WK6', 'WK8', 'WK10', 'WK12', 'WK14', 'WK16', 'WK18', 'WK20',
                   'RK4', 'RK6', 'RK8', 'RK10', 'RK12', 'RK14', 'RK16', 'RK18']
        }
    }
    
    # 선택된 osr_option에 따른 계수 키 목록을 매핑 테이블에서 가져옴.
    # 만약 osr_option이 매핑 테이블에 없으면 기본값으로 '19para'를 사용합니다.
    coeff_keys = coeff_keys_mapping.get(osr_option, coeff_keys_mapping['19para'])
    dx_coeff_keys = coeff_keys['dx']
    dy_coeff_keys = coeff_keys['dy']
    
    # 디자인 행렬 함수 선택 (기존 매핑 사용)
    dm_func = DESIGN_MATRIX_FUNCTIONS['osr'][osr_option]
    
    # UNIQUE_ID로 그룹화
    grouped = df_rawdata.groupby('UNIQUE_ID')
    wkrk_results = []
    
    # 예측값과 잔차를 저장할 컬럼을 미리 생성
    df_rawdata['pred_x'] = np.nan
    df_rawdata['pred_y'] = np.nan
    df_rawdata['residual_x'] = np.nan
    df_rawdata['residual_y'] = np.nan

    for unique_id, group in grouped:
        x, y, rx, ry = get_coordinates(group)
        X_dx, X_dy = dm_func(x, y, rx, ry)
        
        # PROCESS_MODE에 따른 Y값 선택 (기본은 'ADI')
        Y_dx, Y_dy = PROCESS_MODE_FUNCTIONS.get(process_mode, PROCESS_MODE_FUNCTIONS['ADI'])(group)
        
        # 최소자승법으로 회귀 계수 계산
        coeff_dx = np.linalg.lstsq(X_dx, Y_dx, rcond=None)[0]
        coeff_dy = np.linalg.lstsq(X_dy, Y_dy, rcond=None)[0]
        
        # 회귀 계수 저장
        result_coeffs = {'UNIQUE_ID': unique_id}
        for idx, key in enumerate(dx_coeff_keys):
            result_coeffs[key] = coeff_dx[idx]
        for idx, key in enumerate(dy_coeff_keys):
            result_coeffs[key] = coeff_dy[idx]
        wkrk_results.append(result_coeffs)
        
        # 예측값 및 잔차 계산
        pred_x = X_dx.dot(coeff_dx)
        pred_y = X_dy.dot(coeff_dy)
        residual_x = Y_dx - pred_x
        residual_y = Y_dy - pred_y
        
        # 원본 데이터에 결과 반영
        df_rawdata.loc[group.index, 'pred_x'] = pred_x
        df_rawdata.loc[group.index, 'pred_y'] = pred_y
        df_rawdata.loc[group.index, 'residual_x'] = residual_x
        df_rawdata.loc[group.index, 'residual_y'] = residual_y
    
    # 회귀 계수를 DataFrame으로 변환하여 반환
    df_coeffs = pd.DataFrame(wkrk_results)
    return df_coeffs




def detect_outliers_studentized_residual(
    df_rawdata,
    threshold=OUTLIER_THRESHOLD, 
    group_col='UNIQUE_ID',
    get_coordinates_fn=None, 
    get_design_matrices_fn=None,
    dmargin_x=DMARGIN_X,    # X방향 DMARGIN
    dmargin_y=DMARGIN_Y,    # Y방향 DMARGIN
    outlier_spec_ratio=OUTLIER_SPEC_RATIO
):
    """
    Studentized Residual을 기준으로 1차 판정 후,
    추가로 e_x, e_y가 (dmargin_x * outlier_spec_ratio), (dmargin_y * outlier_spec_ratio)를
    각각 초과하는지를 확인해 최종 outlier로 판정.

    Args:
        df_rawdata (DataFrame): DieX, DieY, STEP_PITCH_X, etc... 포함
        threshold (float): Studentized residual 절댓값 임계값
        group_col (str): 그룹핑할 컬럼명 (예: UNIQUE_ID)
        get_coordinates_fn (function): wafer 좌표 구하는 함수 (기본: get_coordinates)
        get_design_matrices_fn (function): design matrix 만드는 함수 (기본: get_kmrc_design_matrices)
        dmargin_x (float): X방향 DMARGIN
        dmargin_y (float): Y방향 DMARGIN
        outlier_spec_ratio (float): DMARGIN 배율

    Returns:
        df_rawdata (DataFrame):
            'is_outlier' 컬럼이 추가됨 (최종 outlier 여부 True/False).
    """

    # 0) get_coordinates_fn, get_design_matrices_fn 기본 설정
    if get_coordinates_fn is None:
        get_coordinates_fn = get_coordinates
    if get_design_matrices_fn is None:
        get_design_matrices_fn = osr_wk6p_rk6p

    df_rawdata['is_outlier'] = False  # 초기화

    grouped = df_rawdata.groupby(group_col)

    for unique_id, group in grouped:
        # (x, y, rx, ry) 좌표 구하기
        x, y, rx, ry = get_coordinates_fn(group)
        
        # 디자인 행렬
        X_dx, X_dy = get_design_matrices_fn(x, y, rx, ry)

        # 종속변수 (raw_x, raw_y) = 계측 Overlay
        Y_dx = group['raw_x'].values
        Y_dy = group['raw_y'].values

        # -----------------------------
        # 1) OLS 회귀계수 + 예측 + 잔차
        coeff_dx = np.linalg.lstsq(X_dx, Y_dx, rcond=None)[0]
        coeff_dy = np.linalg.lstsq(X_dy, Y_dy, rcond=None)[0]

        pred_x = X_dx.dot(coeff_dx)
        pred_y = X_dy.dot(coeff_dy)
        e_x = Y_dx - pred_x  # residual_x
        e_y = Y_dy - pred_y  # residual_y

        n_x, p_x = X_dx.shape
        n_y, p_y = X_dy.shape

        # -----------------------------
        # 2) Hat Matrix 계산
        inv_x = np.linalg.inv(X_dx.T @ X_dx)
        H_dx = X_dx @ inv_x @ X_dx.T
        h_x_diag = np.diag(H_dx)

        inv_y = np.linalg.inv(X_dy.T @ X_dy)
        H_dy = X_dy @ inv_y @ X_dy.T
        h_y_diag = np.diag(H_dy)

        # -----------------------------
        # 3) MSE(추정분산) 계산
        SSE_x = np.sum(e_x**2)
        SSE_y = np.sum(e_y**2)
        dof_x = max(n_x - p_x, 1)
        dof_y = max(n_y - p_y, 1)

        MSE_x = SSE_x / dof_x
        MSE_y = SSE_y / dof_y

        # -----------------------------
        # 4) Studentized Residual 계산
        eps = 1e-15
        denom_x = np.sqrt(np.clip((1.0 - h_x_diag), eps, None) * MSE_x)
        denom_y = np.sqrt(np.clip((1.0 - h_y_diag), eps, None) * MSE_y)

        r_x = e_x / denom_x  # studentized residual_x
        r_y = e_y / denom_y  # studentized residual_y

        # (1단계) studentized residual 기준 outlier 후보
        sr_mask = (np.abs(r_x) > threshold) | (np.abs(r_y) > threshold)

        # -----------------------------
        # 5) (2단계) e_x, e_y가 DMARGIN * ratio 초과?
        #    X방향은 dmargin_x, Y방향은 dmargin_y 사용
        limit_x = dmargin_x * outlier_spec_ratio
        limit_y = dmargin_y * outlier_spec_ratio

        # residual이 limit를 초과하는지
        bigger_than_margin_mask = (np.abs(e_x) > limit_x) | (np.abs(e_y) > limit_y)

        # 최종 outlier = (1단계) & (2단계)
        final_outlier_mask = sr_mask & bigger_than_margin_mask

        # df_rawdata 반영
        df_rawdata.loc[group.index, 'is_outlier'] = final_outlier_mask

    return df_rawdata







def reorder_coefficients(df_coeffs):
    # 원하는 컬럼 순서 정의
    desired_order = [
        'UNIQUE_ID',
        # WK 계수
        'WK1', 'WK2', 'WK3', 'WK4', 'WK5', 'WK6', 'WK7', 'WK8', 'WK9', 'WK10',
        'WK11', 'WK12', 'WK13', 'WK14', 'WK15', 'WK16', 'WK17', 'WK18', 'WK19', 'WK20',
        # RK 계수
        'RK3', 'RK4', 'RK5', 'RK6', 'RK7', 'RK8', 'RK9', 'RK10', 'RK11', 'RK12',
        'RK13', 'RK14', 'RK15', 'RK16', 'RK17', 'RK18', 'RK19'
    ]
    # 데이터프레임의 실제 컬럼과 교집합을 구하여 존재하는 컬럼만 사용
    existing_columns = [col for col in desired_order if col in df_coeffs.columns]
    # 데이터프레임의 컬럼을 재정렬
    df_coeffs = df_coeffs[existing_columns]
    return df_coeffs






# Function to perform PSM decorrection

def psm_decorrect(df_rawdata, df_psm_input, cpe_fit_option=DEFAULT_CPE_FIT_OPTION):
    """
    PSM 보정 결과를 계산하는 함수입니다.
    
    인자:
        df_rawdata: 원시 데이터 프레임 (예: 'coordinate_X', 'coordinate_Y', 'residual_x', 'residual_y',
                    'TEST', 'DieX', 'DieY', 'UNIQUE_ID3' 등 포함)
        df_psm_input: PSM 입력 데이터 프레임 (예: 'UNIQUE_ID', 'dCol', 'dRow' 및 PSM 파라메터 값들)
        psm_option: 사용할 PSM 디자인 행렬 옵션 (예: '33para' 또는 '38para'; 기본값은 DEFAULT_PSM_OPTION)
    
    동작:
      - design_matrix.py에서 선택한 psm 디자인 행렬 함수를 가져와 rx, ry 값으로 행렬을 생성합니다.
      - 각 그룹(UNIQUE_ID3, DieX, DieY)에 대해 PSM 입력 데이터에서 파라메터 값을 추출합니다.
        파라메터 개수는 디자인 행렬의 열 수(n_params)에 따라 결정되며, df_psm_input에서
        열 인덱스 15부터 (n_params * 2)개를 가져와 짝수 인덱스는 X, 홀수 인덱스는 Y 파라메터로 사용합니다.
      - 계산된 디자인 행렬과 파라메터 벡터로 PSM 보정값(psm_fit_x, psm_fit_y)을 구한 후,
        기존 residual_x, residual_y에서 차감하여 보정된 잔차(residual_x_depsm, residual_y_depsm)를 산출합니다.
    """
    # 선택한 psm 옵션에 따른 디자인 행렬 함수 가져오기
    dm_func = DESIGN_MATRIX_FUNCTIONS['cpe_fit'][cpe_fit_option]
    
    # 그룹별로 계산 (그룹 기준: UNIQUE_ID3, DieX, DieY)
    grouped = df_rawdata.groupby(['UNIQUE_ID3', 'DieX', 'DieY'])
    psm_input_list = []

    for (unique_id, diex, diey), group in grouped:
        test = group['TEST']
        die_x = group['DieX']
        die_y = group['DieY']
        rx = group['coordinate_X'].values
        ry = group['coordinate_Y'].values

        X_dx, X_dy = dm_func(rx, ry)
        

        psm_row = df_psm_input[
            (df_psm_input['UNIQUE_ID'] == unique_id) &
            (df_psm_input['dCol'] == diex) &
            (df_psm_input['dRow'] == diey)
        ]

        if psm_row.empty:
            Y_dx = np.zeros(36)
            Y_dy = np.zeros(36)
        else:
            rk_values = psm_row.iloc[:, 15:87]
            Y_dx = rk_values.iloc[:, ::2].values.flatten()
            Y_dy = rk_values.iloc[:, 1::2].values.flatten()

        psm_fit_x = X_dx.dot(Y_dx)
        psm_fit_y = X_dy.dot(Y_dy)

        residual_x_depsm = group['residual_x'].values - psm_fit_x
        residual_y_depsm = group['residual_y'].values - psm_fit_y

        psm_input_list.append(pd.DataFrame({
            'UNIQUE_ID': unique_id,
            'TEST' : test,
            'DieX' : die_x,
            'DieY' : die_y,
            'psm_fit_x': psm_fit_x,
            'psm_fit_y': psm_fit_y,
            'residual_x_depsm': residual_x_depsm,
            'residual_y_depsm': residual_y_depsm
        }))


    # 결과 병합
    df_psm_de = pd.concat(psm_input_list, ignore_index=True)

    # 정렬 (★ 기존데이터의 정렬순서와 맞춰주기위한 작업)
    df_psm_de = df_psm_de.sort_values(by=['UNIQUE_ID', 'TEST', 'DieX', 'DieY'])

    # 'UNIQUE_ID', 'TEST', 'DieX', 'DieY' 컬럼을 삭제
    df_psm_de = df_psm_de.drop(['UNIQUE_ID', 'TEST', 'DieX', 'DieY'], axis=1)

    # ★★★ concat쓰려면 인덱스 리셋해야함. df_rawdata의 index와 df_psm_de의 index를 기준으로 병합함. 
    df_psm_de = df_psm_de.reset_index(drop=True)

    return df_psm_de




'''
def g_optimal(X_past, die_x, die_y, chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam, lambdas,rx,ry, cpe_option='38para' ):

    rx_nor = rx / chip_pitch_x
    ry_nor = ry / chip_pitch_y

    def virtual_38(rx, ry):

        X_dx = np.vstack([
            np.ones(len(rx)),
            rx, -ry,
            (rx ** 2), (rx * ry), (ry ** 2),
            (rx ** 3), (rx ** 2 * ry), (rx * ry ** 2), (ry ** 3),
            (rx ** 3 * ry), (rx ** 2 * ry ** 2), (rx * ry ** 3), (ry ** 4),
            (rx ** 3 * ry ** 2), (rx ** 2 * ry ** 3), (rx * ry ** 4), (ry ** 5),
            (rx ** 3 * ry ** 3), (rx ** 2 * ry ** 4),
            (rx ** 3 * ry ** 4)
        ]).T

        X_dy = np.vstack([
            np.ones(len(ry)),
            ry, rx,
            (ry ** 2), (ry * rx), (rx ** 2),
            (ry ** 3), (ry ** 2 * rx), (ry * rx ** 2),
            (ry ** 4), (ry ** 3 * rx), (ry ** 2 * rx ** 2),
            (ry ** 5), (ry ** 4 * rx) , (ry ** 3 * rx ** 2),
            (ry ** 5 * rx), (ry ** 4 * rx ** 2)
        ]).T  
        return X_dx, X_dy
    
    Xm_dx, Xm_dy = virtual_38(rx_nor,ry_nor)


    if X_past.shape[1] == 21:
        X = Xm_dx
    else:
        X = Xm_dy


    dm_func = DESIGN_MATRIX_FUNCTIONS['cpe'][cpe_option]
    ridge_term = lam * np.diag(lambdas)
    x_values = np.linspace(chip_center_x-0.5*chip_pitch_x,chip_center_x+0.5*chip_pitch_x,10)
    y_values = np.linspace(chip_center_y-0.5*chip_pitch_y,chip_center_y+0.5*chip_pitch_y,10)
    coordinates = []
    for i in x_values:
        for j in y_values:
            if (i**2+j**2)**0.5 < 144000:
                #print((i**2+j**2)**0.5)
                coordinates.append(((i-chip_center_x)/chip_pitch_x, (j-chip_center_y)/chip_pitch_y))        
    df_vir = pd.DataFrame(coordinates, columns=['coordinate_X', 'coordinate_Y'])
    #num_vir = df_vir.shape[0]
    #num_vir = int(num_vir)
    # print('df_vir', df_vir)
    # print(die_x,die_y)
    #print('X', X)
    df_vir['coordinate_X'] = df_vir['coordinate_X'].astype(float)
    df_vir['coordinate_Y'] = df_vir['coordinate_Y'].astype(float)

    

    rx2 = df_vir['coordinate_X'].values
    ry2 = df_vir['coordinate_Y'].values

    X_dx2, X_dy2 = virtual_38(rx2,ry2)

    if X.shape[1] == 21:
        X_ver = X_dx2
    else:
        X_ver = X_dy2


    XtX = X.T @ X
    XtX_ridge = XtX + ridge_term
    # solve를 사용해 수치적으로 안전한 해 구함
    X_df = X_ver @ np.linalg.solve(XtX_ridge, X.T)
    # 각 row의 제곱합 (== 대각 요소에 해당)
    leverage = np.sum(X_df**2, axis=1)
    G_OPT = round(np.sqrt(np.max(leverage)), 3)
    #if die_x == -4 and die_y == 4 :
    #    print(die_x, die_y, G_OPT, lam)

    return G_OPT



def ridge_regression(X, Y, die_x, die_y,chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, rx, ry, lam_init=0.0):
    if X.shape[1] == 21:
        lambdas = [0,0.01,0.01,1,1,0.1,1,1,1,0.1,1,1,1,1,1,1,1,1,1,1,1]
    else:
        lambdas = [0,0.01,0.01,0.1,0.1,1,0.1,0.1,1,1,1,1,1,1,1,1,1]

    def find_x_for_y_099(lam_p2, g_opt_p2, lam_p1, g_opt_p1, target_y=0.999):
        # 기울기 a, 절편 b 계산
        a = (g_opt_p1 - g_opt_p2) / (lam_p1 - lam_p2)
        b = g_opt_p2 - a * lam_p2

        # y = target_y일 때 x 계산
        if a == 0:
            x_at_target_y = lam_p1 + 0.1
        else:
            x_at_target_y = (target_y - b) / a
        if x_at_target_y < 0:
            x_at_target_y = lam_p1 - 0.5*(lam_p2 - lam_p1)

        return x_at_target_y

    lam = lam_init
    g_opt = g_optimal(X, die_x, die_y,chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam, lambdas, rx, ry)

    if g_opt>1:
            
        for i in range(0,50):
            
            if i == 0:
                lam_p1 = lam
                g_opt_p1 = g_opt
                if g_opt>100:
                    lam = 0.1
                elif g_opt>50:
                    lam = 0.03
                elif g_opt>10:
                    lam = 0.02
                else:
                    lam = 0.005
                g_opt = g_optimal(X, die_x, die_y, chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam, lambdas, rx, ry)

            elif i == 1:
                lam_p2, lam_p1, g_opt_p2, g_opt_p1 = lam_p1, lam, g_opt_p1, g_opt
                if g_opt_p2 > 1 and g_opt_p1 > 1:
                    lam = lam + (lam_p1 - lam_p2)/2
                    g_opt = g_optimal(X, die_x, die_y, chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam, lambdas, rx, ry)
                else:
                    lam = lam - (lam_p1 - lam_p2)/2
                    g_opt = g_optimal(X, die_x, die_y, chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam, lambdas, rx, ry)
            
            elif i == 2:
                lam_p3, lam_p2, lam_p1, g_opt_p3, g_opt_p2, g_opt_p1 = lam_p2, lam_p1, lam, g_opt_p2,g_opt_p1, g_opt
                if g_opt_p1 > 1:
                    lam = lam + (lam_p1 - lam_p2)/2
                    g_opt = g_optimal(X, die_x, die_y, chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam, lambdas, rx, ry)
                else:
                    lam = lam - abs(lam_p1 - lam_p2)/2
                    g_opt = g_optimal(X, die_x, die_y, chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam, lambdas, rx, ry)

            elif i == 3:
                lam_p3, lam_p2, lam_p1, g_opt_p3, g_opt_p2, g_opt_p1 = lam_p2, lam_p1, lam, g_opt_p2,g_opt_p1, g_opt
                if g_opt_p1 > 1:
                    lam = lam + (lam_p1 - lam_p2)/2
                    g_opt = g_optimal(X, die_x, die_y, chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam, lambdas, rx, ry)
                else:
                    lam = lam - abs(lam_p1 - lam_p2)/2
                    g_opt = g_optimal(X, die_x, die_y, chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam, lambdas, rx, ry)            

            else:
                lam_p3, lam_p2, lam_p1, g_opt_p3, g_opt_p2, g_opt_p1 = lam_p2, lam_p1, lam, g_opt_p2,g_opt_p1, g_opt
                lam = find_x_for_y_099(lam_p2, g_opt_p2, lam_p1, g_opt_p1, target_y=0.999)
                g_opt = g_optimal(X, die_x, die_y, chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam, lambdas, rx, ry)
            
            #if die_x == -4 and die_y == 4 and i > 2 :
                #print('i=', i, lam_p3, lam_p2, lam_p1,lam, g_opt_p3, g_opt_p2, g_opt_p1, g_opt)

            if 0.999 <= g_opt <= 1.0 or i == 49:
                print(i, die_x, die_y, g_opt, round(lam,5))
                break



    # 회귀 수행
    XtX = X.T @ X
    Xty = X.T @ Y
    ridge_term = lam * np.diag(lambdas)
    beta = np.linalg.inv(XtX + ridge_term) @ Xty

    return beta
'''







def g_optimal(X,chip_pitch_x,chip_pitch_y,chip_center_x,chip_center_y,lam,lambdas,cpe_option='38para'):
    dm_func = DESIGN_MATRIX_FUNCTIONS['cpe'][cpe_option]

    ridge_term = lam * np.diag(lambdas)

    x_values = np.linspace(
        chip_center_x - 0.5 * chip_pitch_x,
        chip_center_x + 0.5 * chip_pitch_x,
        10
    )
    y_values = np.linspace(
        chip_center_y - 0.5 * chip_pitch_y,
        chip_center_y + 0.5 * chip_pitch_y,
        10
    )

    coordinates = []
    for i in x_values:
        for j in y_values:
            r = np.sqrt(i ** 2 + j ** 2)
            if r < 144000:
                coordinates.append(
                    ((i - chip_center_x) * 1e-6, (j - chip_center_y) * 1e-6)
                )

    if not coordinates:
        raise ValueError("No valid virtual coordinates generated within 144000 radius.")

    coords = np.array(coordinates)
    rx2 = coords[:, 0]
    ry2 = coords[:, 1]

    X_dx2, X_dy2 = dm_func(rx2, ry2)

    if X.shape[1] == 21:
        X_ver = X_dx2
    else:
        X_ver = X_dy2

    XtX_ridge = X.T @ X + ridge_term

    try:
        temp = np.linalg.solve(XtX_ridge, X.T)
        X_df = X_ver @ temp
    except np.linalg.LinAlgError:
        raise RuntimeError("Matrix inversion failed in ridge regression.")

    leverage = np.sum(X_df ** 2, axis=1)
    g_opt = round(np.sqrt(np.max(leverage)), 3)
    print(g_opt)
    return g_opt, lam

def ridge_regression(
    X,
    Y,
    chip_pitch_x,
    chip_pitch_y,
    chip_center_x,
    chip_center_y,
    lam=0.0
):
    """
    Ridge 회귀 + lam 최적화

    Parameters
    ----------
    X : ndarray (n_samples, n_features)
    Y : ndarray (n_samples,)
    chip_pitch_x, chip_pitch_y : float
    chip_center_x, chip_center_y : float
    lam : float, default=0.0
        0.0이면 자동으로 경사하강법으로 찾음

    Returns
    -------
    beta : ndarray (n_features,)
    """

    # 항별 lambda 설정
    if X.shape[1] == 21:
        lambdas = [0,0.01,0.01,1,1,0.1,1,1,1,0.1,1,1,1,1,1,1,1,1,1,1,1]
    else:
        lambdas = [0,0.01,0.01,0.1,0.1,1,0.1,0.1,1,1,1,1,1,1,1,1,1]

    # lam=0이면 경사하강법으로 탐색
    if lam == 0.0:
        lam = optimize_lambda_gd(
            X,
            chip_pitch_x,
            chip_pitch_y,
            chip_center_x,
            chip_center_y,
            lambdas,
            initial_lambda=0.1,
            lr=0.5,
            max_iter=30,
            tol=1e-4
        )

    XtX = X.T @ X
    Xty = X.T @ Y
    ridge_term = lam * np.diag(lambdas)

    beta = np.linalg.solve(XtX + ridge_term, Xty)

    return beta



# ------------------------------
# lambda 최적화 함수
# ------------------------------
def optimize_lambda_gd(
    X,
    chip_pitch_x,
    chip_pitch_y,
    chip_center_x,
    chip_center_y,
    lambdas,
    initial_lambda=0.1,
    lr=0.5,
    max_iter=30,
    tol=1e-4
):
    lam = initial_lambda

    prev_loss = None

    for i in range(max_iter):
        g_opt, _ = g_optimal(
            X,
            chip_pitch_x,
            chip_pitch_y,
            chip_center_x,
            chip_center_y,
            lam,
            lambdas
        )
        loss = (g_opt - 1.0) ** 2

        if loss < tol:
            break

        # 수치 미분
        eps = 1e-4
        g_opt_eps, _ = g_optimal(
            X,
            chip_pitch_x,
            chip_pitch_y,
            chip_center_x,
            chip_center_y,
            lam + eps,
            lambdas
        )
        loss_eps = (g_opt_eps - 1.0) ** 2

        grad = (loss_eps - loss) / eps

        # gradient descent update
        lam = lam - lr * grad

        # lam 음수 방지
        lam = max(lam, 0.0)

        # 변화가 너무 적으면 조기 종료
        if prev_loss is not None and abs(prev_loss - loss) < 1e-8:
            break

        prev_loss = loss
    print(chip_center_x,chip_center_y,i,g_opt)
    return lam










# Function to model residuals using CPE 19-parameter model

def resi_to_cpe(df_rawdata, cpe_option=DEFAULT_CPE_OPTION):

    """
    CPE 보정을 위한 회귀분석을 수행합니다.
    각 그룹(UNIQUE_ID, DieX, DieY)에서 residual_x_depsm, residual_y_depsm을 대상으로 
    선택한 CPE 디자인 행렬(cpe_option)에 따라 회귀 계수를 산출합니다.
    
    인자:
        df_rawdata: 원시 데이터 프레임 (coordinate_X, coordinate_Y, residual_x_depsm, residual_y_depsm, 
                    UNIQUE_ID, DieX, DieY, UNIQUE_ID4 등 포함)
        cpe_option: 사용할 CPE 디자인 행렬 옵션 (예: '6para' 또는 '15para'; 기본값은 DEFAULT_CPE_OPTION)
        
    반환:
        각 그룹별 회귀 계수를 저장한 DataFrame (계수는 RK1, RK2, ... 형식)
    """
    # 선택한 옵션에 맞는 CPE 디자인 행렬 함수 가져오기
    dm_func = DESIGN_MATRIX_FUNCTIONS['cpe'][cpe_option]    
 
    grouped = df_rawdata.groupby(['UNIQUE_ID', 'DieX', 'DieY'])
    shot_regression_results = []

    for (unique_id, die_x, die_y), group in grouped:

        chip_pitch_x = group['STEP_PITCH_X'].values[0]
        chip_pitch_y = group['STEP_PITCH_Y'].values[0]
        chip_center_x = group['fcp_x'].values[0]
        chip_center_y = group['fcp_y'].values[0]
        
        rx = group['coordinate_X'].values
        ry = group['coordinate_Y'].values

        Yx = group['residual_x_depsm'].values
        Yy = group['residual_y_depsm'].values

        unique_id4 = group['UNIQUE_ID4'].values[0] # UNIQUE_ID4는 그룹별로 동일하므로 첫번째 값만 사용

        X_dx, X_dy = dm_func(rx, ry)

        if cpe_option == '38para':
            coeff_dx = ridge_regression(X_dx, Yx,chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam=0)
            coeff_dy = ridge_regression(X_dy, Yy,chip_pitch_x, chip_pitch_y, chip_center_x, chip_center_y, lam=0)

        else:
            coeff_dx = np.linalg.lstsq(X_dx, Yx, rcond=None)[0]
            coeff_dy = np.linalg.lstsq(X_dy, Yy, rcond=None)[0]

        if cpe_option == '15para':
            result = {
                'UNIQUE_ID': unique_id,
                'UNIQUE_ID4': unique_id4,
                'DieX': die_x,
                'DieY': die_y,
                'RK1': coeff_dx[0],
                'RK2': coeff_dy[0],
                'RK3': coeff_dx[1],
                'RK4': coeff_dy[1],
                'RK5': coeff_dx[2],
                'RK6': coeff_dy[2],
                'RK7': coeff_dx[3],
                'RK8': coeff_dy[3],
                'RK9': 0, 
                'RK10': coeff_dy[4],
                'RK11': coeff_dx[4], 
                'RK12': coeff_dy[5],
                'RK13': coeff_dx[5],
                'RK14': coeff_dy[6],
                'RK15': 0,
                'RK16': coeff_dy[7],
                'RK17': 0,
                'RK18': 0,
                'RK19': coeff_dx[6],
                'RK20': 0
            }
        elif cpe_option == '6para':
            result = {
                'UNIQUE_ID': unique_id,
                'UNIQUE_ID4': unique_id4,
                'DieX': die_x,
                'DieY': die_y,
                'RK1': coeff_dx[0],
                'RK2': coeff_dy[0],
                'RK3': coeff_dx[1],
                'RK4': coeff_dy[1],
                'RK5': coeff_dx[2],
                'RK6': coeff_dy[2],
                'RK7': 0,
                'RK8': 0,
                'RK9': 0,
                'RK10': 0,
                'RK11': 0,
                'RK12': 0,
                'RK13': 0,
                'RK14': 0,
                'RK15': 0,
                'RK16': 0,
                'RK17': 0,
                'RK18': 0,
                'RK19': 0,
                'RK20': 0
            }    
        elif cpe_option == '38para':
            result = {
                'UNIQUE_ID': unique_id,
                'UNIQUE_ID4': unique_id4,
                'DieX': die_x,
                'DieY': die_y,
                'RK1': coeff_dx[0],
                'RK2': coeff_dy[0],
                'RK3': coeff_dx[1],
                'RK4': coeff_dy[1],
                'RK5': coeff_dx[2],
                'RK6': coeff_dy[2],
                'RK7': coeff_dx[3],
                'RK8': coeff_dy[3],
                'RK9': coeff_dx[4],
                'RK10': coeff_dy[4],
                'RK11': coeff_dx[5],
                'RK12': coeff_dy[5],
                'RK13': coeff_dx[6],
                'RK14': coeff_dy[6],
                'RK15': coeff_dx[7],
                'RK16': coeff_dy[7],
                'RK17': coeff_dx[8],
                'RK18': coeff_dy[8],
                'RK19': coeff_dx[9],
                'RK20': 0,
                'RK21': 0,
                'RK22': coeff_dy[9],
                'RK23': coeff_dx[10],
                'RK24': coeff_dy[10],
                'RK25': coeff_dx[11],
                'RK26': coeff_dy[11],
                'RK27': coeff_dx[12],
                'RK28': 0,
                'RK29': coeff_dx[13],
                'RK30': 0,
                'RK31': 0,
                'RK32': coeff_dy[12],
                'RK33': 0,
                'RK34': coeff_dy[13],
                'RK35': coeff_dx[14],
                'RK36': coeff_dy[14],
                'RK37': coeff_dx[15],
                'RK38': 0,
                'RK39': coeff_dx[16],
                'RK40': 0,
                'RK41': coeff_dx[17],
                'RK42': 0,
                'RK43': 0,
                'RK44': 0,
                'RK45': 0,
                'RK46': coeff_dy[15],
                'RK47': 0,
                'RK48': coeff_dy[16],
                'RK49': coeff_dx[18],
                'RK50': 0,
                'RK51': coeff_dx[19],
                'RK52': 0,
                'RK53': 0,
                'RK54': 0,
                'RK55': 0,
                'RK56': 0,
                'RK57': 0,
                'RK58': 0,
                'RK59': 0,
                'RK60': 0,
                'RK61': 0,
                'RK62': 0,
                'RK63': 0,
                'RK64': 0,
                'RK65': coeff_dx[20]
            }  
        else: # RK18para
            result = {
                'UNIQUE_ID': unique_id,
                'UNIQUE_ID4': unique_id4,
                'DieX': die_x,
                'DieY': die_y,
                'RK1': coeff_dx[0],
                'RK2': coeff_dy[0],
                'RK3': coeff_dx[1],
                'RK4': coeff_dy[1],
                'RK5': coeff_dx[2],
                'RK6': coeff_dy[2],
                'RK7': coeff_dx[3],
                'RK8': coeff_dy[3],
                'RK9': coeff_dx[4],
                'RK10': coeff_dy[4],
                'RK11': coeff_dx[5],
                'RK12': coeff_dy[5],
                'RK13': 0,  # 기존에는 coeff_dx[6] 대신 0 처리
                'RK14': coeff_dy[6],
                'RK15': coeff_dx[6],
                'RK16': coeff_dy[7],
                'RK17': coeff_dx[7],
                'RK18': coeff_dy[8],
                'RK19': coeff_dx[8],
                'RK20': 0
            }

        shot_regression_results.append(result)

    df_cpe_k = pd.DataFrame(shot_regression_results)
    return df_cpe_k


# Function to fit CPE model and compute residuals
def cpe_k_to_fit(df_rawdata, df_cpe_k):
    results = []
    grouped = df_rawdata.groupby(['UNIQUE_ID', 'DieX', 'DieY'])

    for (unique_id, dx, dy), group in grouped:
        test = group['TEST']

        rx = group['coordinate_X'].values
        ry = group['coordinate_Y'].values
        residual_x_depsm = group['residual_x_depsm'].values
        residual_y_depsm = group['residual_y_depsm'].values


        X_dx, X_dy = cpe_38para(rx, ry)

        cpe_row = df_cpe_k[
            (df_cpe_k['UNIQUE_ID'] == unique_id) &
            (df_cpe_k['DieX'] == dx) &
            (df_cpe_k['DieY'] == dy)
        ]

        if cpe_row.empty:
            Y_dx = np.zeros(21)
            Y_dy = np.zeros(17)
        else:
            rk_values = cpe_row.iloc[:, 4:69]
            Y_dx = rk_values.iloc[:,[0,2,4,6,8,10,12,14,16,18,22,24,26,28,34,36,38,40,48,50,64]].values.flatten()
            Y_dy = rk_values.iloc[:,[1,3,5,7,9,11,13,15,17,21,23,25,31,33,35,45,47]].values.flatten()

        cpe_pred_x = X_dx.dot(Y_dx)
        cpe_pred_y = X_dy.dot(Y_dy)

        cpe_resi_x = residual_x_depsm - cpe_pred_x
        cpe_resi_y = residual_y_depsm - cpe_pred_y

        results.append(pd.DataFrame({
            'UNIQUE_ID': unique_id,
            'TEST': test,
            'DieX': dx,
            'DieY': dy,
            'cpe_pred_x': cpe_pred_x,
            'cpe_pred_y': cpe_pred_y,
            'cpe_resi_x': cpe_resi_x,
            'cpe_resi_y': cpe_resi_y
        }))

    # 결과 병합
    df_cpe_fit_res = pd.concat(results, ignore_index=True)



    # 정렬 (★ 기존데이터의 정렬순서와 맞춰주기위한 작업)
    df_cpe_fit_res = df_cpe_fit_res.sort_values(by=['UNIQUE_ID', 'TEST', 'DieX', 'DieY'])

    # 'UNIQUE_ID', 'TEST', 'DieX', 'DieY' 컬럼을 삭제
    df_cpe_fit_res = df_cpe_fit_res.drop(['UNIQUE_ID', 'TEST', 'DieX', 'DieY'], axis=1)

    # ★★★ concat쓰려면 인덱스 리셋해야함. df_rawdata의 index와 df_psm_de의 index를 기준으로 병합함. 
    df_cpe_fit_res = df_cpe_fit_res.reset_index(drop=True)

    return df_cpe_fit_res


# Function to compute ideal PSM
def ideal_psm(df_rawdata):
    df_rawdata['ideal_psm_x'] = -df_rawdata['cpe_pred_x']
    df_rawdata['ideal_psm_y'] = -df_rawdata['cpe_pred_y']
    return df_rawdata

# Function to compute delta PSM
def delta_psm(df_rawdata):
    df_rawdata['delta_psm_x'] = df_rawdata['ideal_psm_x'] - df_rawdata['psm_fit_x']
    df_rawdata['delta_psm_y'] = df_rawdata['ideal_psm_y'] - df_rawdata['psm_fit_y']
    return df_rawdata

# end
