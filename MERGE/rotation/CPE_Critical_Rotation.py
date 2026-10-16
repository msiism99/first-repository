# %% 00. 경로 / 대상 제품 / 비교 설정
from pathlib import Path
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import json
import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, FileLink

BASE_DIR = Path(r"C:\PHOTO_ANALYSIS\BASIC")
STAGE_DIR = BASE_DIR / "output_decorrect_notebook" / "stages"
OUTPUT_DIR = BASE_DIR / "output_cpe_critical_rotation"
MODES = ["ADI", "OCO"]
FILTERS = {}  # 예: {"LOT_ID": ["LOT_A", "LOT_B"]}; 여러 컬럼은 AND, 컬럼 안의 값은 OR
FILTERS_BY_MODE = {"ADI": {}, "OCO": {}}  # 필요하면 mode별 제품/recipe 필터 추가
ROTATION_DEG = 90  # +90 또는 -90; 원래 장비 X 오차를 회전 좌표의 Y 오차로 변환
USE_SAVED_SOLVER_SETTINGS = True
SOLVER_OVERRIDES = {}  # 예: {"G_OPT_SPEC": 1.0}; 아래 원본 solver 셀 실행 후 적용
RUN_OLS_DIAGNOSTIC = True  # ridge/span 없는 진단 회귀; 실측 point에서의 설명력만 비교
USE_WAFER_CONTEXT = True
STD_DDOF = 1
UM_TO_NM = 1000.0
EXCEL_PREVIEW_ROWS = 10000
SHOW_PLOTS = True
PREVIEW_ROWS = 8
WAFER_KEYS = ["LOT_ID", "Wafer", "photo_transn_seq"]
SHOT_KEYS = WAFER_KEYS + ["fcp_x", "fcp_y"]
COORDS = ["coordinate_X", "coordinate_Y"]
TARGET = "raw_minus_total_fit_x"
NATIVE_CASES = ["X21_NATIVE", "ROT_Y17_NATIVE"]
if not MODES or any(mode not in ["ADI", "OCO"] for mode in MODES) or len(set(MODES)) != len(MODES):
    raise ValueError("MODES는 ADI/OCO 중 중복 없이 지정하세요.")
if ROTATION_DEG not in [90, -90]:
    raise ValueError("ROTATION_DEG는 +90 또는 -90입니다.")
if not STAGE_DIR.is_dir():
    raise FileNotFoundError(f"stages 폴더 없음: {STAGE_DIR}")
TABLE_DIR, PLOT_DIR = OUTPUT_DIR / "tables", OUTPUT_DIR / "plots"
TABLE_DIR.mkdir(parents=True, exist_ok=True)
PLOT_DIR.mkdir(parents=True, exist_ok=True)
input_manifest, output_manifest = [], {}
plt.rcParams.update({"axes.unicode_minus": False, "figure.dpi": 110})
print("입력:", STAGE_DIR)
print("출력:", OUTPUT_DIR)
print("선택된 모든 wafer는 critical X 제품으로 취급합니다. 제품 필터는 FILTERS에 지정하세요.")

# %% 01. 저장 파일 읽기 / ID 정규화 / 중간 결과 저장
def normalized_id(value):
    if pd.isna(value):
        return pd.NA
    value = str(value).strip()
    try:
        number = Decimal(value)
        return str(int(number)) if number.is_finite() and number == number.to_integral_value() else value
    except (InvalidOperation, ValueError, OverflowError):
        return value

def normalize_keys(frame):
    out = frame.copy()
    for key in WAFER_KEYS:
        if key not in out:
            raise ValueError(f"wafer 키 누락: {key}")
        values = out[key].astype("string").str.strip()
        if key != "LOT_ID":
            lookup = {value: normalized_id(value) for value in values.dropna().unique()}
            values = values.map(lookup)
        out[key] = values.astype("string")
    return out

def read_full(stems, directory=STAGE_DIR, required=True):
    failures = []
    for stem in stems:
        for suffix in [".parquet", ".xlsx"]:
            path = directory / (stem + suffix)
            if not path.is_file():
                continue
            try:
                frame = pd.read_parquet(path) if suffix == ".parquet" else pd.read_excel(path, dtype={key: "string" for key in WAFER_KEYS})
            except Exception as exc:
                failures.append(f"{path.name}: {type(exc).__name__}: {exc}")
                continue
            input_manifest.append(dict(path=str(path), rows=len(frame), columns=len(frame.columns), bytes=path.stat().st_size, mtime_ns=path.stat().st_mtime_ns, fallback_errors="; ".join(failures)))
            return frame
    if required:
        raise FileNotFoundError(f"전체 Parquet/Excel 필요: {stems}. sample Excel은 입력에서 제외합니다. {'; '.join(failures)}")
    if failures:
        print("선택 입력 읽기 실패:", "; ".join(failures))
    return None

