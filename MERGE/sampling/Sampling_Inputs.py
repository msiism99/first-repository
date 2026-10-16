# %% 00. 경로 / 대표 wafer / 진단 설정
from pathlib import Path
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import hashlib
import json
import os
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import matplotlib.pyplot as plt
from scipy.spatial import ConvexHull, Delaunay, QhullError
from IPython.display import display, FileLink

BASE_DIR = Path(r"C:\PHOTO_ANALYSIS\BASIC")
STAGE_DIR = BASE_DIR / "output_decorrect_notebook" / "stages"
OUTPUT_DIR = BASE_DIR / "output_cpe_sampling_diagnostics"
MODES = ["ADI", "OCO"]
WAFER_SELECTION = {"ADI": None, "OCO": None}  # 예: {"LOT_ID": "LOT_A", "Wafer": 3}; None이면 자동 선정
FILTERS = {}  # 예: {"LOT_ID": ["LOT_A"]}; 입력 또는 wafer_context 컬럼으로 문제 제품 선택
USE_WAFER_CONTEXT = True
USE_VALID_X_MASK = True  # CPE 직전 X 컬럼이 있으면 값의 크기는 쓰지 않고 유효 point 조건만 맞춤
ROTATION_DEG = 90
USE_SAVED_SOLVER_SETTINGS = True
SOLVER_OVERRIDES = {}
COMMON_SHOT_SIZE_UM = None  # 예: (26000., 33000.); None이면 두 sampling의 pitch/좌표 범위 사용
COMMON_GRID_N = 25
COORD_ROUND_DECIMALS = 3  # sampling 패턴 식별에만 사용. 회귀에는 원래 좌표 사용
SVD_RCOND = 1e-10
ALIAS_COSINE_THRESHOLD = .98
SYNTHETIC_SIGNAL_RMS_NM = 1.0
ASSUMED_POINT_NOISE_NM = .2  # 실제 noise 추정값이 아닌 iid noise 가정. 0으로 끌 수 있음
RANDOM_MIXTURES = 12
RANDOM_SEED = 20261016
RUN_OBSERVED_CHECK = True
EXCEL_PREVIEW_ROWS = 10000
PREVIEW_ROWS = 8
SHOW_PLOTS = True
UM_TO_NM = 1000.
WAFER_KEYS = ["LOT_ID", "Wafer", "photo_transn_seq"]
SHOT_KEYS = WAFER_KEYS + ["fcp_x", "fcp_y"]
COORDS = ["coordinate_X", "coordinate_Y"]
GEOMETRY = ["STEP_PITCH_X", "STEP_PITCH_Y", "CHIP_X_NUM", "CHIP_Y_NUM"]
TARGET = "raw_minus_total_fit_x"
NATIVE_CASES = ["X21_NATIVE", "ROT_Y17_NATIVE"]
if ROTATION_DEG not in [90, -90] or COMMON_GRID_N < 5 or ASSUMED_POINT_NOISE_NM < 0 or SYNTHETIC_SIGNAL_RMS_NM <= 0:
    raise ValueError("회전각 / grid / signal / noise 설정을 확인하세요.")
if not STAGE_DIR.is_dir():
    raise FileNotFoundError(STAGE_DIR)
TABLE_DIR, PLOT_DIR = OUTPUT_DIR / "tables", OUTPUT_DIR / "plots"
TABLE_DIR.mkdir(parents=True, exist_ok=True)
PLOT_DIR.mkdir(parents=True, exist_ok=True)
input_manifest, output_manifest = [], {}
plt.rcParams.update({"axes.unicode_minus": False, "figure.dpi": 110})
print("출력:", OUTPUT_DIR)
print("각 mode에서 대표 wafer 하나를 선택합니다. 비교 방향은 같은 critical X의 X21 / 회전 Y17입니다.")

# %% 01. 필요한 좌표 컬럼만 읽기 / 필터 / 중간 파일 저장
def normalized_id(value):
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    try:
        number = Decimal(text)
        return str(int(number)) if number.is_finite() and number == number.to_integral_value() else text
    except (InvalidOperation, ValueError, OverflowError):
        return text

