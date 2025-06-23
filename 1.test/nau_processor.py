# 250602 xlwings 적용하면서 all mark는 삭제함. 나중에 추가하던지..




import os
import pandas as pd
import numpy as np  
from datetime import datetime
from openpyxl import load_workbook
import xlwings as xw

def load_excel_sheets(file_path):
    """
    xlwings를 사용해 RawData-1 시트를 header 포함 / 미포함 형태로 모두 로딩
    """
    app = xw.App(visible=False)
    try:
        wb = app.books.open(file_path)
        sheet = wb.sheets['RawData-1']

        # header 있는 DataFrame
        rawdata_file = sheet.used_range.options(pd.DataFrame, header=1, index=False).value

        # header 없는 DataFrame (방법 2)
        raw_values = sheet.used_range.value
        rawdata_file_no_header = pd.DataFrame(raw_values)

        # 디버깅용 저장
        rawdata_file.to_csv('rawdata_file.csv', index=False)
        rawdata_file_no_header.to_csv('rawdata_file_no_header.csv', index=False)

    finally:
        wb.close()
        app.quit()

    return rawdata_file, rawdata_file_no_header


def read_sheet_with_xlwings(file_path, sheet_name):
    """xlwings로 지정한 시트를 읽어 DataFrame 반환"""
    app = xw.App(visible=False)
    try:
        wb = app.books.open(file_path)
        sheet = wb.sheets[sheet_name]
        df = sheet.used_range.options(pd.DataFrame, header=1, index=False).value
    finally:
        wb.close()
        app.quit()
    return df



def remove_duplicate_files(folder_path):
    """E1 파일만 남기고 E2, E3 파일 삭제"""
    unique_files = {}
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path) and file_name.endswith('.nau'):
            file_name_without_extension = os.path.splitext(file_name)[0]
            split_file_name = file_name_without_extension.split("_")
            base_name = "_".join(split_file_name[:-1])
            file_suffix = split_file_name[-1]
            if base_name not in unique_files:
                if file_suffix == "E1":
                    unique_files[base_name] = file_path
            else:
                if file_suffix in ["E2", "E3"]:
                    try:
                        os.remove(file_path)
                        print(f"중복 파일 {file_name} 삭제 완료")
                    except Exception as e:
                        print(f"{file_name} 파일 삭제 중 에러 발생: {e}")

def extract_file_info(file_name):
    """파일명에서 필요한 정보를 추출하여 반환"""
    file_name_without_extension = os.path.splitext(file_name)[0]
    split_file_name = file_name_without_extension.split("_")
    info_dict = {
        'base_name': "_".join(split_file_name[:-1]),
        'file_suffix': split_file_name[-1],
        'split_file_name': split_file_name
    }
    return info_dict



def get_column_index(header_row, target_name):
    """
    중복 컬럼이 존재할 때, 원하는 컬럼명의 첫 번째 인덱스를 반환합니다.
    """
    for idx, name in enumerate(header_row):
        if isinstance(name, str) and name.strip() == target_name:
            return idx
    raise ValueError(f"'{target_name}' 컬럼을 찾을 수 없습니다.")



