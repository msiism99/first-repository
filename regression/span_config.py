# span_config.py
# RK Span Limit 설정 파일 (6가지 모드)
# 데이터 소스: 01.Span_OCM단위.xlsx (2025-09-21 기준)

# =============================================================================
# Span 모드 설정
# =============================================================================

# SPAN_MODE는 config.py에서 가져옴 (중앙 집중식 설정 관리)
from config import SPAN_MODE

# =============================================================================
# RK Span Limits (6가지 모드)
# =============================================================================

RK_SPAN_LIMITS_OVO2_HARDLIMIT = {
    'RK1': {'min': -100.0, 'max': 100.0},
    'RK2': {'min': -100.0, 'max': 100.0},
    'RK3': {'min': -1000.0, 'max': 1000.0},
    'RK4': {'min': -1000.0, 'max': 1000.0},
    'RK5': {'min': -1000.0, 'max': 1000.0},
    'RK6': {'min': -1000.0, 'max': 1000.0},
    'RK7': {'min': -0.25, 'max': 0.25},
    'RK8': {'min': -10.0, 'max': 10.0},
    'RK9': {'min': -0.06, 'max': 0.06},
    'RK10': {'min': -10.0, 'max': 10.0},
    'RK11': {'min': -10.0, 'max': 10.0},
    'RK12': {'min': -0.25, 'max': 0.25},
    'RK13': {'min': -0.025, 'max': 0.025},
    'RK14': {'min': -1.0, 'max': 1.0},
    'RK15': {'min': -0.002, 'max': 0.002},
    'RK16': {'min': -1.0, 'max': 1.0},
    'RK17': {'min': -0.005, 'max': 0.005},
    'RK18': {'min': -0.002, 'max': 0.002},
    'RK19': {'min': -1.0, 'max': 1.0},
    'RK20': {'min': 0.0, 'max': 0.0},
    # 4차~7차 (RK21~RK72) - OVO2 HARDLIMIT는 모두 0.0 (제어 불가)
    'RK21': {'min': 0.0, 'max': 0.0},
    'RK22': {'min': 0.0, 'max': 0.0},
    'RK23': {'min': 0.0, 'max': 0.0},
    'RK24': {'min': 0.0, 'max': 0.0},
    'RK25': {'min': 0.0, 'max': 0.0},
    'RK26': {'min': 0.0, 'max': 0.0},
    'RK27': {'min': 0.0, 'max': 0.0},
    'RK28': {'min': 0.0, 'max': 0.0},
    'RK29': {'min': 0.0, 'max': 0.0},
    'RK30': {'min': 0.0, 'max': 0.0},
    'RK31': {'min': 0.0, 'max': 0.0},
    'RK32': {'min': 0.0, 'max': 0.0},
    'RK33': {'min': 0.0, 'max': 0.0},
    'RK34': {'min': 0.0, 'max': 0.0},
    'RK35': {'min': 0.0, 'max': 0.0},
    'RK36': {'min': 0.0, 'max': 0.0},
    'RK37': {'min': 0.0, 'max': 0.0},
    'RK38': {'min': 0.0, 'max': 0.0},
    'RK39': {'min': 0.0, 'max': 0.0},
    'RK40': {'min': 0.0, 'max': 0.0},
    'RK41': {'min': 0.0, 'max': 0.0},
    'RK42': {'min': 0.0, 'max': 0.0},
    'RK43': {'min': 0.0, 'max': 0.0},
    'RK44': {'min': 0.0, 'max': 0.0},
    'RK45': {'min': 0.0, 'max': 0.0},
    'RK46': {'min': 0.0, 'max': 0.0},
    'RK47': {'min': 0.0, 'max': 0.0},
    'RK48': {'min': 0.0, 'max': 0.0},
    'RK49': {'min': 0.0, 'max': 0.0},
    'RK50': {'min': 0.0, 'max': 0.0},
    'RK51': {'min': 0.0, 'max': 0.0},
    'RK52': {'min': 0.0, 'max': 0.0},
    'RK53': {'min': 0.0, 'max': 0.0},
    'RK54': {'min': 0.0, 'max': 0.0},
    'RK55': {'min': 0.0, 'max': 0.0},
    'RK56': {'min': 0.0, 'max': 0.0},
    'RK57': {'min': 0.0, 'max': 0.0},
    'RK58': {'min': 0.0, 'max': 0.0},
    'RK59': {'min': 0.0, 'max': 0.0},
    'RK60': {'min': 0.0, 'max': 0.0},
    'RK61': {'min': 0.0, 'max': 0.0},
    'RK62': {'min': 0.0, 'max': 0.0},
    'RK63': {'min': 0.0, 'max': 0.0},
    'RK64': {'min': 0.0, 'max': 0.0},
    'RK65': {'min': 0.0, 'max': 0.0},
    'RK66': {'min': 0.0, 'max': 0.0},
    'RK67': {'min': 0.0, 'max': 0.0},
    'RK68': {'min': 0.0, 'max': 0.0},
    'RK69': {'min': 0.0, 'max': 0.0},
    'RK70': {'min': 0.0, 'max': 0.0},
    'RK71': {'min': 0.0, 'max': 0.0},
    'RK72': {'min': 0.0, 'max': 0.0},
}

