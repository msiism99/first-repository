# -*- coding: utf-8 -*-
"""
PSM_Ph2_MRCPSM.py

MRC 공통 보정 + PSM M1/M2 분리 시뮬레이션 버전.

원본 PSM_Ph2.py는 보존하고, 해당 모듈의 main/output/utility 함수는 재사용한다.
이 파일은 simulate_current_wafer()만 새 목적에 맞게 교체한다.

Flow
----
1) 직전 5 LOT history에서 ADI/OCO raw_y 기준 point별 평균 wafer를 만든다.
2) OCO raw_y company WK/RK fit - ADI raw_y company WK/RK fit = 신규 공통 MRC 성분으로 정의한다.
3) ADI/OCO history raw_y와 current raw_y에서 위 MRC 성분을 제거한다.
4) MRC 제거 후 residual에서 TEST fingerprint를 제거해 real_residual을 만든다.
5) M1 PSM = OCO real_residual CPE33 fit의 NEG 방향.
6) M2 PSM = OCO real residual CPE33 model - ADI real residual CPE33 model의 NEG 방향.

주의
----
M2는 OCO/ADI point_key를 inner merge하지 않는다.
OCO와 ADI의 측정 point가 완전히 일치하지 않아도 shot별 CPE model을 각각 fit한 뒤 beta 차이로 skew model을 만든다.

해석
----
- new_mrc_y_common_neg = -(OCO_raw_company_fit - ADI_raw_company_fit)
- y_after_new_mrc = raw_y + new_mrc_y_common_neg
- M1: y_sim = y_after_new_mrc - fit(OCO_real_residual)
- M2: y_sim = y_after_new_mrc - [fit(OCO_real_residual) - fit(ADI_real_residual)]
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

import PSM_Ph2 as base


RAW_TARGET_COL = "raw_y"
MRC_REMOVED_COL = "mrc_removed_residual_y"
REAL_RESIDUAL_COL = "real_residual_y"


# 새 버전 output은 원본과 분리 저장
base.PSM_EXTRACT_TARGET_COL = RAW_TARGET_COL
base.OUTPUT_EXCEL = "psm_apply_simulation_y_lot5_mrcpsm_cpe33_gopt.xlsx"
base.OUTPUT_ROW_PARQUET = "psm_apply_simulation_y_lot5_mrcpsm_cpe33_gopt_rows.parquet"
base.OUTPUT_SUMMARY_PARQUET = "psm_apply_simulation_y_lot5_mrcpsm_cpe33_gopt_summary.parquet"


def _numeric(s) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def fit_company_y_model(df: pd.DataFrame, target_col: str, label: str) -> Tuple[Optional[Dict], Dict]:
    """회사 WK/RK Y matrix로 history 평균 wafer 또는 wafer-shaped data를 fit."""
    meta = {
        "label": label,
        "target_col": target_col,
        "status": "init",
        "n_points": 0,
        "rank": np.nan,
        "cond": np.nan,
        "target_m3s": np.nan,
        "fit_m3s": np.nan,
        "residual_m3s": np.nan,
    }

    required = ["fcp_x", "fcp_y", "coordinate_X", "coordinate_Y", target_col]
    missing = [c for c in required if c not in df.columns]
    if missing:
        meta["status"] = f"missing_cols:{missing}"
        return None, meta

    work = df.copy()
    for c in required:
        work[c] = _numeric(work[c])

    valid = (
        work["fcp_x"].notna() &
        work["fcp_y"].notna() &
        work["coordinate_X"].notna() &
        work["coordinate_Y"].notna() &
        work[target_col].notna()
    )
    work = work.loc[valid].copy()
    meta["n_points"] = int(len(work))

    if len(work) < base.MIN_POINTS_REGRESSION:
        meta["status"] = "skip_too_few_points"
        return None, meta

    x = work["fcp_x"].to_numpy(dtype=float)
    y = work["fcp_y"].to_numpy(dtype=float)
    rx = work["coordinate_X"].to_numpy(dtype=float)
    ry = work["coordinate_Y"].to_numpy(dtype=float)
    yy = work[target_col].to_numpy(dtype=float)

    X = base.company_y_matrix(x, y, rx, ry)

    try:
        meta["rank"] = int(np.linalg.matrix_rank(X))
    except Exception:
        meta["rank"] = np.nan

    try:
        meta["cond"] = float(np.linalg.cond(X))
    except Exception:
        meta["cond"] = np.nan

    coef, pred = base.fit_lstsq(X, yy)
    resid = yy - pred

    meta.update({
        "status": "ok",
        "target_m3s": base.m3s_y(yy),
        "fit_m3s": base.m3s_y(pred),
        "residual_m3s": base.m3s_y(resid),
    })

    return {
        "coef": coef,
        "pred": pred,
        "meta": meta,
    }, meta


def predict_company_y(df: pd.DataFrame, coef: Optional[np.ndarray]) -> np.ndarray:
    pred = np.full(len(df), np.nan, dtype=float)
    if coef is None or len(df) == 0:
        return pred

    required = ["fcp_x", "fcp_y", "coordinate_X", "coordinate_Y"]
    if any(c not in df.columns for c in required):
        return pred

    x = _numeric(df["fcp_x"])
    y = _numeric(df["fcp_y"])
    rx = _numeric(df["coordinate_X"])
    ry = _numeric(df["coordinate_Y"])

    valid = x.notna() & y.notna() & rx.notna() & ry.notna()
    if valid.sum() == 0:
        return pred

    X = base.company_y_matrix(
        x.loc[valid].to_numpy(dtype=float),
        y.loc[valid].to_numpy(dtype=float),
        rx.loc[valid].to_numpy(dtype=float),
        ry.loc[valid].to_numpy(dtype=float),
    )
    pred[np.where(valid.to_numpy())[0]] = X @ coef
    return pred


def add_mrc_removed_residual(df: pd.DataFrame, beta_mrc_delta: np.ndarray, label: str) -> pd.DataFrame:
    """raw_y에서 공통 신규 MRC 성분을 제거한 residual 생성."""
    out = df.copy()
    out["mrc_delta_fit_y"] = predict_company_y(out, beta_mrc_delta)
    out["new_mrc_y_common_neg"] = -out["mrc_delta_fit_y"]
    out[MRC_REMOVED_COL] = _numeric(out[RAW_TARGET_COL]) + out["new_mrc_y_common_neg"]
    out["mrc_residual_source"] = label
    return out


def add_real_residual_by_test_fpt(df: pd.DataFrame, source_name: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """MRC 제거 residual에서 TEST fingerprint 제거."""
    fpt = base.calc_test_fpt_map(
        df,
        target_col=MRC_REMOVED_COL,
        mode=base.TEST_FPT_MODE,
    )

    out = base.apply_test_fpt_removal(
        df,
        target_col=MRC_REMOVED_COL,
        fpt_df=fpt,
        source_name=source_name,
    )
    out[REAL_RESIDUAL_COL] = out["target_y_fpt_removed"]
    return out, fpt


def build_m2_model_from_model_difference(model_oco: Dict, meta_oco: Dict, model_adi: Dict, meta_adi: Dict):
    """OCO/ADI point merge 대신, 같은 shot_key의 CPE beta 차이로 M2 skew model 생성."""
    model_m2 = {}
    meta_m2 = {}

    common_shots = sorted(set(model_oco.keys()) & set(model_adi.keys()))

    for shot_key in common_shots:
        beta_oco = np.asarray(model_oco[shot_key]["beta"], dtype=float)
        beta_adi = np.asarray(model_adi[shot_key]["beta"], dtype=float)
        beta_skew = beta_oco - beta_adi

        model_m2[shot_key] = {
            "method": f"model_diff:{model_oco[shot_key].get('method')}/{model_adi[shot_key].get('method')}",
            "beta": beta_skew,
            "lambdas": np.nanmax(np.vstack([
                np.asarray(model_oco[shot_key].get("lambdas", np.full_like(beta_skew, np.nan)), dtype=float),
                np.asarray(model_adi[shot_key].get("lambdas", np.full_like(beta_skew, np.nan)), dtype=float),
            ]), axis=0),
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
            "n_points": min(
                model_oco[shot_key].get("n_points", 0),
                model_adi[shot_key].get("n_points", 0),
            ),
            "n_virtual": np.nanmax([
                model_oco[shot_key].get("n_virtual", np.nan),
                model_adi[shot_key].get("n_virtual", np.nan),
            ]),
            "inner_or_partial": "model_diff",
            "span_violation_count": np.nanmax([
                model_oco[shot_key].get("span_violation_count", np.nan),
                model_adi[shot_key].get("span_violation_count", np.nan),
            ]),
        }

        mo = meta_oco.get(shot_key, {})
        ma = meta_adi.get(shot_key, {})
        meta_m2[shot_key] = {
            "status": "ok",
            "n_points": min(mo.get("n_points", 0), ma.get("n_points", 0)),
            "n_terms": len(base.CPE33_KEYS_DY),
            "rank": min(mo.get("rank", np.nan), ma.get("rank", np.nan)),
            "cond": np.nanmax([mo.get("cond", np.nan), ma.get("cond", np.nan)]),
            "target_m3s": np.nan,
            "fit_m3s": np.nan,
            "fit_over_target": np.nan,
            "gopt": model_m2[shot_key]["gopt"],
            "base_lambda": model_m2[shot_key]["base_lambda"],
            "lambda_max": model_m2[shot_key]["lambda_max"],
            "gopt_iter": np.nan,
            "span_iter": np.nan,
            "span_violation_count": model_m2[shot_key]["span_violation_count"],
            "method": model_m2[shot_key]["method"],
            "inner_or_partial": "model_diff",
            "n_virtual": model_m2[shot_key]["n_virtual"],
            "n_virtual_full": np.nan,
            "virtual_source": "model_difference_no_point_merge",
            "base_lambda_scale": np.nan,
        }

    return model_m2, meta_m2


def _coef_row(current_lot, current_wafer, seq_idx, shot_key, model, method: str) -> Dict:
    return {
        "current_LOT_ID": current_lot,
        "current_Wafer": current_wafer,
        "current_seq_idx": seq_idx,
        "shot_key": shot_key,
        "beta": model["beta"],
        "cpe_fit_method": method,
        "base_lambda": model.get("base_lambda", np.nan),
        "lambda_max": model.get("lambda_max", np.nan),
        "gopt": model.get("gopt", np.nan),
    }


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

    hist_lots = base.get_history_lots_for_current_lot(
        current_key=current_key,
        lot_seq_df=lot_seq_df,
        n_lots=base.HISTORY_N_LOTS,
    )

    cur = df_oco[df_oco["_wafer_id"] == current_wafer_id].copy()
    hist_oco = df_oco[df_oco["LOT_ID"].astype(str).isin(hist_lots)].copy()
    hist_adi = df_adi[df_adi["LOT_ID"].astype(str).isin(hist_lots)].copy()

    hist_oco_wafer_ids = sorted(hist_oco["_wafer_id"].dropna().astype(str).unique().tolist())
    hist_adi_wafer_ids = sorted(hist_adi["_wafer_id"].dropna().astype(str).unique().tolist())

    if len(cur) == 0 or len(hist_oco) == 0 or len(hist_adi) == 0:
        return None, None, None, None, None

    # -----------------------------------------------------
    # 1) 직전 5 LOT raw_y 기준 point 평균 wafer 생성
    # -----------------------------------------------------
    avg_oco_raw = base.average_history_by_point(hist_oco, RAW_TARGET_COL)
    avg_adi_raw = base.average_history_by_point(hist_adi, RAW_TARGET_COL)

    # -----------------------------------------------------
    # 2) OCO raw_y K term - ADI raw_y K term = 신규 공통 MRC 성분
    # -----------------------------------------------------
    model_oco_mrc, meta_oco_mrc = fit_company_y_model(avg_oco_raw, "target_y", "OCO_raw_company")
    model_adi_mrc, meta_adi_mrc = fit_company_y_model(avg_adi_raw, "target_y", "ADI_raw_company")

    if model_oco_mrc is None or model_adi_mrc is None:
        return None, None, None, None, None

    beta_mrc_delta = model_oco_mrc["coef"] - model_adi_mrc["coef"]

    # -----------------------------------------------------
    # 3) ADI/OCO history와 current raw_y에서 신규 MRC 성분 제외
    # -----------------------------------------------------
    hist_oco_mrc_removed = add_mrc_removed_residual(hist_oco, beta_mrc_delta, "OCO")
    hist_adi_mrc_removed = add_mrc_removed_residual(hist_adi, beta_mrc_delta, "ADI")

    # -----------------------------------------------------
    # 4) TEST fingerprint 제외 -> real_residual
    # -----------------------------------------------------
    hist_oco_real, fpt_oco = add_real_residual_by_test_fpt(hist_oco_mrc_removed, "OCO")
    hist_adi_real, fpt_adi = add_real_residual_by_test_fpt(hist_adi_mrc_removed, "ADI")

    avg_oco_real = base.average_history_by_point(hist_oco_real, REAL_RESIDUAL_COL)
    avg_adi_real = base.average_history_by_point(hist_adi_real, REAL_RESIDUAL_COL)

    # -----------------------------------------------------
    # 5) M1: OCO real_residual로 CPE33 PSM 추출
    # 6) M2: OCO real residual model - ADI real residual model로 CPE33 PSM 추출
    # -----------------------------------------------------
    model_m1, meta_m1 = base.fit_history_model_by_shot(avg_oco_real)
    model_adi_diag, meta_adi_diag = base.fit_history_model_by_shot(avg_adi_real)
    model_m2, meta_m2 = build_m2_model_from_model_difference(
        model_m1,
        meta_m1,
        model_adi_diag,
        meta_adi_diag,
    )

    # -----------------------------------------------------
    # 현재 wafer simulation base 구성
    # -----------------------------------------------------
    cur["y_base"] = _numeric(cur[base_y_col])                  # actual current residual baseline
    cur["y_raw"] = _numeric(cur[RAW_TARGET_COL])               # old MRC/PSM decorrected raw shape
    cur["mrc_delta_fit_y"] = predict_company_y(cur, beta_mrc_delta)
    cur["new_mrc_y_common_neg"] = -cur["mrc_delta_fit_y"]
    cur["y_after_new_mrc"] = cur["y_raw"] + cur["new_mrc_y_common_neg"]

    cur["fit_oco_y"] = np.nan              # M1 OCO real residual fit
    cur["fit_adi_y"] = np.nan              # diagnostic ADI real residual fit
    cur["fit_skew_y"] = np.nan             # M2 model difference fit

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

        if shot_key in model_m1:
            fit_oco_real = base.predict_cpe33_y_model(rx, ry, model_m1[shot_key])
            new_psm_m1_neg = -fit_oco_real

            cur.loc[idx, "fit_oco_y"] = fit_oco_real
            cur.loc[idx, "new_psm_y_m1_neg"] = new_psm_m1_neg
            cur.loc[idx, "y_sim_m1_neg"] = cur.loc[idx, "y_after_new_mrc"].to_numpy(dtype=float) + new_psm_m1_neg

            n_shot_m1 += 1
            is_normal_m1 = (
                meta_m1.get(shot_key, {}).get("status") == "ok" and
                meta_m1.get(shot_key, {}).get("n_points", 0) >= base.NORMAL_SHOT_MIN_POINTS
            )
            cur.loc[idx, "is_normal_shot_m1"] = is_normal_m1
            if is_normal_m1:
                n_normal_shot_m1 += 1

            coef_rows_m1.append(_coef_row(
                current_lot, current_wafer, seq_idx, shot_key,
                model_m1[shot_key],
                method=model_m1[shot_key]["method"],
            ))

        if shot_key in model_adi_diag:
            cur.loc[idx, "fit_adi_y"] = base.predict_cpe33_y_model(rx, ry, model_adi_diag[shot_key])

        if shot_key in model_m2:
            fit_skew_real = base.predict_cpe33_y_model(rx, ry, model_m2[shot_key])
            new_psm_m2_neg = -fit_skew_real

            cur.loc[idx, "fit_skew_y"] = fit_skew_real
            cur.loc[idx, "new_psm_y_m2_neg"] = new_psm_m2_neg
            cur.loc[idx, "y_sim_m2_neg"] = cur.loc[idx, "y_after_new_mrc"].to_numpy(dtype=float) + new_psm_m2_neg

            n_shot_m2 += 1
            is_normal_m2 = (
                meta_m2.get(shot_key, {}).get("status") == "ok" and
                meta_m2.get(shot_key, {}).get("n_points", 0) >= base.NORMAL_SHOT_MIN_POINTS
            )
            cur.loc[idx, "is_normal_shot_m2"] = is_normal_m2
            if is_normal_m2:
                n_normal_shot_m2 += 1

            coef_rows_m2.append(_coef_row(
                current_lot, current_wafer, seq_idx, shot_key,
                model_m2[shot_key],
                method=model_m2[shot_key]["method"],
            ))

    # -----------------------------------------------------
    # baseline / simulation 각각 회사 WK/RK regression 후 residual M3S 비교
    # -----------------------------------------------------
    cur, coef_base_reg, status_base = base.regression_residual_y_for_wafer(
        cur,
        y_col="y_base",
        result_prefix="baseline",
    )
    cur, coef_mrc_only_reg, status_mrc_only = base.regression_residual_y_for_wafer(
        cur,
        y_col="y_after_new_mrc",
        result_prefix="mrc_only",
    )
    cur, coef_m1_neg_reg, status_m1_neg = base.regression_residual_y_for_wafer(
        cur,
        y_col="y_sim_m1_neg",
        result_prefix="m1_neg",
    )
    cur, coef_m2_neg_reg, status_m2_neg = base.regression_residual_y_for_wafer(
        cur,
        y_col="y_sim_m2_neg",
        result_prefix="m2_neg",
    )

    baseline_m3s_all = base.m3s_y(cur["baseline_residual_y"])
    mrc_only_m3s_all = base.m3s_y(cur["mrc_only_residual_y"])

    m1_all_n, m1_all_base, m1_all_sim, m1_all_delta = base.calc_delta_from_residuals(cur, "m1_neg_residual_y")
    m2_all_n, m2_all_base, m2_all_sim, m2_all_delta = base.calc_delta_from_residuals(cur, "m2_neg_residual_y")
    mrc_all_n, mrc_all_base, mrc_all_sim, mrc_all_delta = base.calc_delta_from_residuals(cur, "mrc_only_residual_y")

    normal_compare_mask = cur["is_normal_shot_m2"]
    m1_norm_n, m1_norm_base, m1_norm_sim, m1_norm_delta = base.calc_delta_from_residuals(
        cur, "m1_neg_residual_y", eval_mask=normal_compare_mask
    )
    m2_norm_n, m2_norm_base, m2_norm_sim, m2_norm_delta = base.calc_delta_from_residuals(
        cur, "m2_neg_residual_y", eval_mask=normal_compare_mask
    )
    mrc_norm_n, mrc_norm_base, mrc_norm_sim, mrc_norm_delta = base.calc_delta_from_residuals(
        cur, "mrc_only_residual_y", eval_mask=normal_compare_mask
    )

    candidates_all = {
        "m1_neg_all": m1_all_delta,
        "m2_neg_all": m2_all_delta,
    }
    valid_candidates_all = {k: v for k, v in candidates_all.items() if pd.notna(v)}
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
    valid_candidates_normal = {k: v for k, v in candidates_normal.items() if pd.notna(v)}
    if valid_candidates_normal:
        best_method_normal = min(valid_candidates_normal, key=valid_candidates_normal.get)
        best_delta_normal = valid_candidates_normal[best_method_normal]
    else:
        best_method_normal = None
        best_delta_normal = np.nan

    m1_lambda_vals = base.list_meta_values(meta_m1, "base_lambda")
    m2_lambda_vals = base.list_meta_values(meta_m2, "base_lambda")
    m1_lambda_max_vals = base.list_meta_values(meta_m1, "lambda_max")
    m2_lambda_max_vals = base.list_meta_values(meta_m2, "lambda_max")
    m1_gopt_vals = base.list_meta_values(meta_m1, "gopt")
    m2_gopt_vals = base.list_meta_values(meta_m2, "gopt")

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
        "psm_extract_target_col": RAW_TARGET_COL,
        "old_psm_col": base.OLD_PSM_COL,
        "mrc_strategy": "common_mrc_delta_from_OCO_raw_company_fit_minus_ADI_raw_company_fit",
        "psm_m1_strategy": "CPE33_fit_OCO_real_residual_NEG",
        "psm_m2_strategy": "CPE33_beta_difference_OCO_real_minus_ADI_real_NEG_no_point_merge",

        "remove_test_fpt_before_cpe": base.REMOVE_TEST_FPT_BEFORE_CPE,
        "test_fpt_mode": base.TEST_FPT_MODE,
        "oco_test_fpt_m3s_y": base.m3s_y(fpt_oco["test_fpt_y"]) if len(fpt_oco) else np.nan,
        "adi_test_fpt_m3s_y": base.m3s_y(fpt_adi["test_fpt_y"]) if len(fpt_adi) else np.nan,
        "n_oco_test_fpt": len(fpt_oco),
        "n_adi_test_fpt": len(fpt_adi),
        "oco_test_fpt_abs_median": float(np.nanmedian(np.abs(fpt_oco["test_fpt_y"]))) if len(fpt_oco) else np.nan,
        "adi_test_fpt_abs_median": float(np.nanmedian(np.abs(fpt_adi["test_fpt_y"]))) if len(fpt_adi) else np.nan,

        "normal_shot_min_points": base.NORMAL_SHOT_MIN_POINTS,
        "normal_compare_mask": "is_normal_shot_m2 = M2_common_shot_model_difference_normal_shots",

        "n_rows_current": len(cur),
        "n_shot_total": n_shot_total,
        "n_shot_m1_success": n_shot_m1,
        "n_shot_m2_success": n_shot_m2,
        "n_m2_common_model_shots": len(model_m2),
        "n_normal_shot_m1": n_normal_shot_m1,
        "n_normal_shot_m2": n_normal_shot_m2,

        "status_mrc_oco_raw_reg": meta_oco_mrc.get("status"),
        "status_mrc_adi_raw_reg": meta_adi_mrc.get("status"),
        "mrc_oco_raw_reg_rank": meta_oco_mrc.get("rank"),
        "mrc_adi_raw_reg_rank": meta_adi_mrc.get("rank"),
        "mrc_oco_raw_reg_cond": meta_oco_mrc.get("cond"),
        "mrc_adi_raw_reg_cond": meta_adi_mrc.get("cond"),
        "mrc_delta_coef_norm": float(np.linalg.norm(beta_mrc_delta)),
        "mrc_delta_fit_m3s_y": base.m3s_y(cur["mrc_delta_fit_y"]),

        "status_baseline_reg": status_base,
        "status_mrc_only_reg": status_mrc_only,
        "status_m1_neg_reg": status_m1_neg,
        "status_m2_neg_reg": status_m2_neg,

        "baseline_m3s_y_all": baseline_m3s_all,
        "mrc_only_m3s_y_all": mrc_only_m3s_all,
        "raw_y_m3s_y_all": base.m3s_y(cur["y_raw"]),
        "y_after_new_mrc_m3s_y_all": base.m3s_y(cur["y_after_new_mrc"]),

        "mrc_only_all_n_rows_valid": mrc_all_n,
        "mrc_only_all_baseline_m3s_y": mrc_all_base,
        "mrc_only_all_sim_m3s_y": mrc_all_sim,
        "mrc_only_all_delta_m3s_y": mrc_all_delta,

        "m1_neg_all_n_rows_valid": m1_all_n,
        "m1_neg_all_baseline_m3s_y": m1_all_base,
        "m1_neg_all_sim_m3s_y": m1_all_sim,
        "m1_neg_all_delta_m3s_y": m1_all_delta,

        "m2_neg_all_n_rows_valid": m2_all_n,
        "m2_neg_all_baseline_m3s_y": m2_all_base,
        "m2_neg_all_sim_m3s_y": m2_all_sim,
        "m2_neg_all_delta_m3s_y": m2_all_delta,

        "mrc_only_normal_n_rows_valid": mrc_norm_n,
        "mrc_only_normal_baseline_m3s_y": mrc_norm_base,
        "mrc_only_normal_sim_m3s_y": mrc_norm_sim,
        "mrc_only_normal_delta_m3s_y": mrc_norm_delta,

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

        "fit_oco_m3s_y": base.m3s_y(cur["fit_oco_y"]),
        "fit_adi_m3s_y": base.m3s_y(cur["fit_adi_y"]),
        "fit_skew_m3s_y": base.m3s_y(cur["fit_skew_y"]),

        "corr_baseline_resid_fit_oco": base.safe_corr(cur["baseline_residual_y"], cur["fit_oco_y"]),
        "corr_baseline_resid_fit_adi": base.safe_corr(cur["baseline_residual_y"], cur["fit_adi_y"]),
        "corr_baseline_resid_fit_skew": base.safe_corr(cur["baseline_residual_y"], cur["fit_skew_y"]),
        "corr_fit_oco_fit_adi": base.safe_corr(cur["fit_oco_y"], cur["fit_adi_y"]),
        "corr_fit_oco_fit_skew": base.safe_corr(cur["fit_oco_y"], cur["fit_skew_y"]),
        "corr_fit_adi_fit_skew": base.safe_corr(cur["fit_adi_y"], cur["fit_skew_y"]),

        "normal_fit_oco_m3s_y": base.m3s_y(cur.loc[normal_compare_mask, "fit_oco_y"]),
        "normal_fit_adi_m3s_y": base.m3s_y(cur.loc[normal_compare_mask, "fit_adi_y"]),
        "normal_fit_skew_m3s_y": base.m3s_y(cur.loc[normal_compare_mask, "fit_skew_y"]),
        "normal_corr_fit_oco_fit_adi": base.safe_corr(
            cur.loc[normal_compare_mask, "fit_oco_y"],
            cur.loc[normal_compare_mask, "fit_adi_y"],
        ),

        # base.main 호환을 위해 기존 이름도 유지한다. 여기서 oco= M1 OCO real model, adi= M2 skew model 진단값이다.
        "oco_base_lambda_median": base.safe_nanmedian(m1_lambda_vals),
        "oco_base_lambda_min": base.safe_nanmin(m1_lambda_vals),
        "oco_base_lambda_max": base.safe_nanmax(m1_lambda_vals),
        "adi_base_lambda_median": base.safe_nanmedian(m2_lambda_vals),
        "adi_base_lambda_min": base.safe_nanmin(m2_lambda_vals),
        "adi_base_lambda_max": base.safe_nanmax(m2_lambda_vals),
        "m1_base_lambda_median": base.safe_nanmedian(m1_lambda_vals),
        "m2_base_lambda_median": base.safe_nanmedian(m2_lambda_vals),

        "oco_lambda_max_median": base.safe_nanmedian(m1_lambda_max_vals),
        "adi_lambda_max_median": base.safe_nanmedian(m2_lambda_max_vals),
        "m1_lambda_max_median": base.safe_nanmedian(m1_lambda_max_vals),
        "m2_lambda_max_median": base.safe_nanmedian(m2_lambda_max_vals),

        "oco_gopt_median": base.safe_nanmedian(m1_gopt_vals),
        "adi_gopt_median": base.safe_nanmedian(m2_gopt_vals),
        "oco_gopt_min": base.safe_nanmin(m1_gopt_vals),
        "oco_gopt_max": base.safe_nanmax(m1_gopt_vals),
        "adi_gopt_min": base.safe_nanmin(m2_gopt_vals),
        "adi_gopt_max": base.safe_nanmax(m2_gopt_vals),
        "m1_gopt_median": base.safe_nanmedian(m1_gopt_vals),
        "m2_gopt_median": base.safe_nanmedian(m2_gopt_vals),
    }

    cur["sim_LOT_ID"] = current_lot
    cur["sim_Wafer"] = current_wafer
    cur["sim_seq_idx"] = seq_idx
    cur["sim_history_lots"] = ", ".join(hist_lots)

    meta_rows = []
    meta_rows.extend(base.make_meta_df(meta_m1, current_lot, current_wafer, seq_idx, source="M1_OCO_REAL_RESIDUAL"))
    meta_rows.extend(base.make_meta_df(meta_adi_diag, current_lot, current_wafer, seq_idx, source="ADI_REAL_RESIDUAL_DIAG"))
    meta_rows.extend(base.make_meta_df(meta_m2, current_lot, current_wafer, seq_idx, source="M2_MODEL_DIFF_OCO_MINUS_ADI_REAL"))

    # MRC company fit meta도 fit_meta sheet에 같이 남긴다.
    for source, meta in [("MRC_OCO_RAW_COMPANY", meta_oco_mrc), ("MRC_ADI_RAW_COMPANY", meta_adi_mrc)]:
        r = dict(meta)
        r.update({
            "current_LOT_ID": current_lot,
            "current_Wafer": current_wafer,
            "current_seq_idx": seq_idx,
            "source": source,
            "shot_key": "__WAFER_COMPANY__",
            "is_normal_shot": meta.get("status") == "ok",
        })
        meta_rows.append(r)

    fpt_rows = []
    fpt_rows.extend(base.fpt_rows_for_output(fpt_oco, current_lot, current_wafer, seq_idx, "OCO_MRC_REMOVED", hist_lots))
    fpt_rows.extend(base.fpt_rows_for_output(fpt_adi, current_lot, current_wafer, seq_idx, "ADI_MRC_REMOVED", hist_lots))

    return cur, summary, (coef_rows_m1, coef_rows_m2), meta_rows, fpt_rows


# 원본 main()이 이 simulate_current_wafer를 사용하도록 교체
base.simulate_current_wafer = simulate_current_wafer


if __name__ == "__main__":
    base.main()
