# %% 00. 입력·제품별 방향·회귀 반경·edge 배율
from dataclasses import dataclass
from pathlib import Path
import copy
import json
import os
from functools import lru_cache
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, FileLink

EP_BASE_DIR = Path(r"E:\PHOTO_ANALYSIS\BASIC")  # 실제 BASIC 폴더로 수정
EP_SOURCES = [
    {"product": "KGVM", "axis": "y", "reference_scale": .5, "folder": EP_BASE_DIR / "edge_comparison_input" / "KGVM"},
    {"product": "KHVF", "axis": "y", "reference_scale": .2, "folder": EP_BASE_DIR / "edge_comparison_input" / "KHVF"},
    {"product": "PBVC", "axis": "x", "reference_scale": .4, "folder": EP_BASE_DIR / "edge_comparison_input" / "PBVC"},
]
EP_OUTPUT_DIR = EP_BASE_DIR / "output_edge_radius_sweep"
EP_INNER_RADIUS_UM = 144000.
EP_MAX_RADIUS_UM = 147000.
EP_STD_DDOF = 1
ER_FIT_RADII_MM = [146., 147.]
ER_SCALES = [i / 10 for i in range(1, 11)]
ER_SAVE_SCENARIO_POINTS = True  # edge가 있는 shot의 검산용 point만 배율/반경별 저장
ER_SAVE_COEFFICIENTS = True
ER_BASELINE_ATOL_UM = 1e-9
ER_SVD_RCOND = 1e-12

if not EP_SOURCES or len({str(s["product"]) for s in EP_SOURCES}) != len(EP_SOURCES):
    raise ValueError("제품명은 서로 달라야 합니다.")
if any(str(s.get("axis", "")).lower() not in {"x", "y"} for s in EP_SOURCES):
    raise ValueError("제품마다 axis를 x/y로 지정하세요.")
EP_PRODUCT_AXES = {str(s["product"]): [str(s["axis"]).lower()] for s in EP_SOURCES}
EP_AXES = sorted({a for axes in EP_PRODUCT_AXES.values() for a in axes})
EP_WAFER_KEYS = ["product", "LOT_ID", "Wafer"]
EP_SHOT_KEYS = EP_WAFER_KEYS + ["fcp_x", "fcp_y"]
if EP_STD_DDOF not in [0, 1] or not 0 < EP_INNER_RADIUS_UM < EP_MAX_RADIUS_UM:
    raise ValueError("표준편차 및 반경 설정을 확인하세요.")
if not ER_SCALES or any(not np.isfinite(s) or not 0 < s <= 1 for s in ER_SCALES):
    raise ValueError("ER_SCALES는 0 초과 1 이하 배율 목록이어야 합니다.")
ER_SCALES = sorted(set(float(s) for s in ER_SCALES))
if 1. not in ER_SCALES:
    raise ValueError("100% 조건은 반드시 포함하세요.")
ER_FIT_RADII_MM = sorted(set(float(r) for r in ER_FIT_RADII_MM))
if len(ER_FIT_RADII_MM) != 2 or any(not np.isfinite(r) or not EP_INNER_RADIUS_UM <= r*1000 <= EP_MAX_RADIUS_UM for r in ER_FIT_RADII_MM):
    raise ValueError("안쪽 평가 반경 이상, 147mm 이하의 회귀 반경 두 개를 지정하세요.")
for source in EP_SOURCES:
    if not any(np.isclose(source["reference_scale"], s) for s in ER_SCALES):
        raise ValueError(f"{source['product']}: reference_scale을 ER_SCALES 안의 값으로 지정하세요.")
for name in ["tables", "plots", "points", "coefficients", "diagnostics", "cases"]:
    (EP_OUTPUT_DIR / name).mkdir(parents=True, exist_ok=True)

# INPUT_HELPERS

print("기준 폴더:", EP_BASE_DIR)
er_inventory = []
for source in EP_SOURCES:
    files, settings = ep_locate_inputs(source)
    er_inventory.append(dict(product=source["product"], axis=EP_PRODUCT_AXES[str(source["product"])][0], points=" | ".join(str(p) for p in files), settings=str(settings)))
display(pd.DataFrame(er_inventory))
print(f"제품별 {len(ER_FIT_RADII_MM)*len(ER_SCALES)}조건. K-MRC 고정 / 회귀 point만 제한 / 평가는 원래 값으로 동일 영역 사용.")