RK_SPAN_LIMITS_OVO3_33P_HARDLIMIT = {
    'RK1': {'min': -100.0, 'max': 100.0},
    'RK2': {'min': -100.0, 'max': 100.0},
    'RK3': {'min': -1000.0, 'max': 1000.0},
    'RK4': {'min': -1000.0, 'max': 1000.0},
    'RK5': {'min': -1000.0, 'max': 1000.0},
    'RK6': {'min': -1000.0, 'max': 1000.0},
    'RK7': {'min': -0.1, 'max': 0.1},
    'RK8': {'min': -10.0, 'max': 10.0},
    'RK9': {'min': -0.1, 'max': 0.1},
    'RK10': {'min': -10.0, 'max': 10.0},
    'RK11': {'min': -10.0, 'max': 10.0},
    'RK12': {'min': -0.1, 'max': 0.1},
    'RK13': {'min': 0.0, 'max': 0.0},
    'RK14': {'min': -1.0, 'max': 1.0},
    'RK15': {'min': -0.01, 'max': 0.01},
    'RK16': {'min': -1.0, 'max': 1.0},
    'RK17': {'min': -0.01, 'max': 0.01},
    'RK18': {'min': -0.01, 'max': 0.01},
    'RK19': {'min': -1.0, 'max': 1.0},
    'RK20': {'min': 0.0, 'max': 0.0},
    # 4차~7차 (RK21~RK72) - OVO3_33P HARDLIMIT
    'RK21': {'min': 0.0, 'max': 0.0},
    'RK22': {'min': -2.0, 'max': 2.0},
    'RK23': {'min': 0.0, 'max': 0.0},
    'RK24': {'min': -2.0, 'max': 2.0},
    'RK25': {'min': -3.0, 'max': 3.0},
    'RK26': {'min': -3.0, 'max': 3.0},
    'RK27': {'min': -2.0, 'max': 2.0},
    'RK28': {'min': 0.0, 'max': 0.0},
    'RK29': {'min': -2.0, 'max': 2.0},
    'RK30': {'min': 0.0, 'max': 0.0},
    'RK31': {'min': 0.0, 'max': 0.0},
    'RK32': {'min': -1.0, 'max': 1.0},
    'RK33': {'min': 0.0, 'max': 0.0},
    'RK34': {'min': -2.0, 'max': 2.0},
    'RK35': {'min': 0.0, 'max': 0.0},
    'RK36': {'min': -2.0, 'max': 2.0},
    'RK37': {'min': -2.0, 'max': 2.0},
    'RK38': {'min': 0.0, 'max': 0.0},
    'RK39': {'min': -2.0, 'max': 2.0},
    'RK40': {'min': 0.0, 'max': 0.0},
    'RK41': {'min': -1.0, 'max': 1.0},
    'RK42': {'min': 0.0, 'max': 0.0},
    'RK43': {'min': 0.0, 'max': 0.0},
    'RK44': {'min': 0.0, 'max': 0.0},
    'RK45': {'min': 0.0, 'max': 0.0},
    'RK46': {'min': -1.0, 'max': 1.0},
    'RK47': {'min': 0.0, 'max': 0.0},
    'RK48': {'min': -1.0, 'max': 1.0},
    'RK49': {'min': 0.0, 'max': 0.0},
    'RK50': {'min': 0.0, 'max': 0.0},
    'RK51': {'min': -1.0, 'max': 1.0},
    'RK52': {'min': 0.0, 'max': 0.0},
    'RK53': {'min': 0.0, 'max': 0.0},
    'RK54': {'min': 0.0, 'max': 0.0},
    'RK55': {'min': 0.0, 'max': 0.0},
    'RK56': {'min': 0.0, 'max': 0.0},
    'RK57': {'min': 0.0, 'max': 0.0},
    'RK58': {'min': 0.0, 'max': 0.0},
    'RK59': {'min': 0.0, 'max': 0.0},
    'RK60': {'min': 0.0, 'max': 0.0},
    'RK61': {'min': 0.0, 'max': 0.0},
    'RK62': {'min': 0.0, 'max': 0.0},
    'RK63': {'min': 0.0, 'max': 0.0},
    'RK64': {'min': 0.0, 'max': 0.0},
    'RK65': {'min': 0.0, 'max': 0.0},
    'RK66': {'min': 0.0, 'max': 0.0},
    'RK67': {'min': 0.0, 'max': 0.0},
    'RK68': {'min': 0.0, 'max': 0.0},
    'RK69': {'min': 0.0, 'max': 0.0},
    'RK70': {'min': 0.0, 'max': 0.0},
    'RK71': {'min': 0.0, 'max': 0.0},
    'RK72': {'min': 0.0, 'max': 0.0},
}