def process_rawdata_sheet(file_path, info_dict, rawdata_file):
    """RawData-1 시트를 처리 (미리 읽어둔 rawdata_file 사용)"""
    # 추출할 컬럼 위치 설정
    columns_to_extract = [0, 1, 2, 3, 4, 5, 6, 7]
    extracted_data_raw = rawdata_file.iloc[:, columns_to_extract].copy()

    # GROUP 컬럼 추가
    extracted_data_raw['GROUP'] = pd.cut(extracted_data_raw['TEST'], bins=[0, 80, 160, 240], labels=['E1', 'E2', 'E3'])

    # 추가 정보 추출 (여기서는 동일 rawdata_file 사용)
    lot_id_value_raw = rawdata_file.columns[13]
    stepseq_value_raw = rawdata_file.iloc[0, 13]
    wafer_value_raw = rawdata_file.iloc[0, 0]
    p_eqpid_value_raw = rawdata_file.iloc[1, 13]
    photo_ppid_value_raw = rawdata_file.iloc[11, 13]
    p_time_value_raw = rawdata_file.iloc[2, 13]
    m_time_value_raw = rawdata_file.iloc[4, 13]
    chuckid_value_raw = rawdata_file.iloc[15, 13]
    mmo_mrc_eqp_value_raw = rawdata_file.iloc[19, 13]

    # 새로운 컬럼 추가
    extracted_data_raw['STEPSEQ'] = stepseq_value_raw
    extracted_data_raw['LOT_ID'] = lot_id_value_raw

    # 추가 정보 컬럼 추가
    extracted_data_raw['STEP_PITCH_X'] = rawdata_file.iloc[6, 13]
    extracted_data_raw['STEP_PITCH_Y'] = rawdata_file.iloc[7, 13]
    extracted_data_raw['MAP_SHIFT_X'] = rawdata_file.iloc[8, 13]
    extracted_data_raw['MAP_SHIFT_Y'] = rawdata_file.iloc[9, 13]


    # === 중복 컬럼 처리: get_column_index 사용 ===
    test_no_idx = get_column_index(rawdata_file.columns, 'Test No')
    coord_x_idx = get_column_index(rawdata_file.columns, 'coordinate_X')
    coord_y_idx = get_column_index(rawdata_file.columns, 'coordinate_Y')
    mrc_rx_idx = get_column_index(rawdata_file.columns, 'MRC_RX')
    mrc_ry_idx = get_column_index(rawdata_file.columns, 'MRC_RY')

    
    # === 좌표 매핑 ===
    coord_map = rawdata_file.iloc[:, [test_no_idx, coord_x_idx, coord_y_idx]] \
        .drop_duplicates(subset=rawdata_file.columns[test_no_idx]) \
        .set_index(rawdata_file.columns[test_no_idx])

    extracted_data_raw['coordinate_X'] = extracted_data_raw['TEST'].map(coord_map[rawdata_file.columns[coord_x_idx]])
    extracted_data_raw['coordinate_Y'] = extracted_data_raw['TEST'].map(coord_map[rawdata_file.columns[coord_y_idx]])


    # === MRC 매핑 ===
    coord_map_mrc = rawdata_file.iloc[:, [test_no_idx, mrc_rx_idx, mrc_ry_idx]] \
        .drop_duplicates(subset=rawdata_file.columns[test_no_idx]) \
        .set_index(rawdata_file.columns[test_no_idx])

    extracted_data_raw['MRC_RX'] = extracted_data_raw['TEST'].map(coord_map_mrc[rawdata_file.columns[mrc_rx_idx]])
    extracted_data_raw['MRC_RY'] = extracted_data_raw['TEST'].map(coord_map_mrc[rawdata_file.columns[mrc_ry_idx]])

    

    # PSM_X, PSM_Y 계산
    mrc_x_minus_mrc_rx = extracted_data_raw['MRC_X'] - extracted_data_raw['MRC_RX']
    mrc_y_minus_mrc_ry = extracted_data_raw['MRC_Y'] - extracted_data_raw['MRC_RY']
    extracted_data_raw['PSM_X'] = 0 - mrc_x_minus_mrc_rx
    extracted_data_raw['PSM_Y'] = 0 - mrc_y_minus_mrc_ry

    # fcp_x, fcp_y 계산
    extracted_data_raw['fcp_x'] = (
        extracted_data_raw['DieX'] * extracted_data_raw['STEP_PITCH_X'] +
        extracted_data_raw['MAP_SHIFT_X']
    )
    extracted_data_raw['fcp_y'] = (
        extracted_data_raw['DieY'] * extracted_data_raw['STEP_PITCH_Y'] +
        extracted_data_raw['MAP_SHIFT_Y']
    )

    # wf_x, wf_y 계산
    extracted_data_raw['wf_x'] = (
        extracted_data_raw['DieX'] * extracted_data_raw['STEP_PITCH_X'] +
        extracted_data_raw['MAP_SHIFT_X'] + extracted_data_raw['coordinate_X']
    )
    extracted_data_raw['wf_y'] = (
        extracted_data_raw['DieY'] * extracted_data_raw['STEP_PITCH_Y'] +
        extracted_data_raw['MAP_SHIFT_Y'] + extracted_data_raw['coordinate_Y']
    )

    # radius 계산
    extracted_data_raw['radius'] = np.sqrt(
        extracted_data_raw['wf_x'] ** 2 + extracted_data_raw['wf_y'] ** 2)

    # 추가 정보 컬럼 추가
    extracted_data_raw['P_EQPID'] = p_eqpid_value_raw
    extracted_data_raw['P_TIME'] = p_time_value_raw
    extracted_data_raw['M_TIME'] = m_time_value_raw
    extracted_data_raw['Photo_PPID'] = photo_ppid_value_raw
    extracted_data_raw['Base_EQP1'] = rawdata_file.iloc[12, 13]
    extracted_data_raw['ChuckID'] = chuckid_value_raw
    extracted_data_raw['ReticleID'] = rawdata_file.iloc[16, 13]
    extracted_data_raw['MMO_MRC_EQP'] = mmo_mrc_eqp_value_raw
    extracted_data_raw['CHIP_X_NUM'] = rawdata_file.iloc[25, 13]
    extracted_data_raw['CHIP_Y_NUM'] = rawdata_file.iloc[26, 13]

    # context 정보추가 (250122)
    extracted_data_raw['Outlier_Spec_Ratio'] = rawdata_file.iloc[20, 13]
    extracted_data_raw['Dmargin_X'] = rawdata_file.iloc[3, 27]
    extracted_data_raw['Dmargin_Y'] = rawdata_file.iloc[4, 27]

    # UNIQUE_ID 컬럼 추가
    extracted_data_raw['UNIQUE_ID'] = extracted_data_raw.apply(
        lambda row: f"{row['STEPSEQ']}_{row['P_EQPID']}_{row['Photo_PPID']}_{row['MMO_MRC_EQP']}_"
                    f"{row['P_TIME']}_{row['M_TIME']}_{row['LOT_ID']}_{row['Wafer']}_{row['GROUP']}", axis=1)
    extracted_data_raw['UNIQUE_ID2'] = extracted_data_raw.apply(
        lambda row: f"{row['STEPSEQ']}_{row['P_EQPID']}_{row['Photo_PPID']}_{row['MMO_MRC_EQP']}_"
                    f"{row['P_TIME']}_{row['M_TIME']}_{row['LOT_ID']}_{row['Wafer']}_{row['TEST']}_"
                    f"{row['DieX']}_{row['DieY']}_{row['GROUP']}", axis=1)
    extracted_data_raw['UNIQUE_ID3'] = extracted_data_raw.apply(
        lambda row: f"{row['STEPSEQ']}_{row['P_EQPID']}_{row['Photo_PPID']}_{row['MMO_MRC_EQP']}_"
                    f"{row['P_TIME']}_{row['M_TIME']}_{row['LOT_ID']}_{row['Wafer']}", axis=1)
    extracted_data_raw['UNIQUE_ID4'] = extracted_data_raw.apply(
        lambda row: f"{row['STEPSEQ']}_{row['P_EQPID']}_{row['Photo_PPID']}_{row['MMO_MRC_EQP']}_"
                    f"{row['P_TIME']}_{row['M_TIME']}_{row['LOT_ID']}_{row['Wafer']}_"
                    f"{row['DieX']}_{row['DieY']}_{row['GROUP']}", axis=1)

    cols_order = [
        'UNIQUE_ID', 'UNIQUE_ID2', 'UNIQUE_ID3', 'UNIQUE_ID4',
        'STEPSEQ', 'LOT_ID', 'Wafer',
        'P_EQPID', 'Photo_PPID', 'P_TIME', 'M_TIME', 'ChuckID', 'ReticleID', 'Base_EQP1', 'MMO_MRC_EQP',
        'GROUP', 'TEST', 'DieX', 'DieY',
        'STEP_PITCH_X', 'STEP_PITCH_Y', 'MAP_SHIFT_X', 'MAP_SHIFT_Y', 'coordinate_X', 'coordinate_Y',
        'fcp_x', 'fcp_y', 'wf_x', 'wf_y', 'radius', 'CHIP_X_NUM', 'CHIP_Y_NUM',
        'Outlier_Spec_Ratio', 'Dmargin_X', 'Dmargin_Y', 
        'X_reg', 'Y_reg', 'MRC_X', 'MRC_Y', 'MRC_RX', 'MRC_RY', 'PSM_X', 'PSM_Y'
    ]
    extracted_data_raw = extracted_data_raw[cols_order]

    return extracted_data_raw


