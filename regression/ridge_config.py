# ridge_config.py
# Ridge Regression Lambda Valve 설정 파일
# 데이터 소스: ridge/ridge valve.xlsx

"""
Ridge Regression에서 사용하는 Lambda Valve 값

Ridge Valve는 각 RK 파라미터에 대한 Ridge Penalty의 기본 강도를 정의합니다.
- 보정 차수에 따라 다른 valve 값 사용
- 1st: 2para, 6para (선형 보정)
- 3rd: 15para, 18para (3차 보정)
- hyper: 72para (7차 보정)

Lambda = Ridge_Valve * tapering_factor
"""

# =============================================================================
# Ridge Valve 정의 (보정 차수별)
# =============================================================================

# 1st order (2para, 6para) - Linear correction
RIDGE_VALVE_1ST = {
    'RK1': 0.1,    # Offset X (um)
    'RK2': 0.1,    # Offset Y (um)
    'RK3': 1.0,    # Magnification X (ppm)
    'RK4': 1.0,    # Magnification Y (ppm)
    'RK5': 1.0,    # Rotation X (urad)
    'RK6': 1.0,    # Rotation Y (urad)
}

# 3rd order (15para, 18para) - 3rd order correction
RIDGE_VALVE_3RD = {
    'RK1': 0.001,   # Offset X
    'RK2': 0.001,   # Offset Y
    'RK3': 0.010,   # Magnification X
    'RK4': 0.010,   # Magnification Y
    'RK5': 0.010,   # Rotation X
    'RK6': 0.010,   # Rotation Y
    'RK7': 1.000,   # X^2 (ppg/um)
    'RK8': 0.100,   # Y^2 (ppg/um)
    'RK9': 1.000,   # XY (ppg/um)
    'RK10': 0.100,  # YX (ppg/um)
    'RK11': 0.100,  # Y^2 (ppg/um)
    'RK12': 1.000,  # X^2 (ppg/um)
    'RK13': 1.000,  # X^3 (ppt/um^2)
    'RK14': 0.100,  # Y^3 (ppt/um^2)
    'RK15': 1.000,  # X^2*Y (ppt/um^2)
    'RK16': 0.100,  # Y^2*X (ppt/um^2)
    'RK17': 1.000,  # X*Y^2 (ppt/um^2)
    'RK18': 1.000,  # Y*X^2 (ppt/um^2)
    'RK19': 0.100,  # Y^3 (ppt/um^2)
    'RK20': 1.000,  # X^3 (ppt/um^2)
}

