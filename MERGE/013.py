# 13

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# =========================================================
# VBA z1_CPE_01~05 기반 CPE38 Ridge Fitting Python version
# ---------------------------------------------------------
# 핵심 반영 사항
# 1) shot 단위 grouping: LOT_ID, Wafer, fcp_x, fcp_y
# 2) measured matrix와 virtual/eval matrix를 분리
# 3) G-optimality type 지원
#    - OT1: H * H.T diagonal
#    - OT2: X_eval * inv(X_meas.T X_meas + L) * X_meas.T max absolute entry
#    - OT3: X_eval * inv(X_meas.T X_meas + L) * X_eval.T diagonal
#    - OT4: inner는 OT2, partial은 OT1
# 4) ridge가 필요한 경우 fast expand + binary refine로 G-opt spec 근처까지 조정
# 5) span over 발생 시 VBA의 ProjectedCoordinateDescentElasticNet(l1=0)에 해당하는
#    box-constrained coordinate descent로 coefficient를 제한
# 6) point가 적어도 skip하지 않고 ridge를 키워 계산
# =========================================================


# =========================================================
# User configurable constants
# =========================================================
SPAN_MODE = "OVO3_38P_F2F"
RIDGE_REGRESSION = True
G_OPT_SPEC = 1.0
USE_VIRTUAL_CHIP_POINTS = True   # VBA virtual grid: chip별 4 corner + center point
G_OPT_TOLERANCE = 0.001          # VBA: G_opt_tolerlance = 0.001
SPAN_TOLERANCE = 0.01            # VBA: span_tolerlance = 0.01
MINIMUM_RIDGE = 0.001            # VBA: minimum_Ridge = 0.001
ADD_RIDGE = 10.0                 # VBA: add_ridge = 10
MAX_GOPT_RETURN = 50             # VBA: max_prevent_fallback_retrun = 50
MAX_SPAN_ITER = 5000             # VBA: max_iter = 5000
CD_TOL = 1e-6                    # VBA: tol = 0.000001
CPE_EVAL_GRID_N = 10
MIN_POINTS_GUIDE = 10
G_OPTIMAL_TYPE = 1               # VBA information 기준: GOT1
VIRTUAL_WAFER_RADIUS = 144000.0  # VBA virtual point keep 조건: R <= 144000               # VBA option D59: 1,2,3,4. 4 = inner OT2 / partial OT1
USE_SPAN_BOX_CONSTRAINT = True   # VBA Balloon projected CD/PGD stage


# =========================================================
# CPE38 design matrix: OVO3 DUV 38para subset
# 기존 017.py와 같은 coefficient mapping 유지
# =========================================================
def cpe_38para(rx: Sequence[float], ry: Sequence[float]) -> Tuple[np.ndarray, np.ndarray]:
    rx = np.asarray(rx, dtype=float)
    ry = np.asarray(ry, dtype=float)

    X_dx = np.vstack([
        np.ones(len(rx)),
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12,
        (rx ** 3 * ry) / 1e19, (rx ** 2 * ry ** 2) / 1e19, (rx * ry ** 3) / 1e19, (ry ** 4) / 1e19,
        (rx ** 3 * ry ** 2) / 1e23, (rx ** 2 * ry ** 3) / 1e23, (rx * ry ** 4) / 1e23, (ry ** 5) / 1e23,
        (rx ** 3 * ry ** 3) / 1e27, (rx ** 2 * ry ** 4) / 1e27,
        (rx ** 3 * ry ** 4) / 1e31,
    ]).T

    X_dy = np.vstack([
        np.ones(len(ry)),
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12,
        (ry ** 4) / 1e19, (ry ** 3 * rx) / 1e19, (ry ** 2 * rx ** 2) / 1e19,
        (ry ** 5) / 1e23, (ry ** 4 * rx) / 1e23, (ry ** 3 * rx ** 2) / 1e23,
        (ry ** 5 * rx) / 1e27, (ry ** 4 * rx ** 2) / 1e27,
    ]).T

    return X_dx, X_dy


CPE38_KEYS_DX = [
    "RK1", "RK3", "RK5",
    "RK7", "RK9", "RK11",
    "RK13", "RK15", "RK17", "RK19",
    "RK23", "RK25", "RK27", "RK29",
    "RK35", "RK37", "RK39", "RK41",
    "RK49", "RK51",
    "RK65",
]

CPE38_KEYS_DY = [
    "RK2", "RK4", "RK6",
    "RK8", "RK10", "RK12",
    "RK14", "RK16", "RK18",
    "RK22", "RK24", "RK26",
    "RK32", "RK34", "RK36",
    "RK46", "RK48",
]


