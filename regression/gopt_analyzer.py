"""
gopt_analyzer.py
G-optimality 기반 CPE Fallback 분석 모듈

프로젝트4: CPE(Correction Per Expose) 회귀분석에서 over-fitting을 방지하기 위해
G-opt 기준으로 shot별 최적 차수를 결정하는 모듈

핵심 개념:
- G-opt = max(diag(Var))
- Var = X₀ M⁻¹ X₀ᵀ (evaluation grid의 분산 행렬)
- M = XᵀX (measurement grid의 정보 행렬)
- G-opt < threshold → 해당 차수 사용 가능
- G-opt >= threshold → 낮은 차수로 Fallback (18para → 6para → 2para)
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict
import logging

# Config import
from config import (
    G_OPT_THRESHOLD,
    CPE_EVAL_GRID,
    CPE_CONDITION_THRESHOLD,
    CPE_MIN_POINTS,
    WAFER_LIMIT_RADIUS,
    CHIP_LIMIT_RADIUS
)

# Design matrix import
from design_matrix import CPE_OPTIONS


# ========================================
# 핵심 G-opt 계산 함수
# ========================================

def create_polynomial_matrix(coords: np.ndarray, polynomial_order: np.ndarray, direction: str) -> np.ndarray:
    """
    좌표로부터 Polynomial design matrix 생성

    Args:
        coords: [N, 2] 좌표 배열 (x, y)
        polynomial_order: [10] boolean 배열 (어떤 항을 사용할지)
        direction: 'x' or 'y'

    Returns:
        [N, M] design matrix (M = polynomial_order에서 True인 항의 개수)
    """
    x = coords[:, 0]
    y = coords[:, 1]

    if direction == 'x':
        # X방향: [1, x, y, x², xy, y², x³, x²y, xy², y³]
        full_matrix = np.column_stack([
            np.ones(len(x)),                    # 1
            x, y,                                # x, y
            x**2, x*y, y**2,                     # x², xy, y²
            x**3, x**2*y, x*y**2, y**3          # x³, x²y, xy², y³
        ])
    else:  # direction == 'y'
        # Y방향: [1, y, x, y², xy, x², y³, xy², x²y, x³]
        full_matrix = np.column_stack([
            np.ones(len(x)),                    # 1
            y, x,                                # y, x (순서 주의!)
            y**2, x*y, x**2,                     # y², xy, x²
            y**3, x*y**2, x**2*y, x**3          # y³, xy², x²y, x³
        ])

    # polynomial_order가 True인 열만 선택
    return full_matrix[:, polynomial_order.astype(bool)]


def calculate_gopt_for_direction(
    eval_coords: np.ndarray,
    meas_coords: np.ndarray,
    polynomial_order: np.ndarray,
    direction: str
) -> float:
    """
    특정 방향(X or Y)의 G-opt 값 계산

    Args:
        eval_coords: [N_eval, 2] Evaluation grid 좌표
        meas_coords: [N_meas, 2] Measurement point 좌표
        polynomial_order: [10] polynomial 차수 정보
        direction: 'x' or 'y'

    Returns:
        G-opt 값 (실패 시 9999.0)
    """
    try:
        # 1. Measurement design matrix 생성
        X_meas = create_polynomial_matrix(meas_coords, polynomial_order, direction)

        # 2. 최소 데이터 포인트 확인
        n_meas, n_params = X_meas.shape
        if n_meas < n_params:
            return 9999.0  # Under-determined system

        # 3. Information matrix M = XᵀX
        M = X_meas.T @ X_meas

        # 4. Condition number 확인 (수치적 안정성)
        cond_num = np.linalg.cond(M)
        if cond_num > CPE_CONDITION_THRESHOLD:
            return 9999.0  # Matrix가 거의 singular

        # 5. Evaluation design matrix 생성
        X_eval = create_polynomial_matrix(eval_coords, polynomial_order, direction)

        # 6. Variance matrix 계산: Var = X₀ M⁻¹ X₀ᵀ
        M_inv = np.linalg.inv(M)
        Var = X_eval @ M_inv @ X_eval.T

        # 7. G-opt = max(diag(Var))
        diag_var = np.diag(Var)
        diag_var = np.maximum(diag_var, 0)  # 음수 방지
        gopt = np.max(np.sqrt(diag_var))

        # 8. 수치적 안정성 검증
        if not np.isfinite(gopt):
            return 9999.0

        return float(gopt)

    except (np.linalg.LinAlgError, ValueError):
        return 9999.0


def calculate_gopt_for_cpe_option(
    eval_coords: np.ndarray,
    meas_coords: np.ndarray,
    cpe_option: str
) -> Tuple[float, float]:
    """
    CPE 옵션에 대한 X, Y 방향 G-opt 계산

    Args:
        eval_coords: [N_eval, 2] Evaluation grid 좌표
        meas_coords: [N_meas, 2] Measurement point 좌표
        cpe_option: '18para', '6para', '2para' 등

    Returns:
        (gopt_x, gopt_y) 튜플
    """
    if cpe_option not in CPE_OPTIONS:
        logging.warning(f"Unknown CPE option: {cpe_option}, using default 18para")
        cpe_option = '18para'

    # CPE_OPTIONS에서 polynomial order 가져오기
    # 참고: gopt_config_gopt.py의 polynomial_order_x/y와 매핑
    # 18para: RK13 제외 (x), RK20 제외 (y)
    # 6para: linear만
    # 2para: offset만

    if cpe_option == '18para':
        # [1, x, y, x², xy, y², x³, x²y, xy², y³]에서 x³ 제외 (RK13)
        poly_x = np.array([1,1,1,1,1,1,0,1,1,1])  # RK13(x³) 제외
        poly_y = np.array([1,1,1,1,1,1,1,1,1,0])  # RK20(x³) 제외
    elif cpe_option == '15para':
        # DUV용: 일부 3차항 제외
        poly_x = np.array([1,1,1,1,0,1,1,0,0,1])  # RK9(xy), RK15(x²y), RK17(xy²) 제외
        poly_y = np.array([1,1,1,1,1,1,1,1,0,0])  # RK18(x²y), RK20(x³) 제외
    elif cpe_option == '6para':
        # Linear만
        poly_x = np.array([1,1,1,0,0,0,0,0,0,0])
        poly_y = np.array([1,1,1,0,0,0,0,0,0,0])
    elif cpe_option == '2para':
        # Offset만
        poly_x = np.array([1,0,0,0,0,0,0,0,0,0])
        poly_y = np.array([1,0,0,0,0,0,0,0,0,0])
    elif cpe_option == '20para':
        # Full 3차
        poly_x = np.array([1,1,1,1,1,1,1,1,1,1])
        poly_y = np.array([1,1,1,1,1,1,1,1,1,1])
    else:
        # 기본값 (18para)
        poly_x = np.array([1,1,1,1,1,1,0,1,1,1])
        poly_y = np.array([1,1,1,1,1,1,1,1,1,0])

    gopt_x = calculate_gopt_for_direction(eval_coords, meas_coords, poly_x, 'x')
    gopt_y = calculate_gopt_for_direction(eval_coords, meas_coords, poly_y, 'y')

    return gopt_x, gopt_y


# ========================================
# Fallback 로직
# ========================================

def determine_cpe_option_with_gopt(
    eval_coords: np.ndarray,
    meas_coords: np.ndarray,
    default_option: str = '18para',
    threshold: float = None
) -> Dict:
    """
    G-opt 기반으로 최적 CPE 옵션 결정 (Fallback 로직)

    Fallback 순서:
    1. default_option (보통 18para) → G-opt 확인
    2. 실패 시 6para → G-opt 확인
    3. 실패 시 2para (offset만) → 무조건 사용

    Args:
        eval_coords: [N_eval, 2] Evaluation grid 좌표
        meas_coords: [N_meas, 2] Measurement point 좌표
        default_option: 시작 CPE 옵션
        threshold: G-opt 임계값 (None이면 config 사용)

    Returns:
        {
            'selected_option': str,       # 최종 선택된 옵션
            'gopt_x': float,              # X방향 G-opt
            'gopt_y': float,              # Y방향 G-opt
            'fallback_count': int,        # Fallback 횟수 (0, 1, 2)
            'status': str                 # 'success', 'fallback_6para', 'fallback_2para', 'edge_shot'
        }
    """
    if threshold is None:
        threshold = G_OPT_THRESHOLD

    # Edge shot 판정 (measurement point가 없거나 eval point가 없음)
    if len(meas_coords) < CPE_MIN_POINTS or len(eval_coords) == 0:
        return {
            'selected_option': '2para',
            'gopt_x': 9999.0,
            'gopt_y': 9999.0,
            'fallback_count': 2,
            'status': 'edge_shot'
        }

    # Fallback 시퀀스: default(18para) → 6para → 2para
    fallback_sequence = [default_option, '6para', '2para']

    for fallback_count, cpe_option in enumerate(fallback_sequence):
        gopt_x, gopt_y = calculate_gopt_for_cpe_option(eval_coords, meas_coords, cpe_option)

        # X, Y 중 더 큰(나쁜) G-opt 선택
        max_gopt = max(gopt_x, gopt_y)

        # G-opt 기준 만족 여부
        if max_gopt < threshold:
            # 성공!
            if fallback_count == 0:
                status = 'success'
            elif fallback_count == 1:
                status = 'fallback_6para'
            else:
                status = 'fallback_2para'

            return {
                'selected_option': cpe_option,
                'gopt_x': gopt_x,
                'gopt_y': gopt_y,
                'fallback_count': fallback_count,
                'status': status
            }

    # 모든 옵션 실패 (2para도 실패) → 강제로 2para 사용
    gopt_x, gopt_y = calculate_gopt_for_cpe_option(eval_coords, meas_coords, '2para')
    return {
        'selected_option': '2para',
        'gopt_x': gopt_x,
        'gopt_y': gopt_y,
        'fallback_count': 2,
        'status': 'fallback_2para'
    }


# ========================================
# Evaluation Grid 생성
# ========================================

# ========================================
# Chip 경계 고려 헬퍼 함수들
# ========================================

def check_edge_shot(
    center: np.ndarray,
    pitch: np.ndarray,
    limit_radius: float
) -> int:
    """
    Shot 또는 Chip이 wafer edge를 벗어나는지 판정
    Reference: gopt_fallback_analyzer_gopt.py의 _check_edge_shot()

    Args:
        center: [2] Shot/Chip 중심 좌표 (mm)
        pitch: [2] Shot/Chip 크기 (mm)
        limit_radius: Wafer 반경 임계값 (mm)

    Returns:
        0: Normal (내부), 1: Edge (경계 걸침)
    """
    # 4개 모서리 위치 계산
    edge_positions = np.array([
        [center[0] - pitch[0]/2, center[1] - pitch[1]/2],  # 좌하
        [center[0] - pitch[0]/2, center[1] + pitch[1]/2],  # 좌상
        [center[0] + pitch[0]/2, center[1] + pitch[1]/2],  # 우상
        [center[0] + pitch[0]/2, center[1] - pitch[1]/2]   # 우하
    ])

    # 각 모서리의 반경 계산
    edge_radius = np.sqrt(edge_positions[:, 0]**2 + edge_positions[:, 1]**2)

    # 하나라도 limit_radius를 초과하면 edge shot
    return 1 if np.max(edge_radius) >= limit_radius else 0


def convert_eval_to_chip_index_floor(
    eval_pos: np.ndarray,
    die_n: int,
    eval_n: int
) -> np.ndarray:
    """
    Evaluation grid index를 chip index로 변환 (floor 방식)
    Reference: gopt_fallback_analyzer_gopt.py의 _convert_eval_to_chip_index_a()

    Args:
        eval_pos: Evaluation grid index
        die_n: Shot 내 chip 개수
        eval_n: Evaluation grid 개수

    Returns:
        Chip index (0 ~ die_n-1)
    """
    chip_idx = np.floor(die_n * eval_pos / (eval_n - 1))
    chip_idx[chip_idx == die_n] = die_n - 1  # 경계값 처리
    return chip_idx


def convert_eval_to_chip_index_ceil(
    eval_pos: np.ndarray,
    die_n: int,
    eval_n: int
) -> np.ndarray:
    """
    Evaluation grid index를 chip index로 변환 (ceil 방식)
    Reference: gopt_fallback_analyzer_gopt.py의 _convert_eval_to_chip_index_b()

    Args:
        eval_pos: Evaluation grid index
        die_n: Shot 내 chip 개수
        eval_n: Evaluation grid 개수

    Returns:
        Chip index (0 ~ die_n-1)
    """
    chip_idx = np.ceil(die_n * eval_pos / (eval_n - 1)) - 1
    chip_idx[chip_idx < 0] = 0  # 음수 방지
    return chip_idx


def generate_eval_grid_with_chip_boundary(
    shot_array: np.ndarray,
    shot_layout: np.ndarray,
    die_layout: np.ndarray,
    eval_layout: np.ndarray,
    limit_radius: float,
    chip_limit_radius: float
) -> Optional[np.ndarray]:
    """
    Chip 경계를 고려한 evaluation grid 생성
    Reference: gopt_fallback_analyzer_gopt.py의 _generate_eval_grid_with_chip()

    Args:
        shot_array: [2] Shot 위치 (DieX, DieY)
        shot_layout: [4] [size_x, size_y, shift_x, shift_y] (mm)
        die_layout: [2] Shot 내 chip 개수 [nx, ny]
        eval_layout: [2] Evaluation grid 크기 [nx, ny]
        limit_radius: Wafer 반경 임계값 (mm)
        chip_limit_radius: Chip 기준 반경 임계값 (mm)

    Returns:
        [N, 2] Evaluation grid 좌표 (shot 중심 기준), None if edge shot with no valid points
    """
    # 1. Shot 중심 좌표 계산 (wafer 기준)
    shot_center = np.array([
        shot_layout[0] * shot_array[0] + shot_layout[2],
        shot_layout[1] * shot_array[1] + shot_layout[3]
    ])

    # 2. Edge shot 여부 판정
    shot_decision = check_edge_shot(shot_center, shot_layout[:2], limit_radius)

    # 3. 기본 evaluation grid 생성
    nx, ny = eval_layout
    eval_grid = np.zeros((nx * ny, 4))

    # Grid index 생성
    for ii in range(ny):
        start_idx = ii * nx
        end_idx = (ii + 1) * nx
        eval_grid[start_idx:end_idx, 0] = np.arange(nx)  # x index
        eval_grid[start_idx:end_idx, 1] = ii              # y index

    # 4. Grid index를 실제 좌표로 변환 (shot 중심 기준)
    eval_grid[:, 2] = (shot_layout[0] / (nx - 1) * eval_grid[:, 0] - shot_layout[0] * 0.5)
    eval_grid[:, 3] = (shot_layout[1] / (ny - 1) * eval_grid[:, 1] - shot_layout[1] * 0.5)

    # 5. Normal shot이면 모든 point 사용
    if shot_decision == 0:
        return eval_grid[:, 2:4]  # 좌표만 반환

    # 6. Edge shot인 경우: Chip 단위로 edge 체크
    n_eval = nx * ny
    temp_grid_calc = np.zeros((n_eval, 13))

    # 각 evaluation point가 속하는 chip 계산 (4개 조합: floor/ceil × floor/ceil)
    temp_grid_calc[:, 0] = convert_eval_to_chip_index_floor(eval_grid[:, 0], die_layout[0], nx)
    temp_grid_calc[:, 1] = convert_eval_to_chip_index_floor(eval_grid[:, 1], die_layout[1], ny)
    temp_grid_calc[:, 2] = convert_eval_to_chip_index_ceil(eval_grid[:, 0], die_layout[0], nx)
    temp_grid_calc[:, 3] = convert_eval_to_chip_index_floor(eval_grid[:, 1], die_layout[1], ny)
    temp_grid_calc[:, 4] = convert_eval_to_chip_index_floor(eval_grid[:, 0], die_layout[0], nx)
    temp_grid_calc[:, 5] = convert_eval_to_chip_index_ceil(eval_grid[:, 1], die_layout[1], ny)
    temp_grid_calc[:, 6] = convert_eval_to_chip_index_ceil(eval_grid[:, 0], die_layout[0], nx)
    temp_grid_calc[:, 7] = convert_eval_to_chip_index_ceil(eval_grid[:, 1], die_layout[1], ny)

    # 7. 각 chip이 wafer edge를 벗어나는지 확인
    for ii in range(0, 8, 2):
        for iii in range(n_eval):
            # Chip 중심 좌표 계산 (shot 기준)
            chip_center_rx = (-shot_layout[0]/2 +
                             (temp_grid_calc[iii, ii] + 0.5) * shot_layout[0] / die_layout[0])
            chip_center_ry = (-shot_layout[1]/2 +
                             (temp_grid_calc[iii, ii+1] + 0.5) * shot_layout[1] / die_layout[1])

            # Chip 중심 좌표 (wafer 기준)
            chip_center_wx = shot_layout[0] * shot_array[0] + shot_layout[2] + chip_center_rx
            chip_center_wy = shot_layout[1] * shot_array[1] + shot_layout[3] + chip_center_ry

            # Chip 크기
            chip_size = np.array([
                shot_layout[0] / die_layout[0],
                shot_layout[1] / die_layout[1]
            ])

            # Edge 판정
            temp_grid_calc[iii, (ii//2) + 8] = check_edge_shot(
                np.array([chip_center_wx, chip_center_wy]),
                chip_size,
                chip_limit_radius
            )

    # 8. 4개 chip 모두가 wafer 내부에 있는 evaluation point만 선택
    edge_sum = np.sum(temp_grid_calc[:, 8:12], axis=1)
    valid_indices = edge_sum < 4  # 4개 chip 모두 내부 (edge=0)

    final_eval_grid = eval_grid[valid_indices, 2:4]  # 좌표만 반환

    return final_eval_grid if final_eval_grid.size > 0 else None


def generate_eval_grid(
    shot_size_x: float,
    shot_size_y: float,
    grid_size: Tuple[int, int] = None
) -> np.ndarray:
    """
    Shot 내부의 evaluation grid 생성 (Simple version, chip 경계 고려 안함)

    Args:
        shot_size_x: Shot X 크기 (mm)
        shot_size_y: Shot Y 크기 (mm)
        grid_size: (nx, ny) evaluation grid 크기

    Returns:
        [N, 2] evaluation grid 좌표 (shot 중심 기준)
    """
    if grid_size is None:
        grid_size = CPE_EVAL_GRID

    nx, ny = grid_size

    # Grid index 생성 (0 ~ nx-1, 0 ~ ny-1)
    x_indices = np.arange(nx)
    y_indices = np.arange(ny)

    # Meshgrid 생성
    X_idx, Y_idx = np.meshgrid(x_indices, y_indices)

    # Index를 실제 좌표로 변환 (shot 중심 기준)
    x_coords = (shot_size_x / (nx - 1)) * X_idx.flatten() - shot_size_x * 0.5
    y_coords = (shot_size_y / (ny - 1)) * Y_idx.flatten() - shot_size_y * 0.5

    eval_coords = np.column_stack([x_coords, y_coords])

    return eval_coords


# ========================================
# Shot별 G-opt 분석 (메인 인터페이스)
# ========================================

def analyze_shot_gopt(
    shot_measurement_coords: np.ndarray,
    shot_size_x: float,
    shot_size_y: float,
    default_cpe_option: str = '18para'
) -> Dict:
    """
    단일 Shot에 대한 G-opt 분석 및 CPE 옵션 결정

    Args:
        shot_measurement_coords: [N, 2] Shot 내 측정 포인트 좌표 (mm, shot 중심 기준)
        shot_size_x: Shot X 크기 (mm)
        shot_size_y: Shot Y 크기 (mm)
        default_cpe_option: 시작 CPE 옵션

    Returns:
        {
            'selected_option': str,
            'gopt_x': float,
            'gopt_y': float,
            'fallback_count': int,
            'status': str,
            'n_meas_points': int,
            'n_eval_points': int
        }
    """
    # 1. Evaluation grid 생성
    eval_coords = generate_eval_grid(shot_size_x, shot_size_y)

    # 2. G-opt 기반 CPE 옵션 결정
    result = determine_cpe_option_with_gopt(
        eval_coords,
        shot_measurement_coords,
        default_option=default_cpe_option
    )

    # 3. 통계 정보 추가
    result['n_meas_points'] = len(shot_measurement_coords)
    result['n_eval_points'] = len(eval_coords)

    return result


# ========================================
# Wafer 전체 Shot별 G-opt 분석
# ========================================

def analyze_wafer_shots_gopt(
    df_rawdata: pd.DataFrame,
    default_cpe_option: str = '18para'
) -> pd.DataFrame:
    """
    Wafer 전체 Shot에 대한 G-opt 분석

    Args:
        df_rawdata: RawData DataFrame (필수 컬럼: UNIQUE_ID4, coordinate_X, coordinate_Y,
                                                   STEP_PITCH_X, STEP_PITCH_Y)
        default_cpe_option: 기본 CPE 옵션

    Returns:
        Shot별 G-opt 분석 결과 DataFrame
        컬럼: UNIQUE_ID4, selected_cpe_option, gopt_x, gopt_y, fallback_count,
              status, n_meas_points, n_eval_points
    """
    results = []

    # UNIQUE_ID4별 그룹핑 (Shot 단위)
    grouped = df_rawdata.groupby('UNIQUE_ID4')

    logging.info(f"Starting G-opt analysis for {len(grouped)} shots")

    for unique_id4, group in grouped:
        # Shot 크기 가져오기 (μm → mm 변환)
        shot_size_x = group['STEP_PITCH_X'].iloc[0] / 1000.0
        shot_size_y = group['STEP_PITCH_Y'].iloc[0] / 1000.0

        # 측정 포인트 좌표 (shot 중심 기준, μm → mm 변환)
        meas_coords = group[['coordinate_X', 'coordinate_Y']].values / 1000.0

        # G-opt 분석
        shot_result = analyze_shot_gopt(
            meas_coords,
            shot_size_x,
            shot_size_y,
            default_cpe_option
        )

        # 결과 저장
        shot_result['UNIQUE_ID4'] = unique_id4
        results.append(shot_result)

    df_gopt = pd.DataFrame(results)

    # 통계 출력
    success_count = len(df_gopt[df_gopt['status'] == 'success'])
    total_shots = len(df_gopt)

    logging.info(f"G-opt analysis completed:")
    logging.info(f"  Total shots: {total_shots}")
    logging.info(f"  Success (default option): {success_count} ({success_count/total_shots*100:.1f}%)")

    option_counts = df_gopt['selected_option'].value_counts()
    for option, count in option_counts.items():
        logging.info(f"  {option}: {count} shots ({count/total_shots*100:.1f}%)")

    return df_gopt


# ========================================
# 편의 함수
# ========================================

def validate_cpe_option(cpe_option: str) -> str:
    """CPE 옵션 검증 및 반환"""
    if cpe_option not in CPE_OPTIONS:
        valid_options = list(CPE_OPTIONS.keys())
        raise ValueError(
            f"Invalid cpe_option: '{cpe_option}'. "
            f"Available options: {valid_options}"
        )
    return cpe_option


def get_cpe_option_info(cpe_option: str) -> Dict:
    """CPE 옵션 정보 반환"""
    validate_cpe_option(cpe_option)
    return CPE_OPTIONS[cpe_option]