RK_SPAN_LIMITS_OVO3_38P_HARDLIMIT = {
    'RK1': {'min': -100.0, 'max': 100.0},
    'RK2': {'min': -100.0, 'max': 100.0},
    'RK3': {'min': -1000.0, 'max': 1000.0},
    'RK4': {'min': -1000.0, 'max': 1000.0},
    'RK5': {'min': -1000.0, 'max': 1000.0},
    'RK6': {'min': -1000.0, 'max': 1000.0},
    'RK7': {'min': -0.25, 'max': 0.25},
    'RK8': {'min': -10.0, 'max': 10.0},
    'RK9': {'min': -0.06, 'max': 0.06},
    'RK10': {'min': -10.0, 'max': 10.0},
    'RK11': {'min': -10.0, 'max': 10.0},
    'RK12': {'min': -0.25, 'max': 0.25},
    'RK13': {'min': -0.025, 'max': 0.025},
    'RK14': {'min': -1.0, 'max': 1.0},
    'RK15': {'min': -0.002, 'max': 0.002},
    'RK16': {'min': -1.0, 'max': 1.0},
    'RK17': {'min': -0.005, 'max': 0.005},
    'RK18': {'min': -0.002, 'max': 0.002},
    'RK19': {'min': -1.0, 'max': 1.0},
    'RK20': {'min': 0.0, 'max': 0.0},
    # 4차~7차 (RK21~RK72) - OVO3_38P HARDLIMIT
    'RK21': {'min': 0.0, 'max': 0.0},
    'RK22': {'min': -7.0, 'max': 7.0},
    'RK23': {'min': -2.5, 'max': 2.5},
    'RK24': {'min': -18.0, 'max': 18.0},
    'RK25': {'min': -8.0, 'max': 8.0},
    'RK26': {'min': -4.0, 'max': 4.0},
    'RK27': {'min': -7.0, 'max': 7.0},
    'RK28': {'min': 0.0, 'max': 0.0},
    'RK29': {'min': -7.0, 'max': 7.0},
    'RK30': {'min': 0.0, 'max': 0.0},
    'RK31': {'min': 0.0, 'max': 0.0},
    'RK32': {'min': -2.5, 'max': 2.5},
    'RK33': {'min': 0.0, 'max': 0.0},
    'RK34': {'min': -5.0, 'max': 5.0},
    'RK35': {'min': -2.0, 'max': 2.0},
    'RK36': {'min': -1.2, 'max': 1.2},
    'RK37': {'min': -2.5, 'max': 2.5},
    'RK38': {'min': 0.0, 'max': 0.0},
    'RK39': {'min': -4.0, 'max': 4.0},
    'RK40': {'min': 0.0, 'max': 0.0},
    'RK41': {'min': -2.5, 'max': 2.5},
    'RK42': {'min': 0.0, 'max': 0.0},
    'RK43': {'min': 0.0, 'max': 0.0},
    'RK44': {'min': 0.0, 'max': 0.0},
    'RK45': {'min': 0.0, 'max': 0.0},
    'RK46': {'min': -1.2, 'max': 1.2},
    'RK47': {'min': 0.0, 'max': 0.0},
    'RK48': {'min': -0.6, 'max': 0.6},
    'RK49': {'min': -0.8, 'max': 0.8},
    'RK50': {'min': 0.0, 'max': 0.0},
    'RK51': {'min': -1.2, 'max': 1.2},
    'RK52': {'min': 0.0, 'max': 0.0},
    'RK53': {'min': 0.0, 'max': 0.0},
    'RK54': {'min': 0.0, 'max': 0.0},
    'RK55': {'min': 0.0, 'max': 0.0},
    'RK56': {'min': 0.0, 'max': 0.0},
    'RK57': {'min': 0.0, 'max': 0.0},
    'RK58': {'min': 0.0, 'max': 0.0},
    'RK59': {'min': 0.0, 'max': 0.0},
    'RK60': {'min': 0.0, 'max': 0.0},
    'RK61': {'min': 0.0, 'max': 0.0},
    'RK62': {'min': 0.0, 'max': 0.0},
    'RK63': {'min': 0.0, 'max': 0.0},
    'RK64': {'min': 0.0, 'max': 0.0},
    'RK65': {'min': -0.7, 'max': 0.7},
    'RK66': {'min': 0.0, 'max': 0.0},
    'RK67': {'min': 0.0, 'max': 0.0},
    'RK68': {'min': 0.0, 'max': 0.0},
    'RK69': {'min': 0.0, 'max': 0.0},
    'RK70': {'min': 0.0, 'max': 0.0},
    'RK71': {'min': 0.0, 'max': 0.0},
    'RK72': {'min': 0.0, 'max': 0.0},
}