def excel_safe(frame):
    out = frame.copy()
    for col in out.select_dtypes(include=["object", "string"]).columns:
        out[col] = out[col].map(lambda value: "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value)
    return out

def save_table(name, frame, excel=True):
    frame.to_parquet(TABLE_DIR / f"{name}.parquet", index=False)
    frame.to_csv(TABLE_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")
    excel_path = None
    if excel:
        sample = len(frame) > EXCEL_PREVIEW_ROWS
        excel_path = TABLE_DIR / (f"{name}_sample_{EXCEL_PREVIEW_ROWS}.xlsx" if sample else f"{name}.xlsx")
        excel_safe(frame.head(EXCEL_PREVIEW_ROWS)).to_excel(excel_path, index=False, engine="openpyxl")
    output_manifest[name] = dict(name=name, rows=len(frame), columns=len(frame.columns), parquet=str(TABLE_DIR / f"{name}.parquet"), excel=str(excel_path) if excel_path else None)
    print(f"[{name}] {len(frame):,} rows × {len(frame.columns)} columns")
    if excel_path is not None:
        display(FileLink(os.path.relpath(excel_path, Path.cwd())))

def apply_filters(frame, mode):
    out = frame
    for rules in [FILTERS, FILTERS_BY_MODE.get(mode, {})]:
        for col, values in rules.items():
            if col not in out:
                raise ValueError(f"{mode}: 필터 컬럼 없음: {col}. 02_input_columns.csv를 확인하세요.")
            if not isinstance(values, (list, tuple, set)) or not values:
                raise ValueError(f"{col}: 필터값은 비어 있지 않은 list/tuple/set으로 지정하세요.")
            wanted = [str(normalized_id(value)) if col in WAFER_KEYS[1:] else str(value).strip() for value in values]
            out = out.loc[out[col].astype("string").str.strip().isin(wanted)]
    return out.reset_index(drop=True)

# %% 02. 대상 wafer 선택 / CPE 직전 X 데이터 확인
frames, selection_rows, column_rows = {}, [], []
context = read_full(["wafer_context"], BASE_DIR / "output_wafer_context", required=False) if USE_WAFER_CONTEXT else None
if context is not None:
    context = normalize_keys(context)
    if context[WAFER_KEYS].isna().any(axis=None) or context.duplicated(WAFER_KEYS).any():
        raise ValueError("wafer_context는 전체 wafer 키가 유효하고 유일해야 합니다.")
for mode in MODES:
    frame = normalize_keys(read_full([f"21_{mode}_WK_RK_REMOVED", f"27_{mode}_FINAL_POINTS"]))
    if context is not None:
        frame = frame.merge(context, how="left", on=WAFER_KEYS, validate="many_to_one", suffixes=("", "_context"))
    column_rows.extend(dict(mode=mode, column=col, dtype=str(frame[col].dtype)) for col in frame)
    pd.DataFrame(column_rows).to_csv(TABLE_DIR / "02_input_columns.csv", index=False, encoding="utf-8-sig")
    frame = apply_filters(frame, mode)
    missing = [col for col in SHOT_KEYS + COORDS + [TARGET] if col not in frame]
    if missing:
        raise ValueError(f"{mode}: CPE 직전 입력 컬럼 누락: {missing}")
    if frame.empty:
        raise ValueError(f"{mode}: 제품 필터에 맞는 데이터가 없습니다.")
    if frame[WAFER_KEYS].isna().any(axis=None):
        raise ValueError(f"{mode}: wafer 키에 결측값이 있습니다.")
    for col in SHOT_KEYS[3:] + COORDS + [TARGET]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["source_row_id"] = np.arange(len(frame), dtype=np.int64)
    frame["rotation_valid_x"] = np.isfinite(frame[SHOT_KEYS[3:] + COORDS + [TARGET]].to_numpy(float)).all(axis=1)
    frames[mode] = frame
    selected = frame.groupby(WAFER_KEYS, dropna=False, sort=False).agg(n_points=(TARGET, "size"), n_valid_x=("rotation_valid_x", "sum")).reset_index()
    selected.insert(0, "mode", mode)
    selection_rows.append(selected)
    print(mode, "wafer 수:", len(selected), "유효 X point:", int(frame["rotation_valid_x"].sum()))
selection = pd.concat(selection_rows, ignore_index=True)
save_table("02_SELECTED_WAFERS", selection)
save_table("02_INPUT_MANIFEST", pd.DataFrame(input_manifest))
display(selection.head(PREVIEW_ROWS))

# %% 07. 회전 설정 / 모델 대응표 / X 한 방향 solver
# 03~06의 원본 solver 정의를 먼저 실행합니다.
SETTINGS_MAP = {
    "span_mode": "SPAN_MODE", "min_points_guide": "MIN_POINTS_GUIDE", "eval_grid_n": "CPE_EVAL_GRID_N", "ridge_regression": "RIDGE_REGRESSION",
    "gopt_spec": "G_OPT_SPEC", "gopt_tolerance": "G_OPT_TOLERANCE", "gopt_type": "G_OPTIMAL_TYPE", "use_span_box_constraint": "USE_SPAN_BOX_CONSTRAINT",
    "use_virtual_chip_points": "USE_VIRTUAL_CHIP_POINTS", "virtual_wafer_radius_um": "VIRTUAL_WAFER_RADIUS", "span_tolerance": "SPAN_TOLERANCE",
    "minimum_ridge": "MINIMUM_RIDGE", "add_ridge": "ADD_RIDGE", "max_gopt_return": "MAX_GOPT_RETURN", "max_span_iter": "MAX_SPAN_ITER", "cd_tol": "CD_TOL", "ridge_valves": "RIDGE_VALVE_HYPER",
}
settings_path = STAGE_DIR.parent / "extension_settings.json"
saved_settings = json.loads(settings_path.read_text(encoding="utf-8")) if USE_SAVED_SOLVER_SETTINGS and settings_path.is_file() else {}
for source, value in {**saved_settings, **saved_settings.get("cpe_options", {})}.items():
    if source in SETTINGS_MAP:
        globals()[SETTINGS_MAP[source]] = value
NATIVE_SPAN_LIMITS = saved_settings.get("active_span_limits", get_active_span_limits(SPAN_MODE))
for key, value in SOLVER_OVERRIDES.items():
    if key not in set(SETTINGS_MAP.values()) | {"NATIVE_SPAN_LIMITS"}:
        raise ValueError(f"SOLVER_OVERRIDES: 지원하지 않는 설정 {key}")
    globals()[key] = value
if "SPAN_MODE" in SOLVER_OVERRIDES and "NATIVE_SPAN_LIMITS" not in SOLVER_OVERRIDES:
    NATIVE_SPAN_LIMITS = get_active_span_limits(SPAN_MODE)
ROTATION_SIGN = 1 if ROTATION_DEG == 90 else -1
X_POWERS = [(0,0), (1,0), (0,1), (2,0), (1,1), (0,2), (3,0), (2,1), (1,2), (0,3), (3,1), (2,2), (1,3), (0,4), (3,2), (2,3), (1,4), (0,5), (3,3), (2,4), (3,4)]
Y_POWERS = [(0,0), (0,1), (1,0), (0,2), (1,1), (2,0), (0,3), (1,2), (2,1), (0,4), (1,3), (2,2), (0,5), (1,4), (2,3), (1,5), (2,4)]
DEGREE_SCALE = {0: 1., 1: 1e6, 2: 1e9, 3: 1e12, 4: 1e19, 5: 1e23, 6: 1e27, 7: 1e31}

def rotate_local(rx, ry):
    return -ROTATION_SIGN * np.asarray(ry), ROTATION_SIGN * np.asarray(rx)

def model_table():
    rows = []
    original_set, rotated_set = set(X_POWERS), {(b,a) for a,b in Y_POWERS}
    for case, names, powers in [(NATIVE_CASES[0], CPE38_KEYS_DX, X_POWERS), (NATIVE_CASES[1], CPE38_KEYS_DY, Y_POWERS)]:
        for name, (a,b) in zip(names, powers):
            rotated = case == NATIVE_CASES[1]
            px, py = (b,a) if rotated else (a,b)
            sign = ROTATION_SIGN * (-ROTATION_SIGN)**a * ROTATION_SIGN**b if rotated else (-1 if name == "RK5" else 1)
            rows.append(dict(
                case=case, term=name, power_x=px, power_y=py, sign_to_original_x=sign, scale=DEGREE_SCALE[a+b], shared_monomial=(px,py) in original_set & rotated_set,
                ridge_valve=get_ridge_valves([name])[0], span_limit_min=NATIVE_SPAN_LIMITS.get(name, {}).get("min", np.nan), span_limit_max=NATIVE_SPAN_LIMITS.get(name, {}).get("max", np.nan),
            ))
    return pd.DataFrame(rows)

def design_information(matrix):
    norms = np.linalg.norm(matrix, axis=0)
    scaled = matrix / np.where(norms > 0, norms, 1.)
    singular = np.linalg.svd(scaled, compute_uv=False)
    rank = int(np.linalg.matrix_rank(scaled))
    condition = float(singular[0] / singular[-1]) if rank == matrix.shape[1] else np.inf
    return rank, condition

def solve_case(matrix, target, evaluation, names, n_virtual, diagnostic=False):
    if diagnostic:
        norms = np.linalg.norm(matrix, axis=0)
        norms = np.where(norms > 0, norms, 1.)
        beta = np.linalg.lstsq(matrix / norms, target, rcond=None)[0] / norms
        return RidgeFitResult(beta, matrix @ beta, np.zeros(len(names)), np.nan, calc_contribution_spans(evaluation, beta, names), [], 0, 0, "ols_diagnostic_column_scaled")
    return solve_vba_style_ridge_one_axis(
        matrix, target, evaluation, names, NATIVE_SPAN_LIMITS, ridge_regression=RIDGE_REGRESSION, gopt_spec=G_OPT_SPEC, gopt_tolerance=G_OPT_TOLERANCE,
        minimum_ridge=MINIMUM_RIDGE, add_ridge=ADD_RIDGE, max_gopt_return=MAX_GOPT_RETURN, gopt_type=G_OPTIMAL_TYPE,
        inner_or_partial=determine_inner_or_partial(len(target), n_virtual), use_span_box_constraint=USE_SPAN_BOX_CONSTRAINT,
        span_tolerance=SPAN_TOLERANCE, cd_tol=CD_TOL, max_span_iter=MAX_SPAN_ITER, base_lambda_scale=choose_base_lambda_scale(len(target)),
    )

term_mapping = model_table()
save_table("07_TERM_MAPPING", term_mapping)
display(term_mapping)
print("공통 단항식:", int(term_mapping.loc[term_mapping["case"].eq(NATIVE_CASES[0]), "shared_monomial"].sum()), "/ X21과 회전 Y17은 포함관계가 아닙니다.")
print("설정:", "저장 설정 반영" if saved_settings else "원본 노트북 기본값", "; 회전:", ROTATION_DEG)

# %% 08. 동일 X point에서 X21 / 회전 Y17 shot별 회귀 및 저장
def fit_rotation_mode(frame, mode):
    out = frame.copy()
    cases = NATIVE_CASES + (["X21_OLS_DIAGNOSTIC", "ROT_Y17_OLS_DIAGNOSTIC"] if RUN_OLS_DIAGNOSTIC else [])
    for case in cases:
        out[f"{case}_fit_x"] = np.nan
        out[f"{case}_residual_x"] = np.nan
    coefficients, diagnostics, reference_norms = [], [], {}
    mapping_lookup = {case: term_mapping.loc[term_mapping["case"].eq(case)].set_index("term").to_dict("index") for case in NATIVE_CASES}
    # wafer 내 shot 간 term 산포를 비교하므로 nm 환산 좌표 범위를 wafer별로 고정합니다.
    for wafer_key, work in out.loc[out["rotation_valid_x"]].groupby(WAFER_KEYS, sort=False):
        coordinates = work[COORDS].drop_duplicates().to_numpy(float)
        reference_x, _ = cpe_38para(coordinates[:,0], coordinates[:,1])
        u, v = rotate_local(coordinates[:,0], coordinates[:,1])
        _, reference_y = cpe_38para(u, v)
        reference_norms[wafer_key] = {NATIVE_CASES[0]: np.max(np.abs(reference_x), axis=0), NATIVE_CASES[1]: np.max(np.abs(reference_y), axis=0)}
    grouped = out.loc[out["rotation_valid_x"]].groupby(SHOT_KEYS, dropna=False, sort=False)
    for shot_index, (key, work) in enumerate(grouped):
        shot = dict(zip(SHOT_KEYS, key))
        rx, ry, error_x = (work[col].to_numpy(float) for col in COORDS + [TARGET])
        if USE_VIRTUAL_CHIP_POINTS:
            gx, gy, virtual_source, n_virtual_full, n_virtual = get_virtual_points_for_group(work, rx, ry, float(shot["fcp_x"]), float(shot["fcp_y"]), wafer_radius=VIRTUAL_WAFER_RADIUS)
        else:
            gx, gy = build_eval_grid_from_data(rx, ry, grid_n=CPE_EVAL_GRID_N)
            virtual_source, n_virtual_full, n_virtual = "measured_range_grid", len(gx), len(gx)
        # 원래 wafer 경계로 자른 virtual point를 회전합니다. 미회전 shot 중심으로 다시 자르지 않습니다.
        ux, uy = rotate_local(rx, ry)
        gux, guy = rotate_local(gx, gy)
        original_matrix, _ = cpe_38para(rx, ry)
        original_eval, _ = cpe_38para(gx, gy)
        _, rotated_matrix = cpe_38para(ux, uy)
        _, rotated_eval = cpe_38para(gux, guy)
        ranks = {False: design_information(original_matrix), True: design_information(rotated_matrix)}
        for case in cases:
            rotated = case.startswith("ROT_")
            matrix, evaluation = (rotated_matrix, rotated_eval) if rotated else (original_matrix, original_eval)
            names = CPE38_KEYS_DY if rotated else CPE38_KEYS_DX
            target, back_sign = (ROTATION_SIGN * error_x, ROTATION_SIGN) if rotated else (error_x, 1)
            fit = solve_case(matrix, target, evaluation, names, n_virtual, diagnostic=case.endswith("DIAGNOSTIC"))
            prediction = back_sign * fit.pred
            if not np.isfinite(prediction).all() or not np.isfinite(fit.beta).all():
                raise ValueError(f"회귀 결과에 비유한 값 발생: {mode}, {shot}, {case}")
            out.loc[work.index, f"{case}_fit_x"] = prediction
            out.loc[work.index, f"{case}_residual_x"] = error_x - prediction
            rank, condition = ranks[rotated]
            diag = dict(
                mode=mode, **shot, case=case, n_valid_x=len(work), n_parameters=len(names), rank=rank, full_column_rank=rank == len(names), column_scaled_condition=condition,
                n_virtual=n_virtual, n_virtual_full=n_virtual_full, virtual_source=virtual_source, inner_or_partial=determine_inner_or_partial(len(work), n_virtual),
                method=fit.method, gopt=fit.gopt, lambda_max=float(np.max(fit.lambdas)), gopt_iterations=fit.gopt_iter, span_iterations=fit.span_iter,
                span_violation_count=len(fit.violations), span_violation_terms="|".join(item[0] for item in fit.violations),
                gopt_within_spec=bool(np.isfinite(fit.gopt) and 0 < fit.gopt < G_OPT_SPEC), max_decomposition_error=float(np.max(np.abs(error_x - (prediction + (error_x - prediction))))),
            )
            diagnostics.append(diag)
            coef = dict(mode=mode, **shot, case=case, coefficient_coordinates="rotated_local_Y" if rotated else "original_local_X", rotation_deg=ROTATION_DEG if rotated else 0)
            native_case = NATIVE_CASES[1] if rotated else NATIVE_CASES[0]
            mapping = mapping_lookup[native_case]
            max_abs_reference = reference_norms[tuple(shot[col] for col in WAFER_KEYS)][native_case]
            for index, name in enumerate(names):
                mono_sign = int(mapping[name]["sign_to_original_x"])
                coef[f"beta_{name}"] = float(fit.beta[index])
                coef[f"signed_peak_nm_{name}"] = float(fit.beta[index] * mono_sign * max_abs_reference[index] * UM_TO_NM)
                coef[f"reference_max_abs_basis_{name}"] = float(max_abs_reference[index])
                coef[f"span_nm_{name}"] = float(fit.spans[name] * UM_TO_NM)
                coef[f"lambda_{name}"] = float(fit.lambdas[index])
            coefficients.append(coef)
        if (shot_index + 1) % 250 == 0:
            print(f"{mode}: {shot_index + 1:,} shots 완료")
    diag_frame = pd.DataFrame(diagnostics)
    if diag_frame.empty:
        raise ValueError(f"{mode}: 회귀 가능한 X point가 없습니다.")
    return out, pd.DataFrame(coefficients), diag_frame

results, all_coefficients, all_diagnostics = {}, [], []
for mode in MODES:
    points, coefficients, diagnostics = fit_rotation_mode(frames[mode], mode)
    results[mode] = points
    all_coefficients.append(coefficients)
    all_diagnostics.append(diagnostics)
    save_table(f"08_{mode}_ROTATION_POINTS", points, excel=False)
    save_table(f"08_{mode}_SHOT_COEFFICIENTS", coefficients)
    save_table(f"08_{mode}_SHOT_DIAGNOSTICS", diagnostics)
coefficient_table = pd.concat(all_coefficients, ignore_index=True)
diagnostic_table = pd.concat(all_diagnostics, ignore_index=True)
save_table("08_ALL_SHOT_DIAGNOSTICS", diagnostic_table)
display(diagnostic_table.head(PREVIEW_ROWS))

# %% 09. Wafer/shot 통계 / CPE budget / term별 산포 비교
def scalar_statistics(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)] * UM_TO_NM
    n = len(values)
    mean = float(np.mean(values)) if n else np.nan
    sigma = float(np.std(values, ddof=STD_DDOF)) if n > STD_DDOF else np.nan
    return dict(n=n, mean_nm=mean, std_nm=sigma, three_sigma_nm=3*sigma, mean_plus_3sigma_nm=mean+3*sigma, abs_mean_plus_3sigma_nm=abs(mean)+3*sigma, rms_nm=float(np.sqrt(np.mean(values**2))) if n else np.nan)

def summarize_points(points, mode, group_keys):
    rows = []
    for key, work in points.groupby(group_keys, dropna=False, sort=False):
        identity = dict(zip(group_keys, key))
        valid = work.loc[work["rotation_valid_x"]]
        for case in NATIVE_CASES + (["X21_OLS_DIAGNOSTIC", "ROT_Y17_OLS_DIAGNOSTIC"] if RUN_OLS_DIAGNOSTIC else []):
            row = dict(mode=mode, **identity, case=case, n_total=len(work), n_invalid_x=len(work)-len(valid))
            for component, col in [("input", TARGET), ("cpe", f"{case}_fit_x"), ("residual", f"{case}_residual_x")]:
                row.update({f"{component}_{name}": value for name,value in scalar_statistics(valid[col]).items()})
            if len(valid) > STD_DDOF:
                covariance = float(np.cov(valid[f"{case}_fit_x"], valid[f"{case}_residual_x"], ddof=STD_DDOF)[0,1] * UM_TO_NM**2)
                row["cpe_residual_covariance_nm2"] = covariance
                row["variance_budget_error_nm2"] = row["input_std_nm"]**2 - row["cpe_std_nm"]**2 - row["residual_std_nm"]**2 - 2*covariance
            rows.append(row)
    return pd.DataFrame(rows)

def paired_comparison(statistics, group_keys):
    left = statistics.loc[statistics["case"].eq(NATIVE_CASES[0])].drop(columns="case")
    right = statistics.loc[statistics["case"].eq(NATIVE_CASES[1])].drop(columns="case")
    pair = left.merge(right, on=["mode"]+group_keys, how="outer", validate="one_to_one", suffixes=("_X21", "_ROT_Y17"), indicator=True)
    if not pair["_merge"].eq("both").all():
        raise ValueError("X21/Y17 비교 키가 일치하지 않습니다.")
    pair = pair.drop(columns="_merge")
    for metric in ["mean_nm", "three_sigma_nm", "abs_mean_plus_3sigma_nm", "rms_nm"]:
        for component in ["cpe", "residual"]:
            prefix = f"{component}_{metric}"
            pair[f"{prefix}_delta_ROT_minus_X21"] = pair[f"{prefix}_ROT_Y17"] - pair[f"{prefix}_X21"]
    pair["residual_3sigma_reduction_pct"] = 100 * (1 - pair["residual_three_sigma_nm_ROT_Y17"] / pair["residual_three_sigma_nm_X21"].where(pair["residual_three_sigma_nm_X21"] > 1e-12))
    return pair

wafer_statistics = pd.concat([summarize_points(points, mode, WAFER_KEYS) for mode,points in results.items()], ignore_index=True)
shot_statistics = pd.concat([summarize_points(points, mode, SHOT_KEYS) for mode,points in results.items()], ignore_index=True)
wafer_comparison, shot_comparison = paired_comparison(wafer_statistics, WAFER_KEYS), paired_comparison(shot_statistics, SHOT_KEYS)
term_rows = []
for (mode, case), coefficients in coefficient_table.groupby(["mode", "case"], sort=False):
    names = CPE38_KEYS_DY if case.startswith("ROT_") else CPE38_KEYS_DX
    for key, group in coefficients.groupby(WAFER_KEYS, dropna=False, sort=False):
        for name in names:
            peaks = group[f"signed_peak_nm_{name}"]
            term_rows.append(dict(mode=mode, **dict(zip(WAFER_KEYS,key)), case=case, term=name, n_shots=len(group), peak_mean_nm=float(peaks.mean()), peak_3sigma_nm=float(3*peaks.std(ddof=STD_DDOF)), mean_abs_peak_nm=float(peaks.abs().mean())))
term_wafer_statistics = pd.DataFrame(term_rows)
for name, table in [("09_WAFER_STATISTICS", wafer_statistics), ("09_SHOT_STATISTICS", shot_statistics), ("09_WAFER_COMPARISON", wafer_comparison), ("09_SHOT_COMPARISON", shot_comparison), ("09_TERM_WAFER_STATISTICS", term_wafer_statistics)]:
    save_table(name, table)
display(wafer_comparison[["mode"] + WAFER_KEYS + ["residual_three_sigma_nm_X21", "residual_three_sigma_nm_ROT_Y17", "residual_3sigma_reduction_pct"]].head(PREVIEW_ROWS))

# %% 10. Wafer별 대응 비교 그래프
plot_paths = []
for mode in MODES:
    pair = wafer_comparison.loc[wafer_comparison["mode"].eq(mode)].reset_index(drop=True)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.7))
    for ax, (component, metric, title) in zip(axes, [("cpe", "three_sigma_nm", "Removed CPE 3sigma"), ("residual", "three_sigma_nm", "Final residual 3sigma"), ("residual", "abs_mean_plus_3sigma_nm", "Final residual |mean|+3sigma")]):
        x, y = pair[f"{component}_{metric}_X21"].to_numpy(float), pair[f"{component}_{metric}_ROT_Y17"].to_numpy(float)
        valid = np.isfinite(x) & np.isfinite(y)
        ax.scatter(x[valid], y[valid], color="tab:blue", s=23, alpha=.7)
        limit = max(float(np.max(np.r_[x[valid],y[valid]])) * 1.06, 1e-6) if valid.any() else 1.
        ax.plot([0,limit], [0,limit], ":", color="gray", label="Equal")
        ax.set(xlabel="Original X21 [nm]", ylabel="Rotated Y17, restored X [nm]", title=title, xlim=(0,limit), ylim=(0,limit))
        ax.text(.03,.97,f"N={int(valid.sum())}; one point = one wafer", transform=ax.transAxes, va="top", fontsize=9)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle(f"{mode}: same critical-X points / rotation {ROTATION_DEG:+d} deg")
    fig.tight_layout()
    path = PLOT_DIR / f"{mode}_X21_vs_rotated_Y17.png"
    fig.savefig(path, dpi=170, bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plot_paths.append(str(path))
    if SHOW_PLOTS:
        display(fig)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(max(9, min(20, len(pair)*.13)), 4.5))
    indices = np.arange(len(pair))
    ax.plot(indices, pair["residual_three_sigma_nm_X21"], "o-", ms=3, lw=.7, label="Original X21")
    ax.plot(indices, pair["residual_three_sigma_nm_ROT_Y17"], "o-", ms=3, lw=.7, label="Rotated Y17 -> original X")
    ax.set(xlabel="Wafer index (see 10_WAFER_PLOT_INDEX)", ylabel="Final residual 3sigma [nm]", title=f"{mode}: paired wafer residual comparison")
    ax.grid(alpha=.2)
    ax.legend()
    fig.tight_layout()
    path = PLOT_DIR / f"{mode}_wafer_residual_3sigma.png"
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plot_paths.append(str(path))
    if SHOW_PLOTS:
        display(fig)
    plt.close(fig)
