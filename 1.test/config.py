# config.py
# 설정 파일: 각종 경로 및 상수를 정의합니다.

# nau 파일이 저장된 기본 폴더 경로
FOLDER_PATH = 'C:/py_data/nau/test/adi' #'C:/PSM SIM/TEST2_로직확인용/2. PRO버전 1매만/adi' #'C:/PSM SIM/250328 D1b GBL 어떻게 할지/시뮬3/1.nau'  #'C:/py_data/nau/1lot'

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