RK_SPAN_LIMITS_OVO2_F2F = {
    'RK1': {'min': -0.1, 'max': 0.1},
    'RK2': {'min': -0.1, 'max': 0.1},
    'RK3': {'min': -0.5, 'max': 0.5},
    'RK4': {'min': -5.0, 'max': 5.0},
    'RK5': {'min': -5.0, 'max': 5.0},
    'RK6': {'min': -5.0, 'max': 5.0},
    'RK7': {'min': -0.1, 'max': 0.1},
    'RK8': {'min': -0.15, 'max': 0.15},
    'RK9': {'min': 0.0, 'max': 0.0},
    'RK10': {'min': -0.5, 'max': 0.5},
    'RK11': {'min': -0.5, 'max': 0.5},
    'RK12': {'min': -0.03, 'max': 0.03},
    'RK13': {'min': -0.003, 'max': 0.003},
    'RK14': {'min': -0.015, 'max': 0.015},
    'RK15': {'min': -0.002, 'max': 0.002},
    'RK16': {'min': -0.05, 'max': 0.05},
    'RK17': {'min': -0.005, 'max': 0.005},
    'RK18': {'min': -0.002, 'max': 0.002},
    'RK19': {'min': -0.05, 'max': 0.05},
    'RK20': {'min': 0.0, 'max': 0.0},
    # 4차~7차 (RK21~RK72) - OVO2 F2F는 모두 0.0 (제어 불가)
    'RK21': {'min': 0.0, 'max': 0.0},
    'RK22': {'min': 0.0, 'max': 0.0},
    'RK23': {'min': 0.0, 'max': 0.0},
    'RK24': {'min': 0.0, 'max': 0.0},
    'RK25': {'min': 0.0, 'max': 0.0},
    'RK26': {'min': 0.0, 'max': 0.0},
    'RK27': {'min': 0.0, 'max': 0.0},
    'RK28': {'min': 0.0, 'max': 0.0},
    'RK29': {'min': 0.0, 'max': 0.0},
    'RK30': {'min': 0.0, 'max': 0.0},
    'RK31': {'min': 0.0, 'max': 0.0},
    'RK32': {'min': 0.0, 'max': 0.0},
    'RK33': {'min': 0.0, 'max': 0.0},
    'RK34': {'min': 0.0, 'max': 0.0},
    'RK35': {'min': 0.0, 'max': 0.0},
    'RK36': {'min': 0.0, 'max': 0.0},
    'RK37': {'min': 0.0, 'max': 0.0},
    'RK38': {'min': 0.0, 'max': 0.0},
    'RK39': {'min': 0.0, 'max': 0.0},
    'RK40': {'min': 0.0, 'max': 0.0},
    'RK41': {'min': 0.0, 'max': 0.0},
    'RK42': {'min': 0.0, 'max': 0.0},
    'RK43': {'min': 0.0, 'max': 0.0},
    'RK44': {'min': 0.0, 'max': 0.0},
    'RK45': {'min': 0.0, 'max': 0.0},
    'RK46': {'min': 0.0, 'max': 0.0},
    'RK47': {'min': 0.0, 'max': 0.0},
    'RK48': {'min': 0.0, 'max': 0.0},
    'RK49': {'min': 0.0, 'max': 0.0},
    'RK50': {'min': 0.0, 'max': 0.0},
    'RK51': {'min': 0.0, 'max': 0.0},
    'RK52': {'min': 0.0, 'max': 0.0},
    'RK53': {'min': 0.0, 'max': 0.0},
    'RK54': {'min': 0.0, 'max': 0.0},
    'RK55': {'min': 0.0, 'max': 0.0},
    'RK56': {'min': 0.0, 'max': 0.0},
    'RK57': {'min': 0.0, 'max': 0.0},
    'RK58': {'min': 0.0, 'max': 0.0},
    'RK59': {'min': 0.0, 'max': 0.0},
    'RK60': {'min': 0.0, 'max': 0.0},
    'RK61': {'min': 0.0, 'max': 0.0},
    'RK62': {'min': 0.0, 'max': 0.0},
    'RK63': {'min': 0.0, 'max': 0.0},
    'RK64': {'min': 0.0, 'max': 0.0},
    'RK65': {'min': 0.0, 'max': 0.0},
    'RK66': {'min': 0.0, 'max': 0.0},
    'RK67': {'min': 0.0, 'max': 0.0},
    'RK68': {'min': 0.0, 'max': 0.0},
    'RK69': {'min': 0.0, 'max': 0.0},
    'RK70': {'min': 0.0, 'max': 0.0},
    'RK71': {'min': 0.0, 'max': 0.0},
    'RK72': {'min': 0.0, 'max': 0.0},
}