''' 
# Test No 좌표 추출 및 CSV 저장 함수 추가
def extract_test_coordinates(rawdata_file_no_header, save_path='test_coordinates.csv'):
    """RawData-1 시트에서 S~U열에 있는 Test No, coordinate_X, coordinate_Y 추출 후 CSV로 저장"""
    test_coord_df = rawdata_file_no_header.iloc[1:, 18:21].copy()
    test_coord_df.columns = ['Test No', 'coordinate_X', 'coordinate_Y']
    test_coord_df.reset_index(drop=True, inplace=True)
    test_coord_df.to_csv(save_path, index=False)
    print(f"Test coordinates saved to {save_path}")
    return test_coord_df
'''




def process_trocs_input_sheet(file_path, info_dict, rawdata_file):
    """Trocs Input 시트를 처리 (추가 정보는 미리 읽은 rawdata_file에서 추출)"""

    # xlwings로 Trocs Input 시트 읽기
    trocs_input_file = read_sheet_with_xlwings(file_path, 'Trocs Input')
    

    # 추가 정보 추출
    stepseq_value_raw = rawdata_file.iloc[0, 13]
    lot_id_value_raw = rawdata_file.columns[13]
    wafer_value_raw = rawdata_file.iloc[0, 0]
    p_eqpid_value_raw = rawdata_file.iloc[1, 13]
    photo_ppid_value_raw = rawdata_file.iloc[11, 13]
    p_time_value_raw = rawdata_file.iloc[2, 13]
    m_time_value_raw = rawdata_file.iloc[4, 13]
    chuckid_value_raw = rawdata_file.iloc[15, 13]
    mmo_mrc_eqp_value_raw = rawdata_file.iloc[19, 13]

    trocs_input_file['STEPSEQ'] = stepseq_value_raw
    trocs_input_file['LOT_ID'] = lot_id_value_raw
    trocs_input_file['Wafer'] = wafer_value_raw
    trocs_input_file['P_EQPID'] = p_eqpid_value_raw
    trocs_input_file['Photo_PPID'] = photo_ppid_value_raw
    trocs_input_file['P_TIME'] = p_time_value_raw
    trocs_input_file['M_TIME'] = m_time_value_raw
    trocs_input_file['ChuckID'] = chuckid_value_raw
    trocs_input_file['MMO_MRC_EQP'] = mmo_mrc_eqp_value_raw

    trocs_input_file['UNIQUE_ID'] = trocs_input_file.apply(
        lambda row: f"{row['STEPSEQ']}_{row['P_EQPID']}_{row['Photo_PPID']}_{row['MMO_MRC_EQP']}_"
                    f"{row['P_TIME']}_{row['M_TIME']}_{row['LOT_ID']}_{row['Wafer']}", axis=1)
    trocs_input_file['UNIQUE_ID2'] = trocs_input_file.apply(
        lambda row: f"{row['UNIQUE_ID']}_{row['dCol']}_{row['dRow']}", axis=1)

    cols_to_insert = ['UNIQUE_ID', 'UNIQUE_ID2', 'STEPSEQ', 'LOT_ID', 'Wafer', 'P_EQPID',
                      'Photo_PPID', 'MMO_MRC_EQP', 'P_TIME', 'M_TIME', 'ChuckID']
    for i, col in enumerate(cols_to_insert):
        trocs_input_file.insert(i, col, trocs_input_file.pop(col))

    return trocs_input_file

