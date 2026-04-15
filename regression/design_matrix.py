# design_matrix.py
import numpy as np

# ----- OSR(WK,RK) 디자인 행렬 -----
def osr_wk20p_rk20p(x, y, rx, ry):
    """
    WK20para, RK20para (1023_1023)   
    WK,RK를 FIT하기 위한 디자인 행렬. 
    """
    X_dx = np.vstack([
        np.ones(len(x)),
        x / 1e6, -y / 1e6,
        (x ** 2) / 1e12, (x * y) / 1e12, (y ** 2) / 1e12,
        (x ** 3) / 1e15, (x ** 2 * y) / 1e15, (x * y ** 2) / 1e15, (y ** 3) / 1e15,
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12
    ]).T

    X_dy = np.vstack([
        np.ones(len(y)),
        y / 1e6, x / 1e6,
        (y ** 2) / 1e12, (y * x) / 1e12, (x ** 2) / 1e12,
        (y ** 3) / 1e15, (y ** 2 * x) / 1e15, (y * x ** 2) / 1e15, (x ** 3) / 1e15,
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12, (rx ** 3) / 1e12
    ]).T

    return X_dx, X_dy


def osr_wk20p_rk19p(x, y, rx, ry):
    """
    WK20para, RK19para (1023_511)
    ASML 스캐너의 KMRC 보정을 위한 디자인 행렬.
    x, y는 3차항까지 모두 사용하고, rx, ry는 rx^3항은 제외.(RK20 보정불가성분분)
    """
    X_dx = np.vstack([
        np.ones(len(x)),
        x / 1e6, -y / 1e6,
        (x ** 2) / 1e12, (x * y) / 1e12, (y ** 2) / 1e12,
        (x ** 3) / 1e15, (x ** 2 * y) / 1e15, (x * y ** 2) / 1e15, (y ** 3) / 1e15,
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12
    ]).T

    X_dy = np.vstack([
        np.ones(len(y)),
        y / 1e6, x / 1e6,
        (y ** 2) / 1e12, (y * x) / 1e12, (x ** 2) / 1e12,
        (y ** 3) / 1e15, (y ** 2 * x) / 1e15, (y * x ** 2) / 1e15, (x ** 3) / 1e15,
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12
    ]).T

    return X_dx, X_dy


