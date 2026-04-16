import numpy as np
import pandas as pd

# 데이터 로드
df_adi = pd.read_excel("df_final_adi_15.xlsx")
df_oco = pd.read_excel("df_final_oco_15.xlsx")


# =========================================================
# 회사 룰 기준 design matrix
# - wafer/field term: fcp_x, fcp_y
# - shot/internal term: coordinate_X, coordinate_Y
# =========================================================
def osr_wk20p_rk20p(x, y, rx, ry):
    """
    회사 코드의 osr_wk20p_rk20p 구조를 그대로 사용.
    x, y   : wafer/field level 좌표 -> fcp_x, fcp_y
    rx, ry : shot 내부 좌표         -> coordinate_X, coordinate_Y

    반환:
        X_dx: X 방향 회귀용 design matrix (N x 19)
        X_dy: Y 방향 회귀용 design matrix (N x 19)
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    rx = np.asarray(rx, dtype=float)
    ry = np.asarray(ry, dtype=float)

    X_dx = np.vstack([
        np.ones(len(x)),
        x / 1e6, -y / 1e6,
        (x ** 2) / 1e12, (x * y) / 1e12, (y ** 2) / 1e12,
        (x ** 3) / 1e15, (x ** 2 * y) / 1e15, (x * y ** 2) / 1e15, (y ** 3) / 1e15,
        rx / 1e6, -ry / 1e6,
        (rx ** 2) / 1e9, (rx * ry) / 1e9, (ry ** 2) / 1e9,
        (rx ** 3) / 1e12, (rx ** 2 * ry) / 1e12, (rx * ry ** 2) / 1e12, (ry ** 3) / 1e12,
    ]).T

    X_dy = np.vstack([
        np.ones(len(y)),
        y / 1e6, x / 1e6,
        (y ** 2) / 1e12, (y * x) / 1e12, (x ** 2) / 1e12,
        (y ** 3) / 1e15, (y ** 2 * x) / 1e15, (y * x ** 2) / 1e15, (x ** 3) / 1e15,
        ry / 1e6, rx / 1e6,
        (ry ** 2) / 1e9, (ry * rx) / 1e9, (rx ** 2) / 1e9,
        (ry ** 3) / 1e12, (ry ** 2 * rx) / 1e12, (ry * rx ** 2) / 1e12, (rx ** 3) / 1e12,
    ]).T

    return X_dx, X_dy


# =========================================================
# coefficient 이름 (회사 룰 순서)
# =========================================================
COEFF_KEYS_DX = [
    "WK1", "WK3", "WK5", "WK7", "WK9", "WK11", "WK13", "WK15", "WK17", "WK19",
    "RK3", "RK5", "RK7", "RK9", "RK11", "RK13", "RK15", "RK17", "RK19",
]

COEFF_KEYS_DY = [
    "WK2", "WK4", "WK6", "WK8", "WK10", "WK12", "WK14", "WK16", "WK18", "WK20",
    "RK4", "RK6", "RK8", "RK10", "RK12", "RK14", "RK16", "RK18", "RK20",
]

WK_COLS_DX = COEFF_KEYS_DX[:10]
RK_COLS_DX = COEFF_KEYS_DX[10:]

WK_COLS_DY = COEFF_KEYS_DY[:10]
RK_COLS_DY = COEFF_KEYS_DY[10:]


# =========================================================
# 유틸
# =========================================================
def normalize_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def fit_lstsq(X, y):
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    return coef, pred


# =========================================================
# wafer 단위 동시 regression
# =========================================================
def run_company_joint_regression(df, label="ADI", min_points=19):
    """
    wafer 단위로 raw_x/raw_y를 회사 룰 osr_wk20p_rk20p로 동시 회귀.

    입력:
      - raw_x, raw_y
      - fcp_x, fcp_y
      - coordinate_X, coordinate_Y
      - LOT_ID, Wafer

    출력:
      - wk_fit_x/y
      - rk_fit_x/y
      - total_fit_x/y
      - raw_minus_total_fit_x/y
      - wafer별 coefficient dataframe
    """
    df = df.copy()

    required_cols = [
        "LOT_ID", "Wafer",
        "raw_x", "raw_y",
        "fcp_x", "fcp_y",
        "coordinate_X", "coordinate_Y",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"[{label}] 필수 컬럼 누락: {missing}")

    normalize_numeric(df, [
        "raw_x", "raw_y",
        "fcp_x", "fcp_y",
        "coordinate_X", "coordinate_Y",
    ])

    # 결과 컬럼 초기화
    result_cols = [
        "wk_fit_x", "wk_fit_y",
        "rk_fit_x", "rk_fit_y",
        "total_fit_x", "total_fit_y",
        "raw_minus_total_fit_x", "raw_minus_total_fit_y",
    ]
    for c in result_cols:
        df[c] = np.nan

    coef_rows = []
    summary_rows = []

    for (lot_id, wafer), grp in df.groupby(["LOT_ID", "Wafer"], dropna=False):
        idx = grp.index

        valid_mask = (
            grp["raw_x"].notna() &
            grp["raw_y"].notna() &
            grp["fcp_x"].notna() &
            grp["fcp_y"].notna() &
            grp["coordinate_X"].notna() &
            grp["coordinate_Y"].notna()
        )

        work = grp.loc[valid_mask].copy()
        n_valid = len(work)

        if n_valid < min_points:
            summary_rows.append({
                "LOT_ID": lot_id,
                "Wafer": wafer,
                "n_total": len(grp),
                "n_valid": n_valid,
                "status": "skip_too_few_points",
            })
            continue

        x = work["fcp_x"].to_numpy(dtype=float)
        y = work["fcp_y"].to_numpy(dtype=float)
        rx = work["coordinate_X"].to_numpy(dtype=float)
        ry = work["coordinate_Y"].to_numpy(dtype=float)

        raw_x = work["raw_x"].to_numpy(dtype=float)
        raw_y = work["raw_y"].to_numpy(dtype=float)

        X_dx, X_dy = osr_wk20p_rk20p(x, y, rx, ry)

        # X 방향 동시 회귀
        coef_x, pred_x = fit_lstsq(X_dx, raw_x)

        # Y 방향 동시 회귀
        coef_y, pred_y = fit_lstsq(X_dy, raw_y)

        # WK / RK block 분리
        wk_fit_x = X_dx[:, :10] @ coef_x[:10]
        rk_fit_x = X_dx[:, 10:] @ coef_x[10:]

        wk_fit_y = X_dy[:, :10] @ coef_y[:10]
        rk_fit_y = X_dy[:, 10:] @ coef_y[10:]

        total_fit_x = wk_fit_x + rk_fit_x
        total_fit_y = wk_fit_y + rk_fit_y

        residual_x = raw_x - total_fit_x
        residual_y = raw_y - total_fit_y

        valid_idx = work.index

        df.loc[valid_idx, "wk_fit_x"] = wk_fit_x
        df.loc[valid_idx, "rk_fit_x"] = rk_fit_x
        df.loc[valid_idx, "total_fit_x"] = total_fit_x
        df.loc[valid_idx, "raw_minus_total_fit_x"] = residual_x

        df.loc[valid_idx, "wk_fit_y"] = wk_fit_y
        df.loc[valid_idx, "rk_fit_y"] = rk_fit_y
        df.loc[valid_idx, "total_fit_y"] = total_fit_y
        df.loc[valid_idx, "raw_minus_total_fit_y"] = residual_y

        # coefficient 저장
        coef_row = {
            "LOT_ID": lot_id,
            "Wafer": wafer,
            "n_total": len(grp),
            "n_valid": n_valid,
        }
        for name, val in zip(COEFF_KEYS_DX, coef_x):
            coef_row[f"{name}_X"] = val
        for name, val in zip(COEFF_KEYS_DY, coef_y):
            coef_row[f"{name}_Y"] = val
        coef_rows.append(coef_row)

        summary_rows.append({
            "LOT_ID": lot_id,
            "Wafer": wafer,
            "n_total": len(grp),
            "n_valid": n_valid,
            "rms_raw_x": float(np.sqrt(np.nanmean(raw_x ** 2))),
            "rms_raw_y": float(np.sqrt(np.nanmean(raw_y ** 2))),
            "rms_residual_x": float(np.sqrt(np.nanmean(residual_x ** 2))),
            "rms_residual_y": float(np.sqrt(np.nanmean(residual_y ** 2))),
            "status": "ok",
        })

    coef_df = pd.DataFrame(coef_rows)
    summary_df = pd.DataFrame(summary_rows)

    print(f"[{label}] regression 완료")
    print(f"  - wafer 수: {df[['LOT_ID','Wafer']].drop_duplicates().shape[0]}")
    print(f"  - coefficient rows: {len(coef_df)}")
    print(f"  - summary rows: {len(summary_df)}")

    return df, coef_df, summary_df


df_adi_reg, coef_adi, summary_adi = run_company_joint_regression(df_adi, label="ADI")
df_oco_reg, coef_oco, summary_oco = run_company_joint_regression(df_oco, label="OCO")

df_adi_reg.to_excel("df_final_adi_company_joint_reg.xlsx", index=False)
df_oco_reg.to_excel("df_final_oco_company_joint_reg.xlsx", index=False)

coef_adi.to_excel("coef_adi_company_joint_reg.xlsx", index=False)
coef_oco.to_excel("coef_oco_company_joint_reg.xlsx", index=False)

summary_adi.to_excel("summary_adi_company_joint_reg.xlsx", index=False)
summary_oco.to_excel("summary_oco_company_joint_reg.xlsx", index=False)