def process_psm_input_sheet(file_path, info_dict, rawdata_file):
    """PerShotMRC 시트를 처리 (추가 정보는 미리 읽은 rawdata_file에서 추출)"""

    # xlwings로 PerShotMRC 시트 읽기
    psm_input_file = read_sheet_with_xlwings(file_path, 'PerShotMRC')
    

    # 추가 정보 추출
    stepseq_value_raw = rawdata_file.iloc[0, 13]
    lot_id_value_raw = rawdata_file.columns[13]
    wafer_value_raw = rawdata_file.iloc[0, 0]
    p_eqpid_value_raw = rawdata_file.iloc[1, 13]
    photo_ppid_value_raw = rawdata_file.iloc[11, 13]
    p_time_value_raw = rawdata_file.iloc[2, 13]
    m_time_value_raw = rawdata_file.iloc[4, 13]
    chuckid_value_raw = rawdata_file.iloc[15, 13]
    mmo_mrc_eqp_value_raw = rawdata_file.iloc[19, 13]

    psm_input_file['STEPSEQ'] = stepseq_value_raw
    psm_input_file['LOT_ID'] = lot_id_value_raw
    psm_input_file['Wafer'] = wafer_value_raw
    psm_input_file['P_EQPID'] = p_eqpid_value_raw
    psm_input_file['Photo_PPID'] = photo_ppid_value_raw
    psm_input_file['P_TIME'] = p_time_value_raw
    psm_input_file['M_TIME'] = m_time_value_raw
    psm_input_file['ChuckID'] = chuckid_value_raw
    psm_input_file['MMO_MRC_EQP'] = mmo_mrc_eqp_value_raw

    psm_input_file['UNIQUE_ID'] = psm_input_file.apply(
        lambda row: f"{row['STEPSEQ']}_{row['P_EQPID']}_{row['Photo_PPID']}_{row['MMO_MRC_EQP']}_"
                    f"{row['P_TIME']}_{row['M_TIME']}_{row['LOT_ID']}_{row['Wafer']}", axis=1)
    psm_input_file['UNIQUE_ID2'] = psm_input_file.apply(
        lambda row: f"{row['UNIQUE_ID']}_{row['dCol']}_{row['dRow']}", axis=1)

    cols_to_insert_psm = ['UNIQUE_ID', 'UNIQUE_ID2', 'STEPSEQ', 'LOT_ID', 'Wafer', 'P_EQPID',
                          'Photo_PPID', 'MMO_MRC_EQP', 'P_TIME', 'M_TIME', 'ChuckID']
    for i, col in enumerate(cols_to_insert_psm):
        psm_input_file.insert(i, col, psm_input_file.pop(col))

    return psm_input_file

