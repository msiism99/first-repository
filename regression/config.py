# config.py
# 설정 파일: 각종 경로 및 상수를 정의합니다.

# nau 파일이 저장된 기본 폴더 경로
FOLDER_PATH = 'C:/py_data/nau/VC075040'    # 'C:/py_data/nau/span_test'

PROCESS_MODE = 'ADI'  # 처리 모드 설정: 'ADI' 또는 'OCO'

# 목적 : case1
# case1 : ADI로 OSR -> OSR_residual -> CPE Regression -> CPE_residual이 TROCS자보정한 결과임.
# case2 : OCO로 OSR -> OSR_residual -> PSM Decorrect -> PSM Decorrect한 OSR_Residual -> CPE Regression한게 Ideal_PSM이 됨. PSM Input에서 Ideal_PSM을 뺀게 Delta_PSM


# design_matrix_config.py
DEFAULT_OSR_OPTION = '19para'
DEFAULT_CPE_OPTION = '38para'  # 옵션: '2para', '6para', '15para', '18para', '20para', '72para', '38para', '33para'
                                # '72para': Ridge Regression 전용 (7차 보정, Hyper)
DEFAULT_CPE_FIT_OPTION = '72para'
DEFAULT_WK_OPTION = 'wk72' # 'wk20'(3차), 'wk42'(5차), 'wk72'(7차)

# CPE 최대 RK 인덱스 (CSV 저장 범위)
MAX_CPE_RK_INDEX = 72  # RK1~RK72까지 저장 (모든 CPE 옵션 공통)

# radius filtering에 사용할 반경 임계값
RADIUS_THRESHOLD = 150000  

# Outlier 판정을 위한 상수들
OUTLIER_THRESHOLD = 3.0      # studentized residual 임계값
DMARGIN_X = 0.005            # X 방향 DMARGIN
DMARGIN_Y = 0.0025           # Y 방향 DMARGIN
OUTLIER_SPEC_RATIO = 1.5     # DMARGIN 배율

# Zernike 분석의 최대 인덱스
MAX_INDEX = 64

# ========================================
# CPE G-opt Fallback 관련 설정
# ========================================
ENABLE_CPE_GOPT = True           # G-opt 기반 Fallback 활성화 여부
                                 # ⚠️  ENABLE_RIDGE_REGRESSION = True이면 이 설정 무시됨
                                 # True: G-opt > 1이면 차수 낮춤 (18→15→6)
                                 # False: 차수 고정 (18para 유지)
G_OPT_THRESHOLD = 1.0            # G-opt 임계값 (이 값보다 작아야 acceptable)
CPE_EVAL_GRID = [10, 10]         # Shot 내 evaluation grid 크기 (10x10 = 100 points)
CPE_CONDITION_THRESHOLD = 1e12   # Matrix condition number 임계값 (수치적 안정성)
CPE_MIN_POINTS = 1               # Shot별 최소 측정 포인트 수 (over-fitting 방지)

# Wafer/Chip Edge 판정 (Chip 경계 고려 로직용)
WAFER_LIMIT_RADIUS = 144.0       # Wafer edge 판정 반경 (mm) - Shot 단위
CHIP_LIMIT_RADIUS = 147.0        # Chip edge 판정 반경 (mm) - Chip 단위

# ========================================
# CPE Span 체크 관련 설정 (프로젝트5)
# ========================================
ENABLE_SPAN_CHECK = True         # Span 체크 활성화 여부 (모니터링 전용)
                                 # True: CPE_K.csv에 span_status 컬럼 추가
                                 #       Span over 여부 체크 및 경고
                                 # False: Span 체크 안 함
                                 # ⚠️  이것은 "모니터링"만 합니다 (제어 없음)
                                 #     Ridge Span control과는 다릅니다

SPAN_MODE = 'OVO3_38P_F2F'     # 기본 Span 모드
                                 # 옵션: 'OVO2_HARDLIMIT', 'OVO3_33P_HARDLIMIT', 'OVO3_38P_HARDLIMIT',
                                 #       'OVO2_F2F', 'OVO3_33P_F2F', 'OVO3_38P_F2F'

# ========================================
# Ridge Regression 관련 설정 (프로젝트9)
# ========================================
ENABLE_RIDGE_REGRESSION = True  # CPE 회귀분석 모드 선택
                                 #
                                 # True: Ridge 모드
                                 #   - G-opt control 자동 ON (lambda 조정)
                                 #   - 차수 고정 (Fallback 없음)
                                 #   - 고차 보정(18para, 72para) 가능
                                 #   - ENABLE_CPE_GOPT 설정 무시됨
                                 #
                                 # False: G-opt Fallback 모드 (기존 방식)
                                 #   - ENABLE_CPE_GOPT에 따라 동작
                                 #   - G-opt > 1이면 차수 낮춤 (18→15→6)

# G-opt 제어 관련
RIDGE_G_OPT_SPEC = 1.0           # G-opt 목표값 (이 값 이하로 유지)
RIDGE_G_OPT_TOLERANCE = 0.05     # G-opt 허용 오차
RIDGE_G_OPT_MAX_ITER = 100        # G-opt 제어 최대 반복 횟수

# Span 제어 관련 (Ridge 전용)
ENABLE_RIDGE_SPAN_CONTROL = True  # Ridge Span control 활성화 (Balloon pushing)
                                   # True: Span over 발생 시 해당 RK의 lambda 증가
                                   #       → RK 계수 감소 → 다른 RK로 재분배
                                   # False: Span control 안 함 (G-opt control만)
                                   # ⚠️  Ridge 모드에서만 동작 (Fallback 모드 무관)
                                   # ⚠️  ENABLE_SPAN_CHECK와 다름:
                                   #     - ENABLE_SPAN_CHECK: 체크만 (모니터링)
                                   #     - ENABLE_RIDGE_SPAN_CONTROL: 실제 제어

RIDGE_SPAN_TOLERANCE = 0.01      # Span 한계 허용 오차 (nm)
RIDGE_SPAN_MAX_ITER = 50         # Span 제어 최대 반복 횟수

# Ridge Lambda 관련
RIDGE_MIN_LAMBDA = 1e-10         # 최소 Lambda 값
RIDGE_MAX_LAMBDA = 1e10          # 최대 Lambda 값
RIDGE_LAMBDA_INCREMENT = 0.1     # Lambda 증가량 (빠른 조정용)

