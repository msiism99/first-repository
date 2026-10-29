# %% 00. 제품별 입력 폴더와 분석 설정
from dataclasses import dataclass
from pathlib import Path
import copy
import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, FileLink

EP_BASE_DIR = Path(r"E:\PHOTO_ANALYSIS\BASIC")  # 실제 BASIC 폴더 경로로 수정. 임시 실행 폴더 대신 이 경로를 사용
EP_SOURCES = [
    {"product": "KGVM", "axis": "y", "folder": EP_BASE_DIR / "edge_comparison_input" / "KGVM"},
    {"product": "KHVF", "axis": "y", "folder": EP_BASE_DIR / "edge_comparison_input" / "KHVF"},
    {"product": "PBVC", "axis": "x", "folder": EP_BASE_DIR / "edge_comparison_input" / "PBVC"},
]
EP_OUTPUT_DIR = EP_BASE_DIR / "output_edge_inner_comparison_critical"
EP_INNER_RADIUS_UM = 144000.0
EP_MAX_RADIUS_UM = 147000.0  # 실제 측정점 반경. 147mm 초과 및 반경 미상은 제외 수를 따로 기록
EP_STD_DDOF = 1
EP_SAVE_POINT_DATA = True  # edge가 있는 shot의 검산용 point 자료만 제품별 Parquet 저장
EP_MIN_EXTRA_INNER_POINTS = 2  # X: 최소 21+2, Y: 최소 17+2. para 수는 줄이지 않음
EP_MAX_SCALED_CONDITION = 1e6
EP_MAX_EDGE_NOISE_GAIN = 5.0  # 안쪽 회귀의 edge 예측 noise gain 진단용 상한. 공정 spec이 아님
EP_SVD_RCOND = 1e-12
EP_RADIAL_BINS_MM = np.arange(140., 147.01, .5)
EP_WAFER_KEYS = ["product", "LOT_ID", "Wafer"]
EP_SHOT_KEYS = EP_WAFER_KEYS + ["fcp_x", "fcp_y"]

if not EP_SOURCES or len({str(s["product"]) for s in EP_SOURCES}) != len(EP_SOURCES):
    raise ValueError("EP_SOURCES에 서로 다른 제품명과 입력 폴더를 지정하세요.")
if any(str(source.get("axis", "")).lower() not in {"x", "y"} for source in EP_SOURCES):
    raise ValueError("EP_SOURCES의 각 제품에 axis를 x 또는 y로 지정하세요.")
EP_PRODUCT_AXES = {str(source["product"]): [str(source["axis"]).lower()] for source in EP_SOURCES}
EP_AXES = sorted({axis for axes in EP_PRODUCT_AXES.values() for axis in axes})  # 내부 함수용 전체 방향 목록
if EP_STD_DDOF not in [0, 1] or not 0 < EP_INNER_RADIUS_UM < EP_MAX_RADIUS_UM:
    raise ValueError("표준편차 ddof 또는 반경 설정을 확인하세요.")
if EP_MIN_EXTRA_INNER_POINTS < 0 or not 0 < EP_SVD_RCOND < 1 or EP_MAX_EDGE_NOISE_GAIN <= 0 or EP_MAX_SCALED_CONDITION <= 1:
    raise ValueError("안쪽 기준 모델의 진단 설정을 확인하세요.")
for folder in [EP_OUTPUT_DIR, EP_OUTPUT_DIR / "tables", EP_OUTPUT_DIR / "points", EP_OUTPUT_DIR / "plots"]:
    folder.mkdir(parents=True, exist_ok=True)


def ep_locate_inputs(source):
    folder = Path(source["folder"])
    candidates = [folder / "27_OCO_FINAL_POINTS.parquet", folder / "stages" / "27_OCO_FINAL_POINTS.parquet",
                  folder / "27_OCO_FINAL_POINTS.xlsx", folder / "stages" / "27_OCO_FINAL_POINTS.xlsx"]
    existing = [p for p in candidates if p.is_file()]
    settings = folder / "extension_settings.json"
    if not existing or not settings.is_file():
        raise FileNotFoundError(f"{source['product']}: {folder}에 전체 27_OCO_FINAL_POINTS.parquet와 extension_settings.json을 두세요. stages 하위 파일 및 전체 Excel도 지원합니다. _sample 파일은 사용하지 않습니다.")
    return existing, settings


def ep_read_product(source):
    candidates, settings_path = ep_locate_inputs(source)
    errors = []
    for path in candidates:
        try:
            frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_excel(path)
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            return frame, settings, path, settings_path
        except (OSError, ValueError, ImportError) as exc:
            errors.append(f"{path.name}: {exc}")
    raise ValueError(f"{source['product']} 입력 읽기 실패: " + " | ".join(errors))