RK_SPAN_LIMITS_OVO3_33P_F2F = {
    'RK1': {'min': -0.1, 'max': 0.1},
    'RK2': {'min': -0.1, 'max': 0.1},
    'RK3': {'min': -2.0, 'max': 2.0},
    'RK4': {'min': -10.0, 'max': 10.0},
    'RK5': {'min': -5.0, 'max': 5.0},
    'RK6': {'min': -5.0, 'max': 5.0},
    'RK7': {'min': -0.1, 'max': 0.1},
    'RK8': {'min': -0.15, 'max': 0.15},
    'RK9': {'min': -0.06, 'max': 0.06},
    'RK10': {'min': -0.5, 'max': 0.5},
    'RK11': {'min': -0.5, 'max': 0.5},
    'RK12': {'min': -0.03, 'max': 0.03},
    'RK13': {'min': 0.0, 'max': 0.0},
    'RK14': {'min': -0.015, 'max': 0.015},
    'RK15': {'min': -0.002, 'max': 0.002},
    'RK16': {'min': -0.05, 'max': 0.05},
    'RK17': {'min': -0.005, 'max': 0.005},
    'RK18': {'min': -0.002, 'max': 0.002},
    'RK19': {'min': -0.023, 'max': 0.023},
    'RK20': {'min': 0.0, 'max': 0.0},
    # 4차~7차 (RK21~RK72) - OVO3_33P F2F
    'RK21': {'min': 0.0, 'max': 0.0},
    'RK22': {'min': -2.0, 'max': 2.0},
    'RK23': {'min': 0.0, 'max': 0.0},
    'RK24': {'min': -2.0, 'max': 2.0},
    'RK25': {'min': -3.0, 'max': 3.0},
    'RK26': {'min': -3.0, 'max': 3.0},
    'RK27': {'min': -2.0, 'max': 2.0},
    'RK28': {'min': 0.0, 'max': 0.0},
    'RK29': {'min': -2.0, 'max': 2.0},
    'RK30': {'min': 0.0, 'max': 0.0},
    'RK31': {'min': 0.0, 'max': 0.0},
    'RK32': {'min': -1.0, 'max': 1.0},
    'RK33': {'min': 0.0, 'max': 0.0},
    'RK34': {'min': -2.0, 'max': 2.0},
    'RK35': {'min': 0.0, 'max': 0.0},
    'RK36': {'min': -2.0, 'max': 2.0},
    'RK37': {'min': -2.0, 'max': 2.0},
    'RK38': {'min': 0.0, 'max': 0.0},
    'RK39': {'min': -2.0, 'max': 2.0},
    'RK40': {'min': 0.0, 'max': 0.0},
    'RK41': {'min': -1.0, 'max': 1.0},
    'RK42': {'min': 0.0, 'max': 0.0},
    'RK43': {'min': 0.0, 'max': 0.0},
    'RK44': {'min': 0.0, 'max': 0.0},
    'RK45': {'min': 0.0, 'max': 0.0},
    'RK46': {'min': -1.0, 'max': 1.0},
    'RK47': {'min': 0.0, 'max': 0.0},
    'RK48': {'min': -1.0, 'max': 1.0},
    'RK49': {'min': 0.0, 'max': 0.0},
    'RK50': {'min': 0.0, 'max': 0.0},
    'RK51': {'min': -1.0, 'max': 1.0},
    'RK52': {'min': 0.0, 'max': 0.0},
    'RK53': {'min': 0.0, 'max': 0.0},
    'RK54': {'min': 0.0, 'max': 0.0},
    'RK55': {'min': 0.0, 'max': 0.0},
    'RK56': {'min': 0.0, 'max': 0.0},
    'RK57': {'min': 0.0, 'max': 0.0},
    'RK58': {'min': 0.0, 'max': 0.0},
    'RK59': {'min': 0.0, 'max': 0.0},
    'RK60': {'min': 0.0, 'max': 0.0},
    'RK61': {'min': 0.0, 'max': 0.0},
    'RK62': {'min': 0.0, 'max': 0.0},
    'RK63': {'min': 0.0, 'max': 0.0},
    'RK64': {'min': 0.0, 'max': 0.0},
    'RK65': {'min': 0.0, 'max': 0.0},
    'RK66': {'min': 0.0, 'max': 0.0},
    'RK67': {'min': 0.0, 'max': 0.0},
    'RK68': {'min': 0.0, 'max': 0.0},
    'RK69': {'min': 0.0, 'max': 0.0},
    'RK70': {'min': 0.0, 'max': 0.0},
    'RK71': {'min': 0.0, 'max': 0.0},
    'RK72': {'min': 0.0, 'max': 0.0},
}

