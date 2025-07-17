# config.py
# 설정 파일: 각종 경로 및 상수를 정의합니다.

FOLDER_PATH = 'C:/users/sungil.moon/Desktop/8Y40M/code/OTS/nau'
PROCESS_MODE = 'ADI'  #'ADI', 'OCO'  둘중에 하나만 입력가능


# design_matrix_config.py
DEFAULT_OSR_OPTION = '19para'
DEFAULT_CPE_OPTION = '15para'
DEFAULT_CPE_FIT_OPTION = '38para'

# radius filtering에 사용할 반경 임계값
RADIUS_THRESHOLD = 150000  

# Outlier 판정을 위한 상수들
OUTLIER_THRESHOLD = 3.0      # studentized residual 임계값
DMARGIN_X = 0.005            # X 방향 DMARGIN
DMARGIN_Y = 0.0025           # Y 방향 DMARGIN
OUTLIER_SPEC_RATIO = 1.5     # DMARGIN 배율

# Zernike 분석의 최대 인덱스
MAX_INDEX = 64          

