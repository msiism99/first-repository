# %% 29. 배율 비교 설정과 28번까지 저장된 OCO 결과 읽기
from dataclasses import dataclass
from pathlib import Path
import copy
import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, FileLink

ES_BASE_DIR = Path.cwd()  # C:\PHOTO_ANALYSIS\BASIC에 노트북 배치
ES_INPUT_DIR = ES_BASE_DIR / "output_decorrect_notebook"
ES_OUTPUT_DIR = ES_BASE_DIR / "output_oco_edge_scale_sweep"
ES_SCALES = [i / 10 for i in range(1, 11)]  # 10~100%, 10% 간격
ES_RADIUS_UM = 144000.0
ES_METRIC_AXES = ["x", "y"]  # X만 보고 싶으면 ["x"]
ES_STD_DDOF = 1  # 표본 표준편차. M3S = abs(mean) + 3*std
ES_SAVE_AFFECTED_POINTS = True  # 영향받는 shot의 point별 결과만 배율별 Parquet 저장
ES_BASELINE_ATOL_UM = 1e-9
ES_FILTERS = {}  # 예: {"LOT_ID": ["LOT_A"], "Wafer": [11]}
ES_WAFER_KEYS = ["LOT_ID", "Wafer"]
ES_SHOT_KEYS = ES_WAFER_KEYS + ["fcp_x", "fcp_y"]

if not ES_SCALES or any(not np.isfinite(v) or v < 0 for v in ES_SCALES):
    raise ValueError("비교 배율은 유한한 0 이상의 수여야 합니다.")
ES_SCALES = sorted(set(float(v) for v in ES_SCALES))
if ES_STD_DDOF not in [0, 1] or not set(ES_METRIC_AXES).issubset({"x", "y"}):
    raise ValueError("ES_STD_DDOF는 0/1, 방향은 x/y로 지정하세요.")
for folder in [ES_OUTPUT_DIR, ES_OUTPUT_DIR / "tables", ES_OUTPUT_DIR / "plots", ES_OUTPUT_DIR / "points"]:
    folder.mkdir(parents=True, exist_ok=True)


def es_read_full(stem):
    errors = []
    for suffix in [".parquet", ".xlsx"]:
        path = ES_INPUT_DIR / "stages" / (stem + suffix)
        if path.is_file():
            try:
                frame = pd.read_parquet(path) if suffix == ".parquet" else pd.read_excel(path)
                print(f"입력: {path.name} — {len(frame):,} rows")
                return frame, path
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
    raise FileNotFoundError(f"{stem} 전체 Parquet/Excel이 필요합니다. _sample 파일은 읽지 않습니다. " + " | ".join(errors))


def es_prepare_points(frame):
    required = ES_SHOT_KEYS + ["coordinate_X", "coordinate_Y", "raw_minus_total_fit_x", "raw_minus_total_fit_y", "CPE_fit_x", "CPE_fit_y", "real_residual_x", "real_residual_y", "measurement_scale", "X_reg_original", "Y_reg_original"]
    missing = [col for col in required if col not in frame]
    if missing:
        raise ValueError(f"27번 OCO 결과에 필수 컬럼이 없습니다: {missing}")
    out = frame.copy().reset_index(drop=True)
    for col, values in ES_FILTERS.items():
        if col not in out:
            raise ValueError(f"필터 컬럼 없음: {col}")
        out = out[out[col].isin(values if isinstance(values, (list, tuple, set)) else [values])].copy()
    out = out.reset_index(drop=True)
    if out.empty:
        raise ValueError("선택한 OCO point가 없습니다. 27번 결과 또는 ES_FILTERS를 확인하세요.")
    number_cols = required[2:] + ["radius", "wf_x", "wf_y", "raw_x", "raw_y", "X_reg", "Y_reg"]
    for col in number_cols:
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "radius" not in out:
        if "wf_x" in out and "wf_y" in out:
            out["radius"] = np.hypot(out["wf_x"], out["wf_y"])
        else:
            out["radius"] = np.hypot(out["fcp_x"] + out["coordinate_X"], out["fcp_y"] + out["coordinate_Y"])
    out["_es_outer"] = out["radius"].gt(ES_RADIUS_UM) & np.isfinite(out["radius"])
    valid_cols = ["raw_minus_total_fit_x", "raw_minus_total_fit_y", "coordinate_X", "coordinate_Y"]
    out["_es_fit_valid"] = np.isfinite(out[valid_cols].to_numpy(float)).all(axis=1)
    needed = out["_es_outer"] & out["_es_fit_valid"]
    if needed.any() and not np.isfinite(out.loc[needed, ["measurement_scale", "X_reg_original", "Y_reg_original"]].to_numpy(float)).all():
        raise ValueError("유효한 외곽 point의 원래 측정값 또는 기존 배율이 없습니다. 05~28 저장 자료를 확인하세요.")
    out["_es_affected"] = out["_es_outer"].groupby([out[col] for col in ES_SHOT_KEYS], observed=True, dropna=False).transform("any")
    return out


es_base_points, es_point_path = es_read_full("27_OCO_FINAL_POINTS")
es_settings_path = ES_INPUT_DIR / "extension_settings.json"
if not es_settings_path.is_file():
    raise FileNotFoundError(f"28번 설정 파일이 필요합니다: {es_settings_path}")
es_saved_settings = json.loads(es_settings_path.read_text(encoding="utf-8"))
es_base_points = es_prepare_points(es_base_points)
es_affected_base = es_base_points[es_base_points["_es_affected"]].copy()
es_wafer_index = es_base_points[ES_WAFER_KEYS].drop_duplicates().sort_values(ES_WAFER_KEYS).reset_index(drop=True)
es_wafer_index.insert(0, "wafer_index", np.arange(len(es_wafer_index)))
es_shot_index = es_affected_base[ES_SHOT_KEYS].drop_duplicates().sort_values(ES_SHOT_KEYS).reset_index(drop=True)
es_shot_index.insert(0, "shot_index", np.arange(len(es_shot_index)))
if not es_shot_index.empty:
    for col in ["DieX", "DieY", "photo_transn_seq"]:
        if col in es_affected_base:
            values = es_affected_base.groupby(ES_SHOT_KEYS, observed=True, dropna=False)[col].first().reset_index()
            es_shot_index = es_shot_index.merge(values, on=ES_SHOT_KEYS, how="left", validate="1:1")
    counts = es_affected_base.assign(n_outer=es_affected_base["_es_outer"].astype(int), n_outer_fit=(es_affected_base["_es_outer"] & es_affected_base["_es_fit_valid"]).astype(int))
    counts = counts.groupby(ES_SHOT_KEYS, observed=True, dropna=False).agg(n_points=("radius", "size"), n_outer_points=("n_outer", "sum"), n_outer_fit_points=("n_outer_fit", "sum")).reset_index()
    es_shot_index = es_shot_index.merge(counts, on=ES_SHOT_KEYS, how="left", validate="1:1")
else:
    for col in ["DieX", "DieY", "n_points", "n_outer_points", "n_outer_fit_points"]:
        es_shot_index[col] = pd.Series(dtype="Int64")
print(f"OCO wafer {len(es_wafer_index):,}, 전체 shot {len(es_base_points[ES_SHOT_KEYS].drop_duplicates()):,}, 재계산 shot {len(es_shot_index):,}")
print("K-MRC 고정. 반경 >144mm point의 배율은 CPE 회귀에만 적용; M3S는 배율 적용 전 측정값에서 새 CPE를 뺀 값으로 두 영역 집계.")
display(es_shot_index.head(10))