RK_SPAN_LIMITS_OVO3_38P_F2F = {
    'RK1': {'min': -0.1, 'max': 0.1},
    'RK2': {'min': -0.1, 'max': 0.1},
    'RK3': {'min': -2.0, 'max': 2.0},
    'RK4': {'min': -10.0, 'max': 10.0},
    'RK5': {'min': -5.0, 'max': 5.0},
    'RK6': {'min': -5.0, 'max': 5.0},
    'RK7': {'min': -0.1, 'max': 0.1},
    'RK8': {'min': -0.15, 'max': 0.15},
    'RK9': {'min': -0.06, 'max': 0.06},
    'RK10': {'min': -0.5, 'max': 0.5},
    'RK11': {'min': -0.5, 'max': 0.5},
    'RK12': {'min': -0.03, 'max': 0.03},
    'RK13': {'min': -0.003, 'max': 0.003},
    'RK14': {'min': -0.015, 'max': 0.015},
    'RK15': {'min': -0.002, 'max': 0.002},
    'RK16': {'min': -0.05, 'max': 0.05},
    'RK17': {'min': -0.005, 'max': 0.005},
    'RK18': {'min': -0.002, 'max': 0.002},
    'RK19': {'min': -0.023, 'max': 0.023},
    'RK20': {'min': 0.0, 'max': 0.0},
    # 4차~7차 (RK21~RK72) - OVO3_38P F2F
    'RK21': {'min': 0.0, 'max': 0.0},
    'RK22': {'min': -7.0, 'max': 7.0},
    'RK23': {'min': -2.5, 'max': 2.5},
    'RK24': {'min': -18.0, 'max': 18.0},
    'RK25': {'min': -8.0, 'max': 8.0},
    'RK26': {'min': -4.0, 'max': 4.0},
    'RK27': {'min': -7.0, 'max': 7.0},
    'RK28': {'min': 0.0, 'max': 0.0},
    'RK29': {'min': -7.0, 'max': 7.0},
    'RK30': {'min': 0.0, 'max': 0.0},
    'RK31': {'min': 0.0, 'max': 0.0},
    'RK32': {'min': -2.5, 'max': 2.5},
    'RK33': {'min': 0.0, 'max': 0.0},
    'RK34': {'min': -5.0, 'max': 5.0},
    'RK35': {'min': -2.0, 'max': 2.0},
    'RK36': {'min': -1.2, 'max': 1.2},
    'RK37': {'min': -2.5, 'max': 2.5},
    'RK38': {'min': 0.0, 'max': 0.0},
    'RK39': {'min': -4.0, 'max': 4.0},
    'RK40': {'min': 0.0, 'max': 0.0},
    'RK41': {'min': -2.5, 'max': 2.5},
    'RK42': {'min': 0.0, 'max': 0.0},
    'RK43': {'min': 0.0, 'max': 0.0},
    'RK44': {'min': 0.0, 'max': 0.0},
    'RK45': {'min': 0.0, 'max': 0.0},
    'RK46': {'min': -1.2, 'max': 1.2},
    'RK47': {'min': 0.0, 'max': 0.0},
    'RK48': {'min': -0.6, 'max': 0.6},
    'RK49': {'min': -0.8, 'max': 0.8},
    'RK50': {'min': 0.0, 'max': 0.0},
    'RK51': {'min': -1.2, 'max': 1.2},
    'RK52': {'min': 0.0, 'max': 0.0},
    'RK53': {'min': 0.0, 'max': 0.0},
    'RK54': {'min': 0.0, 'max': 0.0},
    'RK55': {'min': 0.0, 'max': 0.0},
    'RK56': {'min': 0.0, 'max': 0.0},
    'RK57': {'min': 0.0, 'max': 0.0},
    'RK58': {'min': 0.0, 'max': 0.0},
    'RK59': {'min': 0.0, 'max': 0.0},
    'RK60': {'min': 0.0, 'max': 0.0},
    'RK61': {'min': 0.0, 'max': 0.0},
    'RK62': {'min': 0.0, 'max': 0.0},
    'RK63': {'min': 0.0, 'max': 0.0},
    'RK64': {'min': 0.0, 'max': 0.0},
    'RK65': {'min': -0.7, 'max': 0.7},
    'RK66': {'min': 0.0, 'max': 0.0},
    'RK67': {'min': 0.0, 'max': 0.0},
    'RK68': {'min': 0.0, 'max': 0.0},
    'RK69': {'min': 0.0, 'max': 0.0},
    'RK70': {'min': 0.0, 'max': 0.0},
    'RK71': {'min': 0.0, 'max': 0.0},
    'RK72': {'min': 0.0, 'max': 0.0},
}

# =============================================================================
# Span Limits 매핑
# =============================================================================

