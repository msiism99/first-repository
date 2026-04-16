# 17

import numpy as np
import pandas as pd

# =========================================================
# 입력 데이터 로드
# =========================================================
df_adi = pd.read_excel("df_final_adi_company_joint_reg.xlsx")
df_oco = pd.read_excel("df_final_oco_company_joint_reg.xlsx")


# =========================================================
# 회사 config 기준 값
# =========================================================
SPAN_MODE = "OVO3_38P_F2F"
RIDGE_G_OPT_SPEC = 1.0
RIDGE_G_OPT_TOLERANCE = 0.05
RIDGE_G_OPT_MAX_ITER = 100
RIDGE_MIN_LAMBDA = 1e-10
RIDGE_MAX_LAMBDA = 1e10
RIDGE_LAMBDA_INCREMENT = 0.1
ENABLE_RIDGE_SPAN_CONTROL = True
RIDGE_SPAN_TOLERANCE = 0.01
RIDGE_SPAN_MAX_ITER = 50
CPE_EVAL_GRID_N = 10
MIN_POINTS_GUIDE = 10   # skip 기준이 아니라 'few points 경고 기준'


# =========================================================
# 회사 룰: CPE 38para design matrix
# =========================================================
def cpe_38para(rx, ry):
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
        (rx ** 3 * ry ** 4) / 1e31
    ]).T

    X_dy = np.vstack([
        np.ones(len(ry)),
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12,
        (ry ** 4) / 1e19, (ry ** 3 * rx) / 1e19, (ry ** 2 * rx ** 2) / 1e19,
        (ry ** 5) / 1e23, (ry ** 4 * rx) / 1e23, (ry ** 3 * rx ** 2) / 1e23,
        (ry ** 5 * rx) / 1e27, (ry ** 4 * rx ** 2) / 1e27
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
# span limits
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


def get_active_span_limits(span_mode="OVO3_38P_F2F"):
    if span_mode == "OVO3_38P_HARDLIMIT":
        return RK_SPAN_LIMITS_OVO3_38P_HARDLIMIT
    return RK_SPAN_LIMITS_OVO3_38P_F2F


# =========================================================
# 유틸
# =========================================================
def _to_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def choose_base_lambda_scale(n_points):
    """
    포인트 수가 적을수록 초기 ridge를 더 강하게.
    """
    if n_points >= 10:
        return 1.0
    elif n_points >= 7:
        return 1e4
    elif n_points >= 5:
        return 1e6
    elif n_points >= 3:
        return 1e8
    else:
        return 1e10


def ridge_predict(X, y, lambdas):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    lambdas = np.asarray(lambdas, dtype=float)
    beta = np.linalg.solve(X.T @ X + np.diag(lambdas), X.T @ y)
    pred = X @ beta
    return beta, pred


def build_eval_grid_from_data(rx, ry, grid_n=10):
    rx = np.asarray(rx, dtype=float)
    ry = np.asarray(ry, dtype=float)

    rx_min, rx_max = np.nanmin(rx), np.nanmax(rx)
    ry_min, ry_max = np.nanmin(ry), np.nanmax(ry)

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


def compute_gopt_ridge(X_eval, X_fit, lambdas):
    inv_mat = np.linalg.inv(X_fit.T @ X_fit + np.diag(lambdas))
    h = np.einsum("ij,jk,ik->i", X_eval, inv_mat, X_eval)
    return float(np.sqrt(np.nanmax(h)))


def calc_span_per_coeff(X_eval, beta, coeff_names):
    spans = {}
    for i, name in enumerate(coeff_names):
        contrib = X_eval[:, i] * beta[i]
        spans[name] = float(np.nanmax(contrib) - np.nanmin(contrib))
    return spans


def find_span_violations(spans, span_limits, tolerance=0.01):
    violations = []
    for name, span in spans.items():
        if name not in span_limits:
            continue
        lo = span_limits[name]["min"] - tolerance
        hi = span_limits[name]["max"] + tolerance
        if span < lo or span > hi:
            violations.append((name, span, span_limits[name]["min"], span_limits[name]["max"]))
    return violations

def solve_ridge_with_gopt_and_span(
    X_fit,
    y,
    X_eval,
    coeff_names,
    span_limits,
    base_lambda_scale=1.0,
    gopt_spec=1.0,
    gopt_tol=0.05,   # 이제 직접 안 쓰고, 하위호환용으로만 둠
    gopt_max_iter=100,
    span_max_iter=50,
    min_lambda=1e-10,
    max_lambda=1e10,
    lambda_increment=0.1,
    span_tolerance=0.01,
    enable_span_control=True,
    debug=False,
    debug_label="",
):
    """
    개선 버전:
    - ridge 없이 g_opt < 1 이면 그대로 사용
    - ridge가 필요한 경우(g_opt >= 1)만
      최종 g_opt를 0.99 ~ 1.00 안에 넣도록 lambda 탐색
    - span control은 그 다음 balloon pushing 유지
    """

    n_param = X_fit.shape[1]
    init_lambda = max(min_lambda, min_lambda * base_lambda_scale)

    TARGET_LOW = 0.99
    TARGET_HIGH = 1.00

    def dprint(msg):
        if debug:
            prefix = f"[{debug_label}] " if debug_label else ""
            print(prefix + msg)

    def eval_with_scalar_lambda(lmbd):
        lambdas = np.full(n_param, lmbd, dtype=float)
        beta, pred = ridge_predict(X_fit, y, lambdas)
        gopt = compute_gopt_ridge(X_eval, X_fit, lambdas)
        return {
            "lambda": lmbd,
            "lambdas": lambdas,
            "beta": beta,
            "pred": pred,
            "gopt": gopt,
        }

    # -------------------------------------------------
    # A-0) ridge 없이 먼저 확인
    # -------------------------------------------------
    zero_ridge = eval_with_scalar_lambda(init_lambda)
    dprint(f"A-start: lambda={zero_ridge['lambda']:.3e}, gopt={zero_ridge['gopt']:.6f}, base_lambda_scale={base_lambda_scale:.3e}")

    # 이미 1 미만이면 그대로 사용
    if zero_ridge["gopt"] < gopt_spec:
        best = zero_ridge
        dprint("A-pass immediately: initial gopt < 1.0, no additional ridge needed")

    else:
        # -------------------------------------------------
        # A-1) gopt <= 1.00 되는 최초 bracket 찾기
        # -------------------------------------------------
        low = zero_ridge   # low: 아직 gopt >= 1
        high = None
        cur_lambda = init_lambda

        growth = max(2.0, 1.0 + 10.0 * lambda_increment)

        for i in range(gopt_max_iter):
            next_lambda = min(max_lambda, cur_lambda * growth)
            cand = eval_with_scalar_lambda(next_lambda)

            dprint(f"A-expand[{i+1}]: lambda={cand['lambda']:.3e}, gopt={cand['gopt']:.6f}")

            if cand["gopt"] <= TARGET_HIGH:
                high = cand
                break

            low = cand
            cur_lambda = next_lambda

            if cur_lambda >= max_lambda:
                break

        # 끝까지 못 찾으면 마지막 값 사용
        if high is None:
            best = low
            dprint("A-warning: no satisfying lambda found before max_lambda, using last candidate")
        else:
            dprint(
                f"A-bracket found: "
                f"low=({low['lambda']:.3e}, {low['gopt']:.6f}), "
                f"high=({high['lambda']:.3e}, {high['gopt']:.6f})"
            )

            # -------------------------------------------------
            # A-2) 1.00 아래로 최소 ridge 찾기
            #      -> 가능한 한 1.00에 가깝게
            # -------------------------------------------------
            best = high

            for i in range(min(15, gopt_max_iter)):
                lam_lo = low["lambda"]
                lam_hi = high["lambda"]
                g_lo = low["gopt"]
                g_hi = high["gopt"]

                if lam_hi <= lam_lo:
                    break

                log_lo = np.log(lam_lo)
                log_hi = np.log(lam_hi)

                # target은 1.00 바로 아래
                target = TARGET_HIGH

                if abs(g_lo - g_hi) < 1e-12:
                    log_mid = 0.5 * (log_lo + log_hi)
                else:
                    ratio = (target - g_lo) / (g_hi - g_lo)
                    ratio = float(np.clip(ratio, 0.15, 0.85))
                    log_mid = log_lo + ratio * (log_hi - log_lo)

                lam_mid = float(np.exp(log_mid))
                lam_mid = min(max(lam_mid, lam_lo * 1.001), lam_hi * 0.999)

                mid = eval_with_scalar_lambda(lam_mid)
                dprint(f"A-secant[{i+1}]: lambda={mid['lambda']:.3e}, gopt={mid['gopt']:.6f}")

                if mid["gopt"] <= TARGET_HIGH:
                    high = mid
                    best = mid
                else:
                    low = mid

                if (high["lambda"] / low["lambda"]) < 1.02:
                    dprint("A-secant stop: lambda bracket sufficiently tight")
                    break

            # -------------------------------------------------
            # A-3) 0.99 ~ 1.00 band 안에 최대한 넣기
            # -------------------------------------------------
            # high는 현재 gopt <= 1.00 후보
            # 이걸 가능한 한 0.99 이상으로 올리고 싶음
            for i in range(8):
                g = high["gopt"]

                # 이미 target band면 종료
                if TARGET_LOW <= g <= TARGET_HIGH:
                    dprint(f"A-band hit[{i+1}]: gopt={g:.6f}")
                    break

                # gopt가 너무 낮으면 ridge를 살짝 줄여본다
                if g < TARGET_LOW:
                    lam_try = np.sqrt(low["lambda"] * high["lambda"])
                    trial = eval_with_scalar_lambda(lam_try)
                    dprint(f"A-band refine[{i+1}]: lambda={trial['lambda']:.3e}, gopt={trial['gopt']:.6f}")

                    if trial["gopt"] <= TARGET_HIGH:
                        high = trial
                        best = trial
                    else:
                        low = trial
                else:
                    break

            best = high
            dprint(f"A-final: lambda={best['lambda']:.3e}, gopt={best['gopt']:.6f}")

    # A단계 결과
    lambdas = best["lambdas"].copy()
    beta = best["beta"].copy()
    pred = best["pred"].copy()
    gopt = best["gopt"]

    # -------------------------------------------------
    # B) span balloon pushing
    # -------------------------------------------------
    if enable_span_control:
        for i in range(span_max_iter):
            beta, pred = ridge_predict(X_fit, y, lambdas)
            spans = calc_span_per_coeff(X_eval, beta, coeff_names)
            violations = find_span_violations(spans, span_limits, tolerance=span_tolerance)

            current = {
                "beta": beta.copy(),
                "pred": pred.copy(),
                "gopt": compute_gopt_ridge(X_eval, X_fit, lambdas),
                "lambdas": lambdas.copy(),
                "spans": spans.copy(),
                "violations": violations.copy(),
            }

            if len(violations) == 0:
                dprint(f"B-pass: no span violation, final gopt={current['gopt']:.6f}")
                return current

            vio_names = [v[0] for v in violations]
            dprint(f"B-span[{i+1}]: {len(violations)} violations -> {vio_names}")

            for name, span, lo, hi in violations:
                if name in coeff_names:
                    j = coeff_names.index(name)
                    old_lambda = lambdas[j]
                    lambdas[j] = min(
                        max_lambda,
                        lambdas[j] * (1.0 + 5.0 * lambda_increment) + min_lambda * base_lambda_scale
                    )
                    dprint(
                        f"  push {name}: span={span:.6f}, limit=({lo:.6f},{hi:.6f}), "
                        f"lambda {old_lambda:.3e} -> {lambdas[j]:.3e}"
                    )

        beta, pred = ridge_predict(X_fit, y, lambdas)
        spans = calc_span_per_coeff(X_eval, beta, coeff_names)
        violations = find_span_violations(spans, span_limits, tolerance=span_tolerance)

        final_result = {
            "beta": beta.copy(),
            "pred": pred.copy(),
            "gopt": compute_gopt_ridge(X_eval, X_fit, lambdas),
            "lambdas": lambdas.copy(),
            "spans": spans.copy(),
            "violations": violations.copy(),
        }

        dprint(
            f"B-final after max_iter: gopt={final_result['gopt']:.6f}, "
            f"remaining_violations={len(violations)}"
        )
        return final_result

    dprint(f"No span control: final gopt={gopt:.6f}")
    return {
        "beta": beta.copy(),
        "pred": pred.copy(),
        "gopt": gopt,
        "lambdas": lambdas.copy(),
    }

def run_cpe38_ridge_shotwise_after_wkrk(
    df,
    label="ADI",
    wafer_cols=("LOT_ID", "Wafer"),
    shot_center_cols=("fcp_x", "fcp_y"),
    residual_cols=("residual_x", "residual_y"),
    shot_cols=("coordinate_X", "coordinate_Y"),
    span_mode="OVO3_38P_F2F",
    min_points_guide=10,
):
    """
    shot별 CPE38 ridge fitting.
    point가 적어도 skip하지 않고,
    base lambda를 키워서라도 결과를 산출한다.
    """
    df = df.copy()

    required = list(wafer_cols) + list(shot_center_cols) + list(residual_cols) + list(shot_cols)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"[{label}] 필수 컬럼 누락: {missing}")

    _to_numeric(df, list(shot_center_cols) + list(residual_cols) + list(shot_cols))

    for c in [
        "CPE_fit_x", "CPE_fit_y",
        "real_residual_x", "real_residual_y",
        "CPE_gopt_x", "CPE_gopt_y",
    ]:
        df[c] = np.nan

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
        if n_valid == 0:
            summary_rows.append({
                "LOT_ID": gkey[0],
                "Wafer": gkey[1],
                "fcp_x": gkey[2],
                "fcp_y": gkey[3],
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

        grid_rx, grid_ry = build_eval_grid_from_data(rx, ry, grid_n=CPE_EVAL_GRID_N)
        X_eval_dx, X_eval_dy = cpe_38para(grid_rx, grid_ry)

        few_points_flag = n_valid < min_points_guide
        base_lambda_scale = choose_base_lambda_scale(n_valid)

        fit_x = solve_ridge_with_gopt_and_span(
            X_fit=X_dx,
            y=residual_x,
            X_eval=X_eval_dx,
            coeff_names=CPE38_KEYS_DX,
            span_limits=span_limits,
            base_lambda_scale=base_lambda_scale,
            gopt_spec=RIDGE_G_OPT_SPEC,
            gopt_tol=RIDGE_G_OPT_TOLERANCE,
            gopt_max_iter=RIDGE_G_OPT_MAX_ITER,
            span_max_iter=RIDGE_SPAN_MAX_ITER,
            min_lambda=RIDGE_MIN_LAMBDA,
            max_lambda=RIDGE_MAX_LAMBDA,
            lambda_increment=RIDGE_LAMBDA_INCREMENT,
            span_tolerance=RIDGE_SPAN_TOLERANCE,
            enable_span_control=ENABLE_RIDGE_SPAN_CONTROL,
            debug=False,
            debug_label=f"{label}|{gkey[0]}|W{gkey[1]}|({gkey[2]:.0f},{gkey[3]:.0f})|X",
        )
        fit_y = solve_ridge_with_gopt_and_span(
            X_fit=X_dy,
            y=residual_y,
            X_eval=X_eval_dy,
            coeff_names=CPE38_KEYS_DY,
            span_limits=span_limits,
            base_lambda_scale=base_lambda_scale,
            gopt_spec=RIDGE_G_OPT_SPEC,
            gopt_tol=RIDGE_G_OPT_TOLERANCE,
            gopt_max_iter=RIDGE_G_OPT_MAX_ITER,
            span_max_iter=RIDGE_SPAN_MAX_ITER,
            min_lambda=RIDGE_MIN_LAMBDA,
            max_lambda=RIDGE_MAX_LAMBDA,
            lambda_increment=RIDGE_LAMBDA_INCREMENT,
            span_tolerance=RIDGE_SPAN_TOLERANCE,
            enable_span_control=ENABLE_RIDGE_SPAN_CONTROL,
            debug=False,
            debug_label=f"{label}|{gkey[0]}|W{gkey[1]}|({gkey[2]:.0f},{gkey[3]:.0f})|Y",
        )

        beta_x = fit_x["beta"]
        beta_y = fit_y["beta"]

        cpe_fit_x = fit_x["pred"]
        cpe_fit_y = fit_y["pred"]

        real_residual_x = residual_x - cpe_fit_x
        real_residual_y = residual_y - cpe_fit_y

        valid_idx = work.index

        df.loc[valid_idx, "CPE_fit_x"] = cpe_fit_x
        df.loc[valid_idx, "CPE_fit_y"] = cpe_fit_y
        df.loc[valid_idx, "real_residual_x"] = real_residual_x
        df.loc[valid_idx, "real_residual_y"] = real_residual_y
        df.loc[valid_idx, "CPE_gopt_x"] = fit_x["gopt"]
        df.loc[valid_idx, "CPE_gopt_y"] = fit_y["gopt"]

        coef_row = {
            "LOT_ID": gkey[0],
            "Wafer": gkey[1],
            "fcp_x": gkey[2],
            "fcp_y": gkey[3],
            "n_total": len(grp),
            "n_valid": n_valid,
            "few_points_flag": few_points_flag,
            "base_lambda_scale": base_lambda_scale,
            "gopt_x": fit_x["gopt"],
            "gopt_y": fit_y["gopt"],
        }
        for name, val in zip(CPE38_KEYS_DX, beta_x):
            coef_row[f"{name}_X"] = val
        for name, val in zip(CPE38_KEYS_DY, beta_y):
            coef_row[f"{name}_Y"] = val
        coef_rows.append(coef_row)

        summary_rows.append({
            "LOT_ID": gkey[0],
            "Wafer": gkey[1],
            "fcp_x": gkey[2],
            "fcp_y": gkey[3],
            "n_total": len(grp),
            "n_valid": n_valid,
            "few_points_flag": few_points_flag,
            "base_lambda_scale": base_lambda_scale,
            "gopt_x": fit_x["gopt"],
            "gopt_y": fit_y["gopt"],
            "rms_before_x": float(np.sqrt(np.nanmean(residual_x ** 2))),
            "rms_before_y": float(np.sqrt(np.nanmean(residual_y ** 2))),
            "rms_after_x": float(np.sqrt(np.nanmean(real_residual_x ** 2))),
            "rms_after_y": float(np.sqrt(np.nanmean(real_residual_y ** 2))),
            "status": "ok",
        })

    coef_df = pd.DataFrame(coef_rows)
    summary_df = pd.DataFrame(summary_rows)

    print(f"[{label}] shot별 CPE38 ridge 완료")
    print(f"  shot groups: {len(summary_df)}")
    print(f"  coef rows: {len(coef_df)}")
    if "few_points_flag" in summary_df.columns:
        print(f"  few points shots: {summary_df['few_points_flag'].sum()}")

    return df, coef_df, summary_df