plot_index = pd.concat([wafer_comparison.loc[wafer_comparison["mode"].eq(mode), ["mode"]+WAFER_KEYS].reset_index(drop=True).rename_axis("wafer_index").reset_index() for mode in MODES], ignore_index=True)
save_table("10_WAFER_PLOT_INDEX", plot_index)

# %% 11. 비교 Excel / 설정 / 실행 manifest 저장
notes = pd.DataFrame([
    ("input", f"{TARGET}: raw에서 wafer WK/RK를 제거한 X. WK/RK는 재계산하지 않습니다."),
    ("critical_axis", "두 모델 모두 원래 장비 좌표의 X만 비교합니다."),
    ("rotation", "u=-s*y, v=s*x, error_v=s*error_x; fit_x=s*fit_v; s=+1(+90), -1(-90)."),
    ("X21_NATIVE", "원본 X21의 ridge/G-opt/span 설정으로 재회귀."),
    ("ROT_Y17_NATIVE", "회전한 좌표와 X 오차를 Y17로 회귀하고 원래 X로 복원. Y측 ridge/span 사용."),
    ("OLS_DIAGNOSTIC", "같은 point의 제약 없는 회귀. 학습 point 설명력 진단이며 예측 성능을 뜻하지 않습니다."),
    ("term_peak", "원래 X 단항식으로 변환한 계수 × max(abs(basis)) ×1000. 같은 wafer의 전체 유효 측정 좌표를 공통 기준으로 사용."),
    ("budget", "Var(input)=Var(CPE)+Var(residual)+2Cov(CPE,residual). 3sigma나 variance 단순 가산 불가."),
    ("interpretation", "제거 CPE가 작다는 것만으로 개선으로 판단하지 않습니다. 최종 residual을 함께 저장. 장비 보정은 적용하지 않습니다."),
    ("wafer_statistics", "wafer의 전체 유효 point에서 재계산. shot별 3sigma 평균이 아닙니다."),
    ("product_filter", "FILTERS가 비면 전체 입력을 critical-X 제품으로 취급. 정상 critical-Y 제품을 섞지 마세요."),
    ("missing_Y", "Y 실측값이나 Y residual 불필요. X와 좌표가 유한한 동일 point로 두 모델 비교."),
], columns=["item", "description"])
report_path = OUTPUT_DIR / "CPE_Critical_Rotation_Comparison.xlsx"
with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
    for sheet, table in [("Wafer_comparison", wafer_comparison), ("Shot_comparison", shot_comparison), ("Wafer_statistics", wafer_statistics), ("Term_wafer_statistics", term_wafer_statistics), ("Shot_diagnostics", diagnostic_table), ("Term_mapping", term_mapping), ("Selected_wafers", selection), ("Notes", notes)]:
        if len(table) > 1048575:
            raise ValueError(f"{sheet}: Excel 행 수 제한 초과. tables의 전체 Parquet/CSV를 사용하세요.")
        excel_safe(table).to_excel(writer, sheet_name=sheet, index=False)
        ws = writer.book[sheet]
        ws.freeze_panes = "E2"
        ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(42, max(16, len(str(col[0].value))+2))