def process_mrc_data(file_path, info_dict, rawdata_file, rawdata_file_no_header):
    """MRC 데이터를 처리 (추가 정보는 미리 읽은 rawdata_file에서 추출, header-less 데이터는 rawdata_file_no_header 사용)"""
    # 추가 정보 추출
    stepseq_value_raw = rawdata_file.iloc[0, 13]
    lot_id_value_raw = rawdata_file.columns[13]
    wafer_value_raw = rawdata_file.iloc[0, 0]
    p_eqpid_value_raw = rawdata_file.iloc[1, 13]
    photo_ppid_value_raw = rawdata_file.iloc[11, 13]
    p_time_value_raw = rawdata_file.iloc[2, 13]
    m_time_value_raw = rawdata_file.iloc[4, 13]
    chuckid_value_raw = rawdata_file.iloc[15, 13]
    mmo_mrc_eqp_value_raw = rawdata_file.iloc[19, 13]

    mrc_part1 = rawdata_file_no_header.iloc[0:20, 15:17]
    mrc_part2 = rawdata_file_no_header.iloc[22:40, 15:17]
    mrc_part = pd.concat([mrc_part1, mrc_part2], ignore_index=True)
    print(mrc_part)

    mrc_part.columns = ['K PARA', 'GPM']
    mrc_part['INDEX'] = range(1, len(mrc_part) + 1)

    mrc_part['STEPSEQ'] = stepseq_value_raw
    mrc_part['LOT_ID'] = lot_id_value_raw
    mrc_part['Wafer'] = wafer_value_raw
    mrc_part['P_EQPID'] = p_eqpid_value_raw
    mrc_part['Photo_PPID'] = photo_ppid_value_raw
    mrc_part['P_TIME'] = p_time_value_raw
    mrc_part['M_TIME'] = m_time_value_raw
    mrc_part['ChuckID'] = chuckid_value_raw
    mrc_part['MMO_MRC_EQP'] = mmo_mrc_eqp_value_raw

    mrc_part['UNIQUE_ID'] = mrc_part.apply(
        lambda row: f"{row['STEPSEQ']}_{row['P_EQPID']}_{row['Photo_PPID']}_{row['MMO_MRC_EQP']}_"
                    f"{row['P_TIME']}_{row['M_TIME']}_{row['LOT_ID']}_{row['Wafer']}", axis=1)

    mrc_cols_order = [
        'UNIQUE_ID',
        'STEPSEQ', 'LOT_ID', 'Wafer',
        'P_EQPID', 'Photo_PPID', 'MMO_MRC_EQP', 'P_TIME', 'M_TIME', 'ChuckID',
        'K PARA', 'GPM', 'INDEX'
    ]
    mrc_part = mrc_part[mrc_cols_order]

    return mrc_part