ALL_SPAN_LIMITS = {
    'OVO2_HARDLIMIT': RK_SPAN_LIMITS_OVO2_HARDLIMIT,
    'OVO3_33P_HARDLIMIT': RK_SPAN_LIMITS_OVO3_33P_HARDLIMIT,
    'OVO3_38P_HARDLIMIT': RK_SPAN_LIMITS_OVO3_38P_HARDLIMIT,
    'OVO2_F2F': RK_SPAN_LIMITS_OVO2_F2F,
    'OVO3_33P_F2F': RK_SPAN_LIMITS_OVO3_33P_F2F,
    'OVO3_38P_F2F': RK_SPAN_LIMITS_OVO3_38P_F2F,
}

# =============================================================================
# Span Limit 조회 함수
# =============================================================================

def get_active_span_limits():
    """
    현재 설정된 Span 모드의 limits 반환

    Returns:
        dict: RK1~RK72 span limits (프로젝트10: RK72까지 확장됨)
    """
    if SPAN_MODE not in ALL_SPAN_LIMITS:
        return ALL_SPAN_LIMITS['OVO2_HARDLIMIT']
    return ALL_SPAN_LIMITS[SPAN_MODE]


def get_span_limits(span_mode=None):
    """
    지정된 Span 모드의 limits 반환 (프로젝트9 Ridge용)

    Args:
        span_mode: Span 모드 ('OVO2_HARDLIMIT', 'OVO3_33P_HARDLIMIT', etc.)
                   None이면 현재 설정된 SPAN_MODE 사용

    Returns:
        dict: RK1~RK72 span limits (프로젝트10: RK72까지 확장됨)
    """
    if span_mode is None:
        span_mode = SPAN_MODE

    if span_mode not in ALL_SPAN_LIMITS:
        return ALL_SPAN_LIMITS['OVO2_HARDLIMIT']

    return ALL_SPAN_LIMITS[span_mode]


# =============================================================================
# CPE Option과 SPAN_MODE 호환성 체크 (프로젝트9)
# =============================================================================

# CPE Option별 권장 SPAN_MODE 매핑
CPE_SPAN_COMPATIBILITY = {
    # OVO2 계열 (1~3차 보정)
    '2para': ['OVO2_HARDLIMIT', 'OVO2_F2F'],
    '6para': ['OVO2_HARDLIMIT', 'OVO2_F2F'],
    '15para': ['OVO2_HARDLIMIT', 'OVO2_F2F'],
    '18para': ['OVO2_HARDLIMIT', 'OVO2_F2F'],
    '20para': ['OVO2_HARDLIMIT', 'OVO2_F2F'],

    # OVO3 33para (EUV, RK13 제외)
    '33para': ['OVO3_33P_HARDLIMIT', 'OVO3_33P_F2F'],

    # OVO3 38para (4~7차 선택항)
    '38para': ['OVO3_38P_HARDLIMIT', 'OVO3_38P_F2F'],

    # 72para (Full 7차) - 완전 매칭 없음 (항상 불일치)
    '72para': [],  # 어떤 SPAN_MODE와도 완전 매칭 안 됨
}