# =========================================================
# Span limits copied from your previous 017.py
# 값의 의미: coefficient contribution 또는 coefficient 표시값 기준 limit으로 사용 가능.
# 여기서는 기존 Python 코드와 동일하게 coefficient contribution span 기준으로 사용.
# =========================================================
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
    'RK22': {'min': -7.0, 'max': 7.0},
    'RK23': {'min': -2.5, 'max': 2.5},
    'RK24': {'min': -18.0, 'max': 18.0},
    'RK25': {'min': -8.0, 'max': 8.0},
    'RK26': {'min': -4.0, 'max': 4.0},
    'RK27': {'min': -7.0, 'max': 7.0},
    'RK29': {'min': -7.0, 'max': 7.0},
    'RK32': {'min': -2.5, 'max': 2.5},
    'RK34': {'min': -5.0, 'max': 5.0},
    'RK35': {'min': -2.0, 'max': 2.0},
    'RK36': {'min': -1.2, 'max': 1.2},
    'RK37': {'min': -2.5, 'max': 2.5},
    'RK39': {'min': -4.0, 'max': 4.0},
    'RK41': {'min': -2.5, 'max': 2.5},
    'RK46': {'min': -1.2, 'max': 1.2},
    'RK48': {'min': -0.6, 'max': 0.6},
    'RK49': {'min': -0.8, 'max': 0.8},
    'RK51': {'min': -1.2, 'max': 1.2},
    'RK65': {'min': -0.7, 'max': 0.7},
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
    'RK22': {'min': -7.0, 'max': 7.0},
    'RK23': {'min': -2.5, 'max': 2.5},
    'RK24': {'min': -18.0, 'max': 18.0},
    'RK25': {'min': -8.0, 'max': 8.0},
    'RK26': {'min': -4.0, 'max': 4.0},
    'RK27': {'min': -7.0, 'max': 7.0},
    'RK29': {'min': -7.0, 'max': 7.0},
    'RK32': {'min': -2.5, 'max': 2.5},
    'RK34': {'min': -5.0, 'max': 5.0},
    'RK35': {'min': -2.0, 'max': 2.0},
    'RK36': {'min': -1.2, 'max': 1.2},
    'RK37': {'min': -2.5, 'max': 2.5},
    'RK39': {'min': -4.0, 'max': 4.0},
    'RK41': {'min': -2.5, 'max': 2.5},
    'RK46': {'min': -1.2, 'max': 1.2},
    'RK48': {'min': -0.6, 'max': 0.6},
    'RK49': {'min': -0.8, 'max': 0.8},
    'RK51': {'min': -1.2, 'max': 1.2},
    'RK65': {'min': -0.7, 'max': 0.7},
}


def get_active_span_limits(span_mode: str = "OVO3_38P_F2F") -> Dict[str, Dict[str, float]]:
    if span_mode == "OVO3_38P_HARDLIMIT":
        return RK_SPAN_LIMITS_OVO3_38P_HARDLIMIT
    return RK_SPAN_LIMITS_OVO3_38P_F2F