def process_wk_rk_input_data(file_path, info_dict, rawdata_file):
    """
    RawData-1 시트에서 APC Input (WK, RK)값 및 관련 좌표를 추출하여 DataFrame으로 반환합니다.
    (이 예제에서는 'APC_WK'와 'APC_RK'라는 컬럼명이 존재한다고 가정합니다.)
    """
     
    # 추가 정보 추출
    stepseq_value_raw = rawdata_file.iloc[0, 13]
    lot_id_value_raw = rawdata_file.columns[13]
    wafer_value_raw = rawdata_file.iloc[0, 0]
    p_eqpid_value_raw = rawdata_file.iloc[1, 13]
    photo_ppid_value_raw = rawdata_file.iloc[11, 13]
    p_time_value_raw = rawdata_file.iloc[2, 13]
    m_time_value_raw = rawdata_file.iloc[4, 13]
    chuckid_value_raw = rawdata_file.iloc[15, 13]
    mmo_mrc_eqp_value_raw = rawdata_file.iloc[19, 13]

    # APC Input 데이터 추출
    wk_input = rawdata_file.iloc[0:20, 96]  # (20,)
    rk_input = rawdata_file.iloc[2:20, 97]  # (18,) RK1,2는 제외

    # 두 Series를 세로로 연결하여 (38,1) 형태의 DataFrame 생성
    wk_rk_input = pd.concat([wk_input, rk_input], axis=0, ignore_index=True).to_frame()
    
    # 'GPM' 컬럼명으로 변경
    wk_rk_input.columns = ['GPM']

    # 'K PARA' 컬럼 추가 (W1~W20, R3~R20)
    k_para_labels = [f"W{i+1}" for i in range(20)] + [f"R{i+3}" for i in range(18)]
    wk_rk_input['K PARA'] = k_para_labels
    

    wk_rk_input['INDEX'] = range(1, len(wk_rk_input) + 1)
    wk_rk_input['STEPSEQ'] = stepseq_value_raw
    wk_rk_input['LOT_ID'] = lot_id_value_raw
    wk_rk_input['Wafer'] = wafer_value_raw
    wk_rk_input['P_EQPID'] = p_eqpid_value_raw
    wk_rk_input['Photo_PPID'] = photo_ppid_value_raw
    wk_rk_input['P_TIME'] = p_time_value_raw
    wk_rk_input['M_TIME'] = m_time_value_raw
    wk_rk_input['ChuckID'] = chuckid_value_raw
    wk_rk_input['MMO_MRC_EQP'] = mmo_mrc_eqp_value_raw

    wk_rk_input['UNIQUE_ID'] = wk_rk_input.apply(
        lambda row: f"{row['STEPSEQ']}_{row['P_EQPID']}_{row['Photo_PPID']}_{row['MMO_MRC_EQP']}_"
                    f"{row['P_TIME']}_{row['M_TIME']}_{row['LOT_ID']}_{row['Wafer']}", axis=1)

    wk_rk_cols_order = [
        'UNIQUE_ID',
        'STEPSEQ', 'LOT_ID', 'Wafer',
        'P_EQPID', 'Photo_PPID', 'MMO_MRC_EQP', 'P_TIME', 'M_TIME', 'ChuckID',
        'K PARA', 'GPM', 'INDEX'
    ]
    wk_rk_input = wk_rk_input[wk_rk_cols_order]

    return wk_rk_input