actual_settings = {name: globals()[name] for name in sorted(set(SETTINGS_MAP.values()))}
actual_settings["active_span_limits"] = NATIVE_SPAN_LIMITS
run_settings = dict(
    modes=MODES, filters=FILTERS, filters_by_mode=FILTERS_BY_MODE, rotation_deg=ROTATION_DEG, target=TARGET, input_units="um", output_units="nm",
    std_ddof=STD_DDOF, ols_diagnostic=RUN_OLS_DIAGNOSTIC, term_nm_reference="wafer_measured_points_common_across_shots",
    saved_settings_path=str(settings_path) if saved_settings else None, solver=actual_settings, solver_overrides=SOLVER_OVERRIDES, plots=plot_paths,
)
(OUTPUT_DIR / "rotation_settings.json").write_text(json.dumps(run_settings, ensure_ascii=False, indent=2), encoding="utf-8")
pd.DataFrame(input_manifest).to_csv(OUTPUT_DIR / "input_manifest.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(output_manifest.values()).to_csv(OUTPUT_DIR / "saved_files.csv", index=False, encoding="utf-8-sig")
display(FileLink(os.path.relpath(report_path, Path.cwd())))
print("완료: 같은 critical X 데이터의 X21 / 회전 Y17 비교. 기존 stage와 원본 노트북은 변경하지 않았습니다.")