def osr_wk20p_rk18p(x, y, rx, ry):
    """
    WK20para, RK18para (959_511)
    """
    X_dx = np.vstack([
        np.ones(len(x)),
        x / 1e6, -y / 1e6,
        (x ** 2) / 1e12, (x * y) / 1e12, (y ** 2) / 1e12,
        (x ** 3) / 1e15, (x ** 2 * y) / 1e15, (x * y ** 2) / 1e15, (y ** 3) / 1e15,
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
                         (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12
    ]).T

    X_dy = np.vstack([
        np.ones(len(y)),
        y / 1e6, x / 1e6,
        (y ** 2) / 1e12, (y * x) / 1e12, (x ** 2) / 1e12,
        (y ** 3) / 1e15, (y ** 2 * x) / 1e15, (y * x ** 2) / 1e15, (x ** 3) / 1e15,
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12
    ]).T

    return X_dx, X_dy



def osr_wk20p_rk15p(x, y, rx, ry):
    """
    WK20para, RK15para (623_255) (RK9,RK15,RK17,RK18,RK20 제외)
    """
    X_dx = np.vstack([
        np.ones(len(x)),
        x / 1e6, -y / 1e6,
        (x ** 2) / 1e12, (x * y) / 1e12, (y ** 2) / 1e12,
        (x ** 3) / 1e15, (x ** 2 * y) / 1e15, (x * y ** 2) / 1e15, (y ** 3) / 1e15,
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9,                 (ry ** 2) / 1e9,
        (rx ** 3) / 1e12,                                 (ry ** 3) / 1e12
    ]).T

    X_dy = np.vstack([
        np.ones(len(y)),
        y / 1e6, x / 1e6,
        (y ** 2) / 1e12, (y * x) / 1e12, (x ** 2) / 1e12,
        (y ** 3) / 1e15, (y ** 2 * x) / 1e15, (y * x ** 2) / 1e15, (x ** 3) / 1e15,
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12 
    ]).T

    return X_dx, X_dy

def osr_wk6p_rk6p(x, y, rx, ry):
    """
    WK1~6(7_7), RK1~6(7_7) (WK, RK linear. outlier 판정정용) 
    """
    X_dx = np.vstack([
        np.ones(len(x)),
        x / 1e6, -y / 1e6,
        rx / 1e6, -ry / 1e6
    ]).T

    X_dy = np.vstack([
        np.ones(len(y)),
        y / 1e6, x / 1e6,
        ry / 1e6, rx / 1e6,
    ]).T

    return X_dx, X_dy





# ----- WK Only 디자인 행렬 -----

# 🆕 WK Only 함수들 (새로 추가)
def osr_wk20(x, y):
    """WK 20 parameter only - Global wafer-level systematic error"""
    X_dx = np.vstack([
        np.ones(len(x)),                                                      # WK1
        x / 1e6, -y / 1e6,                                                   # WK3, WK5
        (x ** 2) / 1e12, (x * y) / 1e12, (y ** 2) / 1e12,                   # WK7,9,11
        (x ** 3) / 1e15, (x ** 2 * y) / 1e15, (x * y ** 2) / 1e15, (y ** 3) / 1e15  # WK13,15,17,19
    ]).T

    X_dy = np.vstack([
        np.ones(len(y)),                                                      # WK2
        y / 1e6, x / 1e6,                                                    # WK4, WK6
        (y ** 2) / 1e12, (y * x) / 1e12, (x ** 2) / 1e12,                   # WK8,10,12
        (y ** 3) / 1e15, (y ** 2 * x) / 1e15, (y * x ** 2) / 1e15, (x ** 3) / 1e15  # WK14,16,18,20
    ]).T

    return X_dx, X_dy



def osr_wk72(x, y):
    """
    WK 72 parameter (0~7차) - Global wafer-level systematic error
    7차 polynomial까지 확장된 버전
    """
    X_dx = np.vstack([
        # 0차 (상수항) - WK1
        np.ones(len(x)),
        
        # 1차항 - WK3, WK5  
        x / 1e6, -y / 1e6,
        
        # 2차항 - WK7, WK9, WK11
        (x ** 2) / 1e12, (x * y) / 1e12, (y ** 2) / 1e12,
        
        # 3차항 - WK13, WK15, WK17, WK19
        (x ** 3) / 1e15, (x ** 2 * y) / 1e15, (x * y ** 2) / 1e15, (y ** 3) / 1e15,
        
        # 4차항 - WK21, WK23, WK25, WK27, WK29
        (x ** 4) / 1e18, (x ** 3 * y) / 1e18, (x ** 2 * y ** 2) / 1e18, (x * y ** 3) / 1e18, (y ** 4) / 1e18,
        
        # 5차항 - WK31, WK33, WK35, WK37, WK39, WK41
        (x ** 5) / 1e21, (x ** 4 * y) / 1e21, (x ** 3 * y ** 2) / 1e21, (x ** 2 * y ** 3) / 1e21, (x * y ** 4) / 1e21, (y ** 5) / 1e21,
        
        # 6차항 - WK43, WK45, WK47, WK49, WK51, WK53, WK55
        (x ** 6) / 1e24, (x ** 5 * y) / 1e24, (x ** 4 * y ** 2) / 1e24, (x ** 3 * y ** 3) / 1e24, (x ** 2 * y ** 4) / 1e24, (x * y ** 5) / 1e24, (y ** 6) / 1e24,
        
        # 7차항 - WK57, WK59, WK61, WK63, WK65, WK67, WK69, WK71
        (x ** 7) / 1e27, (x ** 6 * y) / 1e27, (x ** 5 * y ** 2) / 1e27, (x ** 4 * y ** 3) / 1e27, (x ** 3 * y ** 4) / 1e27, (x ** 2 * y ** 5) / 1e27, (x * y ** 6) / 1e27, (y ** 7) / 1e27
    ]).T

    X_dy = np.vstack([
        # 0차 (상수항) - WK2
        np.ones(len(y)),
        
        # 1차항 - WK4, WK6
        y / 1e6, x / 1e6,
        
        # 2차항 - WK8, WK10, WK12
        (y ** 2) / 1e12, (y * x) / 1e12, (x ** 2) / 1e12,
        
        # 3차항 - WK14, WK16, WK18, WK20
        (y ** 3) / 1e15, (y ** 2 * x) / 1e15, (y * x ** 2) / 1e15, (x ** 3) / 1e15,
        
        # 4차항 - WK22, WK24, WK26, WK28, WK30
        (y ** 4) / 1e18, (y ** 3 * x) / 1e18, (y ** 2 * x ** 2) / 1e18, (y * x ** 3) / 1e18, (x ** 4) / 1e18,
        
        # 5차항 - WK32, WK34, WK36, WK38, WK40, WK42
        (y ** 5) / 1e21, (y ** 4 * x) / 1e21, (y ** 3 * x ** 2) / 1e21, (y ** 2 * x ** 3) / 1e21, (y * x ** 4) / 1e21, (x ** 5) / 1e21,
        
        # 6차항 - WK44, WK46, WK48, WK50, WK52, WK54, WK56
        (y ** 6) / 1e24, (y ** 5 * x) / 1e24, (y ** 4 * x ** 2) / 1e24, (y ** 3 * x ** 3) / 1e24, (y ** 2 * x ** 4) / 1e24, (y * x ** 5) / 1e24, (x ** 6) / 1e24,
        
        # 7차항 - WK58, WK60, WK62, WK64, WK66, WK68, WK70, WK72
        (y ** 7) / 1e27, (y ** 6 * x) / 1e27, (y ** 5 * x ** 2) / 1e27, (y ** 4 * x ** 3) / 1e27, (y ** 3 * x ** 4) / 1e27, (y ** 2 * x ** 5) / 1e27, (y * x ** 6) / 1e27, (x ** 7) / 1e27
    ]).T

    return X_dx, X_dy



def osr_wk42(x, y):
    """
    WK 42 parameter (0~5차) - Global wafer-level systematic error
    5차 polynomial까지 확장된 버전
    """
    X_dx = np.vstack([
        # 0차 (상수항) - WK1
        np.ones(len(x)),
        
        # 1차항 - WK3, WK5  
        x / 1e6, -y / 1e6,
        
        # 2차항 - WK7, WK9, WK11
        (x ** 2) / 1e12, (x * y) / 1e12, (y ** 2) / 1e12,
        
        # 3차항 - WK13, WK15, WK17, WK19
        (x ** 3) / 1e15, (x ** 2 * y) / 1e15, (x * y ** 2) / 1e15, (y ** 3) / 1e15,
        
        # 4차항 - WK21, WK23, WK25, WK27, WK29
        (x ** 4) / 1e18, (x ** 3 * y) / 1e18, (x ** 2 * y ** 2) / 1e18, (x * y ** 3) / 1e18, (y ** 4) / 1e18,
        
        # 5차항 - WK31, WK33, WK35, WK37, WK39, WK41
        (x ** 5) / 1e21, (x ** 4 * y) / 1e21, (x ** 3 * y ** 2) / 1e21, (x ** 2 * y ** 3) / 1e21, (x * y ** 4) / 1e21, (y ** 5) / 1e21
    ]).T

    X_dy = np.vstack([
        # 0차 (상수항) - WK2
        np.ones(len(y)),
        
        # 1차항 - WK4, WK6
        y / 1e6, x / 1e6,
        
        # 2차항 - WK8, WK10, WK12
        (y ** 2) / 1e12, (y * x) / 1e12, (x ** 2) / 1e12,
        
        # 3차항 - WK14, WK16, WK18, WK20
        (y ** 3) / 1e15, (y ** 2 * x) / 1e15, (y * x ** 2) / 1e15, (x ** 3) / 1e15,
        
        # 4차항 - WK22, WK24, WK26, WK28, WK30
        (y ** 4) / 1e18, (y ** 3 * x) / 1e18, (y ** 2 * x ** 2) / 1e18, (y * x ** 3) / 1e18, (x ** 4) / 1e18,
        
        # 5차항 - WK32, WK34, WK36, WK38, WK40, WK42
        (y ** 5) / 1e21, (y ** 4 * x) / 1e21, (y ** 3 * x ** 2) / 1e21, (y ** 2 * x ** 3) / 1e21, (y * x ** 4) / 1e21, (x ** 5) / 1e21
    ]).T

    return X_dx, X_dy





# ----- CPE 디자인 행렬 -----

def cpe_20para(rx, ry):
    """
    RK 20para (1023_1023) : RK to FIT용도
    """
    X_dx = np.vstack([
        np.ones(len(rx)),
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12
    ]).T

    X_dy = np.vstack([
        np.ones(len(ry)),
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12, (rx ** 3) / 1e12,
    ]).T     

    return X_dx, X_dy

def cpe_18para(rx, ry):
    """
    RK 18para (959_511)
    """
    X_dx = np.vstack([
        np.ones(len(rx)),
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
                         (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12
    ]).T

    X_dy = np.vstack([
        np.ones(len(ry)),
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12
    ]).T

    return X_dx, X_dy


def cpe_15para(rx, ry):
    """
    RK 15para (623_255)
    """

    X_dx = np.vstack([
        np.ones(len(rx)),
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9,                   (ry ** 2) / 1e9,
        (rx ** 3) / 1e12,                                    (ry ** 3) / 1e12
    ]).T

    X_dy = np.vstack([
        np.ones(len(ry)),
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12
    ]).T

    return X_dx, X_dy


def cpe_6para(rx, ry):
    """
    RK 6para (7_7)
    """
    X_dx = np.vstack([
        np.ones(len(rx)),
        rx / 1e6, -ry / 1e6        
    ]).T

    X_dy = np.vstack([
        np.ones(len(ry)),
        ry / 1e6, rx / 1e6  
    ]).T

    return X_dx, X_dy

def cpe_2para(rx, ry):
    """
    RK 2para (1_1)
    """
    X_dx = np.vstack([
        np.ones(len(rx)),
    ]).T

    X_dy = np.vstack([
        np.ones(len(ry)),
    ]).T

    return X_dx, X_dy


def cpe_33para(rx, ry):
    """
    RK 33para (EUV 보정용)
    RK1~12, RK14~19, RK22,24,25,26,27,29, RK32,34,36,37,39,41, RK46,48,51

    ⚠️  EUV는 RK13 제어 불가 → RK13 제외

    RK 파라미터 구성:
    - 0~3차: RK1~12 (RK13 제외!), RK14~19 (18개)
    - 4차: RK22,24,25,26,27,29 (6개)
    - 5차: RK32,34,36,37,39,41 (6개)
    - 6차: RK46,48,51 (3개)
    총 33개 파라미터
    """
    X_dx = np.vstack([
        # 0차 (상수항) - RK1
        np.ones(len(rx)),

        # 1차항 - RK3, RK5
        rx / 1e6, -ry / 1e6,

        # 2차항 - RK7, RK9, RK11
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,

        # 3차항 - RK15, RK17, RK19 (RK13 제외!)
                         (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12,

        # 4차항 - RK25, RK27, RK29 (RK21, RK23 제외)
                                                (rx ** 2 * ry ** 2) / 1e19, (rx * ry ** 3) / 1e19, (ry ** 4) / 1e19,

        # 5차항 - RK37, RK39, RK41 (RK31, RK33, RK35 제외)
                                                                            (rx ** 2 * ry ** 3) / 1e23, (rx * ry ** 4) / 1e23, (ry ** 5) / 1e23,

        # 6차항 - RK51 (rx^2 * ry^4)
                                                                                                        (rx ** 2 * ry ** 4) / 1e27
    ]).T

    X_dy = np.vstack([
        # 0차 (상수항) - RK2
        np.ones(len(ry)),

        # 1차항 - RK4, RK6
        ry / 1e6, rx / 1e6,

        # 2차항 - RK8, RK10, RK12
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,

        # 3차항 - RK14, RK16, RK18 (RK20 제외)
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12,

        # 4차항 - RK22, RK24, RK26 (RK28, RK30 제외)
        (ry ** 4) / 1e19, (ry ** 3 * rx) / 1e19, (ry ** 2 * rx ** 2) / 1e19,

        # 5차항 - RK32, RK34, RK36 (RK38, RK40, RK42 제외)
        (ry ** 5) / 1e23, (ry ** 4 * rx) / 1e23, (ry ** 3 * rx ** 2) / 1e23,

        # 6차항 - RK46, RK48
                          (ry ** 5 * rx) / 1e27, (ry ** 4 * rx ** 2) / 1e27
    ]).T

    return X_dx, X_dy


def cpe_38para(rx, ry):
    """
    RK 38para (OVO3 보정)
    RK1~19, RK22,23,24,25,26,27,29, RK32,34,35,36,37,39,41, RK46,48,49,51, RK65

    RK 파라미터 구성:
    - 0~3차: RK1~RK19 (19개)
    - 4차: RK22,23,24,25,26,27,29 (7개)
    - 5차: RK32,34,35,36,37,39,41 (7개)
    - 6차: RK46,48,49,51 (4개)
    - 7차: RK65 (1개)
    총 38개 파라미터
    """
    X_dx = np.vstack([
        # 0차 (상수항) - RK1
        np.ones(len(rx)),

        # 1차항 - RK3, RK5
        rx / 1e6, -ry / 1e6,

        # 2차항 - RK7, RK9, RK11
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,

        # 3차항 - RK13, RK15, RK17, RK19
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12,

        # 4차항 - RK23, RK25, RK27, RK29 (RK21 제외)
                        (rx ** 3 * ry) / 1e19, (rx ** 2 * ry ** 2) / 1e19, (rx * ry ** 3) / 1e19, (ry ** 4) / 1e19,

        # 5차항 - RK35, RK37, RK39, RK41 (RK31, RK33 제외)
                                        (rx ** 3 * ry ** 2) / 1e23, (rx ** 2 * ry ** 3) / 1e23, (rx * ry ** 4) / 1e23, (ry ** 5) / 1e23,

        # 6차항 - RK49, RK51 (RK43, RK45, RK47, RK53, RK55 제외)
                                                                    (rx ** 3 * ry ** 3) / 1e27, (rx ** 2 * ry ** 4) / 1e27,

        # 7차항 - RK65 (rx^3 * ry^4)
                                                                                                (rx ** 3 * ry ** 4) / 1e31
    ]).T

    X_dy = np.vstack([
        # 0차 (상수항) - RK2
        np.ones(len(ry)),

        # 1차항 - RK4, RK6
        ry / 1e6, rx / 1e6,

        # 2차항 - RK8, RK10, RK12
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,

        # 3차항 - RK14, RK16, RK18 (RK20 제외)
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12,

        # 4차항 - RK22, RK24, RK26 (RK28, RK30 제외)
        (ry ** 4) / 1e19, (ry ** 3 * rx) / 1e19, (ry ** 2 * rx ** 2) / 1e19,

        # 5차항 - RK32, RK34, RK36 (RK38, RK40, RK42 제외)
        (ry ** 5) / 1e23, (ry ** 4 * rx) / 1e23, (ry ** 3 * rx ** 2) / 1e23,

        # 6차항 - RK46, RK48 (RK44, RK50, RK52, RK54, RK56 제외)
                        (ry ** 5 * rx) / 1e27, (ry ** 4 * rx ** 2) / 1e27
    ]).T

    return X_dx, X_dy


def cpe_72para(rx, ry):
    """
    RK 72para (Hyper 7차 보정)
    Ridge Regression 전용 - 7th order polynomial까지 확장

    RK 파라미터 구성:
    - 0차: RK1, RK2 (offset) - 1개씩
    - 1차: RK3-RK6 (linear) - 2개씩
    - 2차: RK7-RK12 (quadratic) - 3개씩
    - 3차: RK13-RK20 (cubic) - 4개씩
    - 4차: RK21-RK30 (4th order) - 5개씩
    - 5차: RK31-RK42 (5th order) - 6개씩
    - 6차: RK43-RK56 (6th order) - 7개씩
    - 7차: RK57-RK72 (7th order) - 8개씩
    총 36개 파라미터 × 2방향 = 72 파라미터
    """
    X_dx = np.vstack([
        # 0차 (상수항) - RK1
        np.ones(len(rx)),

        # 1차항 - RK3, RK5
        rx / 1e6, -ry / 1e6,

        # 2차항 - RK7, RK9, RK11
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,

        # 3차항 - RK13, RK15, RK17, RK19
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12,

        # 4차항 - RK21, RK23, RK25, RK27, RK29
        (rx ** 4) / 1e19, (rx ** 3 * ry) / 1e19, (rx ** 2 * ry ** 2) / 1e19, (rx * ry ** 3) / 1e19, (ry ** 4) / 1e19,

        # 5차항 - RK31, RK33, RK35, RK37, RK39, RK41
        (rx ** 5) / 1e23, (rx ** 4 * ry) / 1e23, (rx ** 3 * ry ** 2) / 1e23, (rx ** 2 * ry ** 3) / 1e23, (rx * ry ** 4) / 1e23, (ry ** 5) / 1e23,

        # 6차항 - RK43, RK45, RK47, RK49, RK51, RK53, RK55
        (rx ** 6) / 1e27, (rx ** 5 * ry) / 1e27, (rx ** 4 * ry ** 2) / 1e27, (rx ** 3 * ry ** 3) / 1e27, (rx ** 2 * ry ** 4) / 1e27, (rx * ry ** 5) / 1e27, (ry ** 6) / 1e27,

        # 7차항 - RK57, RK59, RK61, RK63, RK65, RK67, RK69, RK71
        (rx ** 7) / 1e31, (rx ** 6 * ry) / 1e31, (rx ** 5 * ry ** 2) / 1e31, (rx ** 4 * ry ** 3) / 1e31, (rx ** 3 * ry ** 4) / 1e31, (rx ** 2 * ry ** 5) / 1e31, (rx * ry ** 6) / 1e31, (ry ** 7) / 1e31
    ]).T

    X_dy = np.vstack([
        # 0차 (상수항) - RK2
        np.ones(len(ry)),

        # 1차항 - RK4, RK6
        ry / 1e6, rx / 1e6,

        # 2차항 - RK8, RK10, RK12
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,

        # 3차항 - RK14, RK16, RK18, RK20
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12, (rx ** 3) / 1e12,

        # 4차항 - RK22, RK24, RK26, RK28, RK30
        (ry ** 4) / 1e19, (ry ** 3 * rx) / 1e19, (ry ** 2 * rx ** 2) / 1e19, (ry * rx ** 3) / 1e19, (rx ** 4) / 1e19,

        # 5차항 - RK32, RK34, RK36, RK38, RK40, RK42
        (ry ** 5) / 1e23, (ry ** 4 * rx) / 1e23, (ry ** 3 * rx ** 2) / 1e23, (ry ** 2 * rx ** 3) / 1e23, (ry * rx ** 4) / 1e23, (rx ** 5) / 1e23,

        # 6차항 - RK44, RK46, RK48, RK50, RK52, RK54, RK56
        (ry ** 6) / 1e27, (ry ** 5 * rx) / 1e27, (ry ** 4 * rx ** 2) / 1e27, (ry ** 3 * rx ** 3) / 1e27, (ry ** 2 * rx ** 4) / 1e27, (ry * rx ** 5) / 1e27, (rx ** 6) / 1e27,

        # 7차항 - RK58, RK60, RK62, RK64, RK66, RK68, RK70, RK72
        (ry ** 7) / 1e31, (ry ** 6 * rx) / 1e31, (ry ** 5 * rx ** 2) / 1e31, (ry ** 4 * rx ** 3) / 1e31, (ry ** 3 * rx ** 4) / 1e31, (ry ** 2 * rx ** 5) / 1e31, (ry * rx ** 6) / 1e31, (rx ** 7) / 1e31
    ]).T

    return X_dx, X_dy



# ----- PSM Fitting용 디자인 행렬 -----


def cpe_k_to_fit(rx, ry):
    """
    PSM input RK값을 Fitting하기 위한 디자인 행렬.
    보정목적이 아니라 해석목적이라서 모든항을 사용.
    """
    X_dx = np.vstack([
        np.ones(len(rx)),
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12,
        (rx ** 4) / 1e19, (rx ** 3 * ry) / 1e19, (rx ** 2 * ry ** 2) / 1e19, (rx * ry ** 3) / 1e19, (ry ** 4) / 1e19,
        (rx ** 5) / 1e23, (rx ** 4 * ry) / 1e23, (rx ** 3 * ry ** 2) / 1e23, (rx ** 2 * ry ** 3) / 1e23, (rx * ry ** 4) / 1e23, (ry ** 5) / 1e23,
        (rx ** 6) / 1e27, (rx ** 5 * ry) / 1e27, (rx ** 4 * ry ** 2) / 1e27, (rx ** 3 * ry ** 3) / 1e27, (rx ** 2 * ry ** 4) / 1e27, (rx * ry ** 5) / 1e27, (ry ** 6) / 1e27,
        (rx ** 7) / 1e31, (rx ** 6 * ry) / 1e31, (rx ** 5 * ry ** 2) / 1e31, (rx ** 4 * ry ** 3) / 1e31, (rx ** 3 * ry ** 4) / 1e31, (rx ** 2 * ry ** 5) / 1e31, (rx * ry ** 6) / 1e31, (ry ** 7) / 1e31
    ]).T

    X_dy = np.vstack([
        np.ones(len(ry)),
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12, (rx ** 3) / 1e12,
        (ry ** 4) / 1e19, (ry ** 3 * rx) / 1e19, (ry ** 2 * rx ** 2) / 1e19, (ry * rx ** 3) / 1e19, (rx ** 4) / 1e19,
        (ry ** 5) / 1e23, (ry ** 4 * rx) / 1e23, (ry ** 3 * rx ** 2) / 1e23, (ry ** 2 * rx ** 3) / 1e23, (ry * rx ** 4) / 1e23, (rx ** 5) / 1e23,
        (ry ** 6) / 1e27, (ry ** 5 * rx) / 1e27, (ry ** 4 * rx ** 2) / 1e27, (ry ** 3 * rx ** 3) / 1e27, (ry ** 2 * rx ** 4) / 1e27, (ry * rx ** 5) / 1e27, (rx ** 6) / 1e27,
        (ry ** 7) / 1e31, (ry ** 6 * rx) / 1e31, (ry ** 5 * rx ** 2) / 1e31, (ry ** 4 * rx ** 3) / 1e31, (ry ** 3 * rx ** 4) / 1e31, (ry ** 2 * rx ** 5) / 1e31, (ry * rx ** 6) / 1e31, (rx ** 7) / 1e31
    ]).T

    return X_dx, X_dy




# ----- 옵션 딕셔너리 구성 -----
# OSR 옵션 통합 정의 (함수 + 계수 키를 한 곳에서 관리)
OSR_OPTIONS = {
    '6para': {
        'func': osr_wk6p_rk6p,
        'coeff_keys': {
            'dx': ['WK1', 'WK3', 'WK5', 'RK3', 'RK5'],
            'dy': ['WK2', 'WK4', 'WK6', 'RK4', 'RK6']
        },
        'description': 'Linear regression: WK 3-parameter + RK 3-parameter'
    },
    '15para': {
        'func': osr_wk20p_rk15p,
        'coeff_keys': {
            'dx': ['WK1', 'WK3', 'WK5', 'WK7', 'WK9', 'WK11', 'WK13', 'WK15', 'WK17', 'WK19',
                   'RK3', 'RK5', 'RK7', 'RK11', 'RK19'],
            'dy': ['WK2', 'WK4', 'WK6', 'WK8', 'WK10', 'WK12', 'WK14', 'WK16', 'WK18', 'WK20',
                   'RK4', 'RK6', 'RK8', 'RK10', 'RK12', 'RK14', 'RK16']
        },
        'description': 'WK 10-parameter + RK 7-parameter'
    },
    '18para': {
        'func': osr_wk20p_rk18p,
        'coeff_keys': {
            'dx': ['WK1', 'WK3', 'WK5', 'WK7', 'WK9', 'WK11', 'WK13', 'WK15', 'WK17', 'WK19',
                   'RK3', 'RK5', 'RK7', 'RK9', 'RK11', 'RK15', 'RK17', 'RK19'],
            'dy': ['WK2', 'WK4', 'WK6', 'WK8', 'WK10', 'WK12', 'WK14', 'WK16', 'WK18', 'WK20',
                   'RK4', 'RK6', 'RK8', 'RK10', 'RK12', 'RK14', 'RK16', 'RK18']
        },
        'description': 'WK 10-parameter + RK 9-parameter'
    },
    '19para': {
        'func': osr_wk20p_rk19p,
        'coeff_keys': {
            'dx': ['WK1', 'WK3', 'WK5', 'WK7', 'WK9', 'WK11', 'WK13', 'WK15', 'WK17', 'WK19',
                   'RK3', 'RK5', 'RK7', 'RK9', 'RK11', 'RK13', 'RK15', 'RK17', 'RK19'],
            'dy': ['WK2', 'WK4', 'WK6', 'WK8', 'WK10', 'WK12', 'WK14', 'WK16', 'WK18', 'WK20',
                   'RK4', 'RK6', 'RK8', 'RK10', 'RK12', 'RK14', 'RK16', 'RK18']
        },
        'description': 'WK 10-parameter + RK 9-parameter (dx with RK13)'
    },
    '20para': {
        'func': osr_wk20p_rk20p,
        'coeff_keys': {
            'dx': ['WK1', 'WK3', 'WK5', 'WK7', 'WK9', 'WK11', 'WK13', 'WK15', 'WK17', 'WK19',
                   'RK3', 'RK5', 'RK7', 'RK9', 'RK11', 'RK13', 'RK15', 'RK17', 'RK19'],
            'dy': ['WK2', 'WK4', 'WK6', 'WK8', 'WK10', 'WK12', 'WK14', 'WK16', 'WK18', 'WK20',
                   'RK4', 'RK6', 'RK8', 'RK10', 'RK12', 'RK14', 'RK16', 'RK18', 'RK20']
        },
        'description': 'Full regression: WK 10-parameter + RK 10-parameter'
    }
}



WK_ONLY_OPTIONS = {
    'wk20': osr_wk20,  
    'wk42': osr_wk42,     # 5차까지   
    'wk72': osr_wk72,     # 7차까지
}



# CPE 옵션 통합 정의 (OSR_OPTIONS와 동일한 구조)
# ⚠️  중요: CPE는 Shot별 개별 보정이므로 RK1, RK2 (Offset) 반드시 포함 필요
#          (OSR과 달리 WK1, WK2가 Offset을 흡수하지 않음)
CPE_OPTIONS = {
    '18para': {
        'func': cpe_18para,
        'coeff_keys': {
            'dx': ['RK1', 'RK3', 'RK5', 'RK7', 'RK9', 'RK11', 'RK15', 'RK17', 'RK19'],  # RK13 제외
            'dy': ['RK2', 'RK4', 'RK6', 'RK8', 'RK10', 'RK12', 'RK14', 'RK16', 'RK18']  # RK20 제외
        },
        'description': 'CPE 18-parameter: Offset + 3rd order RK (RK1~RK19, RK13/RK20 제외) - EUV 권장'
    },
    '15para': {
        'func': cpe_15para,
        'coeff_keys': {
            'dx': ['RK1', 'RK3', 'RK5', 'RK7', 'RK11', 'RK19'],  # RK9, RK15, RK17 제외
            'dy': ['RK2', 'RK4', 'RK6', 'RK8', 'RK10', 'RK12', 'RK14', 'RK16']  # RK18, RK20 제외
        },
        'description': 'CPE 15-parameter: Offset + Partial 3rd order RK (RK9,15,17,18,20 제외) - DUV 권장'
    },
    '6para': {
        'func': cpe_6para,
        'coeff_keys': {
            'dx': ['RK1', 'RK3', 'RK5'],  # offset, x, -y
            'dy': ['RK2', 'RK4', 'RK6']   # offset, y, x
        },
        'description': 'CPE 6-parameter: Offset + Linear RK (RK1~RK6) - Fallback용'
    },
    '2para': {
        'func': cpe_2para,
        'coeff_keys': {
            'dx': ['RK1'],  # offset x
            'dy': ['RK2']   # offset y
        },
        'description': 'CPE 2-parameter: Offset only (RK1, RK2) - 최소 보정'
    },
    '20para': {
        'func': cpe_20para,
        'coeff_keys': {
            'dx': ['RK1', 'RK3', 'RK5', 'RK7', 'RK9', 'RK11', 'RK13', 'RK15', 'RK17', 'RK19'],  # 모든 RK
            'dy': ['RK2', 'RK4', 'RK6', 'RK8', 'RK10', 'RK12', 'RK14', 'RK16', 'RK18', 'RK20']   # 모든 RK
        },
        'description': 'CPE 20-parameter: Full 3rd order RK (RK1~RK20 모든 항 사용)'
    },
    '33para': {
        'func': cpe_33para,
        'coeff_keys': {
            'dx': [
                'RK1',  # 0차
                'RK3', 'RK5',  # 1차
                'RK7', 'RK9', 'RK11',  # 2차
                'RK15', 'RK17', 'RK19',  # 3차 (RK13 제외! - EUV 제어 불가)
                'RK25', 'RK27', 'RK29',  # 4차 (RK21, RK23 제외)
                'RK37', 'RK39', 'RK41',  # 5차 (RK31, RK33, RK35 제외)
                'RK51'  # 6차 (rx^2 * ry^4)
            ],
            'dy': [
                'RK2',  # 0차
                'RK4', 'RK6',  # 1차
                'RK8', 'RK10', 'RK12',  # 2차
                'RK14', 'RK16', 'RK18',  # 3차 (RK20 제외)
                'RK22', 'RK24', 'RK26',  # 4차 (RK28, RK30 제외)
                'RK32', 'RK34', 'RK36',  # 5차 (RK38, RK40, RK42 제외)
                'RK46', 'RK48'  # 6차 (일부)
            ]
        },
        'description': 'CPE 33-parameter: EUV 보정용 (RK13 제외, 4~6차 선택항)'
    },
    '38para': {
        'func': cpe_38para,
        'coeff_keys': {
            'dx': [
                'RK1',  # 0차
                'RK3', 'RK5',  # 1차
                'RK7', 'RK9', 'RK11',  # 2차
                'RK13', 'RK15', 'RK17', 'RK19',  # 3차
                'RK23', 'RK25', 'RK27', 'RK29',  # 4차 (RK21 제외)
                'RK35', 'RK37', 'RK39', 'RK41',  # 5차 (RK31, RK33 제외)
                'RK49', 'RK51',  # 6차 (일부)
                'RK65'  # 7차 (rx^3 * ry^4)
            ],
            'dy': [
                'RK2',  # 0차
                'RK4', 'RK6',  # 1차
                'RK8', 'RK10', 'RK12',  # 2차
                'RK14', 'RK16', 'RK18',  # 3차 (RK20 제외)
                'RK22', 'RK24', 'RK26',  # 4차 (RK28, RK30 제외)
                'RK32', 'RK34', 'RK36',  # 5차 (RK38, RK40, RK42 제외)
                'RK46', 'RK48'  # 6차 (일부)
            ]
        },
        'description': 'CPE 38-parameter: OVO3 보정 (RK1~19 + 고차 선택항)'
    },
    '72para': {
        'func': cpe_72para,
        'coeff_keys': {
            'dx': [
                'RK1',  # 0차
                'RK3', 'RK5',  # 1차
                'RK7', 'RK9', 'RK11',  # 2차
                'RK13', 'RK15', 'RK17', 'RK19',  # 3차
                'RK21', 'RK23', 'RK25', 'RK27', 'RK29',  # 4차
                'RK31', 'RK33', 'RK35', 'RK37', 'RK39', 'RK41',  # 5차
                'RK43', 'RK45', 'RK47', 'RK49', 'RK51', 'RK53', 'RK55',  # 6차
                'RK57', 'RK59', 'RK61', 'RK63', 'RK65', 'RK67', 'RK69', 'RK71'  # 7차
            ],
            'dy': [
                'RK2',  # 0차
                'RK4', 'RK6',  # 1차
                'RK8', 'RK10', 'RK12',  # 2차
                'RK14', 'RK16', 'RK18', 'RK20',  # 3차
                'RK22', 'RK24', 'RK26', 'RK28', 'RK30',  # 4차
                'RK32', 'RK34', 'RK36', 'RK38', 'RK40', 'RK42',  # 5차
                'RK44', 'RK46', 'RK48', 'RK50', 'RK52', 'RK54', 'RK56',  # 6차
                'RK58', 'RK60', 'RK62', 'RK64', 'RK66', 'RK68', 'RK70', 'RK72'  # 7차
            ]
        },
        'description': 'CPE 72-parameter: Hyper 7th order RK (RK1~RK72) - Ridge Regression 전용'
    }
}

CPE_FIT_OPTIONS = {
    '72para': cpe_k_to_fit,    
}


# 최종 선택 딕셔너리
# OSR_OPTIONS, CPE_OPTIONS에서 함수만 추출하여 자동 생성 (하위 호환성 유지)
DESIGN_MATRIX_FUNCTIONS = {
    'osr': {k: v['func'] for k, v in OSR_OPTIONS.items()},
    'wk_only': WK_ONLY_OPTIONS,
    'cpe': {k: v['func'] for k, v in CPE_OPTIONS.items()},  # 🆕 CPE도 통합 구조로 변경
    'cpe_fit': CPE_FIT_OPTIONS,
}


# 계수 키 매핑 (OSR_OPTIONS, CPE_OPTIONS에서 자동 생성)
# 하위 호환성을 위해 OSR은 기존 형태 유지, CPE는 새로 추가
COEFF_KEYS_MAPPING = {k: v['coeff_keys'] for k, v in OSR_OPTIONS.items()}
CPE_COEFF_KEYS_MAPPING = {k: v['coeff_keys'] for k, v in CPE_OPTIONS.items()}  # 🆕 CPE 전용 매핑