def normalize_keys(frame):
    out = frame.copy()
    for key in WAFER_KEYS:
        values = out[key].astype("string").str.strip()
        if key != "LOT_ID":
            values = values.map({value: normalized_id(value) for value in values.dropna().unique()})
        out[key] = values.astype("string")
    return out

def excel_safe(frame):
    out = frame.copy()
    for col in out.select_dtypes(include=["object", "string"]).columns:
        out[col] = out[col].map(lambda value: "'"+value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value)
    return out

def save_table(name, frame, excel=True):
    frame.to_parquet(TABLE_DIR / f"{name}.parquet", index=False)
    frame.to_csv(TABLE_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")
    if excel:
        suffix = f"_sample_{EXCEL_PREVIEW_ROWS}" if len(frame) > EXCEL_PREVIEW_ROWS else ""
        excel_safe(frame.head(EXCEL_PREVIEW_ROWS)).to_excel(TABLE_DIR / f"{name}{suffix}.xlsx", index=False)
    output_manifest[name] = dict(name=name, rows=len(frame), columns=len(frame.columns))
    print(f"[{name}] {len(frame):,} rows × {len(frame.columns)} columns")

def read_coordinates(mode):
    errors = []
    for stem in [f"21_{mode}_WK_RK_REMOVED", f"27_{mode}_FINAL_POINTS", f"15_{mode}_FINAL"]:
        for suffix in [".parquet", ".xlsx"]:
            path = STAGE_DIR / (stem+suffix)
            if not path.is_file():
                continue
            try:
                if suffix == ".parquet":
                    names = pq.read_schema(path).names
                    columns = list(dict.fromkeys(WAFER_KEYS+SHOT_KEYS[3:]+COORDS+GEOMETRY+[TARGET]+list(FILTERS)))
                    data = pd.read_parquet(path, columns=[col for col in columns if col in names])
                else:
                    data = pd.read_excel(path, dtype={key: "string" for key in WAFER_KEYS})
                missing = [col for col in SHOT_KEYS+COORDS if col not in data]
                if missing:
                    raise ValueError(f"좌표/wafer 키 컬럼 누락: {missing}")
                data = normalize_keys(data)
                for col in SHOT_KEYS[3:]+COORDS+GEOMETRY+[TARGET]:
                    if col in data:
                        data[col] = pd.to_numeric(data[col], errors="coerce")
                valid = data[WAFER_KEYS].notna().all(axis=1) & np.isfinite(data[SHOT_KEYS[3:]+COORDS].to_numpy(dtype=float,na_value=np.nan)).all(axis=1)
                if USE_VALID_X_MASK and TARGET in data:
                    valid &= np.isfinite(data[TARGET])
                input_manifest.append(dict(mode=mode, path=str(path), rows=len(data), valid_rows=int(valid.sum()), x_validity_mask_used=USE_VALID_X_MASK and TARGET in data, bytes=path.stat().st_size, mtime_ns=path.stat().st_mtime_ns, fallback_errors="; ".join(errors)))
                return data.loc[valid].reset_index(drop=True)
            except Exception as exc:
                errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
    raise FileNotFoundError(f"{mode}: 전체 Parquet/Excel 좌표 입력 필요. sample 파일은 제외. {'; '.join(errors)}")

def filter_frame(frame, rules):
    out = frame
    for col, values in rules.items():
        if col not in out:
            raise ValueError(f"필터 컬럼 없음: {col}")
        if not isinstance(values, (list, tuple, set)):
            values = [values]
        if not values:
            raise ValueError(f"비어 있는 필터: {col}")
        values = [str(normalized_id(v)) if col in WAFER_KEYS[1:] else str(v).strip() for v in values]
        out = out.loc[out[col].astype("string").str.strip().isin(values)]
    return out

# %% 02. 대표 wafer와 반복 sampling 패턴 추출
frames = {mode: read_coordinates(mode) for mode in MODES}
if USE_WAFER_CONTEXT and FILTERS:
    context_path = next((BASE_DIR / "output_wafer_context" / ("wafer_context"+suffix) for suffix in [".parquet", ".xlsx"] if (BASE_DIR / "output_wafer_context" / ("wafer_context"+suffix)).is_file()), None)
    if context_path:
        context = normalize_keys(pd.read_parquet(context_path) if context_path.suffix == ".parquet" else pd.read_excel(context_path, dtype={key:"string" for key in WAFER_KEYS}))
        if context.duplicated(WAFER_KEYS).any() or context[WAFER_KEYS].isna().any(axis=None):
            raise ValueError("wafer_context 키가 유일하고 유효해야 합니다.")
        for mode in MODES:
            extra = [col for col in FILTERS if col not in frames[mode] and col in context]
            if extra:
                frames[mode] = frames[mode].merge(context[WAFER_KEYS+extra], on=WAFER_KEYS, how="left", validate="many_to_one")
for mode in MODES:
    frames[mode] = filter_frame(filter_frame(frames[mode], FILTERS), WAFER_SELECTION[mode] or {})
    if frames[mode].empty:
        raise ValueError(f"{mode}: 선택 가능한 유효 좌표가 없습니다.")
catalogues = {mode: frame.groupby(WAFER_KEYS, sort=False).size().rename("n_valid_rows").reset_index() for mode,frame in frames.items()}
common = catalogues["ADI"].merge(catalogues["OCO"], on=WAFER_KEYS, suffixes=("_ADI", "_OCO"))
if len(common):
    common["paired_size"] = common[["n_valid_rows_ADI", "n_valid_rows_OCO"]].min(axis=1)
    common_key = common.sort_values("paired_size", ascending=False, kind="stable").iloc[0][WAFER_KEYS].tolist()
else:
    common_key = None
selected_rows, layout_rows, shot_rows, primary_frames, wafer_frames = [], [], [], {}, {}
for mode in MODES:
    key = common_key or catalogues[mode].sort_values("n_valid_rows", ascending=False, kind="stable").iloc[0][WAFER_KEYS].tolist()
    frame = frames[mode].loc[frames[mode][WAFER_KEYS].eq(pd.Series(key, index=WAFER_KEYS)).all(axis=1)].copy()
    wafer_frames[mode] = frame
    selected_rows.append(dict(mode=mode, **dict(zip(WAFER_KEYS,key)), n_points=len(frame), common_wafer=common_key is not None))
    groups, signatures = {}, {}
    for shot_key, work in frame.groupby(["fcp_x", "fcp_y"], sort=False):
        rounded = work[COORDS].round(COORD_ROUND_DECIMALS).sort_values(COORDS).to_numpy(dtype="<f8")
        signature = hashlib.sha256(rounded.tobytes()).hexdigest()[:16]
        groups[shot_key] = work
        signatures.setdefault(signature, []).append(shot_key)
    choices = []
    for signature, keys in signatures.items():
        representative = min(keys, key=lambda key: key[0]**2+key[1]**2)
        work = groups[representative]
        row = dict(mode=mode, layout_id=signature, n_shots=len(keys), n_points=len(work), n_unique_points=len(work[COORDS].drop_duplicates()), fcp_x=representative[0], fcp_y=representative[1])
        choices.append(row)
    best = max(choices, key=lambda row: (row["n_unique_points"], row["n_shots"], -row["fcp_x"]**2-row["fcp_y"]**2))
    primary_frames[mode] = groups[(best["fcp_x"], best["fcp_y"])].copy()
    for row in choices:
        row["is_primary"] = row["layout_id"] == best["layout_id"]
        layout_rows.append(row)
    for signature, keys in signatures.items():
        shot_rows.extend(dict(mode=mode, fcp_x=x, fcp_y=y, layout_id=signature, is_primary=signature == best["layout_id"]) for x,y in keys)
    print(mode, "대표 wafer:", key, "; 대표 shot:", (best["fcp_x"], best["fcp_y"]), "; mark 수:", best["n_points"])
selection, layout_catalogue, shot_layouts = pd.DataFrame(selected_rows), pd.DataFrame(layout_rows), pd.DataFrame(shot_rows)
selected_points = pd.concat([frame.assign(mode=mode) for mode,frame in wafer_frames.items()], ignore_index=True)
for name, table in [("02_SELECTED_WAFERS", selection), ("02_LAYOUT_CATALOGUE", layout_catalogue), ("02_SHOT_LAYOUTS", shot_layouts), ("02_SELECTED_COORDINATES", selected_points)]:
    save_table(name, table)
del frames
display(selection)