# Hyper order (72para) - 7th order correction
RIDGE_VALVE_HYPER = {
    # 0차 (Offset)
    'RK1': 0.00,    # Offset X
    'RK2': 0.00,    # Offset Y
    # 1차 (Linear)
    'RK3': 0.01,    # Magnification X
    'RK4': 0.01,    # Magnification Y
    'RK5': 0.01,    # Rotation X
    'RK6': 0.01,    # Rotation Y
    # 2차 (Quadratic)
    'RK7': 1.00,    # X^2
    'RK8': 0.10,    # Y^2
    'RK9': 1.00,    # XY
    'RK10': 0.10,   # YX
    'RK11': 0.10,   # Y^2
    'RK12': 1.00,   # X^2
    # 3차 (Cubic)
    'RK13': 1.00,   # X^3
    'RK14': 0.10,   # Y^3
    'RK15': 1.00,   # X^2*Y
    'RK16': 0.10,   # Y^2*X
    'RK17': 1.00,   # X*Y^2
    'RK18': 1.00,   # Y*X^2
    'RK19': 0.10,   # Y^3
    'RK20': 1.00,   # X^3
    # 4차 (4th order)
    'RK21': 1.00,   # X^4
    'RK22': 1.00,   # Y^4
    'RK23': 1.00,   # X^3*Y
    'RK24': 1.00,   # Y^3*X
    'RK25': 1.00,   # X^2*Y^2
    'RK26': 1.00,   # Y^2*X^2
    'RK27': 1.00,   # X*Y^3
    'RK28': 1.00,   # Y*X^3
    'RK29': 1.00,   # Y^4
    'RK30': 1.00,   # X^4
    # 5차 (5th order)
    'RK31': 1.00,   # RKS31 (Special)
    'RK32': 1.00,   # X^5
    'RK33': 1.00,   # X^4*Y
    'RK34': 1.00,   # Y^4*X
    'RK35': 1.00,   # X^3*Y^2
    'RK36': 1.00,   # Y^3*X^2
    'RK37': 1.00,   # X^2*Y^3
    'RK38': 1.00,   # Y^2*X^3
    'RK39': 1.00,   # X*Y^4
    'RK40': 1.00,   # Y*X^4
    'RK41': 1.00,   # Y^5
    'RK42': 1.00,   # RKS42 (Special)
    # 6차 (6th order)
    'RK43': 1.00,   # RKS43 (Special)
    'RK44': 1.00,   # RKS44 (Special)
    'RK45': 1.00,   # RKS45 (Special)
    'RK46': 1.00,   # X^6
    'RK47': 1.00,   # X^5*Y
    'RK48': 1.00,   # Y^5*X
    'RK49': 1.00,   # X^4*Y^2
    'RK50': 1.00,   # Y^4*X^2
    'RK51': 1.00,   # X^3*Y^3
    'RK52': 1.00,   # Y^3*X^3
    'RK53': 1.00,   # X^2*Y^4
    'RK54': 1.00,   # RKS54 (Special)
    'RK55': 1.00,   # RKS55 (Special)
    'RK56': 1.00,   # RKS56 (Special)
    # 7차 (7th order)
    'RK57': 1.00,   # RKS57 (Special)
    'RK58': 1.00,   # RKS58 (Special)
    'RK59': 1.00,   # RKS59 (Special)
    'RK60': 1.00,   # RKS60 (Special)
    'RK61': 1.00,   # RKS61 (Special)
    'RK62': 1.00,   # X^7
    'RK63': 1.00,   # X^6*Y
    'RK64': 1.00,   # Y^6*X
    'RK65': 1.00,   # X^5*Y^2
    'RK66': 1.00,   # Y^5*X^2
    'RK67': 1.00,   # X^4*Y^3
    'RK68': 1.00,   # RKS68 (Special)
    'RK69': 1.00,   # RKS69 (Special)
    'RK70': 1.00,   # RKS70 (Special)
    'RK71': 1.00,   # RKS71 (Special)
    'RK72': 1.00,   # RKS72 (Special)
}

# =============================================================================
# Ridge Valve 매핑 (차수 옵션별)
# =============================================================================

RIDGE_VALVE_MAPPING = {
    # Linear (1st order)
    '2para': RIDGE_VALVE_1ST,
    '6para': RIDGE_VALVE_1ST,

    # 3rd order
    '15para': RIDGE_VALVE_3RD,
    '18para': RIDGE_VALVE_3RD,
    '20para': RIDGE_VALVE_3RD,

    # Hyper (4th~7th order)
    '33para': RIDGE_VALVE_HYPER,  # OVO3 보정용 (4~6차 선택항)
    '38para': RIDGE_VALVE_HYPER,  # OVO3 보정용 (4~7차 선택항)
    '72para': RIDGE_VALVE_HYPER,
}

# =============================================================================
# Helper 함수
# =============================================================================

def get_ridge_valve(cpe_option):
    """
    CPE 옵션에 해당하는 Ridge Valve 값 반환

    Args:
        cpe_option: CPE 회귀 옵션 ('2para', '6para', '15para', '18para', '20para', '72para')

    Returns:
        dict: RK별 Ridge Valve 값 딕셔너리
    """
    if cpe_option not in RIDGE_VALVE_MAPPING:
        # 기본값: 3rd order valve 사용
        return RIDGE_VALVE_3RD

    return RIDGE_VALVE_MAPPING[cpe_option]


def get_ridge_valve_for_rk(cpe_option, rk_name):
    """
    특정 RK 파라미터의 Ridge Valve 값 반환

    Args:
        cpe_option: CPE 회귀 옵션
        rk_name: RK 파라미터 이름 (예: 'RK1', 'RK15')

    Returns:
        float: Ridge Valve 값
    """
    valve_dict = get_ridge_valve(cpe_option)

    if rk_name not in valve_dict:
        # RK가 없으면 0 (penalty 없음)
        return 0.0

    return valve_dict[rk_name]