# =========================================================
# Utilities
# =========================================================
def _to_numeric(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def choose_base_lambda_scale(n_points: int) -> float:
    """VBA의 point가 적어도 skip하지 않는 방식을 Python식으로 반영."""
    if n_points >= 10:
        return 1.0
    if n_points >= 7:
        return 1e2
    if n_points >= 5:
        return 1e4
    if n_points >= 3:
        return 1e6
    return 1e8


# =========================================================
# Ridge valve: VBA RV(hyper)
# ---------------------------------------------------------
# RK1/RK2는 0이므로 translation 성분에는 ridge penalty를 주지 않는다.
# RK21 이후는 모두 1로 처리한다.
# =========================================================
RIDGE_VALVE_HYPER = {
    "RK1": 0.0, "RK2": 0.0,
    "RK3": 0.01, "RK4": 0.01, "RK5": 0.01, "RK6": 0.01,
    "RK7": 1.0, "RK8": 0.1, "RK9": 1.0, "RK10": 0.1,
    "RK11": 0.1, "RK12": 1.0,
    "RK13": 1.0, "RK14": 0.1, "RK15": 1.0, "RK16": 0.1,
    "RK17": 1.0, "RK18": 1.0, "RK19": 0.1, "RK20": 1.0,
}


def get_ridge_valves(coeff_names: Sequence[str]) -> np.ndarray:
    return np.array([RIDGE_VALVE_HYPER.get(name, 1.0) for name in coeff_names], dtype=float)


def make_lambda_vector(base_lambda: float, coeff_names: Sequence[str]) -> np.ndarray:
    valves = get_ridge_valves(coeff_names)
    return float(base_lambda) * valves


def build_virtual_chip_points(
    step_pitch_x: float,
    step_pitch_y: float,
    chip_x_num: int,
    chip_y_num: int,
    round_decimals: int = 6,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    VBA virtual grid 재현:
    chip별 4 corner + center point를 shot-local coordinate로 생성하고,
    chip 경계에서 겹치는 corner는 dedup한다.

    예: chip_x_num=2, chip_y_num=1
      - 각 chip 5 point => 10 raw points
      - 가운데 공유 corner 2개 중복 제거
      - 최종 8 virtual points

    coordinate_X/Y가 shot center 기준이라고 보고,
    전체 shot 영역은 [-STEP_PITCH_X/2, +STEP_PITCH_X/2],
                  [-STEP_PITCH_Y/2, +STEP_PITCH_Y/2] 로 둔다.
    """
    chip_x_num = int(chip_x_num) if pd.notna(chip_x_num) and int(chip_x_num) > 0 else 1
    chip_y_num = int(chip_y_num) if pd.notna(chip_y_num) and int(chip_y_num) > 0 else 1

    sx = float(step_pitch_x)
    sy = float(step_pitch_y)

    x_edges = np.linspace(-sx / 2.0, sx / 2.0, chip_x_num + 1)
    y_edges = np.linspace(-sy / 2.0, sy / 2.0, chip_y_num + 1)

    pts = []
    for ix in range(chip_x_num):
        for iy in range(chip_y_num):
            x0, x1 = x_edges[ix], x_edges[ix + 1]
            y0, y1 = y_edges[iy], y_edges[iy + 1]
            xc = (x0 + x1) / 2.0
            yc = (y0 + y1) / 2.0

            pts.extend([
                (x0, y0), (x0, y1), (x1, y0), (x1, y1),
                (xc, yc),
            ])

    pts_unique = sorted({(round(x, round_decimals), round(y, round_decimals)) for x, y in pts})
    rx = np.array([p[0] for p in pts_unique], dtype=float)
    ry = np.array([p[1] for p in pts_unique], dtype=float)
    return rx, ry


def filter_virtual_points_by_wafer_radius(
    rx_v: Sequence[float],
    ry_v: Sequence[float],
    fcp_x: float,
    fcp_y: float,
    wafer_radius: float = VIRTUAL_WAFER_RADIUS,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    VBA edge-shot virtual point filtering.
    virtual point의 wafer 좌표 R이 wafer_radius 이하인 point만 사용한다.

    R = sqrt((fcp_x + rx_v)^2 + (fcp_y + ry_v)^2)
    keep if R <= 144000
    """
    rx_v = np.asarray(rx_v, dtype=float)
    ry_v = np.asarray(ry_v, dtype=float)
    wx = float(fcp_x) + rx_v
    wy = float(fcp_y) + ry_v
    r = np.sqrt(wx * wx + wy * wy)
    keep = r <= float(wafer_radius)
    return rx_v[keep], ry_v[keep], r[keep]


def get_virtual_points_for_group(
    grp: pd.DataFrame,
    fallback_rx: Sequence[float],
    fallback_ry: Sequence[float],
    fcp_x: float,
    fcp_y: float,
    wafer_radius: float = VIRTUAL_WAFER_RADIUS,
) -> Tuple[np.ndarray, np.ndarray, str, int, int]:
    """
    1) full virtual point 생성: chip별 4 corner + center
    2) edge shot 처리: wafer 좌표 R <= wafer_radius point만 keep

    반환:
      rx_v, ry_v, virtual_source, n_virtual_full, n_virtual_kept
    """
    required = ["STEP_PITCH_X", "STEP_PITCH_Y", "CHIP_X_NUM", "CHIP_Y_NUM"]
    if all(c in grp.columns for c in required):
        vals = grp[required].dropna()
        if len(vals) > 0:
            row = vals.iloc[0]
            rx_full, ry_full = build_virtual_chip_points(
                step_pitch_x=row["STEP_PITCH_X"],
                step_pitch_y=row["STEP_PITCH_Y"],
                chip_x_num=row["CHIP_X_NUM"],
                chip_y_num=row["CHIP_Y_NUM"],
            )
            n_full = len(rx_full)
            rx_keep, ry_keep, _ = filter_virtual_points_by_wafer_radius(
                rx_full,
                ry_full,
                fcp_x=fcp_x,
                fcp_y=fcp_y,
                wafer_radius=wafer_radius,
            )

            # 극단 edge에서 virtual point가 너무 적으면 inverse가 과도하게 불안정해질 수 있으므로
            # 빈 배열만 fallback. 일반적으로 VBA도 dummy shot은 제거하지만, 여기서는 안전장치만 둔다.
            if len(rx_keep) > 0:
                src = "chip_corner_center_wafer_clipped"
                return rx_keep, ry_keep, src, n_full, len(rx_keep)

            return rx_full, ry_full, "chip_corner_center_no_clip_points_fallback", n_full, n_full

    rx_v, ry_v = build_eval_grid_from_data(fallback_rx, fallback_ry, grid_n=CPE_EVAL_GRID_N)
    return rx_v, ry_v, "measured_range_grid_fallback", len(rx_v), len(rx_v)


def stable_inverse_or_pinv(A: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.inv(A)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(A)


def ridge_predict(X: np.ndarray, y: np.ndarray, lambdas: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    lambdas = np.asarray(lambdas, dtype=float)
    A = X.T @ X + np.diag(lambdas)
    b = X.T @ y
    try:
        beta = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        beta = np.linalg.pinv(A) @ b
    return beta, X @ beta


def build_eval_grid_from_data(rx: Sequence[float], ry: Sequence[float], grid_n: int = 10) -> Tuple[np.ndarray, np.ndarray]:
    rx = np.asarray(rx, dtype=float)
    ry = np.asarray(ry, dtype=float)

    rx_min, rx_max = np.nanmin(rx), np.nanmax(rx)
    ry_min, ry_max = np.nanmin(ry), np.nanmax(ry)

    if not np.isfinite(rx_min) or not np.isfinite(rx_max):
        rx_min, rx_max = -1.0, 1.0
    if not np.isfinite(ry_min) or not np.isfinite(ry_max):
        ry_min, ry_max = -1.0, 1.0

    if rx_min == rx_max:
        rx_min -= 1.0
        rx_max += 1.0
    if ry_min == ry_max:
        ry_min -= 1.0
        ry_max += 1.0

    gx = np.linspace(rx_min, rx_max, grid_n)
    gy = np.linspace(ry_min, ry_max, grid_n)
    RX, RY = np.meshgrid(gx, gy)
    return RX.ravel(), RY.ravel()


def gopt_value(
    X_meas: np.ndarray,
    X_eval: np.ndarray,
    lambdas: np.ndarray,
    gopt_type: int = 4,
    inner_or_partial: str = "partial",
) -> float:
    """
    VBA G_optimal_type 반영.
    - Type1: H H.T diag의 sqrt(max)
    - Type2: H matrix element의 max abs. VBA는 raw max를 쓰지만 안정성을 위해 abs 사용.
    - Type3: X_eval inv(...) X_eval.T diag의 sqrt(max)
    - Type4: inner=Type2, partial=Type1
    """
    X_meas = np.asarray(X_meas, dtype=float)
    X_eval = np.asarray(X_eval, dtype=float)
    lambdas = np.asarray(lambdas, dtype=float)

    A = X_meas.T @ X_meas + np.diag(lambdas)
    invA = stable_inverse_or_pinv(A)

    effective_type = gopt_type
    if gopt_type == 4:
        effective_type = 2 if inner_or_partial == "inner" else 1

    if effective_type == 1:
        H = X_eval @ invA @ X_meas.T
        # diag(H H.T) = row-wise sum of H^2
        diag_val = np.sum(H * H, axis=1)
        max_val = np.nanmax(diag_val)
        return float(np.sqrt(max(max_val, 0.0)))

    if effective_type == 2:
        H = X_eval @ invA @ X_meas.T
        # VBA Type2는 hat_matrix(row, col)의 최대값을 찾은 뒤 sqrt 처리한다.
        # abs(max)가 아니라 signed max를 사용한다는 점이 중요하다.
        max_val = float(np.nanmax(H))
        if max_val < 0:
            return 999.0
        return float(np.sqrt(max_val))

    if effective_type == 3:
        M = X_eval @ invA @ X_eval.T
        diag_val = np.diag(M)
        max_val = np.nanmax(diag_val)
        return float(np.sqrt(max(max_val, 0.0)))

    raise ValueError(f"Unsupported gopt_type: {gopt_type}")


def calc_contribution_spans(X_eval: np.ndarray, beta: np.ndarray, coeff_names: Sequence[str]) -> Dict[str, float]:
    spans = {}
    for i, name in enumerate(coeff_names):
        contrib = X_eval[:, i] * beta[i]
        spans[name] = float(np.nanmax(contrib) - np.nanmin(contrib))
    return spans


def find_span_violations(
    spans: Dict[str, float],
    span_limits: Dict[str, Dict[str, float]],
    tolerance: float = 0.01,
) -> List[Tuple[str, float, float, float]]:
    violations = []
    for name, span in spans.items():
        if name not in span_limits:
            continue
        lo = span_limits[name]["min"] - tolerance
        hi = span_limits[name]["max"] + tolerance
        # span은 non-negative이므로 실제로는 max 초과를 주로 감지.
        if span < lo or span > hi:
            violations.append((name, span, span_limits[name]["min"], span_limits[name]["max"]))
    return violations


def build_beta_bounds_from_span(
    X_eval: np.ndarray,
    coeff_names: Sequence[str],
    span_limits: Dict[str, Dict[str, float]],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    VBA의 min_Span_X/Y, max_Span_X/Y에 대응하는 box constraint 근사.
    contribution span = range(X_j * beta_j)가 span_limit 안에 들어오도록
    beta_j bound를 계산한다.
    """
    n = len(coeff_names)
    lo = np.full(n, -np.inf, dtype=float)
    hi = np.full(n, np.inf, dtype=float)

    for j, name in enumerate(coeff_names):
        if name not in span_limits:
            continue
        lim = span_limits[name]
        span_abs = max(abs(float(lim["min"])), abs(float(lim["max"])))
        xj_range = float(np.nanmax(X_eval[:, j]) - np.nanmin(X_eval[:, j]))
        if xj_range <= 0 or not np.isfinite(xj_range):
            continue
        b = span_abs / xj_range
        lo[j] = -b
        hi[j] = b
    return lo, hi


def projected_coordinate_descent_ridge(
    X: np.ndarray,
    y: np.ndarray,
    lambdas: np.ndarray,
    beta_init: Optional[np.ndarray] = None,
    lower: Optional[np.ndarray] = None,
    upper: Optional[np.ndarray] = None,
    tol: float = 1e-6,
    max_iter: int = 5000,
) -> Tuple[np.ndarray, np.ndarray, int, float]:
    """
    VBA ProjectedCoordinateDescentElasticNet(l1=0) 근사.
    solve min ||y-Xb||^2 + sum(lambda_j*b_j^2), s.t. lower <= b <= upper
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    lambdas = np.asarray(lambdas, dtype=float)
    n_param = X.shape[1]

    if beta_init is None:
        beta, _ = ridge_predict(X, y, lambdas)
    else:
        beta = np.asarray(beta_init, dtype=float).copy()

    if lower is None:
        lower = np.full(n_param, -np.inf)
    if upper is None:
        upper = np.full(n_param, np.inf)

    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    beta = np.clip(beta, lower, upper)

    # residual = y - X beta
    residual = y - X @ beta
    col_norm2 = np.sum(X * X, axis=0)

    last_delta = np.inf
    for it in range(1, max_iter + 1):
        max_delta = 0.0
        for j in range(n_param):
            denom = col_norm2[j] + lambdas[j]
            if denom <= 0 or not np.isfinite(denom):
                continue

            # add old contribution back
            residual += X[:, j] * beta[j]
            rho = float(X[:, j] @ residual)
            new_beta = rho / denom
            new_beta = min(max(new_beta, lower[j]), upper[j])

            delta = abs(new_beta - beta[j])
            beta[j] = new_beta
            residual -= X[:, j] * beta[j]
            if delta > max_delta:
                max_delta = delta

        last_delta = max_delta
        if max_delta < tol:
            break

    return beta, X @ beta, it, float(last_delta)


@dataclass
class RidgeFitResult:
    beta: np.ndarray
    pred: np.ndarray
    lambdas: np.ndarray
    gopt: float
    spans: Dict[str, float]
    violations: List[Tuple[str, float, float, float]]
    gopt_iter: int
    span_iter: int
    method: str


def solve_vba_style_ridge_one_axis(
    X_fit: np.ndarray,
    y: np.ndarray,
    X_eval: np.ndarray,
    coeff_names: Sequence[str],
    span_limits: Dict[str, Dict[str, float]],
    ridge_regression: bool = True,
    gopt_spec: float = 1.0,
    gopt_tolerance: float = 0.001,
    minimum_ridge: float = 0.001,
    add_ridge: float = 10.0,
    max_gopt_return: int = 50,
    gopt_type: int = 4,
    inner_or_partial: str = "partial",
    use_span_box_constraint: bool = True,
    span_tolerance: float = 0.01,
    cd_tol: float = 1e-6,
    max_span_iter: int = 5000,
    base_lambda_scale: float = 1.0,
    debug: bool = False,
) -> RidgeFitResult:
    """
    VBA flow에 맞춘 한 방향(X or Y) fitting.
    - 초기 ridge는 0에 가까운 값이 아니라 VBA minimum_Ridge 기준 사용
    - Gopt가 spec 이상이면 ridge를 빠르게 키운 뒤 이분탐색으로 spec 근처를 찾음
    - span over가 남으면 projected coordinate descent로 coefficient를 box constraint 안에 넣음
    """
    X_fit = np.asarray(X_fit, dtype=float)
    X_eval = np.asarray(X_eval, dtype=float)
    y = np.asarray(y, dtype=float)
    n_param = X_fit.shape[1]

    if n_param != len(coeff_names):
        raise ValueError(f"n_param({n_param}) != len(coeff_names)({len(coeff_names)})")

    # VBA에서 ramda_ridge=0으로 시작하더라도 Ridge_regression True일 때 Gopt 제어 단계에서 ridge를 올림.
    initial_lambda = 0.0 if not ridge_regression else 0.0
    lambdas = make_lambda_vector(initial_lambda, coeff_names)

    beta, pred = ridge_predict(X_fit, y, lambdas)
    g = gopt_value(X_fit, X_eval, lambdas, gopt_type=gopt_type, inner_or_partial=inner_or_partial)

    gopt_iter = 0
    method = "ols"

    if ridge_regression and (not np.isfinite(g) or g >= gopt_spec or g == 0):
        # fast ridge up: VBA ridge_up_Gopt_fast에 해당
        low_lambda = 0.0
        high_lambda = max(minimum_ridge * base_lambda_scale, minimum_ridge)
        high_lambda = max(high_lambda, minimum_ridge)
        high_lambdas = make_lambda_vector(high_lambda, coeff_names)
        high_g = gopt_value(X_fit, X_eval, high_lambdas, gopt_type=gopt_type, inner_or_partial=inner_or_partial)

        while (not np.isfinite(high_g) or high_g >= gopt_spec) and gopt_iter < max_gopt_return:
            low_lambda = high_lambda
            high_lambda = high_lambda * add_ridge
            high_lambdas = make_lambda_vector(high_lambda, coeff_names)
            high_g = gopt_value(X_fit, X_eval, high_lambdas, gopt_type=gopt_type, inner_or_partial=inner_or_partial)
            gopt_iter += 1
            if debug:
                print(f"fast ridge: lambda={high_lambda:.6g}, gopt={high_g:.6g}")

        # slow refine: VBA ridge_up_Gopt_slow에 해당
        target_low = max(0.0, gopt_spec - gopt_tolerance)
        target_high = gopt_spec
        best_lambda = high_lambda
        best_g = high_g

        # high가 spec 아래로 내려간 경우에만 bracket refine
        if np.isfinite(high_g) and high_g < gopt_spec:
            lo = low_lambda
            hi = high_lambda
            for _ in range(max_gopt_return):
                mid = (lo + hi) / 2.0
                mid_lambdas = make_lambda_vector(mid, coeff_names)
                mid_g = gopt_value(X_fit, X_eval, mid_lambdas, gopt_type=gopt_type, inner_or_partial=inner_or_partial)
                gopt_iter += 1

                if debug:
                    print(f"slow ridge: lambda={mid:.6g}, gopt={mid_g:.6g}")

                if target_low <= mid_g < target_high:
                    best_lambda = mid
                    best_g = mid_g
                    break

                # lambda 증가 -> gopt 감소하는 방향
                if mid_g >= gopt_spec or not np.isfinite(mid_g):
                    lo = mid
                else:
                    hi = mid
                    best_lambda = mid
                    best_g = mid_g

                # VBA의 소수점 3자리 ridge refine 종료 감각 반영
                if abs(hi - lo) < max(minimum_ridge * 1e-3, 1e-12):
                    break

        lambdas = make_lambda_vector(best_lambda, coeff_names)
        beta, pred = ridge_predict(X_fit, y, lambdas)
        g = gopt_value(X_fit, X_eval, lambdas, gopt_type=gopt_type, inner_or_partial=inner_or_partial)
        method = "ridge_gopt"

    spans = calc_contribution_spans(X_eval, beta, coeff_names)
    violations = find_span_violations(spans, span_limits, tolerance=span_tolerance)
    span_iter = 0

    if ridge_regression and use_span_box_constraint and len(violations) > 0:
        lower, upper = build_beta_bounds_from_span(X_eval, coeff_names, span_limits)
        beta_cd, pred_cd, span_iter, _ = projected_coordinate_descent_ridge(
            X_fit,
            y,
            lambdas,
            beta_init=beta,
            lower=lower,
            upper=upper,
            tol=cd_tol,
            max_iter=max_span_iter,
        )
        beta = beta_cd
        pred = pred_cd
        spans = calc_contribution_spans(X_eval, beta, coeff_names)
        violations = find_span_violations(spans, span_limits, tolerance=span_tolerance)
        g = gopt_value(X_fit, X_eval, lambdas, gopt_type=gopt_type, inner_or_partial=inner_or_partial)
        method = "ridge_gopt_box_cd"

    return RidgeFitResult(
        beta=beta,
        pred=pred,
        lambdas=lambdas,
        gopt=float(g),
        spans=spans,
        violations=violations,
        gopt_iter=int(gopt_iter),
        span_iter=int(span_iter),
        method=method,
    )


def determine_inner_or_partial(n_valid: int, n_virtual: int) -> str:
    """VBA: virtual_points = Vgrid_XY면 inner, 아니면 partial."""
    return "inner" if n_valid >= n_virtual else "partial"


def run_cpe38_vba_style_shotwise(
    df: pd.DataFrame,
    label: str = "ADI",
    wafer_cols: Tuple[str, str] = ("LOT_ID", "Wafer"),
    shot_center_cols: Tuple[str, str] = ("fcp_x", "fcp_y"),
    residual_cols: Tuple[str, str] = ("raw_minus_total_fit_x", "raw_minus_total_fit_y"),
    shot_cols: Tuple[str, str] = ("coordinate_X", "coordinate_Y"),
    span_mode: str = SPAN_MODE,
    min_points_guide: int = MIN_POINTS_GUIDE,
    eval_grid_n: int = CPE_EVAL_GRID_N,
    ridge_regression: bool = RIDGE_REGRESSION,
    gopt_spec: float = G_OPT_SPEC,
    gopt_tolerance: float = G_OPT_TOLERANCE,
    gopt_type: int = G_OPTIMAL_TYPE,
    use_span_box_constraint: bool = USE_SPAN_BOX_CONSTRAINT,
    debug: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    기존 018.py의 run_cpe38_ridge_shotwise_after_wkrk 대체 함수.

    Required input columns:
      LOT_ID, Wafer, fcp_x, fcp_y,
      raw_minus_total_fit_x, raw_minus_total_fit_y,
      coordinate_X, coordinate_Y
    """
    df = df.copy()

    required = list(wafer_cols) + list(shot_center_cols) + list(residual_cols) + list(shot_cols)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"[{label}] 필수 컬럼 누락: {missing}")

    _to_numeric(df, list(shot_center_cols) + list(residual_cols) + list(shot_cols))

    out_cols = [
        "CPE_fit_x", "CPE_fit_y",
        "real_residual_x", "real_residual_y",
        "CPE_gopt_x", "CPE_gopt_y",
        "CPE_lambda_max_x", "CPE_lambda_max_y",
        "CPE_method_x", "CPE_method_y",
        "CPE_inner_or_partial",
    ]
    for c in out_cols:
        df[c] = np.nan if not c.startswith("CPE_method") and c != "CPE_inner_or_partial" else None

    span_limits = get_active_span_limits(span_mode)
    coef_rows = []
    summary_rows = []

    group_keys = list(wafer_cols) + list(shot_center_cols)

    for gkey, grp in df.groupby(group_keys, dropna=False):
        valid_mask = (
            grp[residual_cols[0]].notna() &
            grp[residual_cols[1]].notna() &
            grp[shot_cols[0]].notna() &
            grp[shot_cols[1]].notna()
        )
        work = grp.loc[valid_mask].copy()
        n_valid = len(work)

        lot_id = gkey[0]
        wafer = gkey[1]
        fcp_x = gkey[2]
        fcp_y = gkey[3]

        if n_valid == 0:
            summary_rows.append({
                "LOT_ID": lot_id,
                "Wafer": wafer,
                "fcp_x": fcp_x,
                "fcp_y": fcp_y,
                "n_total": len(grp),
                "n_valid": 0,
                "few_points_flag": True,
                "status": "no_valid_points",
            })
            continue

        rx = work[shot_cols[0]].to_numpy(dtype=float)
        ry = work[shot_cols[1]].to_numpy(dtype=float)
        residual_x = work[residual_cols[0]].to_numpy(dtype=float)
        residual_y = work[residual_cols[1]].to_numpy(dtype=float)

        X_dx, X_dy = cpe_38para(rx, ry)

        # VBA virtual shot matrix:
        # chip별 4 corner + center point를 사용한다.
        if USE_VIRTUAL_CHIP_POINTS:
            grid_rx, grid_ry, virtual_source, n_virtual_full, n_virtual = get_virtual_points_for_group(
                work,
                rx,
                ry,
                fcp_x=fcp_x,
                fcp_y=fcp_y,
                wafer_radius=VIRTUAL_WAFER_RADIUS,
            )
        else:
            grid_rx, grid_ry = build_eval_grid_from_data(rx, ry, grid_n=eval_grid_n)
            virtual_source = "measured_range_grid"
            n_virtual_full = len(grid_rx)
            n_virtual = len(grid_rx)

        X_eval_dx, X_eval_dy = cpe_38para(grid_rx, grid_ry)
        inner_or_partial = determine_inner_or_partial(n_valid=n_valid, n_virtual=n_virtual)

        few_points_flag = n_valid < min_points_guide
        base_lambda_scale = choose_base_lambda_scale(n_valid)

        fit_x = solve_vba_style_ridge_one_axis(
            X_fit=X_dx,
            y=residual_x,
            X_eval=X_eval_dx,
            coeff_names=CPE38_KEYS_DX,
            span_limits=span_limits,
            ridge_regression=ridge_regression,
            gopt_spec=gopt_spec,
            gopt_tolerance=gopt_tolerance,
            minimum_ridge=MINIMUM_RIDGE,
            add_ridge=ADD_RIDGE,
            max_gopt_return=MAX_GOPT_RETURN,
            gopt_type=gopt_type,
            inner_or_partial=inner_or_partial,
            use_span_box_constraint=use_span_box_constraint,
            span_tolerance=SPAN_TOLERANCE,
            cd_tol=CD_TOL,
            max_span_iter=MAX_SPAN_ITER,
            base_lambda_scale=base_lambda_scale,
            debug=debug,
        )

        fit_y = solve_vba_style_ridge_one_axis(
            X_fit=X_dy,
            y=residual_y,
            X_eval=X_eval_dy,
            coeff_names=CPE38_KEYS_DY,
            span_limits=span_limits,
            ridge_regression=ridge_regression,
            gopt_spec=gopt_spec,
            gopt_tolerance=gopt_tolerance,
            minimum_ridge=MINIMUM_RIDGE,
            add_ridge=ADD_RIDGE,
            max_gopt_return=MAX_GOPT_RETURN,
            gopt_type=gopt_type,
            inner_or_partial=inner_or_partial,
            use_span_box_constraint=use_span_box_constraint,
            span_tolerance=SPAN_TOLERANCE,
            cd_tol=CD_TOL,
            max_span_iter=MAX_SPAN_ITER,
            base_lambda_scale=base_lambda_scale,
            debug=debug,
        )

        cpe_fit_x = fit_x.pred
        cpe_fit_y = fit_y.pred
        real_residual_x = residual_x - cpe_fit_x
        real_residual_y = residual_y - cpe_fit_y

        valid_idx = work.index
        df.loc[valid_idx, "CPE_fit_x"] = cpe_fit_x
        df.loc[valid_idx, "CPE_fit_y"] = cpe_fit_y
        df.loc[valid_idx, "real_residual_x"] = real_residual_x
        df.loc[valid_idx, "real_residual_y"] = real_residual_y
        df.loc[valid_idx, "CPE_gopt_x"] = fit_x.gopt
        df.loc[valid_idx, "CPE_gopt_y"] = fit_y.gopt
        df.loc[valid_idx, "CPE_lambda_max_x"] = float(np.nanmax(fit_x.lambdas))
        df.loc[valid_idx, "CPE_lambda_max_y"] = float(np.nanmax(fit_y.lambdas))
        df.loc[valid_idx, "CPE_method_x"] = fit_x.method
        df.loc[valid_idx, "CPE_method_y"] = fit_y.method
        df.loc[valid_idx, "CPE_inner_or_partial"] = inner_or_partial

        coef_row = {
            "LOT_ID": lot_id,
            "Wafer": wafer,
            "fcp_x": fcp_x,
            "fcp_y": fcp_y,
            "n_total": len(grp),
            "n_valid": n_valid,
            "n_virtual": n_virtual,
            "n_virtual_full": n_virtual_full,
            "virtual_source": virtual_source,
            "inner_or_partial": inner_or_partial,
            "few_points_flag": few_points_flag,
            "base_lambda_scale": base_lambda_scale,
            "gopt_x": fit_x.gopt,
            "gopt_y": fit_y.gopt,
            "lambda_max_x": float(np.nanmax(fit_x.lambdas)),
            "lambda_max_y": float(np.nanmax(fit_y.lambdas)),
            "gopt_iter_x": fit_x.gopt_iter,
            "gopt_iter_y": fit_y.gopt_iter,
            "span_iter_x": fit_x.span_iter,
            "span_iter_y": fit_y.span_iter,
            "span_violation_count_x": len(fit_x.violations),
            "span_violation_count_y": len(fit_y.violations),
            "method_x": fit_x.method,
            "method_y": fit_y.method,
        }
        for name, val in zip(CPE38_KEYS_DX, fit_x.beta):
            coef_row[f"{name}_X"] = val
            coef_row[f"span_{name}_X"] = fit_x.spans.get(name, np.nan)
        for name, val in zip(CPE38_KEYS_DY, fit_y.beta):
            coef_row[f"{name}_Y"] = val
            coef_row[f"span_{name}_Y"] = fit_y.spans.get(name, np.nan)
        coef_rows.append(coef_row)

        summary_rows.append({
            "LOT_ID": lot_id,
            "Wafer": wafer,
            "fcp_x": fcp_x,
            "fcp_y": fcp_y,
            "n_total": len(grp),
            "n_valid": n_valid,
            "n_virtual": n_virtual,
            "n_virtual_full": n_virtual_full,
            "virtual_source": virtual_source,
            "inner_or_partial": inner_or_partial,
            "metro_ratio": n_valid / max(n_virtual, 1),
            "few_points_flag": few_points_flag,
            "base_lambda_scale": base_lambda_scale,
            "gopt_x": fit_x.gopt,
            "gopt_y": fit_y.gopt,
            "lambda_max_x": float(np.nanmax(fit_x.lambdas)),
            "lambda_max_y": float(np.nanmax(fit_y.lambdas)),
            "gopt_iter_x": fit_x.gopt_iter,
            "gopt_iter_y": fit_y.gopt_iter,
            "span_iter_x": fit_x.span_iter,
            "span_iter_y": fit_y.span_iter,
            "span_violation_count_x": len(fit_x.violations),
            "span_violation_count_y": len(fit_y.violations),
            "rms_before_x": float(np.sqrt(np.nanmean(residual_x ** 2))),
            "rms_before_y": float(np.sqrt(np.nanmean(residual_y ** 2))),
            "rms_after_x": float(np.sqrt(np.nanmean(real_residual_x ** 2))),
            "rms_after_y": float(np.sqrt(np.nanmean(real_residual_y ** 2))),
            "method_x": fit_x.method,
            "method_y": fit_y.method,
            "status": "ok",
        })

    coef_df = pd.DataFrame(coef_rows)
    summary_df = pd.DataFrame(summary_rows)

    print(f"[{label}] VBA-style CPE38 ridge 완료")
    print(f"  shot groups: {len(summary_df)}")
    print(f"  coef rows: {len(coef_df)}")
    if "few_points_flag" in summary_df.columns:
        print(f"  few points shots: {int(summary_df['few_points_flag'].sum())}")
    if "span_violation_count_x" in summary_df.columns:
        print(f"  remaining span violations X/Y: "
              f"{int(summary_df['span_violation_count_x'].sum())}/"
              f"{int(summary_df['span_violation_count_y'].sum())}")

    return df, coef_df, summary_df


# =========================================================
# Example execution: 기존 016.py output을 입력으로 사용
# =========================================================
if __name__ == "__main__":
    df_adi = df_adi_reg.copy()
    df_oco = df_oco_reg.copy()


    df_adi_cpe, coef_adi_cpe, summary_adi_cpe = run_cpe38_vba_style_shotwise(
        df_adi,
        label="ADI",
        wafer_cols=("LOT_ID", "Wafer"),
        shot_center_cols=("fcp_x", "fcp_y"),
        residual_cols=("raw_minus_total_fit_x", "raw_minus_total_fit_y"),
        shot_cols=("coordinate_X", "coordinate_Y"),
        span_mode=SPAN_MODE,
        min_points_guide=MIN_POINTS_GUIDE,
        eval_grid_n=CPE_EVAL_GRID_N,
        ridge_regression=RIDGE_REGRESSION,
        gopt_spec=G_OPT_SPEC,
        gopt_tolerance=G_OPT_TOLERANCE,
        gopt_type=G_OPTIMAL_TYPE,
        use_span_box_constraint=USE_SPAN_BOX_CONSTRAINT,
        debug=False,
    )

    df_oco_cpe, coef_oco_cpe, summary_oco_cpe = run_cpe38_vba_style_shotwise(
        df_oco,
        label="OCO",
        wafer_cols=("LOT_ID", "Wafer"),
        shot_center_cols=("fcp_x", "fcp_y"),
        residual_cols=("raw_minus_total_fit_x", "raw_minus_total_fit_y"),
        shot_cols=("coordinate_X", "coordinate_Y"),
        span_mode=SPAN_MODE,
        min_points_guide=MIN_POINTS_GUIDE,
        eval_grid_n=CPE_EVAL_GRID_N,
        ridge_regression=RIDGE_REGRESSION,
        gopt_spec=G_OPT_SPEC,
        gopt_tolerance=G_OPT_TOLERANCE,
        gopt_type=G_OPTIMAL_TYPE,
        use_span_box_constraint=USE_SPAN_BOX_CONSTRAINT,
        debug=False,
    )
    '''
    with pd.ExcelWriter(
        "OCO.xlsx",
        engine="xlsxwriter",
        engine_kwargs={"options": {"use_zip64": True}}
    ) as writer:
        df_oco_cpe.to_excel(writer, sheet_name="Sheet1", index=False)

    with pd.ExcelWriter(
        "ADI.xlsx",
        engine="xlsxwriter",
        engine_kwargs={"options": {"use_zip64": True}}
    ) as writer:
        df_adi_cpe.to_excel(writer, sheet_name="Sheet1", index=False)
    '''

    df_adi_cpe.to_parquet("ADI.parquet", index=False)
    df_oco_cpe.to_parquet("OCO.parquet", index=False)

    coef_adi_cpe.to_excel("coef_adi_cpe38.xlsx", index=False)
    coef_oco_cpe.to_excel("coef_oco_cpe38.xlsx", index=False)

    #summary_adi_cpe.to_excel("summary_adi_cpe38_vba_style_ridge_shotwise.xlsx", index=False)
    #summary_oco_cpe.to_excel("summary_oco_cpe38_vba_style_ridge_shotwise.xlsx", index=False)

    print("저장 완료")