def process_nau_file(file_path):
    """하나의 nau 파일을 처리하여 데이터프레임 반환"""
    file_name = os.path.basename(file_path)
    info_dict = extract_file_info(file_name)

    # RawData-1 시트를 한 번만 읽기 (header 포함 및 header 없이)
    rawdata_file, rawdata_file_no_header = load_excel_sheets(file_path)

    rawdata_df = process_rawdata_sheet(file_path, info_dict, rawdata_file)
    trocs_input_df = process_trocs_input_sheet(file_path, info_dict, rawdata_file)
    psm_input_df = process_psm_input_sheet(file_path, info_dict, rawdata_file)
    mrc_df = process_mrc_data(file_path, info_dict, rawdata_file, rawdata_file_no_header)
    wk_rk_input_df = process_wk_rk_input_data(file_path, info_dict, rawdata_file)
    

    return rawdata_df, trocs_input_df, psm_input_df, mrc_df, wk_rk_input_df

def save_combined_data(rawdata_list, trocs_input_list, psm_input_list, mrc_list, wk_rk_input_list):
    # 결과 파일을 저장할 폴더 지정
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    # 각 리스트를 하나의 DataFrame으로 결합합니다.
    combined_rawdata = pd.concat(rawdata_list, ignore_index=True)
    combined_trocs = pd.concat(trocs_input_list, ignore_index=True)
    combined_psm = pd.concat(psm_input_list, ignore_index=True)
    combined_mrc = pd.concat(mrc_list, ignore_index=True)
    combined_wk_rk = pd.concat(wk_rk_input_list, ignore_index=True)
    

    # 정렬
    combined_rawdata = combined_rawdata.sort_values(by=['UNIQUE_ID', 'TEST', 'DieX', 'DieY'])
    combined_trocs = combined_trocs.sort_values(by=['UNIQUE_ID', 'dCol', 'dRow'])
    combined_psm = combined_psm.sort_values(by=['UNIQUE_ID', 'dCol', 'dRow'])
    combined_mrc = combined_mrc.sort_values(by=['UNIQUE_ID', 'INDEX'])

    # 파일명을 결과 폴더 경로와 함께 지정하여 저장합니다.
    combined_rawdata.to_csv(os.path.join(results_dir, "RawData-1.csv"), index=False)
    combined_trocs.to_csv(os.path.join(results_dir, "Trocs_Input.csv"), index=False)
    combined_psm.to_csv(os.path.join(results_dir, "PerShotMRC.csv"), index=False)
    combined_mrc.to_csv(os.path.join(results_dir, "MRC.csv"), index=False)
    combined_wk_rk.to_csv(os.path.join(results_dir, "WK_RK_INPUT.csv"), index=False)
    



def main():
    folder_path = 'C:/py_data/nau/2lot'
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 작업 시작")

    remove_duplicate_files(folder_path)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 중복 파일 제거 완료")

    rawdata_list = []
    trocs_input_list = []
    psm_input_list = []
    mrc_list = []
    wk_rk_input_list = []


    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} nau 파일 처리 시작")
    for file_name in os.listdir(folder_path):
        if file_name.endswith('.nau'):
            file_path = os.path.join(folder_path, file_name)
            try:
                rawdata_df, trocs_input_df, psm_input_df, mrc_df, wk_rk_input_df = process_nau_file(file_path)
                rawdata_list.append(rawdata_df)
                trocs_input_list.append(trocs_input_df)
                psm_input_list.append(psm_input_df)
                mrc_list.append(mrc_df)
                wk_rk_input_list.append(wk_rk_input_df)
                
                print(f"{file_name} 처리 완료")
            except Exception as e:
                print(f"{file_name} 처리 중 에러 발생: {e}")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} nau 파일 처리 완료")

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 데이터 저장 시작")

    save_combined_data(rawdata_list, trocs_input_list, psm_input_list, mrc_list, wk_rk_input_list)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 데이터 저장 완료")

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 작업 완료")

if __name__ == "__main__":
    main()



