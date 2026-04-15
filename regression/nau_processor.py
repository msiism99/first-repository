"""
NAU 파일 처리기 (NAU File Processor) v2.1.0

Description:
    NAU파일을 처리하여 overlay 분석에 필요한 데이터를 추출하고 CSV 파일로 변환하는 스크립트입니다.
    Refactored version of v2.0.0 for better maintainability and code reuse.

Main Features:
    - xlwings 기반 Excel 처리 (안정성 확보)
    - 중복 로직 제거 (메타데이터 추출, ID 생성)
    - 매직 넘버 상수화

Output Files:
    - RawData-1.csv
    - Trocs_Input.csv
    - PerShotMRC.csv
    - MRC.csv
    - WK_RK_INPUT.csv
    - test_coordinates.csv
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
import xlwings as xw

# =============================================================================
# CONSTANTS (Magic Numbers)
# =============================================================================
COL_METADATA = 13  # Column index for metadata (N column)
COL_MRC_START = 15  # P column
COL_MRC_END = 17  # R column (exclusive)

# Metadata Row Indices (0-based)
ROW_WAFER = 0
ROW_STEPSEQ = 0
ROW_PEQPID = 1
ROW_PTIME = 2
ROW_MTIME = 4
ROW_STEP_PITCH_X = 6
ROW_STEP_PITCH_Y = 7
ROW_MAP_SHIFT_X = 8
ROW_MAP_SHIFT_Y = 9
ROW_PHOTO_PPID = 11
ROW_BASE_EQP1 = 12
ROW_CHUCKID = 15
ROW_RETICLEID = 16
ROW_MMO_MRC_EQP = 19
ROW_OUTLIER_SPEC_RATIO = 20
ROW_CHIP_X_NUM = 25
ROW_CHIP_Y_NUM = 26
ROW_DMARGIN_X = 3  # In column 27 (AB column)? Need to verify context
ROW_DMARGIN_Y = 4  # In column 27

# Column indices for Test Coordinates extraction
COL_TEST_NO = 18  # S column
COL_COORD_X = 19  # T column
COL_COORD_Y = 20  # U column

# APC Input Row/Col indices
COL_WK_INPUT = 96  # CQ column
COL_RK_INPUT = 97  # CR column

# Explicit Column Orders for Consistency
ORDER_TROCS_PSM = [
    "UNIQUE_ID",
    "UNIQUE_ID2",
    "STEPSEQ",
    "LOT_ID",
    "Wafer",
    "P_EQPID",
    "Photo_PPID",
    "MMO_MRC_EQP",
    "P_TIME",
    "M_TIME",
    "ChuckID",
]

ORDER_MRC_WKRK = [
    "UNIQUE_ID",
    "STEPSEQ",
    "LOT_ID",
    "Wafer",
    "P_EQPID",
    "Photo_PPID",
    "MMO_MRC_EQP",
    "P_TIME",
    "M_TIME",
    "ChuckID",
    "K PARA",
    "GPM",
    "INDEX",
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_column_index(header_row, target_name):
    """
    Find index of a column by name, handling duplicates by returning the first match.
    """
    for idx, name in enumerate(header_row):
        if isinstance(name, str) and name.strip() == target_name:
            return idx
    raise ValueError(f"'{target_name}' 컬럼을 찾을 수 없습니다.")


def extract_common_metadata(rawdata_file):
    """
    Extract common metadata from RawData-1 sheet.
    Returns a dictionary of metadata values.
    """
    metadata = {}

    # Check if rawdata_file is valid
    if rawdata_file is None or rawdata_file.empty:
        raise ValueError("RawData-1 DataFrame is empty or None")

    # Extract single values using direct indexing
    # Note: rawdata_file is a DataFrame, so we use iloc
    metadata["STEPSEQ"] = rawdata_file.iloc[ROW_STEPSEQ, COL_METADATA]
    metadata["LOT_ID"] = rawdata_file.columns[COL_METADATA]  # Header itself is LOT_ID
    metadata["Wafer"] = rawdata_file.iloc[ROW_WAFER, 0]  # Column 0 is Wafer index
    metadata["P_EQPID"] = rawdata_file.iloc[ROW_PEQPID, COL_METADATA]
    metadata["Photo_PPID"] = rawdata_file.iloc[ROW_PHOTO_PPID, COL_METADATA]
    metadata["P_TIME"] = rawdata_file.iloc[ROW_PTIME, COL_METADATA]
    metadata["M_TIME"] = rawdata_file.iloc[ROW_MTIME, COL_METADATA]
    metadata["ChuckID"] = rawdata_file.iloc[ROW_CHUCKID, COL_METADATA]
    metadata["MMO_MRC_EQP"] = rawdata_file.iloc[ROW_MMO_MRC_EQP, COL_METADATA]

    return metadata


def add_unique_ids(df, metadata, level="die"):
    """
    Add UNIQUE_ID columns to the DataFrame.
    level: 'die' (default, includes Test/Die info) or 'wafer' (wafer level only)
    """
    # Create base UNIQUE_ID string parts
    base_id_parts = [
        str(metadata["STEPSEQ"]),
        str(metadata["P_EQPID"]),
        str(metadata["Photo_PPID"]),
        str(metadata["MMO_MRC_EQP"]),
        str(metadata["P_TIME"]),
        str(metadata["M_TIME"]),
        str(metadata["LOT_ID"]),
        str(metadata["Wafer"]),
    ]

    base_id = "_".join(base_id_parts)

    # Note: Trocs_Input and PerShotMRC do NOT use UNIQUE_ID3 in original code.
    # Only RawData-1 seems to use it extensively.
    # We will add it conditionally or just for 'die' level if needed.
    # But strictly following original:
    # Trocs/PSM: UNIQUE_ID (wafer level), UNIQUE_ID2 (shot pos level)

    if level == "die":
        # UNIQUE_ID3: Wafer Level ID (No Group) - Only for RawData-1
        df["UNIQUE_ID3"] = base_id

    if "GROUP" in df.columns:
        # UNIQUE_ID: Wafer Level + Group
        df["UNIQUE_ID"] = df["GROUP"].apply(lambda g: f"{base_id}_{g}")

        if level == "die" and all(c in df.columns for c in ["TEST", "DieX", "DieY"]):
            # UNIQUE_ID2: Measurement Point Level
            df["UNIQUE_ID2"] = df.apply(
                lambda row: f"{base_id}_{row['TEST']}_{row['DieX']}_{row['DieY']}_{row['GROUP']}",
                axis=1,
            )

            # UNIQUE_ID4: Die Level (No Test No)
            df["UNIQUE_ID4"] = df.apply(
                lambda row: f"{base_id}_{row['DieX']}_{row['DieY']}_{row['GROUP']}",
                axis=1,
            )
    else:
        # If no GROUP column (e.g. Trocs/MRC data often don't differentiate groups or treat whole wafer)
        # But for consistency, we often need UNIQUE_ID.
        # If the input df assumes one group or wafer-level, we might just use base_id as UNIQUE_ID
        df["UNIQUE_ID"] = base_id

        if level == "shot_pos" and all(c in df.columns for c in ["dCol", "dRow"]):
            df["UNIQUE_ID2"] = df.apply(
                lambda row: f"{base_id}_{row['dCol']}_{row['dRow']}", axis=1
            )

    return df


def extract_file_info(file_name):
    """파일명에서 기본 정보 추출"""
    file_name_without_extension = os.path.splitext(file_name)[0]
    split_file_name = file_name_without_extension.split("_")

    info_dict = {
        "base_name": "_".join(split_file_name[:-1]),
        "file_suffix": split_file_name[-1],
        "split_file_name": split_file_name,
    }
    return info_dict


def remove_duplicate_files(folder_path):
    """E1 파일만 남기고 E2, E3 파일 삭제"""
    unique_files = {}
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path) and file_name.endswith(".nau"):
            info = extract_file_info(file_name)
            base_name = info["base_name"]
            suffix = info["file_suffix"]

            if base_name not in unique_files:
                if suffix == "E1":
                    unique_files[base_name] = file_path
            else:
                if suffix in ["E2", "E3"]:
                    try:
                        os.remove(file_path)
                        print(f"중복 파일 {file_name} 삭제 완료")
                    except Exception as e:
                        print(f"{file_name} 파일 삭제 중 에러 발생: {e}")


# =============================================================================
# EXCEL LOADING (xlwings)
# =============================================================================
def load_excel_sheets(file_path):
    """RawData-1 시트 로딩 (Header 포함/미포함)"""
    app = xw.App(visible=False)
    wb = None
    try:
        wb = app.books.open(file_path)
        sheet = wb.sheets["RawData-1"]

        # Header included
        rawdata_file = sheet.used_range.options(
            pd.DataFrame, header=1, index=False
        ).value
        # No header (for raw extraction)
        rawdata_file_no_header = pd.DataFrame(sheet.used_range.value)

        # Debug outputs
        # rawdata_file.to_csv('rawdata_file.csv', index=False)
        # rawdata_file_no_header.to_csv('rawdata_file_no_header.csv', index=False)

        return rawdata_file, rawdata_file_no_header

    finally:
        if wb:
            wb.close()
        app.quit()


def read_sheet_with_xlwings(file_path, sheet_name):
    """특정 시트 읽기"""
    app = xw.App(visible=False)
    wb = None
    try:
        wb = app.books.open(file_path)
        sheet = wb.sheets[sheet_name]
        df = sheet.used_range.options(pd.DataFrame, header=1, index=False).value
        return df
    finally:
        if wb:
            wb.close()
        app.quit()


# =============================================================================
# SHEET PROCESSING FUNCTIONS
# =============================================================================
def process_rawdata_sheet(file_path, info_dict, rawdata_file):
    """Process RawData-1 Sheet"""
    # 1. Extract Metadata
    meta = extract_common_metadata(rawdata_file)

    # 2. Extract Basic Columns
    # Columns 0-7: Wafer, TEST, DieX, DieY, X_reg, Y_reg, MRC_X, MRC_Y
    columns_to_extract = [0, 1, 2, 3, 4, 5, 6, 7]
    extracted = rawdata_file.iloc[:, columns_to_extract].copy()

    # 3. Add GROUP info
    extracted["GROUP"] = pd.cut(
        extracted["TEST"], bins=[0, 80, 160, 240], labels=["E1", "E2", "E3"]
    )

    # 4. Attach Metadata to DataFrame
    for key, val in meta.items():
        extracted[key] = val

    # Additional Step Params
    extracted["STEP_PITCH_X"] = rawdata_file.iloc[ROW_STEP_PITCH_X, COL_METADATA]
    extracted["STEP_PITCH_Y"] = rawdata_file.iloc[ROW_STEP_PITCH_Y, COL_METADATA]
    extracted["MAP_SHIFT_X"] = rawdata_file.iloc[ROW_MAP_SHIFT_X, COL_METADATA]
    extracted["MAP_SHIFT_Y"] = rawdata_file.iloc[ROW_MAP_SHIFT_Y, COL_METADATA]

    # Additional Equipment Params
    extracted["Base_EQP1"] = rawdata_file.iloc[ROW_BASE_EQP1, COL_METADATA]
    extracted["ReticleID"] = rawdata_file.iloc[ROW_RETICLEID, COL_METADATA]
    extracted["CHIP_X_NUM"] = rawdata_file.iloc[ROW_CHIP_X_NUM, COL_METADATA]
    extracted["CHIP_Y_NUM"] = rawdata_file.iloc[ROW_CHIP_Y_NUM, COL_METADATA]

    # Context/Outlier Params
    extracted["Outlier_Spec_Ratio"] = rawdata_file.iloc[
        ROW_OUTLIER_SPEC_RATIO, COL_METADATA
    ]
    extracted["Dmargin_X"] = rawdata_file.iloc[
        ROW_DMARGIN_X, 27
    ]  # Check column index 27 (AB)
    extracted["Dmargin_Y"] = rawdata_file.iloc[ROW_DMARGIN_Y, 27]

    # 5. Handle Duplicate Columns & Coordinate Mapping
    test_no_idx = get_column_index(rawdata_file.columns, "Test No")
    coord_x_idx = get_column_index(rawdata_file.columns, "coordinate_X")
    coord_y_idx = get_column_index(rawdata_file.columns, "coordinate_Y")
    mrc_rx_idx = get_column_index(rawdata_file.columns, "MRC_RX")
    mrc_ry_idx = get_column_index(rawdata_file.columns, "MRC_RY")

    # Create Mapping Dictionaries
    # Use column names from the found indices to ensure correct referencing
    col_test_no = rawdata_file.columns[test_no_idx]
    col_coord_x = rawdata_file.columns[coord_x_idx]
    col_coord_y = rawdata_file.columns[coord_y_idx]
    col_mrc_rx = rawdata_file.columns[mrc_rx_idx]
    col_mrc_ry = rawdata_file.columns[mrc_ry_idx]

    coord_map = (
        rawdata_file.iloc[:, [test_no_idx, coord_x_idx, coord_y_idx]]
        .drop_duplicates(subset=col_test_no)
        .set_index(col_test_no)
    )

    mrc_map = (
        rawdata_file.iloc[:, [test_no_idx, mrc_rx_idx, mrc_ry_idx]]
        .drop_duplicates(subset=col_test_no)
        .set_index(col_test_no)
    )

    # Apply Mapping
    extracted["coordinate_X"] = extracted["TEST"].map(coord_map[col_coord_x])
    extracted["coordinate_Y"] = extracted["TEST"].map(coord_map[col_coord_y])
    extracted["MRC_RX"] = extracted["TEST"].map(mrc_map[col_mrc_rx])
    extracted["MRC_RY"] = extracted["TEST"].map(mrc_map[col_mrc_ry])

    # 6. Calculations
    # PSM Calculation
    # PSM = -(MRC_X - MRC_RX)
    extracted["PSM_X"] = -(extracted["MRC_X"] - extracted["MRC_RX"])
    extracted["PSM_Y"] = -(extracted["MRC_Y"] - extracted["MRC_RY"])

    # FCP (Field Center Position)
    extracted["fcp_x"] = (
        extracted["DieX"] * extracted["STEP_PITCH_X"] + extracted["MAP_SHIFT_X"]
    )
    extracted["fcp_y"] = (
        extracted["DieY"] * extracted["STEP_PITCH_Y"] + extracted["MAP_SHIFT_Y"]
    )

    # Wafer Coordinate
    extracted["wf_x"] = extracted["fcp_x"] + extracted["coordinate_X"]
    extracted["wf_y"] = extracted["fcp_y"] + extracted["coordinate_Y"]

    # Radius
    extracted["radius"] = np.sqrt(extracted["wf_x"] ** 2 + extracted["wf_y"] ** 2)

    # 7. Add Unique IDs
    extracted = add_unique_ids(extracted, meta, level="die")

    # 8. Reorder Columns
    cols_order = [
        "UNIQUE_ID",
        "UNIQUE_ID2",
        "UNIQUE_ID3",
        "UNIQUE_ID4",
        "STEPSEQ",
        "LOT_ID",
        "Wafer",
        "P_EQPID",
        "Photo_PPID",
        "P_TIME",
        "M_TIME",
        "ChuckID",
        "ReticleID",
        "Base_EQP1",
        "MMO_MRC_EQP",
        "GROUP",
        "TEST",
        "DieX",
        "DieY",
        "STEP_PITCH_X",
        "STEP_PITCH_Y",
        "MAP_SHIFT_X",
        "MAP_SHIFT_Y",
        "coordinate_X",
        "coordinate_Y",
        "fcp_x",
        "fcp_y",
        "wf_x",
        "wf_y",
        "radius",
        "CHIP_X_NUM",
        "CHIP_Y_NUM",
        "Outlier_Spec_Ratio",
        "Dmargin_X",
        "Dmargin_Y",
        "X_reg",
        "Y_reg",
        "MRC_X",
        "MRC_Y",
        "MRC_RX",
        "MRC_RY",
        "PSM_X",
        "PSM_Y",
    ]
    # Filter only existing columns
    cols_order = [c for c in cols_order if c in extracted.columns]

    print(f"{file_path} - RawData-1 Processed")
    return extracted[cols_order]


def process_trocs_input_sheet(file_path, info_dict, rawdata_file):
    """Process Trocs Input Sheet"""
    df = read_sheet_with_xlwings(file_path, "Trocs Input")
    meta = extract_common_metadata(rawdata_file)

    for key, val in meta.items():
        df[key] = val

    df = add_unique_ids(df, meta, level="shot_pos")

    # Reorder based on explicit list + remaining columns
    cols_fixed = ORDER_TROCS_PSM
    cols_remaining = [c for c in df.columns if c not in cols_fixed]
    return df[cols_fixed + cols_remaining]


def process_psm_input_sheet(file_path, info_dict, rawdata_file):
    """Process PerShotMRC Sheet"""
    df = read_sheet_with_xlwings(file_path, "PerShotMRC")
    meta = extract_common_metadata(rawdata_file)

    for key, val in meta.items():
        df[key] = val

    df = add_unique_ids(df, meta, level="shot_pos")

    # Reorder based on explicit list + remaining columns
    cols_fixed = ORDER_TROCS_PSM
    cols_remaining = [c for c in df.columns if c not in cols_fixed]
    return df[cols_fixed + cols_remaining]


def process_mrc_data(file_path, info_dict, rawdata_file, rawdata_file_no_header):
    """Process MRC Parameters (extracted from raw locations)"""
    meta = extract_common_metadata(rawdata_file)

    # Extract MRC Blocks (Magic Numbers centralized here for now, could be constants)
    # Block 1: Rows 0-19, Cols 15-16 (P, Q)
    mrc1 = rawdata_file_no_header.iloc[0:20, COL_MRC_START:COL_MRC_END]
    # Block 2: Rows 22-39, Cols 15-16
    mrc2 = rawdata_file_no_header.iloc[22:40, COL_MRC_START:COL_MRC_END]

    mrc_df = pd.concat([mrc1, mrc2], ignore_index=True)
    mrc_df.columns = ["K PARA", "GPM"]
    mrc_df["INDEX"] = range(1, len(mrc_df) + 1)

    for key, val in meta.items():
        mrc_df[key] = val

    # MRC uses Wafer Level Unique ID
    mrc_df = add_unique_ids(mrc_df, meta, level="wafer")

    # Explicit Reorder
    cols_order = [c for c in ORDER_MRC_WKRK if c in mrc_df.columns]
    return mrc_df[cols_order]


def process_wk_rk_input_data(file_path, info_dict, rawdata_file):
    """Process APC WK/RK Input"""
    meta = extract_common_metadata(rawdata_file)

    # WK: Rows 0-19 at COL_WK_INPUT (96)
    wk_input = rawdata_file.iloc[0:20, COL_WK_INPUT]
    # RK: Rows 2-19 at COL_RK_INPUT (97) - Skip RK1, RK2
    rk_input = rawdata_file.iloc[2:20, COL_RK_INPUT]

    wk_rk_df = pd.concat([wk_input, rk_input], axis=0, ignore_index=True).to_frame()
    wk_rk_df.columns = ["GPM"]

    # Create Labels
    labels = [f"W{i + 1}" for i in range(20)] + [f"R{i + 3}" for i in range(18)]
    wk_rk_df["K PARA"] = labels
    wk_rk_df["INDEX"] = range(1, len(wk_rk_df) + 1)

    for key, val in meta.items():
        wk_rk_df[key] = val

    wk_rk_df = add_unique_ids(wk_rk_df, meta, level="wafer")

    # Explicit Reorder
    cols_order = [c for c in ORDER_MRC_WKRK if c in wk_rk_df.columns]
    return wk_rk_df[cols_order]


def extract_test_coord(rawdata_file, rawdata_file_no_header):
    """Extract Test Coordinates Map"""
    # S~U Columns (18-20)
    test_coord = rawdata_file_no_header.iloc[1:, COL_TEST_NO : COL_TEST_NO + 3].copy()
    test_coord.columns = ["Test No", "coordinate_X", "coordinate_Y"]

    test_coord = test_coord.dropna().drop_duplicates(subset=["Test No"])

    # Numeric conversion
    for col in test_coord.columns:
        test_coord[col] = pd.to_numeric(test_coord[col], errors="coerce")

    # Add context
    meta = extract_common_metadata(rawdata_file)
    # Construct a simpler unique ID for this table
    unique_id = (
        f"{meta['STEPSEQ']}_{meta['P_EQPID']}_{meta['Photo_PPID']}_{meta['MMO_MRC_EQP']}_"
        f"{meta['P_TIME']}_{meta['M_TIME']}_{meta['LOT_ID']}_{meta['Wafer']}"
    )

    test_coord.insert(0, "UNIQUE_ID", unique_id)
    test_coord["STEP_PITCH_X"] = rawdata_file.iloc[ROW_STEP_PITCH_X, COL_METADATA]
    test_coord["STEP_PITCH_Y"] = rawdata_file.iloc[ROW_STEP_PITCH_Y, COL_METADATA]
    test_coord["MAP_SHIFT_X"] = rawdata_file.iloc[ROW_MAP_SHIFT_X, COL_METADATA]
    test_coord["MAP_SHIFT_Y"] = rawdata_file.iloc[ROW_MAP_SHIFT_Y, COL_METADATA]

    return test_coord


# =============================================================================
# MAIN PROCESSING
# =============================================================================
def process_nau_file(file_path):
    """Process a single NAU file and return all DataFrames"""
    file_name = os.path.basename(file_path)
    info_dict = extract_file_info(file_name)

    # Load once
    rawdata_file, rawdata_file_no_header = load_excel_sheets(file_path)

    # Process all
    rawdata_df = process_rawdata_sheet(file_path, info_dict, rawdata_file)
    trocs_df = process_trocs_input_sheet(file_path, info_dict, rawdata_file)
    psm_df = process_psm_input_sheet(file_path, info_dict, rawdata_file)
    mrc_df = process_mrc_data(
        file_path, info_dict, rawdata_file, rawdata_file_no_header
    )
    wkrk_df = process_wk_rk_input_data(file_path, info_dict, rawdata_file)
    test_coord_df = extract_test_coord(rawdata_file, rawdata_file_no_header)

    return rawdata_df, trocs_df, psm_df, mrc_df, wkrk_df, test_coord_df


def check_edge_shot(rawdata_df, wafer_radius=150000):
    """
    RawData의 각 shot이 wafer edge에 있는지 판정

    Edge shot 판정 기준:
        - Shot의 Field Center Point (fcp_x, fcp_y)를 중심으로
        - STEP_PITCH_X, STEP_PITCH_Y를 사용하여 shot의 4개 모서리 좌표 계산
        - 어떤 모서리라도 wafer_radius를 초과하면 edge shot으로 판정

    Args:
        rawdata_df: RawData DataFrame
            필수 컬럼: UNIQUE_ID, DieX, DieY, fcp_x, fcp_y, STEP_PITCH_X, STEP_PITCH_Y
        wafer_radius: Wafer 반경 임계값 (um 단위, 기본값: 150mm)

    Returns:
        DataFrame: Is_Edge_Shot, Max_Corner_Distance 컬럼이 추가된 DataFrame
    """
    # Edge shot 정보 저장 리스트
    edge_shot_info = []

    # UNIQUE_ID 그룹별로 처리
    for unique_id, group in rawdata_df.groupby('UNIQUE_ID'):
        # 그룹 내에서 동일한 step pitch 값 사용
        step_pitch_x = group['STEP_PITCH_X'].iloc[0]
        step_pitch_y = group['STEP_PITCH_Y'].iloc[0]

        for _, row in group.iterrows():
            # Field Center Point 좌표
            fcp_x = row['fcp_x']
            fcp_y = row['fcp_y']

            # Shot의 4개 모서리 좌표 계산
            half_pitch_x = step_pitch_x / 2
            half_pitch_y = step_pitch_y / 2

            corners = [
                (fcp_x - half_pitch_x, fcp_y - half_pitch_y),  # Bottom Left
                (fcp_x + half_pitch_x, fcp_y - half_pitch_y),  # Bottom Right
                (fcp_x - half_pitch_x, fcp_y + half_pitch_y),  # Top Left
                (fcp_x + half_pitch_x, fcp_y + half_pitch_y),  # Top Right
            ]

            # 각 모서리에서 원점까지의 거리 계산
            distances = [np.sqrt(c[0]**2 + c[1]**2) for c in corners]
            max_distance = max(distances)

            # 어떤 모서리라도 wafer radius를 초과하면 edge shot
            is_edge_shot = max_distance > wafer_radius

            edge_shot_info.append({
                'Is_Edge_Shot': is_edge_shot,
                'Max_Corner_Distance': max_distance
            })

    # Edge shot 정보를 DataFrame으로 변환
    edge_df = pd.DataFrame(edge_shot_info)

    # 원본 DataFrame에 컬럼 추가
    result_df = pd.concat([rawdata_df.reset_index(drop=True), edge_df], axis=1)

    return result_df


def save_combined_data(
    rawdata_list, trocs_list, psm_list, mrc_list, wkrk_list, test_coord_list
):
    """Combine and save all results to 'results/' directory"""
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    print("Merging data...")
    combined_raw = pd.concat(rawdata_list, ignore_index=True)
    combined_trocs = pd.concat(trocs_list, ignore_index=True)
    combined_psm = pd.concat(psm_list, ignore_index=True)
    combined_mrc = pd.concat(mrc_list, ignore_index=True)
    combined_wkrk = pd.concat(wkrk_list, ignore_index=True)
    combined_test = pd.concat(test_coord_list, ignore_index=True)

    print("Sorting data...")
    # Sorting logic
    if "UNIQUE_ID" in combined_raw.columns:
        combined_raw.sort_values(by=["UNIQUE_ID", "TEST", "DieX", "DieY"], inplace=True)
    if "UNIQUE_ID" in combined_trocs.columns:
        combined_trocs.sort_values(by=["UNIQUE_ID", "dCol", "dRow"], inplace=True)
    if "UNIQUE_ID" in combined_psm.columns:
        combined_psm.sort_values(by=["UNIQUE_ID", "dCol", "dRow"], inplace=True)
    if "UNIQUE_ID" in combined_mrc.columns:
        combined_mrc.sort_values(by=["UNIQUE_ID", "INDEX"], inplace=True)
    if "UNIQUE_ID" in combined_wkrk.columns:
        combined_wkrk.sort_values(by=["UNIQUE_ID", "INDEX"], inplace=True)

    # Edge shot 판정 (프로젝트8)
    print("Checking edge shots...")
    from config import RADIUS_THRESHOLD
    combined_raw = check_edge_shot(combined_raw, wafer_radius=RADIUS_THRESHOLD)
    print("Edge shot check completed.")

    print("Saving files...")
    combined_raw.to_csv(os.path.join(results_dir, "RawData-1.csv"), index=False)
    combined_trocs.to_csv(os.path.join(results_dir, "Trocs_Input.csv"), index=False)
    combined_psm.to_csv(os.path.join(results_dir, "PerShotMRC.csv"), index=False)
    combined_mrc.to_csv(os.path.join(results_dir, "MRC.csv"), index=False)
    combined_wkrk.to_csv(os.path.join(results_dir, "WK_RK_INPUT.csv"), index=False)
    combined_test.to_csv(os.path.join(results_dir, "Test_Coord.csv"), index=False)

    print("All saved successfully.")
