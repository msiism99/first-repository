# -*- coding: utf-8 -*-
"""
PSM 적용 시뮬레이션 최종 통합본
- Input:
    OCO.parquet
    ADI.parquet

- Main idea:
    1) 현재 wafer 기준 직전 LOT 5개를 history로 사용
    2) history LOT 5개 전체 wafer에서 TEST별 FPT 계산
       - OCO / ADI는 TEST 체계가 다르므로 각각 별도 계산
    3) CPE33 Y fitting target에서 TEST FPT 제거
    4) CPE33 Y-only G_OPT ridge fitting
       - lambda는 wafer 고정이 아니라 shot별 자동 결정
       - MERGE/013.py의 G_OPT ridge flow를 CPE33 Y에 이식
    5) M1 / M2 모두 NEG 방향만 계산
       - M1_NEG = -fit_oco
       - M2_NEG = -(fit_oco - fit_adi)
    6) 전체 shot 결과와 정상 shot 결과를 함께 산출
       - normal 비교는 M1/M2 모두 is_normal_shot_m2 mask를 공통 사용
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import xlwings as xw
    XLWINGS_AVAILABLE = True
except Exception:
    XLWINGS_AVAILABLE = False


# =========================================================
# 0. Settings
# =========================================================
ADI_PATH = "ADI.parquet"
OCO_PATH = "OCO.parquet"

OUTPUT_EXCEL = "psm_apply_simulation_y_lot5_testfpt_cpe33_gopt.xlsx"
OUTPUT_ROW_PARQUET = "psm_apply_simulation_y_lot5_testfpt_cpe33_gopt_rows.parquet"
OUTPUT_SUMMARY_PARQUET = "psm_apply_simulation_y_lot5_testfpt_cpe33_gopt_summary.parquet"

# 기존 wafer 5매가 아니라 직전 LOT 5개 사용
HISTORY_N_LOTS = 5

KEY_DECIMALS = 1

# CPE 추출 target
PSM_EXTRACT_TARGET_COL = "raw_minus_total_fit_y"

# 현재 wafer 적용 base
BASE_Y_COL_CANDIDATES = [
    "Y_reg",
    "Y_REG",
    "Y_reg_demrc",
    "Y_REG_DEMRC",
]

# 기존 PSM 컬럼
OLD_PSM_COL = "psm_fit_y"

# TEST FPT 제거
REMOVE_TEST_FPT_BEFORE_CPE = True
TEST_FPT_MODE = "median"  # "median" 추천. 필요시 "mean"

# 정상 shot 판정 기준
NORMAL_SHOT_MIN_POINTS = 25

# 회사 WK/RK regression 최소 point
MIN_POINTS_REGRESSION = 19

# row 결과 저장 여부
SAVE_ALL_ROW_RESULTS = True

TIME_COL_CANDIDATES = [
    "M_TIME", "m_time",
    "tkout_time", "TKOUT_TIME",
    "tkin_tsdt", "TKIN_TSDT",
    "event_tsdt", "EVENT_TSDT",
    "transn_occur_date", "TRANSN_OCCUR_DATE",
]


# =========================================================
# 1. G_OPT ridge settings
# =========================================================
RIDGE_REGRESSION = True
G_OPT_SPEC = 1.0
G_OPT_TOLERANCE = 0.001
MINIMUM_RIDGE = 0.001
ADD_RIDGE = 10.0
MAX_GOPT_RETURN = 50
MAX_SPAN_ITER = 5000
CD_TOL = 1e-6
G_OPTIMAL_TYPE = 1

USE_VIRTUAL_CHIP_POINTS = True
VIRTUAL_WAFER_RADIUS = 144000.0
CPE_EVAL_GRID_N = 10
MIN_POINTS_GUIDE = 10

USE_SPAN_BOX_CONSTRAINT = True
SPAN_TOLERANCE = 0.01


# =========================================================
# 2. CPE33 Y design matrix
# =========================================================
CPE33_KEYS_DY = [
    "RK2", "RK4", "RK6",
    "RK8", "RK10", "RK12",
    "RK14", "RK16", "RK18",
    "RK22", "RK24", "RK26",
    "RK32", "RK34", "RK36",
    "RK46", "RK48",
]


def cpe33_y_matrix(rx, ry):
    rx = np.asarray(rx, dtype=float)
    ry = np.asarray(ry, dtype=float)

    X_dy = np.vstack([
        np.ones(len(ry)),                 # RK2
        ry / 1e6,                         # RK4
        rx / 1e6,                         # RK6

        (ry ** 2) / 1e9,                  # RK8
        (ry * rx) / 1e9,                  # RK10
        (rx ** 2) / 1e9,                  # RK12

        (ry ** 3) / 1e12,                 # RK14
        (ry ** 2 * rx) / 1e12,            # RK16
        (ry * rx ** 2) / 1e12,            # RK18

        (ry ** 4) / 1e19,                 # RK22
        (ry ** 3 * rx) / 1e19,            # RK24
        (ry ** 2 * rx ** 2) / 1e19,       # RK26

        (ry ** 5) / 1e23,                 # RK32
        (ry ** 4 * rx) / 1e23,            # RK34
        (ry ** 3 * rx ** 2) / 1e23,       # RK36

        (ry ** 5 * rx) / 1e27,            # RK46
        (ry ** 4 * rx ** 2) / 1e27,       # RK48
    ]).T

    return X_dy


# =========================================================
# 3. Ridge valve / span limit
# =========================================================
RIDGE_VALVE_HYPER = {
    "RK1": 0.0, "RK2": 0.0,
    "RK3": 0.01, "RK4": 0.01,
    "RK5": 0.01, "RK6": 0.01,
    "RK7": 1.0, "RK8": 0.1,
    "RK9": 1.0, "RK10": 0.1,
    "RK11": 0.1, "RK12": 1.0,
    "RK13": 1.0, "RK14": 0.1,
    "RK15": 1.0, "RK16": 0.1,
    "RK17": 1.0, "RK18": 1.0,
    "RK19": 0.1, "RK20": 1.0,
}


def get_ridge_valves(coeff_names: Sequence[str]) -> np.ndarray:
    return np.array([RIDGE_VALVE_HYPER.get(name, 1.0) for name in coeff_names], dtype=float)


def make_lambda_vector(base_lambda: float, coeff_names: Sequence[str]) -> np.ndarray:
    valves = get_ridge_valves(coeff_names)
    return float(base_lambda) * valves


RK_SPAN_LIMITS_CPE33_Y = {
    "RK2":  {"min": -0.1,   "max": 0.1},
    "RK4":  {"min": -10.0,  "max": 10.0},
    "RK6":  {"min": -5.0,   "max": 5.0},
    "RK8":  {"min": -0.15,  "max": 0.15},
    "RK10": {"min": -0.5,   "max": 0.5},
    "RK12": {"min": -0.03,  "max": 0.03},
    "RK14": {"min": -0.015, "max": 0.015},
    "RK16": {"min": -0.05,  "max": 0.05},
    "RK18": {"min": -0.002, "max": 0.002},
    "RK22": {"min": -7.0,   "max": 7.0},
    "RK24": {"min": -18.0,  "max": 18.0},
    "RK26": {"min": -4.0,   "max": 4.0},
    "RK32": {"min": -2.5,   "max": 2.5},
    "RK34": {"min": -5.0,   "max": 5.0},
    "RK36": {"min": -1.2,   "max": 1.2},
    "RK46": {"min": -1.2,   "max": 1.2},
    "RK48": {"min": -0.6,   "max": 0.6},
}


# =========================================================
# 4. Common math utilities
# =========================================================
def m3s_y(y):
    y = pd.to_numeric(pd.Series(y), errors="coerce").dropna()

    if len(y) <= 1:
        return np.nan

    return 3.0 * y.std(ddof=1)


def safe_corr(a, b):
    a = pd.to_numeric(pd.Series(a), errors="coerce")
    b = pd.to_numeric(pd.Series(b), errors="coerce")

    valid = a.notna() & b.notna()

    if valid.sum() < 3:
        return np.nan

    return a[valid].corr(b[valid])


def choose_base_lambda_scale(n_points: int) -> float:
    if n_points >= 10:
        return 1.0
    if n_points >= 7:
        return 1e2
    if n_points >= 5:
        return 1e4
    if n_points >= 3:
        return 1e6
    return 1e8


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


def gopt_value(
    X_meas: np.ndarray,
    X_eval: np.ndarray,
    lambdas: np.ndarray,
    gopt_type: int = 1,
    inner_or_partial: str = "partial",
) -> float:
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
        diag_val = np.sum(H * H, axis=1)
        max_val = np.nanmax(diag_val)
        return float(np.sqrt(max(max_val, 0.0)))

    if effective_type == 2:
        H = X_eval @ invA @ X_meas.T
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

        if span < lo or span > hi:
            violations.append((name, span, span_limits[name]["min"], span_limits[name]["max"]))

    return violations


def build_beta_bounds_from_span(
    X_eval: np.ndarray,
    coeff_names: Sequence[str],
    span_limits: Dict[str, Dict[str, float]],
) -> Tuple[np.ndarray, np.ndarray]:
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

    residual = y - X @ beta
    col_norm2 = np.sum(X * X, axis=0)

    last_delta = np.inf

    for it in range(1, max_iter + 1):
        max_delta = 0.0

        for j in range(n_param):
            denom = col_norm2[j] + lambdas[j]

            if denom <= 0 or not np.isfinite(denom):
                continue

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
    base_lambda: float
    gopt: float
    spans: Dict[str, float]
    violations: List[Tuple[str, float, float, float]]
    gopt_iter: int
    span_iter: int
    method: str


def solve_gopt_ridge_one_axis(
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
    gopt_type: int = 1,
    inner_or_partial: str = "partial",
    use_span_box_constraint: bool = True,
    span_tolerance: float = 0.01,
    cd_tol: float = 1e-6,
    max_span_iter: int = 5000,
    base_lambda_scale: float = 1.0,
    debug: bool = False,
) -> RidgeFitResult:
    X_fit = np.asarray(X_fit, dtype=float)
    X_eval = np.asarray(X_eval, dtype=float)
    y = np.asarray(y, dtype=float)

    n_param = X_fit.shape[1]

    if n_param != len(coeff_names):
        raise ValueError(f"n_param({n_param}) != len(coeff_names)({len(coeff_names)})")

    initial_lambda = 0.0
    lambdas = make_lambda_vector(initial_lambda, coeff_names)

    beta, pred = ridge_predict(X_fit, y, lambdas)
    g = gopt_value(
        X_fit,
        X_eval,
        lambdas,
        gopt_type=gopt_type,
        inner_or_partial=inner_or_partial,
    )

    gopt_iter = 0
    method = "ols"
    selected_base_lambda = initial_lambda

    if ridge_regression and (not np.isfinite(g) or g >= gopt_spec or g == 0):
        low_lambda = 0.0

        high_lambda = max(minimum_ridge * base_lambda_scale, minimum_ridge)
        high_lambdas = make_lambda_vector(high_lambda, coeff_names)

        high_g = gopt_value(
            X_fit,
            X_eval,
            high_lambdas,
            gopt_type=gopt_type,
            inner_or_partial=inner_or_partial,
        )

        while (not np.isfinite(high_g) or high_g >= gopt_spec) and gopt_iter < max_gopt_return:
            low_lambda = high_lambda
            high_lambda = high_lambda * add_ridge

            high_lambdas = make_lambda_vector(high_lambda, coeff_names)
            high_g = gopt_value(
                X_fit,
                X_eval,
                high_lambdas,
                gopt_type=gopt_type,
                inner_or_partial=inner_or_partial,
            )

            gopt_iter += 1

            if debug:
                print(f"fast ridge: lambda={high_lambda:.6g}, gopt={high_g:.6g}")

        target_low = max(0.0, gopt_spec - gopt_tolerance)
        target_high = gopt_spec

        best_lambda = high_lambda
        best_g = high_g

        if np.isfinite(high_g) and high_g < gopt_spec:
            lo = low_lambda
            hi = high_lambda

            for _ in range(max_gopt_return):
                mid = (lo + hi) / 2.0
                mid_lambdas = make_lambda_vector(mid, coeff_names)

                mid_g = gopt_value(
                    X_fit,
                    X_eval,
                    mid_lambdas,
                    gopt_type=gopt_type,
                    inner_or_partial=inner_or_partial,
                )

                gopt_iter += 1

                if debug:
                    print(f"slow ridge: lambda={mid:.6g}, gopt={mid_g:.6g}")

                if target_low <= mid_g < target_high:
                    best_lambda = mid
                    best_g = mid_g
                    break

                if mid_g >= gopt_spec or not np.isfinite(mid_g):
                    lo = mid
                else:
                    hi = mid
                    best_lambda = mid
                    best_g = mid_g

                if abs(hi - lo) < max(minimum_ridge * 1e-3, 1e-12):
                    break

        selected_base_lambda = best_lambda
        lambdas = make_lambda_vector(best_lambda, coeff_names)

        beta, pred = ridge_predict(X_fit, y, lambdas)
        g = gopt_value(
            X_fit,
            X_eval,
            lambdas,
            gopt_type=gopt_type,
            inner_or_partial=inner_or_partial,
        )

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

        g = gopt_value(
            X_fit,
            X_eval,
            lambdas,
            gopt_type=gopt_type,
            inner_or_partial=inner_or_partial,
        )

        method = "ridge_gopt_box_cd"

    return RidgeFitResult(
        beta=beta,
        pred=pred,
        lambdas=lambdas,
        base_lambda=float(selected_base_lambda),
        gopt=float(g),
        spans=spans,
        violations=violations,
        gopt_iter=int(gopt_iter),
        span_iter=int(span_iter),
        method=method,
    )


# =========================================================
# 5. Virtual / eval points
# =========================================================
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


def build_virtual_chip_points(
    step_pitch_x: float,
    step_pitch_y: float,
    chip_x_num: int,
    chip_y_num: int,
    round_decimals: int = 6,
) -> Tuple[np.ndarray, np.ndarray]:
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

            if len(rx_keep) > 0:
                return rx_keep, ry_keep, "chip_corner_center_wafer_clipped", n_full, len(rx_keep)

            return rx_full, ry_full, "chip_corner_center_no_clip_points_fallback", n_full, n_full

    rx_v, ry_v = build_eval_grid_from_data(fallback_rx, fallback_ry, grid_n=CPE_EVAL_GRID_N)

    return rx_v, ry_v, "measured_range_grid_fallback", len(rx_v), len(rx_v)


def determine_inner_or_partial(n_valid: int, n_virtual: int) -> str:
    return "inner" if n_valid >= n_virtual else "partial"


# =========================================================
# 6. Data utilities
# =========================================================
def require_columns(df, cols, label="df"):
    missing = [c for c in cols if c not in df.columns]

    if missing:
        raise ValueError(f"[{label}] 필수 컬럼 누락: {missing}")


def find_first_existing_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c

    return None


def normalize_alias(df):
    df = df.copy()

    if "Coordinate_X" in df.columns and "coordinate_X" not in df.columns:
        df["coordinate_X"] = df["Coordinate_X"]

    if "Coordinate_Y" in df.columns and "coordinate_Y" not in df.columns:
        df["coordinate_Y"] = df["Coordinate_Y"]

    if "FCP_X" in df.columns and "fcp_x" not in df.columns:
        df["fcp_x"] = df["FCP_X"]

    if "FCP_Y" in df.columns and "fcp_y" not in df.columns:
        df["fcp_y"] = df["FCP_Y"]

    return df


def add_round_keys(df, key_decimals=1):
    df = normalize_alias(df)

    required = ["LOT_ID", "Wafer", "fcp_x", "fcp_y", "coordinate_X", "coordinate_Y"]
    require_columns(df, required, label="add_round_keys input")

    df = df.copy()

    for c in ["Wafer", "fcp_x", "fcp_y", "coordinate_X", "coordinate_Y"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["_lot_key"] = df["LOT_ID"].astype(str).str.strip()
    df["_wafer_key"] = df["Wafer"].astype("Int64").astype(str)

    df["_fcp_x_key"] = df["fcp_x"].round(key_decimals)
    df["_fcp_y_key"] = df["fcp_y"].round(key_decimals)
    df["_cx_key"] = df["coordinate_X"].round(key_decimals)
    df["_cy_key"] = df["coordinate_Y"].round(key_decimals)

    df["_wafer_id"] = df["_lot_key"] + "_" + df["_wafer_key"]

    df["_shot_key"] = (
        df["_fcp_x_key"].astype(str) + "_" +
        df["_fcp_y_key"].astype(str)
    )

    df["_point_key"] = (
        df["_fcp_x_key"].astype(str) + "_" +
        df["_fcp_y_key"].astype(str) + "_" +
        df["_cx_key"].astype(str) + "_" +
        df["_cy_key"].astype(str)
    )

    return df


def make_wafer_sequence(df_oco):
    time_col = find_first_existing_col(df_oco, TIME_COL_CANDIDATES)
    grp_cols = ["LOT_ID", "Wafer", "_wafer_id"]

    if time_col is not None:
        tmp = df_oco.copy()
        tmp[time_col] = pd.to_datetime(tmp[time_col], errors="coerce")

        seq = (
            tmp
            .groupby(grp_cols, dropna=False)
            .agg(
                wafer_time=(time_col, "min"),
                row_count=("LOT_ID", "size"),
            )
            .reset_index()
        )

        seq = seq.sort_values(
            ["wafer_time", "LOT_ID", "Wafer"],
            ascending=[True, True, True],
            na_position="last"
        ).reset_index(drop=True)

    else:
        print("⚠️ 시간 컬럼을 찾지 못했습니다. LOT_ID/Wafer 기준으로 정렬합니다.")

        seq = (
            df_oco
            .groupby(grp_cols, dropna=False)
            .size()
            .reset_index(name="row_count")
            .sort_values(["LOT_ID", "Wafer"])
            .reset_index(drop=True)
        )

        seq["wafer_time"] = pd.NaT

    seq["seq_idx"] = np.arange(len(seq))

    return seq


def add_lot_sequence_to_wafer_sequence(seq_df):
    lot_seq = (
        seq_df
        .groupby("LOT_ID", dropna=False)
        .agg(
            lot_time=("wafer_time", "min"),
            n_wafers_in_lot=("Wafer", "nunique"),
            wafer_ids_in_lot=("_wafer_id", lambda x: ", ".join(map(str, x)))
        )
        .reset_index()
    )

    lot_seq = lot_seq.sort_values(
        ["lot_time", "LOT_ID"],
        ascending=[True, True],
        na_position="last"
    ).reset_index(drop=True)

    lot_seq["lot_seq_idx"] = np.arange(len(lot_seq))

    seq_df = seq_df.merge(
        lot_seq[["LOT_ID", "lot_time", "lot_seq_idx", "n_wafers_in_lot", "wafer_ids_in_lot"]],
        on="LOT_ID",
        how="left",
        validate="m:1"
    )

    return seq_df, lot_seq


def get_history_lots_for_current_lot(current_key, lot_seq_df, n_lots=5):
    current_lot_seq_idx = int(current_key["lot_seq_idx"])

    hist_lots = (
        lot_seq_df[
            (lot_seq_df["lot_seq_idx"] >= current_lot_seq_idx - n_lots) &
            (lot_seq_df["lot_seq_idx"] < current_lot_seq_idx)
        ]
        .sort_values("lot_seq_idx")
        ["LOT_ID"]
        .astype(str)
        .tolist()
    )

    return hist_lots


# =========================================================
# 7. TEST FPT
# =========================================================
def calc_test_fpt_map(df_hist, target_col, mode="median"):
    if len(df_hist) == 0:
        return pd.DataFrame(columns=["TEST", "test_fpt_y", "n_fpt_rows"])

    require_columns(df_hist, ["TEST", target_col], label="calc_test_fpt_map input")

    tmp = df_hist.copy()
    tmp["TEST"] = tmp["TEST"].astype(str).str.strip()
    tmp["_target_y_for_fpt"] = pd.to_numeric(tmp[target_col], errors="coerce")

    tmp = tmp.dropna(subset=["_target_y_for_fpt"]).copy()

    if len(tmp) == 0:
        return pd.DataFrame(columns=["TEST", "test_fpt_y", "n_fpt_rows"])

    if mode == "median":
        fpt = (
            tmp
            .groupby("TEST", dropna=False)["_target_y_for_fpt"]
            .agg(test_fpt_y="median", n_fpt_rows="size")
            .reset_index()
        )

    elif mode == "mean":
        fpt = (
            tmp
            .groupby("TEST", dropna=False)["_target_y_for_fpt"]
            .agg(test_fpt_y="mean", n_fpt_rows="size")
            .reset_index()
        )

    else:
        raise ValueError(f"Unknown TEST_FPT_MODE: {mode}")

    return fpt


def apply_test_fpt_removal(df_hist, target_col, fpt_df, source_name):
    if len(df_hist) == 0:
        out = df_hist.copy()
        out["test_fpt_y"] = np.nan
        out["target_y_fpt_removed"] = np.nan
        out["fpt_source"] = source_name
        return out

    out = df_hist.copy()

    require_columns(out, ["TEST", target_col], label=f"apply_test_fpt_removal {source_name}")

    out["TEST"] = out["TEST"].astype(str).str.strip()
    out["_target_y_original"] = pd.to_numeric(out[target_col], errors="coerce")

    fpt_use = fpt_df.copy()

    if len(fpt_use) > 0:
        fpt_use["TEST"] = fpt_use["TEST"].astype(str).str.strip()

        out = out.merge(
            fpt_use[["TEST", "test_fpt_y", "n_fpt_rows"]],
            on="TEST",
            how="left",
            validate="m:1"
        )
    else:
        out["test_fpt_y"] = np.nan
        out["n_fpt_rows"] = np.nan

    if REMOVE_TEST_FPT_BEFORE_CPE:
        out["target_y_fpt_removed"] = out["_target_y_original"] - out["test_fpt_y"]
    else:
        out["target_y_fpt_removed"] = out["_target_y_original"]

    out["fpt_source"] = source_name

    return out


def average_history_by_point(df_hist, target_col):
    tmp = df_hist.copy()
    tmp["_target_y"] = pd.to_numeric(tmp[target_col], errors="coerce")

    agg_dict = {
        "fcp_x": ("fcp_x", "mean"),
        "fcp_y": ("fcp_y", "mean"),
        "coordinate_X": ("coordinate_X", "mean"),
        "coordinate_Y": ("coordinate_Y", "mean"),
        "target_y": ("_target_y", "mean"),
        "n_hist_point": ("_target_y", "size"),
    }

    optional_meta_cols = [
        "STEP_PITCH_X", "STEP_PITCH_Y",
        "CHIP_X_NUM", "CHIP_Y_NUM",
    ]

    for c in optional_meta_cols:
        if c in tmp.columns:
            agg_dict[c] = (c, "first")

    if "TEST" in tmp.columns:
        agg_dict["TEST"] = ("TEST", "first")

    if "test_fpt_y" in tmp.columns:
        agg_dict["test_fpt_y"] = ("test_fpt_y", "first")

    if "n_fpt_rows" in tmp.columns:
        agg_dict["n_fpt_rows"] = ("n_fpt_rows", "first")

    avg = (
        tmp
        .dropna(subset=["_target_y"])
        .groupby(["_shot_key", "_point_key"], dropna=False)
        .agg(**agg_dict)
        .reset_index()
    )

    return avg


# =========================================================
# 8. CPE33 Y GOPT fitting per shot
# =========================================================
def fit_cpe33_y_model_gopt(grp: pd.DataFrame):
    work = grp.copy()

    rx = pd.to_numeric(work["coordinate_X"], errors="coerce").to_numpy(dtype=float)
    ry = pd.to_numeric(work["coordinate_Y"], errors="coerce").to_numpy(dtype=float)
    yy = pd.to_numeric(work["target_y"], errors="coerce").to_numpy(dtype=float)

    valid = np.isfinite(rx) & np.isfinite(ry) & np.isfinite(yy)

    rx = rx[valid]
    ry = ry[valid]
    yy = yy[valid]

    n_valid = len(yy)

    meta = {
        "status": "init",
        "n_points": n_valid,
        "n_terms": len(CPE33_KEYS_DY),
        "rank": np.nan,
        "cond": np.nan,
        "target_m3s": m3s_y(yy),
        "fit_m3s": np.nan,
        "fit_over_target": np.nan,
        "gopt": np.nan,
        "base_lambda": np.nan,
        "lambda_max": np.nan,
        "gopt_iter": np.nan,
        "span_iter": np.nan,
        "span_violation_count": np.nan,
        "method": None,
        "inner_or_partial": None,
        "n_virtual": np.nan,
        "n_virtual_full": np.nan,
        "virtual_source": None,
        "base_lambda_scale": np.nan,
    }

    if n_valid == 0:
        meta["status"] = "no_valid_points"
        return None, meta

    X_fit = cpe33_y_matrix(rx, ry)

    try:
        meta["rank"] = np.linalg.matrix_rank(X_fit)
    except Exception:
        meta["rank"] = np.nan

    try:
        meta["cond"] = np.linalg.cond(X_fit)
    except Exception:
        meta["cond"] = np.nan

    if "fcp_x" in work.columns:
        fcp_x_s = pd.to_numeric(work["fcp_x"], errors="coerce").dropna()
        fcp_x = float(fcp_x_s.iloc[0]) if len(fcp_x_s) else 0.0
    else:
        fcp_x = 0.0

    if "fcp_y" in work.columns:
        fcp_y_s = pd.to_numeric(work["fcp_y"], errors="coerce").dropna()
        fcp_y = float(fcp_y_s.iloc[0]) if len(fcp_y_s) else 0.0
    else:
        fcp_y = 0.0

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
        grid_rx, grid_ry = build_eval_grid_from_data(rx, ry, grid_n=CPE_EVAL_GRID_N)
        virtual_source = "measured_range_grid"
        n_virtual_full = len(grid_rx)
        n_virtual = len(grid_rx)

    X_eval = cpe33_y_matrix(grid_rx, grid_ry)

    inner_or_partial = determine_inner_or_partial(n_valid=n_valid, n_virtual=n_virtual)
    base_lambda_scale = choose_base_lambda_scale(n_valid)

    fit = solve_gopt_ridge_one_axis(
        X_fit=X_fit,
        y=yy,
        X_eval=X_eval,
        coeff_names=CPE33_KEYS_DY,
        span_limits=RK_SPAN_LIMITS_CPE33_Y,
        ridge_regression=RIDGE_REGRESSION,
        gopt_spec=G_OPT_SPEC,
        gopt_tolerance=G_OPT_TOLERANCE,
        minimum_ridge=MINIMUM_RIDGE,
        add_ridge=ADD_RIDGE,
        max_gopt_return=MAX_GOPT_RETURN,
        gopt_type=G_OPTIMAL_TYPE,
        inner_or_partial=inner_or_partial,
        use_span_box_constraint=USE_SPAN_BOX_CONSTRAINT,
        span_tolerance=SPAN_TOLERANCE,
        cd_tol=CD_TOL,
        max_span_iter=MAX_SPAN_ITER,
        base_lambda_scale=base_lambda_scale,
        debug=False,
    )

    pred = fit.pred

    fit_m3s = m3s_y(pred)
    target_m3s = meta["target_m3s"]

    meta.update({
        "status": "ok",
        "fit_m3s": fit_m3s,
        "fit_over_target": (
            fit_m3s / target_m3s
            if pd.notna(target_m3s) and target_m3s != 0
            else np.nan
        ),
        "gopt": fit.gopt,
        "base_lambda": fit.base_lambda,
        "lambda_max": float(np.nanmax(fit.lambdas)),
        "gopt_iter": fit.gopt_iter,
        "span_iter": fit.span_iter,
        "span_violation_count": len(fit.violations),
        "method": fit.method,
        "inner_or_partial": inner_or_partial,
        "n_virtual": n_virtual,
        "n_virtual_full": n_virtual_full,
        "virtual_source": virtual_source,
        "base_lambda_scale": base_lambda_scale,
    })

    model = {
        "method": fit.method,
        "beta": fit.beta,
        "lambdas": fit.lambdas,
        "base_lambda": fit.base_lambda,
        "lambda_max": float(np.nanmax(fit.lambdas)),
        "gopt": fit.gopt,
        "n_points": n_valid,
        "n_virtual": n_virtual,
        "inner_or_partial": inner_or_partial,
        "span_violation_count": len(fit.violations),
    }

    return model, meta


def predict_cpe33_y_model(rx, ry, model):
    rx = np.asarray(rx, dtype=float)
    ry = np.asarray(ry, dtype=float)

    pred = np.full(len(rx), np.nan)

    valid = np.isfinite(rx) & np.isfinite(ry)

    if valid.sum() == 0:
        return pred

    X = cpe33_y_matrix(rx[valid], ry[valid])
    pred[valid] = X @ model["beta"]

    return pred


def fit_history_model_by_shot(avg_df):
    model_by_shot = {}
    meta_by_shot = {}

    if len(avg_df) == 0:
        return model_by_shot, meta_by_shot

    for shot_key, g in avg_df.groupby("_shot_key", dropna=False):
        model, meta = fit_cpe33_y_model_gopt(g)

        meta["shot_key"] = shot_key
        meta_by_shot[shot_key] = meta

        if model is not None and meta["status"] == "ok":
            model_by_shot[shot_key] = model

    return model_by_shot, meta_by_shot


# =========================================================
# 9. Company WK/RK Y regression
# =========================================================
COEFF_KEYS_DY_COMPANY = [
    "WK2", "WK4", "WK6", "WK8", "WK10", "WK12", "WK14", "WK16", "WK18", "WK20",
    "RK4", "RK6", "RK8", "RK10", "RK12", "RK14", "RK16", "RK18", "RK20",
]


def company_y_matrix(x, y, rx, ry):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    rx = np.asarray(rx, dtype=float)
    ry = np.asarray(ry, dtype=float)

    X_dy = np.vstack([
        np.ones(len(y)),
        y / 1e6,
        x / 1e6,

        (y ** 2) / 1e12,
        (y * x) / 1e12,
        (x ** 2) / 1e12,

        (y ** 3) / 1e15,
        (y ** 2 * x) / 1e15,
        (y * x ** 2) / 1e15,
        (x ** 3) / 1e15,

        ry / 1e6,
        rx / 1e6,

        (ry ** 2) / 1e9,
        (ry * rx) / 1e9,
        (rx ** 2) / 1e9,

        (ry ** 3) / 1e12,
        (ry ** 2 * rx) / 1e12,
        (ry * rx ** 2) / 1e12,
        (rx ** 3) / 1e12,
    ]).T

    return X_dy


def fit_lstsq(X, y):
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    return coef, pred


def regression_residual_y_for_wafer(df, y_col, result_prefix):
    df = df.copy()

    out_fit_col = f"{result_prefix}_fit_y"
    out_resid_col = f"{result_prefix}_residual_y"

    df[out_fit_col] = np.nan
    df[out_resid_col] = np.nan

    required = ["fcp_x", "fcp_y", "coordinate_X", "coordinate_Y", y_col]

    for c in required:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    valid = (
        df["fcp_x"].notna() &
        df["fcp_y"].notna() &
        df["coordinate_X"].notna() &
        df["coordinate_Y"].notna() &
        df[y_col].notna()
    )

    work = df.loc[valid].copy()

    if len(work) < MIN_POINTS_REGRESSION:
        return df, None, "skip_too_few_points"

    x = work["fcp_x"].to_numpy(dtype=float)
    y = work["fcp_y"].to_numpy(dtype=float)
    rx = work["coordinate_X"].to_numpy(dtype=float)
    ry = work["coordinate_Y"].to_numpy(dtype=float)
    yy = work[y_col].to_numpy(dtype=float)

    X = company_y_matrix(x, y, rx, ry)
    coef, pred = fit_lstsq(X, yy)

    resid = yy - pred

    df.loc[work.index, out_fit_col] = pred
    df.loc[work.index, out_resid_col] = resid

    coef_dict = {f"{name}_Y": val for name, val in zip(COEFF_KEYS_DY_COMPANY, coef)}

    return df, coef_dict, "ok"


# =========================================================
# 10. Summary utilities
# =========================================================
def calc_delta_from_residuals(df, sim_resid_col, eval_mask=None):
    if eval_mask is None:
        valid = (
            df["baseline_residual_y"].notna() &
            df[sim_resid_col].notna()
        )
    else:
        valid = (
            eval_mask.fillna(False).astype(bool) &
            df["baseline_residual_y"].notna() &
            df[sim_resid_col].notna()
        )

    base_m3s = m3s_y(df.loc[valid, "baseline_residual_y"])
    sim_m3s = m3s_y(df.loc[valid, sim_resid_col])

    delta = (
        sim_m3s - base_m3s
        if pd.notna(sim_m3s) and pd.notna(base_m3s)
        else np.nan
    )

    return int(valid.sum()), base_m3s, sim_m3s, delta


def make_coef_long(model_rows, method_name):
    rows = []

    for r in model_rows:
        beta = r["beta"]

        for name, val in zip(CPE33_KEYS_DY, beta):
            rows.append({
                "current_LOT_ID": r["current_LOT_ID"],
                "current_Wafer": r["current_Wafer"],
                "current_seq_idx": r["current_seq_idx"],
                "shot_key": r["shot_key"],
                "method": method_name,
                "cpe_fit_method": r.get("cpe_fit_method", None),

                "base_lambda": r.get("base_lambda", np.nan),
                "lambda_max": r.get("lambda_max", np.nan),
                "gopt": r.get("gopt", np.nan),

                "Term": name,
                "Coefficient_Y": val,
            })

    return pd.DataFrame(rows)


def make_meta_df(meta_by_shot, current_lot, current_wafer, seq_idx, source):
    rows = []

    for shot_key, meta in meta_by_shot.items():
        r = dict(meta)
        r.update({
            "current_LOT_ID": current_lot,
            "current_Wafer": current_wafer,
            "current_seq_idx": seq_idx,
            "source": source,
            "shot_key": shot_key,
            "is_normal_shot": (
                meta.get("status") == "ok" and
                meta.get("n_points", 0) >= NORMAL_SHOT_MIN_POINTS
            ),
        })
        rows.append(r)

    return rows


def list_meta_values(meta_dict, key):
    vals = [
        m.get(key, np.nan)
        for m in meta_dict.values()
        if m.get("status") == "ok"
    ]

    vals = pd.to_numeric(pd.Series(vals), errors="coerce").dropna().to_numpy(dtype=float)

    return vals


def safe_nanmedian(vals):
    vals = np.asarray(vals, dtype=float)
    return float(np.nanmedian(vals)) if len(vals) else np.nan


def safe_nanmin(vals):
    vals = np.asarray(vals, dtype=float)
    return float(np.nanmin(vals)) if len(vals) else np.nan


def safe_nanmax(vals):
    vals = np.asarray(vals, dtype=float)
    return float(np.nanmax(vals)) if len(vals) else np.nan


def fpt_rows_for_output(fpt_df, current_lot, current_wafer, seq_idx, source, hist_lots):
    if fpt_df is None or len(fpt_df) == 0:
        return []

    out = fpt_df.copy()
    out["current_LOT_ID"] = current_lot
    out["current_Wafer"] = current_wafer
    out["current_seq_idx"] = seq_idx
    out["source"] = source
    out["history_lots"] = ", ".join(hist_lots)

    return out.to_dict("records")


# =========================================================
# 11. Simulation per wafer
# =========================================================
def simulate_current_wafer(
    current_key,
    seq_idx,
    seq_df,
    lot_seq_df,
    df_oco,
    df_adi,
    base_y_col,
):
    current_wafer_id = current_key["_wafer_id"]
    current_lot = str(current_key["LOT_ID"])
    current_wafer = current_key["Wafer"]
    current_lot_seq_idx = int(current_key["lot_seq_idx"])

    hist_lots = get_history_lots_for_current_lot(
        current_key=current_key,
        lot_seq_df=lot_seq_df,
        n_lots=HISTORY_N_LOTS
    )

    cur = df_oco[df_oco["_wafer_id"] == current_wafer_id].copy()

    hist_oco = df_oco[df_oco["LOT_ID"].astype(str).isin(hist_lots)].copy()
    hist_adi = df_adi[df_adi["LOT_ID"].astype(str).isin(hist_lots)].copy()

    hist_oco_wafer_ids = sorted(hist_oco["_wafer_id"].dropna().astype(str).unique().tolist())
    hist_adi_wafer_ids = sorted(hist_adi["_wafer_id"].dropna().astype(str).unique().tolist())

    if len(cur) == 0 or len(hist_oco) == 0 or len(hist_adi) == 0:
        return None, None, None, None, None

    # -----------------------------------------------------
    # 1) TEST FPT 계산
    # -----------------------------------------------------
    fpt_oco = calc_test_fpt_map(
        hist_oco,
        target_col=PSM_EXTRACT_TARGET_COL,
        mode=TEST_FPT_MODE
    )

    fpt_adi = calc_test_fpt_map(
        hist_adi,
        target_col=PSM_EXTRACT_TARGET_COL,
        mode=TEST_FPT_MODE
    )

    hist_oco_fpt = apply_test_fpt_removal(
        hist_oco,
        target_col=PSM_EXTRACT_TARGET_COL,
        fpt_df=fpt_oco,
        source_name="OCO"
    )

    hist_adi_fpt = apply_test_fpt_removal(
        hist_adi,
        target_col=PSM_EXTRACT_TARGET_COL,
        fpt_df=fpt_adi,
        source_name="ADI"
    )

    if REMOVE_TEST_FPT_BEFORE_CPE:
        cpe_target_col = "target_y_fpt_removed"
    else:
        cpe_target_col = PSM_EXTRACT_TARGET_COL

    # -----------------------------------------------------
    # 2) FPT 제거 후 point 평균 map 생성
    # -----------------------------------------------------
    avg_oco = average_history_by_point(hist_oco_fpt, cpe_target_col)
    avg_adi = average_history_by_point(hist_adi_fpt, cpe_target_col)

    # -----------------------------------------------------
    # 3) shot별 CPE33 G_OPT ridge fitting
    # -----------------------------------------------------
    model_oco, meta_oco = fit_history_model_by_shot(avg_oco)
    model_adi, meta_adi = fit_history_model_by_shot(avg_adi)

    # -----------------------------------------------------
    # 4) 현재 wafer에서 기존 PSM 제거 후 새 PSM 후보 적용
    # -----------------------------------------------------
    cur["y_base"] = pd.to_numeric(cur[base_y_col], errors="coerce")
    cur["old_psm_y"] = pd.to_numeric(cur[OLD_PSM_COL], errors="coerce")
    cur["y_psm_decor"] = cur["y_base"] - cur["old_psm_y"]

    cur["fit_oco_y"] = np.nan
    cur["fit_adi_y"] = np.nan
    cur["fit_skew_y"] = np.nan

    cur["new_psm_y_m1_neg"] = np.nan
    cur["new_psm_y_m2_neg"] = np.nan

    cur["y_sim_m1_neg"] = np.nan
    cur["y_sim_m2_neg"] = np.nan

    cur["is_normal_shot_m1"] = False
    cur["is_normal_shot_m2"] = False

    coef_rows_m1 = []
    coef_rows_m2 = []

    n_shot_total = cur["_shot_key"].nunique()
    n_shot_m1 = 0
    n_shot_m2 = 0
    n_normal_shot_m1 = 0
    n_normal_shot_m2 = 0

    for shot_key, g in cur.groupby("_shot_key", dropna=False):
        idx = g.index

        rx = g["coordinate_X"].to_numpy(dtype=float)
        ry = g["coordinate_Y"].to_numpy(dtype=float)

        y_psm_decor = cur.loc[idx, "y_psm_decor"].to_numpy(dtype=float)

        # M1_NEG = -fit_oco
        if shot_key in model_oco:
            fit_oco = predict_cpe33_y_model(rx, ry, model_oco[shot_key])
            new_psm_m1_neg = -fit_oco

            cur.loc[idx, "fit_oco_y"] = fit_oco
            cur.loc[idx, "new_psm_y_m1_neg"] = new_psm_m1_neg
            cur.loc[idx, "y_sim_m1_neg"] = y_psm_decor + new_psm_m1_neg

            n_shot_m1 += 1

            is_normal_m1 = (
                meta_oco.get(shot_key, {}).get("status") == "ok" and
                meta_oco.get(shot_key, {}).get("n_points", 0) >= NORMAL_SHOT_MIN_POINTS
            )

            if is_normal_m1:
                n_normal_shot_m1 += 1

            cur.loc[idx, "is_normal_shot_m1"] = is_normal_m1

            coef_rows_m1.append({
                "current_LOT_ID": current_lot,
                "current_Wafer": current_wafer,
                "current_seq_idx": seq_idx,
                "shot_key": shot_key,
                "beta": model_oco[shot_key]["beta"],
                "cpe_fit_method": model_oco[shot_key]["method"],
                "base_lambda": model_oco[shot_key].get("base_lambda", np.nan),
                "lambda_max": model_oco[shot_key].get("lambda_max", np.nan),
                "gopt": model_oco[shot_key].get("gopt", np.nan),
            })

        # M2_NEG = -(fit_oco - fit_adi)
        if shot_key in model_oco and shot_key in model_adi:
            fit_oco = predict_cpe33_y_model(rx, ry, model_oco[shot_key])
            fit_adi = predict_cpe33_y_model(rx, ry, model_adi[shot_key])

            skew = fit_oco - fit_adi
            new_psm_m2_neg = -skew

            cur.loc[idx, "fit_oco_y"] = fit_oco
            cur.loc[idx, "fit_adi_y"] = fit_adi
            cur.loc[idx, "fit_skew_y"] = skew

            cur.loc[idx, "new_psm_y_m2_neg"] = new_psm_m2_neg
            cur.loc[idx, "y_sim_m2_neg"] = y_psm_decor + new_psm_m2_neg

            n_shot_m2 += 1

            is_normal_m2 = (
                meta_oco.get(shot_key, {}).get("status") == "ok" and
                meta_adi.get(shot_key, {}).get("status") == "ok" and
                meta_oco.get(shot_key, {}).get("n_points", 0) >= NORMAL_SHOT_MIN_POINTS and
                meta_adi.get(shot_key, {}).get("n_points", 0) >= NORMAL_SHOT_MIN_POINTS
            )

            if is_normal_m2:
                n_normal_shot_m2 += 1

            cur.loc[idx, "is_normal_shot_m2"] = is_normal_m2

            beta_skew = model_oco[shot_key]["beta"] - model_adi[shot_key]["beta"]

            coef_rows_m2.append({
                "current_LOT_ID": current_lot,
                "current_Wafer": current_wafer,
                "current_seq_idx": seq_idx,
                "shot_key": shot_key,
                "beta": beta_skew,
                "cpe_fit_method": f"{model_oco[shot_key]['method']}/{model_adi[shot_key]['method']}",

                "base_lambda_oco": model_oco[shot_key].get("base_lambda", np.nan),
                "base_lambda_adi": model_adi[shot_key].get("base_lambda", np.nan),
                "lambda_max_oco": model_oco[shot_key].get("lambda_max", np.nan),
                "lambda_max_adi": model_adi[shot_key].get("lambda_max", np.nan),
                "gopt_oco": model_oco[shot_key].get("gopt", np.nan),
                "gopt_adi": model_adi[shot_key].get("gopt", np.nan),

                "base_lambda": np.nanmax([
                    model_oco[shot_key].get("base_lambda", np.nan),
                    model_adi[shot_key].get("base_lambda", np.nan),
                ]),
                "lambda_max": np.nanmax([
                    model_oco[shot_key].get("lambda_max", np.nan),
                    model_adi[shot_key].get("lambda_max", np.nan),
                ]),
                "gopt": np.nanmax([
                    model_oco[shot_key].get("gopt", np.nan),
                    model_adi[shot_key].get("gopt", np.nan),
                ]),
            })

    # -----------------------------------------------------
    # 5) baseline / simulation 각각 회사 WK/RK regression
    # -----------------------------------------------------
    cur, coef_base_reg, status_base = regression_residual_y_for_wafer(
        cur,
        y_col="y_base",
        result_prefix="baseline"
    )

    cur, coef_m1_neg_reg, status_m1_neg = regression_residual_y_for_wafer(
        cur,
        y_col="y_sim_m1_neg",
        result_prefix="m1_neg"
    )

    cur, coef_m2_neg_reg, status_m2_neg = regression_residual_y_for_wafer(
        cur,
        y_col="y_sim_m2_neg",
        result_prefix="m2_neg"
    )

    # -----------------------------------------------------
    # 6) M3S 계산
    # -----------------------------------------------------
    baseline_m3s_all = m3s_y(cur["baseline_residual_y"])

    m1_all_n, m1_all_base, m1_all_sim, m1_all_delta = calc_delta_from_residuals(
        cur,
        "m1_neg_residual_y"
    )

    m2_all_n, m2_all_base, m2_all_sim, m2_all_delta = calc_delta_from_residuals(
        cur,
        "m2_neg_residual_y"
    )

    # normal 비교는 M1/M2 모두 같은 mask 사용
    normal_compare_mask = cur["is_normal_shot_m2"]

    m1_norm_n, m1_norm_base, m1_norm_sim, m1_norm_delta = calc_delta_from_residuals(
        cur,
        "m1_neg_residual_y",
        eval_mask=normal_compare_mask
    )

    m2_norm_n, m2_norm_base, m2_norm_sim, m2_norm_delta = calc_delta_from_residuals(
        cur,
        "m2_neg_residual_y",
        eval_mask=normal_compare_mask
    )

    candidates_all = {
        "m1_neg_all": m1_all_delta,
        "m2_neg_all": m2_all_delta,
    }

    valid_candidates_all = {
        k: v for k, v in candidates_all.items()
        if pd.notna(v)
    }

    if valid_candidates_all:
        best_method_all = min(valid_candidates_all, key=valid_candidates_all.get)
        best_delta_all = valid_candidates_all[best_method_all]
    else:
        best_method_all = None
        best_delta_all = np.nan

    candidates_normal = {
        "m1_neg_normal": m1_norm_delta,
        "m2_neg_normal": m2_norm_delta,
    }

    valid_candidates_normal = {
        k: v for k, v in candidates_normal.items()
        if pd.notna(v)
    }

    if valid_candidates_normal:
        best_method_normal = min(valid_candidates_normal, key=valid_candidates_normal.get)
        best_delta_normal = valid_candidates_normal[best_method_normal]
    else:
        best_method_normal = None
        best_delta_normal = np.nan

    # -----------------------------------------------------
    # 7) lambda / gopt diagnostic
    # -----------------------------------------------------
    oco_lambda_vals = list_meta_values(meta_oco, "base_lambda")
    adi_lambda_vals = list_meta_values(meta_adi, "base_lambda")

    oco_lambda_max_vals = list_meta_values(meta_oco, "lambda_max")
    adi_lambda_max_vals = list_meta_values(meta_adi, "lambda_max")

    oco_gopt_vals = list_meta_values(meta_oco, "gopt")
    adi_gopt_vals = list_meta_values(meta_adi, "gopt")

    summary = {
        "LOT_ID": current_lot,
        "Wafer": current_wafer,
        "_wafer_id": current_wafer_id,
        "seq_idx": seq_idx,
        "current_lot_seq_idx": current_lot_seq_idx,
        "wafer_time": current_key.get("wafer_time", pd.NaT),

        "history_lots": ", ".join(hist_lots),
        "n_history_lots": len(hist_lots),
        "history_oco_wafer_ids": ", ".join(hist_oco_wafer_ids),
        "history_adi_wafer_ids": ", ".join(hist_adi_wafer_ids),
        "n_history_oco_wafers": len(hist_oco_wafer_ids),
        "n_history_adi_wafers": len(hist_adi_wafer_ids),

        "base_y_col": base_y_col,
        "psm_extract_target_col": PSM_EXTRACT_TARGET_COL,
        "old_psm_col": OLD_PSM_COL,

        "remove_test_fpt_before_cpe": REMOVE_TEST_FPT_BEFORE_CPE,
        "test_fpt_mode": TEST_FPT_MODE,
        "oco_test_fpt_m3s_y": m3s_y(fpt_oco["test_fpt_y"]) if len(fpt_oco) else np.nan,
        "adi_test_fpt_m3s_y": m3s_y(fpt_adi["test_fpt_y"]) if len(fpt_adi) else np.nan,
        "n_oco_test_fpt": len(fpt_oco),
        "n_adi_test_fpt": len(fpt_adi),
        "oco_test_fpt_abs_median": float(np.nanmedian(np.abs(fpt_oco["test_fpt_y"]))) if len(fpt_oco) else np.nan,
        "adi_test_fpt_abs_median": float(np.nanmedian(np.abs(fpt_adi["test_fpt_y"]))) if len(fpt_adi) else np.nan,

        "gopt_spec": G_OPT_SPEC,
        "gopt_tolerance": G_OPT_TOLERANCE,
        "minimum_ridge": MINIMUM_RIDGE,
        "add_ridge": ADD_RIDGE,
        "goptimal_type": G_OPTIMAL_TYPE,
        "use_virtual_chip_points": USE_VIRTUAL_CHIP_POINTS,
        "use_span_box_constraint": USE_SPAN_BOX_CONSTRAINT,

        "normal_shot_min_points": NORMAL_SHOT_MIN_POINTS,
        "normal_compare_mask": "is_normal_shot_m2 = OCO_and_ADI_normal_shots",

        "n_rows_current": len(cur),
        "n_shot_total": n_shot_total,
        "n_shot_m1_success": n_shot_m1,
        "n_shot_m2_success": n_shot_m2,
        "n_normal_shot_m1": n_normal_shot_m1,
        "n_normal_shot_m2": n_normal_shot_m2,

        "status_baseline_reg": status_base,
        "status_m1_neg_reg": status_m1_neg,
        "status_m2_neg_reg": status_m2_neg,

        "baseline_m3s_y_all": baseline_m3s_all,

        "m1_neg_all_n_rows_valid": m1_all_n,
        "m1_neg_all_baseline_m3s_y": m1_all_base,
        "m1_neg_all_sim_m3s_y": m1_all_sim,
        "m1_neg_all_delta_m3s_y": m1_all_delta,

        "m2_neg_all_n_rows_valid": m2_all_n,
        "m2_neg_all_baseline_m3s_y": m2_all_base,
        "m2_neg_all_sim_m3s_y": m2_all_sim,
        "m2_neg_all_delta_m3s_y": m2_all_delta,

        "m1_neg_normal_n_rows_valid": m1_norm_n,
        "m1_neg_normal_baseline_m3s_y": m1_norm_base,
        "m1_neg_normal_sim_m3s_y": m1_norm_sim,
        "m1_neg_normal_delta_m3s_y": m1_norm_delta,

        "m2_neg_normal_n_rows_valid": m2_norm_n,
        "m2_neg_normal_baseline_m3s_y": m2_norm_base,
        "m2_neg_normal_sim_m3s_y": m2_norm_sim,
        "m2_neg_normal_delta_m3s_y": m2_norm_delta,

        "best_method_all": best_method_all,
        "best_delta_all_m3s_y": best_delta_all,
        "best_method_normal": best_method_normal,
        "best_delta_normal_m3s_y": best_delta_normal,

        "fit_oco_m3s_y": m3s_y(cur["fit_oco_y"]),
        "fit_adi_m3s_y": m3s_y(cur["fit_adi_y"]),
        "fit_skew_m3s_y": m3s_y(cur["fit_skew_y"]),

        "corr_baseline_resid_fit_oco": safe_corr(cur["baseline_residual_y"], cur["fit_oco_y"]),
        "corr_baseline_resid_fit_adi": safe_corr(cur["baseline_residual_y"], cur["fit_adi_y"]),
        "corr_baseline_resid_fit_skew": safe_corr(cur["baseline_residual_y"], cur["fit_skew_y"]),
        "corr_fit_oco_fit_adi": safe_corr(cur["fit_oco_y"], cur["fit_adi_y"]),
        "corr_fit_oco_fit_skew": safe_corr(cur["fit_oco_y"], cur["fit_skew_y"]),
        "corr_fit_adi_fit_skew": safe_corr(cur["fit_adi_y"], cur["fit_skew_y"]),

        "normal_fit_oco_m3s_y": m3s_y(cur.loc[normal_compare_mask, "fit_oco_y"]),
        "normal_fit_adi_m3s_y": m3s_y(cur.loc[normal_compare_mask, "fit_adi_y"]),
        "normal_fit_skew_m3s_y": m3s_y(cur.loc[normal_compare_mask, "fit_skew_y"]),
        "normal_corr_fit_oco_fit_adi": safe_corr(
            cur.loc[normal_compare_mask, "fit_oco_y"],
            cur.loc[normal_compare_mask, "fit_adi_y"],
        ),

        "oco_base_lambda_median": safe_nanmedian(oco_lambda_vals),
        "oco_base_lambda_min": safe_nanmin(oco_lambda_vals),
        "oco_base_lambda_max": safe_nanmax(oco_lambda_vals),
        "adi_base_lambda_median": safe_nanmedian(adi_lambda_vals),
        "adi_base_lambda_min": safe_nanmin(adi_lambda_vals),
        "adi_base_lambda_max": safe_nanmax(adi_lambda_vals),

        "oco_lambda_max_median": safe_nanmedian(oco_lambda_max_vals),
        "adi_lambda_max_median": safe_nanmedian(adi_lambda_max_vals),

        "oco_gopt_median": safe_nanmedian(oco_gopt_vals),
        "adi_gopt_median": safe_nanmedian(adi_gopt_vals),
        "oco_gopt_min": safe_nanmin(oco_gopt_vals),
        "oco_gopt_max": safe_nanmax(oco_gopt_vals),
        "adi_gopt_min": safe_nanmin(adi_gopt_vals),
        "adi_gopt_max": safe_nanmax(adi_gopt_vals),
    }

    cur["sim_LOT_ID"] = current_lot
    cur["sim_Wafer"] = current_wafer
    cur["sim_seq_idx"] = seq_idx
    cur["sim_history_lots"] = ", ".join(hist_lots)

    meta_rows = []
    meta_rows.extend(make_meta_df(meta_oco, current_lot, current_wafer, seq_idx, source="OCO"))
    meta_rows.extend(make_meta_df(meta_adi, current_lot, current_wafer, seq_idx, source="ADI"))

    fpt_rows = []
    fpt_rows.extend(fpt_rows_for_output(fpt_oco, current_lot, current_wafer, seq_idx, "OCO", hist_lots))
    fpt_rows.extend(fpt_rows_for_output(fpt_adi, current_lot, current_wafer, seq_idx, "ADI", hist_lots))

    return cur, summary, (coef_rows_m1, coef_rows_m2), meta_rows, fpt_rows


# =========================================================
# 12. Excel writer
# =========================================================
def write_excel_xlwings(path, sheet_dict):
    if not XLWINGS_AVAILABLE:
        print("xlwings 사용 불가. Excel 저장은 건너뜁니다.")
        return

    path = os.path.abspath(path)

    if os.path.exists(path):
        os.remove(path)

    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    app.screen_updating = False

    try:
        wb = app.books.add()

        for i, (sheet_name, df) in enumerate(sheet_dict.items()):
            safe_name = str(sheet_name)[:31]

            if i == 0:
                sht = wb.sheets[0]
                sht.name = safe_name
            else:
                sht = wb.sheets.add(name=safe_name, after=wb.sheets[-1])

            sht.clear()

            if df is None or len(df) == 0:
                sht.range("A1").value = "No data"
                continue

            sht.range("A1").options(index=False, header=True).value = df

            used = sht.used_range
            used.api.Font.Name = "맑은 고딕"
            used.api.Font.Size = 10

            header = sht.range((1, 1), (1, len(df.columns)))
            header.api.Font.Bold = True
            header.color = (217, 234, 247)

            try:
                used.api.AutoFilter()
            except Exception:
                pass

            sht.autofit()

        wb.save(path)
        wb.close()

    finally:
        app.quit()

    print(f"Excel 저장 완료: {path}")


# =========================================================
# 13. Overall summary
# =========================================================
def build_overall_summary(df_summary):
    if len(df_summary) == 0:
        return pd.DataFrame()

    metric_cols = [
        "baseline_m3s_y_all",

        "m1_neg_all_sim_m3s_y",
        "m1_neg_all_delta_m3s_y",
        "m2_neg_all_sim_m3s_y",
        "m2_neg_all_delta_m3s_y",

        "m1_neg_normal_sim_m3s_y",
        "m1_neg_normal_delta_m3s_y",
        "m2_neg_normal_sim_m3s_y",
        "m2_neg_normal_delta_m3s_y",

        "fit_oco_m3s_y",
        "fit_adi_m3s_y",
        "fit_skew_m3s_y",

        "normal_fit_oco_m3s_y",
        "normal_fit_adi_m3s_y",
        "normal_fit_skew_m3s_y",

        "oco_test_fpt_m3s_y",
        "adi_test_fpt_m3s_y",

        "oco_base_lambda_median",
        "adi_base_lambda_median",
        "oco_gopt_median",
        "adi_gopt_median",
    ]

    rows = []

    for col in metric_cols:
        if col not in df_summary.columns:
            continue

        s = pd.to_numeric(df_summary[col], errors="coerce").dropna()

        if len(s) == 0:
            continue

        rows.append({
            "metric": col,
            "count": int(len(s)),
            "mean": float(s.mean()),
            "std": float(s.std(ddof=1)) if len(s) > 1 else np.nan,
            "min": float(s.min()),
            "p25": float(s.quantile(0.25)),
            "median": float(s.median()),
            "p75": float(s.quantile(0.75)),
            "max": float(s.max()),
        })

    return pd.DataFrame(rows)


# =========================================================
# 14. Main
# =========================================================
def main():
    print("=" * 100)
    print("[LOAD PARQUET]")
    print("=" * 100)

    df_adi = pd.read_parquet(ADI_PATH)
    df_oco = pd.read_parquet(OCO_PATH)

    print("ADI:", df_adi.shape)
    print("OCO:", df_oco.shape)

    base_y_col = find_first_existing_col(df_oco, BASE_Y_COL_CANDIDATES)

    if base_y_col is None:
        raise ValueError(f"OCO에서 base Y column을 찾지 못했습니다. 후보: {BASE_Y_COL_CANDIDATES}")

    print("Base Y column for application:", base_y_col)
    print("PSM extract target column:", PSM_EXTRACT_TARGET_COL)
    print("Old PSM column:", OLD_PSM_COL)
    print("History LOT count:", HISTORY_N_LOTS)
    print("Remove TEST FPT:", REMOVE_TEST_FPT_BEFORE_CPE)
    print("TEST FPT mode:", TEST_FPT_MODE)
    print("G_OPT_SPEC:", G_OPT_SPEC)
    print("G_OPT_TOLERANCE:", G_OPT_TOLERANCE)
    print("MINIMUM_RIDGE:", MINIMUM_RIDGE)
    print("ADD_RIDGE:", ADD_RIDGE)
    print("G_OPTIMAL_TYPE:", G_OPTIMAL_TYPE)
    print("Normal shot min points:", NORMAL_SHOT_MIN_POINTS)

    require_columns(
        df_oco,
        [base_y_col, OLD_PSM_COL, PSM_EXTRACT_TARGET_COL, "TEST"],
        label="OCO"
    )

    require_columns(
        df_adi,
        [PSM_EXTRACT_TARGET_COL, "TEST"],
        label="ADI"
    )

    df_adi = add_round_keys(df_adi, key_decimals=KEY_DECIMALS)
    df_oco = add_round_keys(df_oco, key_decimals=KEY_DECIMALS)

    print("=" * 100)
    print("[MAKE WAFER / LOT SEQUENCE]")
    print("=" * 100)

    seq_df = make_wafer_sequence(df_oco)
    seq_df, lot_seq_df = add_lot_sequence_to_wafer_sequence(seq_df)

    print(seq_df.head(20))
    print("total wafer sequence:", len(seq_df))
    print("total lot sequence:", len(lot_seq_df))
    print(lot_seq_df.head(20))

    row_results = []
    summary_rows = []
    coef_rows_m1_all = []
    coef_rows_m2_all = []
    meta_rows_all = []
    fpt_rows_all = []

    print("=" * 100)
    print("[RUN SIMULATION]")
    print("=" * 100)

    for _, current_key in seq_df.iterrows():
        seq_idx = int(current_key["seq_idx"])

        # current LOT 기준 직전 LOT 5개가 없으면 skip
        if int(current_key["lot_seq_idx"]) < HISTORY_N_LOTS:
            continue

        print(
            f"simulate seq={seq_idx}, "
            f"lot_seq={int(current_key['lot_seq_idx'])}, "
            f"wafer={current_key['_wafer_id']}"
        )

        row_df, summary, coef_pair, meta_rows, fpt_rows = simulate_current_wafer(
            current_key=current_key,
            seq_idx=seq_idx,
            seq_df=seq_df,
            lot_seq_df=lot_seq_df,
            df_oco=df_oco,
            df_adi=df_adi,
            base_y_col=base_y_col,
        )

        if row_df is None:
            continue

        if SAVE_ALL_ROW_RESULTS:
            row_results.append(row_df)

        summary_rows.append(summary)

        coef_m1, coef_m2 = coef_pair
        coef_rows_m1_all.extend(coef_m1)
        coef_rows_m2_all.extend(coef_m2)
        meta_rows_all.extend(meta_rows)
        fpt_rows_all.extend(fpt_rows)

    df_rows = pd.concat(row_results, ignore_index=True) if row_results else pd.DataFrame()
    df_summary = pd.DataFrame(summary_rows)
    df_meta = pd.DataFrame(meta_rows_all)
    df_fpt = pd.DataFrame(fpt_rows_all)

    df_coef_m1_long = make_coef_long(
        coef_rows_m1_all,
        method_name="method1_oco_fit_neg"
    )

    df_coef_m2_long = make_coef_long(
        coef_rows_m2_all,
        method_name="method2_oco_minus_adi_fit_neg"
    )

    df_overall_summary = build_overall_summary(df_summary)

    print("=" * 100)
    print("[RESULT SUMMARY]")
    print("=" * 100)

    print("row result:", df_rows.shape)
    print("summary:", df_summary.shape)
    print("fit meta:", df_meta.shape)
    print("fpt map:", df_fpt.shape)
    print("overall summary:", df_overall_summary.shape)

    if len(df_summary) > 0:
        print("\n전체 shot 기준 M1 delta")
        print(df_summary["m1_neg_all_delta_m3s_y"].describe())

        print("\n전체 shot 기준 M2 delta")
        print(df_summary["m2_neg_all_delta_m3s_y"].describe())

        print("\n정상 shot 기준 M1 delta")
        print(df_summary["m1_neg_normal_delta_m3s_y"].describe())

        print("\n정상 shot 기준 M2 delta")
        print(df_summary["m2_neg_normal_delta_m3s_y"].describe())

        print("\nfit_adi_m3s_y")
        print(df_summary["fit_adi_m3s_y"].describe())

        print("\nnormal_fit_adi_m3s_y")
        print(df_summary["normal_fit_adi_m3s_y"].describe())

        print("\nTEST FPT M3S")
        fpt_cols = [
            "oco_test_fpt_m3s_y",
            "adi_test_fpt_m3s_y",
            "oco_test_fpt_abs_median",
            "adi_test_fpt_abs_median",
        ]
        print(df_summary[fpt_cols].describe())

        print("\nbase lambda / GOPT median OCO/ADI")
        print(df_summary[[
            "oco_base_lambda_median",
            "adi_base_lambda_median",
            "oco_gopt_median",
            "adi_gopt_median",
        ]].describe())

        for col in ["m1_neg_all", "m2_neg_all", "m1_neg_normal", "m2_neg_normal"]:
            base_col = f"{col}_baseline_m3s_y"
            delta_col = f"{col}_delta_m3s_y"

            if base_col in df_summary.columns and delta_col in df_summary.columns:
                df_summary[f"{col}_improve_rate"] = (
                    -df_summary[delta_col] / df_summary[base_col]
                )

        improve_cols = [
            c for c in [
                "m1_neg_all_improve_rate",
                "m2_neg_all_improve_rate",
                "m1_neg_normal_improve_rate",
                "m2_neg_normal_improve_rate",
            ]
            if c in df_summary.columns
        ]

        if improve_cols:
            print("\nImprove rate summary")
            print(df_summary[improve_cols].describe())

    if SAVE_ALL_ROW_RESULTS and len(df_rows) > 0:
        df_rows.to_parquet(OUTPUT_ROW_PARQUET, index=False)
        print(f"Parquet 저장 완료: {OUTPUT_ROW_PARQUET}")

    df_summary.to_parquet(OUTPUT_SUMMARY_PARQUET, index=False)
    print(f"Parquet 저장 완료: {OUTPUT_SUMMARY_PARQUET}")

    write_excel_xlwings(
        OUTPUT_EXCEL,
        {
            "summary": df_summary,
            "overall_summary": df_overall_summary,
            "fit_meta": df_meta,
            "test_fpt_map": df_fpt,
            "wafer_sequence": seq_df,
            "lot_sequence": lot_seq_df,
            "coef_m1": df_coef_m1_long,
            "coef_m2": df_coef_m2_long,
            "row_result_sample": df_rows.head(200000) if len(df_rows) > 0 else df_rows,
        }
    )

    print("완료")


if __name__ == "__main__":
    main()