def ep_prepare_points(frame, product, axes=None):
    axes = EP_AXES if axes is None else axes
    required = ["LOT_ID", "Wafer", "fcp_x", "fcp_y", "coordinate_X", "coordinate_Y", "measurement_scale"] + [f"raw_minus_total_fit_{axis}" for axis in axes]
    missing = [col for col in required if col not in frame]
    if missing:
        raise ValueError(f"{product}: 27번 전체 point 자료에 필수 컬럼이 없습니다: {missing}")
    out = frame.copy().reset_index(drop=True)
    out["product"] = str(product)
    numeric = required[1:] + ["radius", "wf_x", "wf_y"] + [f"{axis.upper()}_reg_original" for axis in axes]
    for col in numeric:
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if out.empty or out[EP_SHOT_KEYS].isna().any().any() or not np.isfinite(out[["Wafer", "fcp_x", "fcp_y"]].to_numpy(float)).all():
        raise ValueError(f"{product}: LOT/wafer/shot 식별자가 없거나 입력이 비어 있습니다.")
    if "photo_transn_seq" in out:
        photos = out.groupby(EP_WAFER_KEYS, observed=True, dropna=False).photo_transn_seq.nunique()
        if photos.gt(1).any():
            raise ValueError(f"{product}: 한 LOT/wafer에 여러 photo 이력이 있습니다. 실행별 자료를 섞지 말고 한 이력씩 분리하세요.")
    if "radius" not in out:
        out["radius"] = np.hypot(out.wf_x, out.wf_y) if {"wf_x", "wf_y"}.issubset(out.columns) else np.hypot(out.fcp_x + out.coordinate_X, out.fcp_y + out.coordinate_Y)
    elif out.radius.isna().any():
        fallback = np.hypot(out.wf_x, out.wf_y) if {"wf_x", "wf_y"}.issubset(out.columns) else np.hypot(out.fcp_x + out.coordinate_X, out.fcp_y + out.coordinate_Y)
        out["radius"] = out.radius.fillna(fallback)
    finite_scale = np.isfinite(out.measurement_scale)
    if not finite_scale.all() or out.measurement_scale.lt(0).any():
        raise ValueError(f"{product}: measurement_scale이 유한한 0 이상 값이어야 합니다.")
    scaled = out.measurement_scale.ne(1.)
    for axis in axes:
        col = f"{axis.upper()}_reg_original"
        needed = scaled & np.isfinite(out[f"raw_minus_total_fit_{axis}"])
        if needed.any() and (col not in out or not np.isfinite(out.loc[needed, col].to_numpy(float)).all()):
            raise ValueError(f"{product}: 배율 적용 전 값 복원에 필요한 {col}이 없습니다. 27번 전체 Parquet을 확인하세요.")
        restore = pd.Series(0., index=out.index)
        if needed.any():
            restore.loc[needed] = (1. - out.loc[needed, "measurement_scale"]) * out.loc[needed, col]
        # 기적용 MRC/PSM decorrection과 고정 K-MRC는 유지. 측정값 배율만 100%로 복원.
        out[f"input100_{axis}"] = out[f"raw_minus_total_fit_{axis}"] + restore
    in_range = np.isfinite(out.radius) & out.radius.ge(0) & out.radius.le(EP_MAX_RADIUS_UM)
    audit = dict(product=product, axis="/".join(axes), n_input=len(out), n_radius_unknown=int((~np.isfinite(out.radius)).sum()),
                 n_outside_radius=int((np.isfinite(out.radius) & ~in_range).sum()), n_scaled=int(scaled.sum()))
    out = out.loc[in_range].copy().reset_index(drop=True)
    if out.empty:
        raise ValueError(f"{product}: 분석 반경 안의 측정점이 없습니다.")
    out["region"] = np.where(out.radius.le(EP_INNER_RADIUS_UM), "INNER", "EDGE")
    out["_fit_valid"] = np.isfinite(out[["coordinate_X", "coordinate_Y"] + [f"input100_{axis}" for axis in axes]].to_numpy(float)).all(axis=1)
    out["_has_edge_shot"] = out.region.eq("EDGE").groupby([out[k] for k in EP_SHOT_KEYS], observed=True, dropna=False).transform("any")
    audit.update(n_used=len(out), n_inner=int(out.region.eq("INNER").sum()), n_edge=int(out.region.eq("EDGE").sum()), n_fit_valid=int(out._fit_valid.sum()))
    return out, audit


ep_input_inventory = []
for source in EP_SOURCES:
    paths, settings_path = ep_locate_inputs(source)
    ep_input_inventory.append(dict(product=source["product"], axis=EP_PRODUCT_AXES[str(source["product"])][0], point_files=" | ".join(str(p) for p in paths), settings_file=str(settings_path)))
print("분석 기준 폴더:", EP_BASE_DIR)
display(pd.DataFrame(ep_input_inventory))
print("00~07번을 순서대로 실행하세요. DB 조회 없이 제품별로 읽고 처리하며, 기존 입력 파일은 변경하지 않습니다.")