def validate_cpe_span_compatibility(cpe_option, span_mode, enable_span_control=False):
    """
    CPE Option과 SPAN_MODE의 호환성을 검증하고 경고 발생

    안정적인 운영을 위해 불일치 시 경고 메시지를 출력합니다.
    진행은 가능하지만, 의도하지 않은 설정 조합을 방지합니다.

    Args:
        cpe_option: CPE 회귀분석 옵션 ('38para', '33para', '72para', etc.)
        span_mode: Span 제어 모드 ('OVO3_38P_F2F', etc.)
        enable_span_control: Span control 활성화 여부 (True면 더 엄격한 경고)

    Returns:
        dict: {
            'compatible': bool,      # 호환 여부
            'warning_level': str,    # 'none', 'info', 'warning', 'critical'
            'message': str,          # 경고 메시지
            'recommendation': str    # 권장 설정
        }
    """
    import logging

    # CPE Option이 정의된 것인지 확인
    if cpe_option not in CPE_SPAN_COMPATIBILITY:
        return {
            'compatible': False,
            'warning_level': 'critical',
            'message': f"❌ 알 수 없는 CPE Option: '{cpe_option}'",
            'recommendation': f"유효한 CPE Option: {list(CPE_SPAN_COMPATIBILITY.keys())}"
        }

    # SPAN_MODE가 정의된 것인지 확인
    if span_mode not in ALL_SPAN_LIMITS:
        return {
            'compatible': False,
            'warning_level': 'critical',
            'message': f"❌ 알 수 없는 SPAN_MODE: '{span_mode}'",
            'recommendation': f"유효한 SPAN_MODE: {list(ALL_SPAN_LIMITS.keys())}"
        }

    # 권장 SPAN_MODE 목록 가져오기
    recommended_modes = CPE_SPAN_COMPATIBILITY[cpe_option]

    # 호환성 체크
    if span_mode in recommended_modes:
        # 완전 일치: 가장 안전한 조합
        return {
            'compatible': True,
            'warning_level': 'none',
            'message': f"✅ CPE Option '{cpe_option}'와 SPAN_MODE '{span_mode}' 일치 (권장 조합)",
            'recommendation': ''
        }

    # 불일치 케이스
    if cpe_option == '72para':
        # 72para는 어떤 SPAN_MODE와도 완전 매칭 안 됨 (고급 사용)
        if enable_span_control:
            # Span control ON: 정보성 경고 (Balloon pushing 사용)
            return {
                'compatible': False,
                'warning_level': 'info',
                'message': (
                    f"ℹ️  CPE Option '72para'는 어떤 SPAN_MODE와도 완전 매칭되지 않습니다.\n"
                    f"   현재 SPAN_MODE: '{span_mode}'\n"
                    f"   → 72para로 회귀분석하면 설비가 제어 못 하는 RK에도 값이 생깁니다.\n"
                    f"   → Span control ON: Balloon pushing으로 재분배 (정상 동작)"
                ),
                'recommendation': f"권장: DEFAULT_CPE_OPTION을 '{span_mode}'에 맞는 옵션으로 변경 (안정적 운영)"
            }
        else:
            # Span control OFF: 경고 (Violation 발생 가능)
            return {
                'compatible': False,
                'warning_level': 'warning',
                'message': (
                    f"⚠️  CPE Option '72para'와 SPAN_MODE '{span_mode}' 불일치!\n"
                    f"   → 72para로 회귀분석하면 설비가 제어 못 하는 RK에도 값이 생깁니다.\n"
                    f"   → Span control OFF: Span violation이 대량 발생할 수 있습니다!"
                ),
                'recommendation': (
                    f"권장:\n"
                    f"   1. ENABLE_RIDGE_SPAN_CONTROL = True로 설정 (Balloon pushing)\n"
                    f"   2. 또는 DEFAULT_CPE_OPTION을 '{span_mode}'에 맞는 옵션으로 변경"
                )
            }

    # 일반 불일치 (72para 외)
    if recommended_modes:
        recommended_str = ', '.join(recommended_modes)
    else:
        recommended_str = '(없음)'

    if enable_span_control:
        # Span control ON: 경고 (Balloon pushing 작동하지만 비효율적)
        return {
            'compatible': False,
            'warning_level': 'warning',
            'message': (
                f"⚠️  CPE Option '{cpe_option}'와 SPAN_MODE '{span_mode}' 불일치!\n"
                f"   → 권장 SPAN_MODE: {recommended_str}\n"
                f"   → Span control ON: Balloon pushing 작동하지만 비효율적일 수 있습니다."
            ),
            'recommendation': f"권장: SPAN_MODE를 {recommended_str} 중 하나로 변경"
        }
    else:
        # Span control OFF: 심각한 경고
        return {
            'compatible': False,
            'warning_level': 'critical',
            'message': (
                f"❌ CPE Option '{cpe_option}'와 SPAN_MODE '{span_mode}' 불일치!\n"
                f"   → 권장 SPAN_MODE: {recommended_str}\n"
                f"   → Span control OFF: 의도하지 않은 설정 조합입니다!"
            ),
            'recommendation': (
                f"권장:\n"
                f"   1. SPAN_MODE를 {recommended_str} 중 하나로 변경 (안정적)\n"
                f"   2. 또는 ENABLE_RIDGE_SPAN_CONTROL = True로 설정 (고급)"
            )
        }


def check_and_warn_cpe_span_compatibility(cpe_option, span_mode, enable_span_control=False):
    """
    CPE Option과 SPAN_MODE 호환성을 체크하고 경고 로그 출력

    이 함수는 validate_cpe_span_compatibility()를 호출하고
    결과에 따라 적절한 로그 레벨로 경고를 출력합니다.

    Args:
        cpe_option: CPE 회귀분석 옵션
        span_mode: Span 제어 모드
        enable_span_control: Span control 활성화 여부

    Returns:
        bool: 호환 여부 (True: 호환, False: 불일치)
    """
    import logging

    result = validate_cpe_span_compatibility(cpe_option, span_mode, enable_span_control)

    # 로그 출력
    if result['warning_level'] == 'none':
        logging.info(result['message'])
    elif result['warning_level'] == 'info':
        logging.info(result['message'])
        if result['recommendation']:
            logging.info(f"   {result['recommendation']}")
    elif result['warning_level'] == 'warning':
        logging.warning(result['message'])
        if result['recommendation']:
            logging.warning(f"   {result['recommendation']}")
    elif result['warning_level'] == 'critical':
        logging.warning("=" * 80)
        logging.warning(result['message'])
        if result['recommendation']:
            logging.warning(f"   {result['recommendation']}")
        logging.warning("=" * 80)

    return result['compatible']
